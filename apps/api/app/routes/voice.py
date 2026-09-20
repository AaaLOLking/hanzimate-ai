import json
from dataclasses import asdict
from datetime import timedelta

from fastapi import APIRouter, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.auth import CurrentUser, SessionDependency
from app.models import (
    ErrorCluster,
    LearnerProfile,
    SessionEvent,
    Utterance,
    VoiceSession,
    VoiceSessionStatus,
    Workspace,
    utc_now,
)
from app.providers.realtime import (
    RealtimeConnection,
    RealtimeProviderError,
    resolve_realtime_provider,
)
from app.realtime.lifecycle import as_utc
from app.realtime.memory import build_memory, render_markdown
from app.realtime.policy import (
    SKILL_VERSION,
    build_requested_config,
    build_session_update,
    realtime_capabilities,
)
from app.scenarios import SCENARIOS_BY_ID
from app.schemas import (
    RealtimeConnectionOutput,
    SdpAnswerOutput,
    SdpOfferInput,
    SessionEventInput,
    SessionEventOutput,
    UtteranceInput,
    UtteranceOutput,
    UtterancePlaybackInput,
    VoiceSessionCreate,
    VoiceSessionCreateOutput,
    VoiceSessionFinalizeInput,
    VoiceSessionOutput,
    VoiceSessionPreferencesInput,
    VoiceSessionPreferencesOutput,
    VoiceSessionStatusInput,
)

router = APIRouter(prefix="/api/v1/voice/sessions", tags=["voice"])

ALLOWED_TRANSITIONS = {
    VoiceSessionStatus.CREATED: {
        VoiceSessionStatus.CONNECTING,
        VoiceSessionStatus.ACTIVE,
        VoiceSessionStatus.ENDING,
        VoiceSessionStatus.COMPLETED,
        VoiceSessionStatus.FAILED,
    },
    VoiceSessionStatus.CONNECTING: {
        VoiceSessionStatus.RECONNECTING,
        VoiceSessionStatus.ACTIVE,
        VoiceSessionStatus.ENDING,
        VoiceSessionStatus.FAILED,
    },
    VoiceSessionStatus.RECONNECTING: {
        VoiceSessionStatus.ACTIVE,
        VoiceSessionStatus.ENDING,
        VoiceSessionStatus.COMPLETED,
        VoiceSessionStatus.FAILED,
    },
    VoiceSessionStatus.ACTIVE: {
        VoiceSessionStatus.RECONNECTING,
        VoiceSessionStatus.ENDING,
        VoiceSessionStatus.COMPLETED,
        VoiceSessionStatus.FAILED,
    },
    VoiceSessionStatus.ENDING: {
        VoiceSessionStatus.COMPLETED,
        VoiceSessionStatus.FAILED,
    },
    VoiceSessionStatus.COMPLETED: set(),
    VoiceSessionStatus.FAILED: set(),
}


def get_owned_workspace(
    database_session: SessionDependency, user: CurrentUser, workspace_id: str
) -> Workspace:
    workspace = database_session.scalar(
        select(Workspace).where(Workspace.id == workspace_id, Workspace.user_id == user.id)
    )
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace


def get_owned_voice_session(
    database_session: SessionDependency, user: CurrentUser, voice_session_id: str
) -> VoiceSession:
    voice_session = database_session.scalar(
        select(VoiceSession).where(
            VoiceSession.id == voice_session_id, VoiceSession.user_id == user.id
        )
    )
    if voice_session is None:
        raise HTTPException(status_code=404, detail="Voice session not found")
    return voice_session


