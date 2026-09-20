import asyncio
import hashlib
import json
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.auth import CurrentUser, SessionDependency
from app.models import SessionEvent, VoiceSession
from app.realtime.tools import TOOL_DESCRIPTIONS, ToolArguments, execute_tool, result

router = APIRouter(prefix="/api/v1/voice/sessions", tags=["tools"])


class ToolScope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    connection_epoch: int = Field(ge=0)
    response_id: str = Field(min_length=1, max_length=120)


class ToolCall(ToolScope):
    call_id: str = Field(min_length=1, max_length=120)
    name: Literal["hsk_lookup", "web_search", "expert_answer"]
    arguments: str = Field(max_length=8000)


def event_key(kind: str, scope: ToolScope, call_id=""):
    value = f"{scope.connection_epoch}:{scope.response_id}:{call_id}"
    return f"tool-{kind}-" + hashlib.sha256(value.encode()).hexdigest()[:48]


def owned(db, user, session_id):
    voice = db.scalar(
        select(VoiceSession).where(VoiceSession.id == session_id, VoiceSession.user_id == user.id)
    )
    if not voice:
        raise HTTPException(404, "Session not found")
    return voice


def current(voice, scope):
    return voice.connection_epoch == scope.connection_epoch and voice.status in {
        "active",
        "connecting",
        "reconnecting",
    }


def find_event(db, session_id, key):
    return db.scalar(
        select(SessionEvent).where(
            SessionEvent.session_id == session_id, SessionEvent.client_event_id == key
        )
    )


@router.post("/{session_id}/tools/cancel")
def cancel_tools(session_id: str, scope: ToolScope, db: SessionDependency, user: CurrentUser):
    owned(db, user, session_id)
    key = event_key("cancel", scope)
    if not find_event(db, session_id, key):
        db.add(
            SessionEvent(
                session_id=session_id,
                client_event_id=key,
                event_type="tool_cancelled",
                event_payload=scope.model_dump(),
            )
        )
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
    return {"status": "cancelled"}


@router.get("/{session_id}/tools")
def tool_status(session_id: str, request: Request, db: SessionDependency, user: CurrentUser):
    owned(db, user, session_id)
    settings = request.app.state.settings
    return {
        "tools": [
            {
                "name": name,
                "description": description,
                "available": name == "hsk_lookup"
                or (name == "web_search" and bool(settings.tavily_api_key))
                or (name == "expert_answer" and bool(settings.deepseek_api_key)),
            }
            for name, description in TOOL_DESCRIPTIONS.items()
        ]
    }


@router.post("/{session_id}/tools/execute")
async def run_tool(
    session_id: str, call: ToolCall, request: Request, db: SessionDependency, user: CurrentUser
):
    voice = owned(db, user, session_id)
    if not current(voice, call):
        raise HTTPException(409, "Tool call belongs to an inactive connection")
    cancel_key = event_key("cancel", call)
    if find_event(db, session_id, cancel_key):
        return result("cancelled", "本轮已取消。")
    key = event_key("call", call, call.call_id)
    fingerprint = hashlib.sha256(call.model_dump_json().encode()).hexdigest()
    prior = find_event(db, session_id, key)
    if prior:
        if prior.event_payload.get("fingerprint") != fingerprint:
            raise HTTPException(409, "Call ID reused with different arguments")
        return prior.event_payload["result"]
    try:
        arguments = ToolArguments.model_validate(json.loads(call.arguments))
    except (ValidationError, ValueError):
        return result("failed", "工具参数无效，query 必须是非空文本；不要猜测结果。")
    settings = request.app.state.settings
    external_slot = None
    if call.name != "hsk_lookup":
        used = (
            db.scalar(
                select(func.count())
                .select_from(SessionEvent)
                .where(
                    SessionEvent.session_id == session_id,
                    SessionEvent.event_type == "tool_external",
                )
            )
            or 0
        )
        if used >= settings.tool_external_session_limit:
            return result("unavailable", "本次会话外部工具调用额度已用完。")
        external_slot = used
    payload = {
        **call.model_dump(exclude={"arguments"}),
        "fingerprint": fingerprint,
        "result": result("running", "工具正在执行；重复请求不会重新执行。"),
    }
    event = SessionEvent(
        session_id=session_id,
        client_event_id=key,
        event_type="tool_local" if call.name == "hsk_lookup" else "tool_external",
        event_payload=payload,
    )
    db.add(event)
    if external_slot is not None:
        # The unique session/event key reserves a budget slot in the same transaction.
        # Concurrent requests may retry, but cannot both spend the final slot.
        db.add(
            SessionEvent(
                session_id=session_id,
                client_event_id=f"tool-budget-{external_slot}",
                event_type="tool_budget_reserved",
                event_payload={"slot": external_slot},
            )
        )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        prior = find_event(db, session_id, key)
        if prior and prior.event_payload.get("fingerprint") == fingerprint:
            return prior.event_payload["result"]
        raise HTTPException(409, "Conflicting tool call") from None
    try:
        output = await asyncio.wait_for(
            asyncio.to_thread(execute_tool, call.name, arguments, settings),
            timeout=settings.tool_timeout_seconds,
        )
    except TimeoutError:
        output = result("failed", "查询超时，没有获得可靠结果。")
    except Exception:
        # Never return provider error bodies: they may contain credentials or user data.
        output = result("failed", "工具服务暂时失败，没有获得可靠结果。")
    db.expire_all()
    voice = owned(db, user, session_id)
    if not current(voice, call) or find_event(db, session_id, cancel_key):
        output = result("cancelled", "连接或问题已变化，丢弃旧结果。")
    event = find_event(db, session_id, key)
    event.event_payload = {**payload, "result": output}
    db.commit()
    return output
