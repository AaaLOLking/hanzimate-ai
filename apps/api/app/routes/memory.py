from fastapi import APIRouter, HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.auth import CurrentUser, SessionDependency
from app.models import ErrorCluster, ErrorEvent, LearnerProfile, ReviewCard, VoiceSession, utc_now
from app.reviews import ensure_review_card
from app.schemas import (
    ErrorClusterOutput,
    ErrorClusterUpdateInput,
    ErrorDecisionInput,
    ErrorEventOutput,
)

router = APIRouter(prefix="/api/v1", tags=["learning-memory"])


@router.get("/errors", response_model=list[ErrorEventOutput])
def list_error_events(
    database_session: SessionDependency,
    user: CurrentUser,
    status: str | None = None,
) -> list[ErrorEvent]:
    if status is not None and status not in {"candidate", "confirmed", "rejected"}:
        raise HTTPException(status_code=422, detail="Unsupported error status")
    statement = select(ErrorEvent).where(ErrorEvent.user_id == user.id)
    if status is not None:
        statement = statement.where(ErrorEvent.status == status)
    return list(
        database_session.scalars(statement.order_by(ErrorEvent.observed_at.desc()).limit(100))
    )


@router.patch("/errors/{error_id}", response_model=ErrorEventOutput)
def decide_error_event(
    error_id: str,
    payload: ErrorDecisionInput,
    database_session: SessionDependency,
    user: CurrentUser,
) -> ErrorEvent:
    event = database_session.scalar(
        select(ErrorEvent).where(ErrorEvent.id == error_id, ErrorEvent.user_id == user.id)
    )
    if event is None:
        raise HTTPException(status_code=404, detail="Error event not found")
    if event.status == payload.status:
        return event
    if event.status != "candidate":
        raise HTTPException(status_code=409, detail="This error decision is already final")

    if payload.corrected_text:
        event.corrected_text = payload.corrected_text
    event.status = payload.status
    if payload.status == "confirmed":
        cluster = database_session.scalar(
            select(ErrorCluster).where(
                ErrorCluster.user_id == user.id,
                ErrorCluster.canonical_key == event.canonical_key,
            )
        )
        now = utc_now()
        if cluster is None:
            cluster = ErrorCluster(
                user_id=user.id,
                canonical_key=event.canonical_key,
                error_type=event.error_type,
                subtype=event.subtype,
                explanation=event.explanation,
                corrected_example=event.corrected_text,
                first_seen_at=event.observed_at,
                last_seen_at=event.observed_at,
            )
            database_session.add(cluster)
            database_session.flush()
        else:
            cluster.status = "active"
            cluster.occurrence_count += 1
            # Confirmed events are generated after the existing cluster observation. Assigning
            # directly also avoids comparing offset-aware values with SQLite's naive datetimes.
            cluster.last_seen_at = event.observed_at
            cluster.corrected_example = event.corrected_text
            cluster.explanation = event.explanation
            cluster.updated_at = now
        event.cluster_id = cluster.id
        ensure_review_card(database_session, cluster)

    database_session.flush()
    _refresh_profile_memory_count(database_session, user.id)
    _refresh_workspace_review_state(database_session, event)
    database_session.commit()
    database_session.refresh(event)
    return event


@router.get("/error-clusters", response_model=list[ErrorClusterOutput])
def list_error_clusters(
    database_session: SessionDependency,
    user: CurrentUser,
    status: str = "active",
) -> list[ErrorCluster]:
    if status not in {"active", "archived"}:
        raise HTTPException(status_code=422, detail="Unsupported cluster status")
    return list(
        database_session.scalars(
            select(ErrorCluster)
            .options(selectinload(ErrorCluster.review_card))
            .where(ErrorCluster.user_id == user.id, ErrorCluster.status == status)
            .order_by(ErrorCluster.last_seen_at.desc())
            .limit(100)
        )
    )


@router.delete("/error-clusters/{cluster_id}", status_code=204)
def archive_error_cluster(
    cluster_id: str,
    database_session: SessionDependency,
    user: CurrentUser,
) -> Response:
    cluster = database_session.scalar(
        select(ErrorCluster).where(
            ErrorCluster.id == cluster_id,
            ErrorCluster.user_id == user.id,
        )
    )
    if cluster is None:
        raise HTTPException(status_code=404, detail="Error cluster not found")
    cluster.status = "archived"
    cluster.updated_at = utc_now()
    card = database_session.scalar(
        select(ReviewCard).where(ReviewCard.error_cluster_id == cluster.id)
    )
    if card is not None:
        card.status = "suspended"
    database_session.flush()
    _refresh_profile_memory_count(database_session, user.id)
    database_session.commit()
    return Response(status_code=204)


@router.patch("/error-clusters/{cluster_id}", response_model=ErrorClusterOutput)
def update_error_cluster(
    cluster_id: str,
    payload: ErrorClusterUpdateInput,
    database_session: SessionDependency,
    user: CurrentUser,
) -> ErrorCluster:
    cluster = database_session.scalar(
        select(ErrorCluster)
        .options(selectinload(ErrorCluster.review_card))
        .where(
            ErrorCluster.id == cluster_id,
            ErrorCluster.user_id == user.id,
            ErrorCluster.status == "active",
        )
    )
    if cluster is None:
        raise HTTPException(status_code=404, detail="Error cluster not found")
    cluster.explanation = payload.explanation.strip()
    cluster.corrected_example = payload.corrected_example.strip()
    cluster.updated_at = utc_now()
    database_session.commit()
    database_session.refresh(cluster)
    return cluster


def _refresh_profile_memory_count(database_session: SessionDependency, user_id: str) -> None:
    profile = database_session.get(LearnerProfile, user_id)
    if profile is None:
        return
    count = database_session.scalar(
        select(func.count(ErrorCluster.id)).where(
            ErrorCluster.user_id == user_id,
            ErrorCluster.status == "active",
        )
    )
    profile.skill_estimates = {
        **profile.skill_estimates,
        "confirmed_error_clusters": int(count or 0),
    }
    profile.projection_version += 1


def _refresh_workspace_review_state(
    database_session: SessionDependency, event: ErrorEvent
) -> None:
    remaining = database_session.scalar(
        select(func.count(ErrorEvent.id)).where(
            ErrorEvent.session_id == event.session_id,
            ErrorEvent.status == "candidate",
        )
    )
    # Resolve through the owning session without accepting a caller-provided workspace id.
    voice_session = database_session.get(VoiceSession, event.session_id)
    workspace = voice_session.workspace if voice_session else None
    if workspace is None:
        return
    workspace.state = {
        **workspace.state,
        "candidate_error_count": int(remaining or 0),
    }
    if not remaining:
        workspace.status = "completed"