def build_context_pack(
    database_session: SessionDependency,
    user: CurrentUser,
    workspace: Workspace,
    correction_mode: str,
    speech_speed: str,
    patience: str = "patient",
) -> dict[str, object]:
    profile = database_session.get(LearnerProfile, user.id)
    confirmed_errors = list(
        database_session.scalars(
            select(ErrorCluster)
            .where(ErrorCluster.user_id == user.id, ErrorCluster.status == "active")
            .order_by(ErrorCluster.last_seen_at.desc())
            .limit(5)
        )
    )
    objective = workspace.state.get("objective", f"完成“{workspace.title}”场景对话")
    teaching_policies = {
        "immersion": "交流优先；通话中不主动纠错，结束后集中反馈。",
        "coach": "等学习者表达完成；每轮最多纠正一个高价值问题。",
        "exam": "通话中不提示答案或纠错；结束后统一反馈。",
    }
    return {
        "objective": objective,
        "practice_mode": workspace.state.get("practice_mode", "scenario"),
        "custom_objective": workspace.state.get("custom_objective"),
        "scenario_id": workspace.state.get("scenario_id"),
        "estimated_hsk_band": profile.estimated_hsk_band if profile else "not_sure",
        "support_language": profile.support_language if profile else "English",
        "correction_mode": correction_mode,
        "speech_speed": speech_speed,
        "patience": patience,
        "teaching_policy": teaching_policies[correction_mode],
        "confirmed_errors": [
            {
                "id": error.id,
                "canonical_key": error.canonical_key,
                "error_type": error.error_type,
                "subtype": error.subtype,
                "explanation": error.explanation,
                "corrected_example": error.corrected_example,
                "occurrence_count": error.occurrence_count,
            }
            for error in confirmed_errors
        ],
        "skill_version": SKILL_VERSION,
    }


def transition_voice_session(voice_session: VoiceSession, target: VoiceSessionStatus) -> None:
    current = VoiceSessionStatus(voice_session.status)
    if target == current:
        return
    if target not in ALLOWED_TRANSITIONS[current]:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot transition voice session from {current} to {target}",
        )
    voice_session.status = target
    if target == VoiceSessionStatus.ACTIVE and voice_session.started_at is None:
        voice_session.started_at = utc_now()
        voice_session.deadline_at = voice_session.started_at + timedelta(
            seconds=voice_session.max_duration_seconds
        )
    if target == VoiceSessionStatus.ENDING and voice_session.ending_at is None:
        voice_session.ending_at = utc_now()
    if target in {VoiceSessionStatus.COMPLETED, VoiceSessionStatus.FAILED}:
        voice_session.ended_at = utc_now()


def connection_payload(voice_session: VoiceSession, connection) -> RealtimeConnectionOutput:
    return RealtimeConnectionOutput.model_validate(
        {
            **asdict(connection),
            "session_update": build_session_update(voice_session),
            "capabilities": realtime_capabilities(connection.mode),
        }
    )


def same_create_request(voice_session: VoiceSession, payload: VoiceSessionCreate) -> bool:
    if voice_session.context_pack.get("continuous", False) != payload.continuous:
        return False
    if voice_session.context_pack.get("practice_mode", "scenario") != payload.practice_mode:
        return False
    if voice_session.context_pack.get("custom_objective") != (payload.custom_objective or None):
        return False
    expected_config = build_requested_config(
        correction_mode=payload.correction_mode,
        speech_speed=payload.speech_speed,
        patience=payload.patience,
    )
    if voice_session.protocol_version != payload.protocol_version:
        return False
    if voice_session.requested_config != expected_config:
        return False
    if payload.workspace_id and voice_session.workspace_id != payload.workspace_id:
        return False
    saved_scenario_id = voice_session.context_pack.get("scenario_id")
    return not payload.scenario_id or payload.scenario_id == saved_scenario_id


