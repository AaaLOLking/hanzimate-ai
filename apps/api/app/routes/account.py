from __future__ import annotations

from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import delete, func, select

from app.auth import CurrentUser, SessionDependency
from app.model_usage import build_usage_summary
from app.models import (
    AccountDeletionReceipt,
    BetaFeedback,
    Consent,
    ErrorCluster,
    ErrorEvent,
    LearnerMission,
    LearnerProfile,
    LearningEvidence,
    LessonMessage,
    LessonProgress,
    ModelRun,
    ReviewAttempt,
    ReviewCard,
    ReviewLog,
    ReviewPreference,
    ReviewReminder,
    SessionEvent,
    SessionSummary,
    User,
    Utterance,
    VoiceSession,
    Workspace,
    utc_now,
)
from app.schemas import AccountDeleteInput, AccountDeleteOutput, AccountOverviewOutput

router = APIRouter(prefix="/api/v1/account", tags=["account"])


def _latest(session: SessionDependency, model: type[Any], user_id: str, order: Any) -> Any:
    return session.scalars(
        select(model).where(model.user_id == user_id).order_by(order.desc()).limit(1)
    ).first()


def _count(session: SessionDependency, model: type[Any], *conditions: Any) -> int:
    return int(session.scalar(select(func.count()).select_from(model).where(*conditions)) or 0)


@router.get("", response_model=AccountOverviewOutput)
def get_account_overview(
    request: Request,
    session: SessionDependency,
    user: CurrentUser,
) -> dict[str, Any]:
    consent = _latest(session, Consent, user.id, Consent.granted_at)
    mission = _latest(session, LearnerMission, user.id, LearnerMission.updated_at)
    profile = session.get(LearnerProfile, user.id)
    return {
        "user": user,
        "consent": consent,
        "mission": mission,
        "profile": profile,
        "stats": {
            "workspaces": _count(session, Workspace, Workspace.user_id == user.id),
            "conversations": _count(session, VoiceSession, VoiceSession.user_id == user.id),
            "lessons_started": _count(
                session, LessonProgress, LessonProgress.user_id == user.id
            ),
            "lessons_completed": _count(
                session,
                LessonProgress,
                LessonProgress.user_id == user.id,
                LessonProgress.status == "completed",
            ),
            "active_memories": _count(
                session,
                ErrorCluster,
                ErrorCluster.user_id == user.id,
                ErrorCluster.status == "active",
            ),
            "review_attempts": _count(
                session, ReviewAttempt, ReviewAttempt.user_id == user.id
            ),
        },
        "model_usage": build_usage_summary(session, user.id, request.app.state.settings),
    }


def _json_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    return value


def _export_row(item: Any, *, excluded: set[str] | None = None) -> dict[str, Any]:
    hidden = excluded or set()
    return {
        column.key: _json_value(getattr(item, column.key))
        for column in item.__table__.columns
        if column.key not in hidden
    }


def _owned_rows(session: SessionDependency, model: type[Any], user_id: str) -> list[Any]:
    return list(session.scalars(select(model).where(model.user_id == user_id)))


