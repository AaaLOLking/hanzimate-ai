import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SessionEvent, VoiceSession, VoiceSessionStatus, utc_now

LOGGER = logging.getLogger(__name__)
HEARTBEAT_STALE_AFTER = timedelta(seconds=90)
SWEEP_INTERVAL_SECONDS = 30


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def ending_manifest(voice_session: VoiceSession, reason: str) -> dict[str, object]:
    return {
        "known_client_event_ids": [
            utterance.client_event_id for utterance in voice_session.utterances
        ],
        "connection_epoch": voice_session.connection_epoch,
        "config_revision": voice_session.config_revision,
        "server_reason": reason,
    }


def sweep_stale_voice_sessions(
    session: Session,
    now: datetime | None = None,
) -> int:
    observed_at = as_utc(now or utc_now())
    candidates = session.scalars(
        select(VoiceSession).where(
            VoiceSession.protocol_version == "live-v1",
            VoiceSession.status.in_(
                [
                    VoiceSessionStatus.CONNECTING,
                    VoiceSessionStatus.RECONNECTING,
                    VoiceSessionStatus.ACTIVE,
                ]
            ),
        )
    )
    swept = 0
    for voice_session in candidates:
        reason = None
        if (
            not voice_session.context_pack.get("continuous", False)
            and voice_session.deadline_at
            and as_utc(voice_session.deadline_at) <= observed_at
        ):
            reason = "practice_limit"
        else:
            activity = (
                voice_session.last_event_at or voice_session.started_at or voice_session.created_at
            )
            if as_utc(activity) + HEARTBEAT_STALE_AFTER <= observed_at:
                reason = "client_abandoned"
        if reason is None:
            continue

        voice_session.status = VoiceSessionStatus.ENDING
        voice_session.transport_status = "closed"
        voice_session.ending_at = observed_at
        voice_session.end_reason = reason
        voice_session.closing_manifest = ending_manifest(voice_session, reason)
        voice_session.last_event_at = observed_at
        session.add(
            SessionEvent(
                session_id=voice_session.id,
                client_event_id=f"session-timeout-{voice_session.id}",
                event_type="session_timeout",
                elapsed_ms=None,
                event_payload={"reason": reason},
                created_at=observed_at,
            )
        )
        swept += 1
    if swept:
        session.commit()
    return swept


async def voice_session_lifecycle_worker(database) -> None:
    def tick() -> None:
        with database.session_factory() as session:
            sweep_stale_voice_sessions(session)

    while True:
        try:
            await asyncio.to_thread(tick)
        except Exception:
            LOGGER.exception("Voice session lifecycle tick failed; retrying on next tick")
        await asyncio.sleep(SWEEP_INTERVAL_SECONDS)