@router.post("", response_model=VoiceSessionCreateOutput, status_code=201)
def create_voice_session(
    payload: VoiceSessionCreate,
    request: Request,
    response: Response,
    database_session: SessionDependency,
    user: CurrentUser,
) -> VoiceSessionCreateOutput:
    provider = resolve_realtime_provider(request.app.state.settings)
    connection = provider.connection
    if payload.client_session_id:
        existing = database_session.scalar(
            select(VoiceSession).where(
                VoiceSession.user_id == user.id,
                VoiceSession.client_session_id == payload.client_session_id,
            )
        )
        if existing:
            if not same_create_request(existing, payload):
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "idempotency_conflict",
                        "message": "client_session_id was already used with different settings",
                        "retryable": False,
                    },
                )
            response.status_code = 200
            return VoiceSessionCreateOutput(
                session=existing,
                connection=connection_payload(existing, connection),
            )

    scenario = SCENARIOS_BY_ID.get(payload.scenario_id) if payload.scenario_id else None
    if payload.scenario_id and scenario is None:
        raise HTTPException(status_code=404, detail="Conversation scenario not found")
    if payload.workspace_id:
        workspace = get_owned_workspace(database_session, user, payload.workspace_id)
        if workspace.kind != "conversation":
            raise HTTPException(status_code=409, detail="Workspace is not a conversation")
        if scenario:
            workspace.title = scenario["title"]
            workspace.state = {
                **workspace.state,
                "scenario_id": scenario["id"],
                "objective": scenario["objective"],
                "opening_line": scenario["opening_line"],
                "prompt_starters": scenario["prompt_starters"],
                "safety_note": scenario["safety_note"],
            }
            workspace.status = "active"
            workspace.last_opened_at = utc_now()
    else:
        title = scenario["title"] if scenario else payload.scenario
        state = (
            {
                "scenario_id": scenario["id"],
                "objective": scenario["objective"],
                "opening_line": scenario["opening_line"],
                "prompt_starters": scenario["prompt_starters"],
                "safety_note": scenario["safety_note"],
            }
            if scenario
            else {"objective": f"在“{payload.scenario}”场景中完成一次自然交流"}
        )
        workspace = Workspace(
            user_id=user.id,
            kind="conversation",
            title=title,
            state=state,
        )
        database_session.add(workspace)
        database_session.flush()

    if payload.practice_mode != "scenario":
        free = payload.practice_mode == "free"
        workspace.title = "自由对话" if free else "自定义练习"
        workspace.state = {
            **workspace.state,
            "practice_mode": payload.practice_mode,
            "custom_objective": payload.custom_objective if not free else None,
            "scenario_id": None,
            "objective": "围绕学习者感兴趣的话题自然交流，可以随时换话题"
            if free
            else payload.custom_objective,
            "opening_line": "你好！今天想聊些什么？"
            if free
            else "你好！我们按你的目标来练习，你想先从哪里开始？",
            "prompt_starters": ["我想聊聊今天发生的事。", "你可以帮我找一个话题吗？"]
            if free
            else ["我们开始练习吧。", "请先给我一个示例。"],
            "safety_note": None,
        }
    else:
        workspace.state = {**workspace.state, "practice_mode": "scenario", "custom_objective": None}
    workspace.status = "active"

    requested_config = build_requested_config(
        correction_mode=payload.correction_mode,
        speech_speed=payload.speech_speed,
        patience=payload.patience,
    )
    voice_session = VoiceSession(
        workspace_id=workspace.id,
        user_id=user.id,
        client_session_id=payload.client_session_id,
        protocol_version=payload.protocol_version,
        correction_mode=payload.correction_mode,
        speech_speed=payload.speech_speed,
        patience=payload.patience,
        provider=connection.provider,
        model=connection.model,
        voice=connection.voice,
        connection_mode=connection.mode,
        skill_version=SKILL_VERSION,
        max_duration_seconds=connection.max_duration_seconds,
        requested_config=requested_config,
        transport_status="idle",
        context_pack=build_context_pack(
            database_session,
            user,
            workspace,
            payload.correction_mode,
            payload.speech_speed,
            payload.patience,
        ),
    )
    database_session.add(voice_session)
    voice_session.context_pack = {**voice_session.context_pack, "continuous": payload.continuous}
    try:
        database_session.flush()
        workspace.state = {**workspace.state, "active_session_id": voice_session.id}
        database_session.commit()
    except IntegrityError:
        database_session.rollback()
        if not payload.client_session_id:
            raise
        duplicate = database_session.scalar(
            select(VoiceSession).where(
                VoiceSession.user_id == user.id,
                VoiceSession.client_session_id == payload.client_session_id,
            )
        )
        if duplicate is None or not same_create_request(duplicate, payload):
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "idempotency_conflict",
                    "message": "client_session_id was already used with different settings",
                    "retryable": False,
                },
            ) from None
        response.status_code = 200
        return VoiceSessionCreateOutput(
            session=duplicate,
            connection=connection_payload(duplicate, connection),
        )
    database_session.refresh(voice_session)
    return VoiceSessionCreateOutput(
        session=voice_session,
        connection=connection_payload(voice_session, connection),
    )