@router.get("/export")
def export_account_data(
    session: SessionDependency,
    user: CurrentUser,
) -> JSONResponse:
    voice_sessions = _owned_rows(session, VoiceSession, user.id)
    session_ids = [item.id for item in voice_sessions]
    utterances = (
        list(session.scalars(select(Utterance).where(Utterance.session_id.in_(session_ids))))
        if session_ids
        else []
    )
    session_events = (
        list(
            session.scalars(select(SessionEvent).where(SessionEvent.session_id.in_(session_ids)))
        )
        if session_ids
        else []
    )
    profile = session.get(LearnerProfile, user.id)
    preference = session.get(ReviewPreference, user.id)
    collections: dict[str, list[Any]] = {
        "consents": _owned_rows(session, Consent, user.id),
        "missions": _owned_rows(session, LearnerMission, user.id),
        "workspaces": _owned_rows(session, Workspace, user.id),
        "conversation_sessions": voice_sessions,
        "utterances": utterances,
        "session_events": session_events,
        "session_summaries": _owned_rows(session, SessionSummary, user.id),
        "error_events": _owned_rows(session, ErrorEvent, user.id),
        "error_memories": _owned_rows(session, ErrorCluster, user.id),
        "lesson_progress": _owned_rows(session, LessonProgress, user.id),
        "learning_evidence": _owned_rows(session, LearningEvidence, user.id),
        "lesson_messages": _owned_rows(session, LessonMessage, user.id),
        "review_cards": _owned_rows(session, ReviewCard, user.id),
        "review_attempts": _owned_rows(session, ReviewAttempt, user.id),
        "review_logs": _owned_rows(session, ReviewLog, user.id),
        "review_reminders": _owned_rows(session, ReviewReminder, user.id),
        "model_runs": _owned_rows(session, ModelRun, user.id),
        "beta_feedback": _owned_rows(session, BetaFeedback, user.id),
    }
    exported = {
        key: [
            _export_row(item, excluded={"answer_rule"} if key == "learning_evidence" else set())
            for item in items
        ]
        for key, items in collections.items()
    }
    archive = {
        "format": "hanzimate-personal-data-v1",
        "generated_at": utc_now().isoformat(),
        "account": _export_row(user),
        "learning_profile": _export_row(profile) if profile else None,
        "review_preference": _export_row(preference) if preference else None,
        "record_counts": {key: len(items) for key, items in collections.items()},
        "data": exported,
        "notes": [
            "This archive contains personal learning data only.",
            "Provider credentials and private course answer rules are never included.",
            "Raw audio is not stored by the MVP.",
        ],
    }
    filename = f"hanzimate-data-{utc_now().date().isoformat()}.json"
    return JSONResponse(
        content=archive,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _delete_owned(
    session: SessionDependency,
    model: type[Any],
    *conditions: Any,
) -> int:
    result = session.execute(delete(model).where(*conditions))
    return int(result.rowcount or 0)


@router.delete("", response_model=AccountDeleteOutput)
def delete_account(
    payload: AccountDeleteInput,
    session: SessionDependency,
    user: CurrentUser,
) -> dict[str, Any]:
    if payload.email.strip().casefold() != user.email.casefold():
        raise HTTPException(status_code=422, detail="邮箱与当前账户不一致")

    session_ids = list(
        session.scalars(select(VoiceSession.id).where(VoiceSession.user_id == user.id))
    )
    deleted: dict[str, int] = {}

    for label, model in (
        ("review_logs", ReviewLog),
        ("review_attempts", ReviewAttempt),
        ("review_reminders", ReviewReminder),
        ("review_cards", ReviewCard),
        ("review_preferences", ReviewPreference),
        ("error_events", ErrorEvent),
        ("session_summaries", SessionSummary),
    ):
        deleted[label] = _delete_owned(session, model, model.user_id == user.id)

    deleted["utterances"] = (
        _delete_owned(session, Utterance, Utterance.session_id.in_(session_ids))
        if session_ids
        else 0
    )
    deleted["session_events"] = (
        _delete_owned(session, SessionEvent, SessionEvent.session_id.in_(session_ids))
        if session_ids
        else 0
    )

    for label, model in (
        ("conversation_sessions", VoiceSession),
        ("lesson_messages", LessonMessage),
        ("learning_evidence", LearningEvidence),
        ("lesson_progress", LessonProgress),
        ("error_memories", ErrorCluster),
        ("workspaces", Workspace),
        ("consents", Consent),
        ("missions", LearnerMission),
        ("learning_profiles", LearnerProfile),
        ("model_runs", ModelRun),
        ("beta_feedback", BetaFeedback),
    ):
        deleted[label] = _delete_owned(session, model, model.user_id == user.id)

    deleted["accounts"] = _delete_owned(session, User, User.id == user.id)
    receipt = AccountDeletionReceipt(deleted_records=deleted)
    session.add(receipt)
    session.commit()
    session.refresh(receipt)
    return {
        "receipt_id": receipt.id,
        "deleted_at": receipt.deleted_at,
        "deleted_records": receipt.deleted_records,
    }