@router.get("/{voice_session_id}", response_model=VoiceSessionOutput)
def restore_voice_session(
    voice_session_id: str, database_session: SessionDependency, user: CurrentUser
) -> VoiceSession:
    return get_owned_voice_session(database_session, user, voice_session_id)


@router.post("/{voice_session_id}/resume", response_model=VoiceSessionCreateOutput)
def resume_voice_session(
    voice_session_id: str,
    request: Request,
    database_session: SessionDependency,
    user: CurrentUser,
) -> VoiceSessionCreateOutput:
    voice_session = get_owned_voice_session(database_session, user, voice_session_id)
    if voice_session.status == VoiceSessionStatus.ENDING:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "session_ending",
                "message": "This session is already ending and can only be finalized",
                "retryable": False,
            },
        )
    if voice_session.status in {VoiceSessionStatus.COMPLETED, VoiceSessionStatus.FAILED}:
        raise HTTPException(status_code=409, detail="Voice session is already closed")

    resolved = resolve_realtime_provider(request.app.state.settings).connection
    voice_session.context_pack = {
        **voice_session.context_pack,
        "conversation_memory": build_memory(voice_session),
    }
    database_session.commit()
    if voice_session.connection_mode == "mock":
        connection = RealtimeConnection(
            mode="mock",
            provider=voice_session.provider,
            model=voice_session.model,
            voice=voice_session.voice,
            max_duration_seconds=voice_session.max_duration_seconds,
            fallback_reason="This session was created as a local simulation.",
        )
    else:
        if (resolved.mode, resolved.model, resolved.voice) != (
            voice_session.connection_mode,
            voice_session.model,
            voice_session.voice,
        ):
            raise HTTPException(
                status_code=409, detail="Provider settings changed; start a new session"
            )
        connection = resolved
    return VoiceSessionCreateOutput(
        session=voice_session,
        connection=connection_payload(voice_session, connection),
    )


@router.patch("/{voice_session_id}/status", response_model=VoiceSessionOutput)
def update_voice_session_status(
    voice_session_id: str,
    payload: VoiceSessionStatusInput,
    database_session: SessionDependency,
    user: CurrentUser,
) -> VoiceSession:
    voice_session = get_owned_voice_session(database_session, user, voice_session_id)
    if (
        voice_session.protocol_version == "live-v1"
        and payload.connection_epoch is not None
        and payload.connection_epoch != voice_session.connection_epoch
    ):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "stale_connection",
                "message": "This update belongs to an older media connection",
                "retryable": False,
            },
        )
    if payload.closing_manifest is not None:
        if len(json.dumps(payload.closing_manifest, ensure_ascii=False)) > 64 * 1024:
            raise HTTPException(status_code=422, detail="Closing manifest is too large")
        voice_session.closing_manifest = payload.closing_manifest
    if payload.end_reason is not None:
        voice_session.end_reason = payload.end_reason
    transition_voice_session(voice_session, VoiceSessionStatus(payload.status))
    if payload.failure_reason is not None:
        voice_session.failure_reason = payload.failure_reason
    if payload.status == "active":
        voice_session.transport_status = (
            "connected" if voice_session.connection_mode == "webrtc" else "text_fallback"
        )
    elif payload.status == "reconnecting":
        voice_session.transport_status = "reconnecting"
    elif payload.status == "ending":
        voice_session.transport_status = "closed"
    database_session.commit()
    database_session.refresh(voice_session)
    return voice_session


@router.get("/{voice_session_id}/transcript.md")
def export_voice_transcript(
    voice_session_id: str, database_session: SessionDependency, user: CurrentUser
) -> Response:
    voice_session = get_owned_voice_session(database_session, user, voice_session_id)
    return Response(
        render_markdown(voice_session),
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="conversation-{voice_session.id}.md"'
        },
    )


@router.post("/{voice_session_id}/offer", response_model=SdpAnswerOutput)
def exchange_sdp_offer(
    voice_session_id: str,
    payload: SdpOfferInput,
    request: Request,
    database_session: SessionDependency,
    user: CurrentUser,
) -> SdpAnswerOutput:
    voice_session = get_owned_voice_session(database_session, user, voice_session_id)
    provider = resolve_realtime_provider(request.app.state.settings)
    if voice_session.connection_mode != "webrtc" or provider.connection.mode != "webrtc":
        raise HTTPException(status_code=409, detail="Session is using local simulation")

    if voice_session.protocol_version == "live-v1":
        if payload.connection_epoch != voice_session.connection_epoch + 1:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "stale_connection",
                    "message": "connection_epoch must advance by one",
                    "retryable": False,
                },
            )
        voice_session.connection_epoch = payload.connection_epoch

    current_status = VoiceSessionStatus(voice_session.status)
    reconnecting = current_status in {
        VoiceSessionStatus.ACTIVE,
        VoiceSessionStatus.RECONNECTING,
    }
    transition_voice_session(
        voice_session,
        VoiceSessionStatus.RECONNECTING if reconnecting else VoiceSessionStatus.CONNECTING,
    )
    voice_session.transport_status = "reconnecting" if reconnecting else "connecting"
    database_session.commit()
    try:
        answer_sdp = provider.exchange_offer(payload.sdp)
    except RealtimeProviderError as error:
        # Keep the learning session writable so the browser can degrade to text mode.
        if voice_session.protocol_version != "live-v1":
            transition_voice_session(voice_session, VoiceSessionStatus.ACTIVE)
        elif reconnecting:
            transition_voice_session(voice_session, VoiceSessionStatus.ACTIVE)
        voice_session.transport_status = "error"
        voice_session.failure_reason = str(error)
        database_session.commit()
        raise HTTPException(status_code=502, detail=str(error)) from error

    if voice_session.protocol_version != "live-v1":
        transition_voice_session(voice_session, VoiceSessionStatus.ACTIVE)
        voice_session.transport_status = "connected"
    voice_session.failure_reason = None
    database_session.commit()
    return SdpAnswerOutput(sdp=answer_sdp, connection_epoch=voice_session.connection_epoch)


@router.patch("/{voice_session_id}/preferences", response_model=VoiceSessionPreferencesOutput)
def update_voice_session_preferences(
    voice_session_id: str,
    payload: VoiceSessionPreferencesInput,
    database_session: SessionDependency,
    user: CurrentUser,
) -> VoiceSessionPreferencesOutput:
    voice_session = get_owned_voice_session(database_session, user, voice_session_id)
    if voice_session.protocol_version != "live-v1":
        raise HTTPException(status_code=409, detail="Preferences require a live-v1 session")
    if voice_session.status not in {
        VoiceSessionStatus.CONNECTING,
        VoiceSessionStatus.RECONNECTING,
        VoiceSessionStatus.ACTIVE,
    }:
        raise HTTPException(status_code=409, detail="Session is not accepting preference changes")
    if payload.expected_config_revision != voice_session.config_revision:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "config_revision_conflict",
                "message": "Realtime settings changed in another request",
                "retryable": True,
                "current_config_revision": voice_session.config_revision,
            },
        )

    if payload.speech_speed is not None:
        voice_session.speech_speed = payload.speech_speed
    if payload.patience is not None:
        voice_session.patience = payload.patience
    context_pack = dict(voice_session.context_pack)
    context_pack.update(
        {"speech_speed": voice_session.speech_speed, "patience": voice_session.patience}
    )
    voice_session.context_pack = context_pack
    voice_session.requested_config = build_requested_config(
        correction_mode=voice_session.correction_mode,
        speech_speed=voice_session.speech_speed,
        patience=voice_session.patience,
    )
    voice_session.config_revision += 1
    database_session.commit()
    database_session.refresh(voice_session)
    return VoiceSessionPreferencesOutput(
        config_revision=voice_session.config_revision,
        applied_config_revision=voice_session.applied_config_revision,
        requested_config=voice_session.requested_config,
        session_update=build_session_update(voice_session),
    )


def same_utterance(existing: Utterance, payload: UtteranceInput) -> bool:
    fields = (
        "sequence_no",
        "connection_epoch",
        "provider_item_id",
        "provider_response_id",
        "content_index",
        "speaker",
        "transcript",
        "source",
        "is_final",
        "transcript_status",
        "started_ms",
        "ended_ms",
    )
    same_transcript = all(getattr(existing, field) == getattr(payload, field) for field in fields)
    playback_compatible = existing.playback_status == payload.playback_status or (
        payload.playback_status == "unknown"
        and existing.playback_status in {"completed", "interrupted"}
    )
    return same_transcript and playback_compatible


def same_provider_utterance(existing: Utterance, payload: UtteranceInput) -> bool:
    fields = (
        "connection_epoch",
        "provider_item_id",
        "provider_response_id",
        "content_index",
        "speaker",
        "transcript",
        "source",
        "is_final",
        "transcript_status",
        "started_ms",
        "ended_ms",
    )
    same_transcript = all(getattr(existing, field) == getattr(payload, field) for field in fields)
    playback_compatible = existing.playback_status == payload.playback_status or (
        payload.playback_status == "unknown"
        and existing.playback_status in {"completed", "interrupted"}
    )
    return same_transcript and playback_compatible


@router.post("/{voice_session_id}/utterances", response_model=UtteranceOutput, status_code=201)
def append_utterance(
    voice_session_id: str,
    payload: UtteranceInput,
    database_session: SessionDependency,
    user: CurrentUser,
) -> Utterance:
    voice_session = get_owned_voice_session(database_session, user, voice_session_id)
    if voice_session.status not in {
        VoiceSessionStatus.CONNECTING,
        VoiceSessionStatus.RECONNECTING,
        VoiceSessionStatus.ACTIVE,
        VoiceSessionStatus.ENDING,
    }:
        raise HTTPException(
            status_code=409, detail="Voice session is not accepting transcript events"
        )

    if (
        voice_session.protocol_version == "live-v1"
        and payload.connection_epoch != voice_session.connection_epoch
    ):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "stale_connection",
                "message": "Transcript belongs to an older media connection",
                "retryable": False,
            },
        )
    if voice_session.status == VoiceSessionStatus.ENDING:
        manifest = voice_session.closing_manifest or {}
        known_ids = manifest.get("known_client_event_ids", [])
        if payload.client_event_id not in known_ids:
            raise HTTPException(status_code=409, detail="Ending session rejects new utterances")

    existing = database_session.scalar(
        select(Utterance).where(
            Utterance.session_id == voice_session.id,
            Utterance.client_event_id == payload.client_event_id,
        )
    )
    if existing:
        if same_utterance(existing, payload):
            return existing
        raise HTTPException(
            status_code=409,
            detail={
                "code": "idempotency_conflict",
                "message": "client_event_id was reused with different transcript content",
                "retryable": False,
            },
        )

    if payload.provider_item_id:
        provider_existing = database_session.scalar(
            select(Utterance).where(
                Utterance.session_id == voice_session.id,
                Utterance.connection_epoch == payload.connection_epoch,
                Utterance.provider_item_id == payload.provider_item_id,
                Utterance.content_index == payload.content_index,
                Utterance.speaker == payload.speaker,
            )
        )
        if provider_existing:
            if same_provider_utterance(provider_existing, payload):
                return provider_existing
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "provider_item_conflict",
                    "message": "Provider item was already saved with different content",
                    "retryable": False,
                },
            )

    utterance = Utterance(session_id=voice_session.id, **payload.model_dump())
    database_session.add(utterance)
    try:
        database_session.commit()
    except IntegrityError as error:
        database_session.rollback()
        raise HTTPException(status_code=409, detail="Utterance sequence already exists") from error
    database_session.refresh(utterance)
    return utterance


@router.patch(
    "/{voice_session_id}/utterances/{utterance_id}/playback",
    response_model=UtteranceOutput,
)
def update_utterance_playback(
    voice_session_id: str,
    utterance_id: str,
    payload: UtterancePlaybackInput,
    database_session: SessionDependency,
    user: CurrentUser,
) -> Utterance:
    voice_session = get_owned_voice_session(database_session, user, voice_session_id)
    utterance = database_session.scalar(
        select(Utterance).where(
            Utterance.id == utterance_id,
            Utterance.session_id == voice_session.id,
        )
    )
    if utterance is None:
        raise HTTPException(status_code=404, detail="Utterance not found")
    if utterance.speaker != "assistant":
        raise HTTPException(status_code=409, detail="User utterances do not have playback state")
    if payload.connection_epoch != utterance.connection_epoch:
        raise HTTPException(status_code=409, detail="Playback update belongs to another connection")
    if utterance.playback_status == payload.playback_status:
        return utterance
    if utterance.playback_status != "unknown":
        raise HTTPException(status_code=409, detail="Playback state is already final")
    if voice_session.status in {VoiceSessionStatus.COMPLETED, VoiceSessionStatus.FAILED}:
        raise HTTPException(status_code=409, detail="Session is closed")
    utterance.playback_status = payload.playback_status
    database_session.commit()
    database_session.refresh(utterance)
    return utterance


@router.get("/{voice_session_id}/events", response_model=list[SessionEventOutput])
def list_session_events(
    voice_session_id: str, database_session: SessionDependency, user: CurrentUser
) -> list[SessionEvent]:
    voice_session = get_owned_voice_session(database_session, user, voice_session_id)
    return list(
        database_session.scalars(
            select(SessionEvent)
            .where(SessionEvent.session_id == voice_session.id)
            .order_by(SessionEvent.created_at)
        )
    )


@router.post("/{voice_session_id}/events", response_model=SessionEventOutput, status_code=201)
def append_session_event(
    voice_session_id: str,
    payload: SessionEventInput,
    database_session: SessionDependency,
    user: CurrentUser,
) -> SessionEvent:
    voice_session = get_owned_voice_session(database_session, user, voice_session_id)
    if len(json.dumps(payload.event_payload, ensure_ascii=False)) > 4096:
        raise HTTPException(status_code=422, detail="Session event payload is too large")

    existing = database_session.scalar(
        select(SessionEvent).where(
            SessionEvent.session_id == voice_session.id,
            SessionEvent.client_event_id == payload.client_event_id,
        )
    )
    if existing:
        return existing

    event = SessionEvent(session_id=voice_session.id, **payload.model_dump())
    database_session.add(event)
    if payload.event_type == "reconnect_attempt":
        voice_session.reconnect_count += 1
    elif payload.event_type == "interruption":
        voice_session.interruption_count += 1
    elif payload.event_type == "provider_first_response":
        latency_ms = payload.event_payload.get("latency_ms")
        if (
            voice_session.first_response_latency_ms is None
            and isinstance(latency_ms, int)
            and 0 <= latency_ms <= 120_000
        ):
            voice_session.first_response_latency_ms = latency_ms
    elif payload.event_type == "config_applied" and voice_session.protocol_version == "live-v1":
        config_revision = payload.event_payload.get("config_revision")
        connection_epoch = payload.event_payload.get("connection_epoch")
        if connection_epoch != voice_session.connection_epoch:
            raise HTTPException(
                status_code=409, detail="Config receipt belongs to another connection"
            )
        if config_revision != voice_session.config_revision:
            raise HTTPException(
                status_code=409, detail="Config receipt is not the current revision"
            )
        voice_session.applied_config_revision = config_revision
    voice_session.last_event_at = utc_now()
    try:
        database_session.commit()
    except IntegrityError:
        database_session.rollback()
        duplicate = database_session.scalar(
            select(SessionEvent).where(
                SessionEvent.session_id == voice_session.id,
                SessionEvent.client_event_id == payload.client_event_id,
            )
        )
        if duplicate:
            return duplicate
        raise
    database_session.refresh(event)
    return event


@router.post("/{voice_session_id}/finalize", response_model=VoiceSessionOutput)
def finalize_voice_session(
    voice_session_id: str,
    payload: VoiceSessionFinalizeInput,
    database_session: SessionDependency,
    user: CurrentUser,
) -> VoiceSession:
    voice_session = get_owned_voice_session(database_session, user, voice_session_id)
    if voice_session.status == VoiceSessionStatus.COMPLETED:
        return voice_session
    if (
        voice_session.protocol_version == "live-v1"
        and voice_session.status != VoiceSessionStatus.ENDING
    ):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "session_not_ending",
                "message": "Begin the ending phase before finalizing a live session",
                "retryable": True,
            },
        )

    expected_by_id = {item.client_event_id: item for item in payload.expected_utterances}
    saved_by_id = {item.client_event_id: item for item in voice_session.utterances}
    missing_ids = sorted(set(expected_by_id) - set(saved_by_id))
    mismatched_ids = sorted(
        item_id
        for item_id, expected in expected_by_id.items()
        if item_id in saved_by_id
        and (
            saved_by_id[item_id].transcript_status != expected.transcript_status
            or saved_by_id[item_id].playback_status != expected.playback_status
        )
    )
    declared_missing = set(payload.missing_client_event_ids)
    manifest_ids = set((voice_session.closing_manifest or {}).get("known_client_event_ids", []))
    if declared_missing - manifest_ids:
        raise HTTPException(status_code=422, detail="Missing IDs must belong to closing manifest")
    unresolved_ids = sorted(set(missing_ids) | set(mismatched_ids) | declared_missing)
    incomplete_saved = sorted(
        item.client_event_id
        for item in voice_session.utterances
        if item.transcript_status != "final"
    )
    incomplete_ids = sorted(set(unresolved_ids) | set(incomplete_saved))
    if incomplete_ids and not payload.allow_incomplete:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "transcript_pending",
                "message": "Some conversation records are not saved or final",
                "retryable": True,
                "missing_client_event_ids": incomplete_ids,
            },
        )
    if incomplete_ids:
        voice_session.end_reason = "save_incomplete"
        voice_session.failure_reason = (
            f"Conversation record is incomplete ({len(incomplete_ids)} item(s))"
        )

    transition_voice_session(voice_session, VoiceSessionStatus.COMPLETED)
    duration_limit = (
        2147483647
        if voice_session.context_pack.get("continuous")
        else voice_session.max_duration_seconds
    )
    if voice_session.protocol_version == "live-v1" and voice_session.started_at:
        ended_at = voice_session.ending_at or voice_session.ended_at or utc_now()
        voice_session.duration_seconds = min(
            max(0, int((as_utc(ended_at) - as_utc(voice_session.started_at)).total_seconds())),
            duration_limit,
        )
    elif payload.duration_seconds is not None:
        voice_session.duration_seconds = min(payload.duration_seconds, duration_limit)
    elif voice_session.started_at and voice_session.ended_at:
        voice_session.duration_seconds = min(
            int(
                (as_utc(voice_session.ended_at) - as_utc(voice_session.started_at)).total_seconds()
            ),
            duration_limit,
        )

    workspace = voice_session.workspace
    transcript_preview = " ".join(
        utterance.transcript for utterance in voice_session.utterances[-3:]
    )[:300]
    workspace.state = {
        **workspace.state,
        "last_session_id": voice_session.id,
        "last_transcript_preview": transcript_preview,
        "active_session_id": None,
        "progress": 100,
    }
    workspace.status = "completed"
    workspace.last_opened_at = utc_now()
    database_session.commit()
    database_session.refresh(voice_session)
    return voice_session
