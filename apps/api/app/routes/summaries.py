from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.auth import CurrentUser, SessionDependency
from app.model_usage import (
    add_model_run,
    elapsed_ms,
    estimate_tokens,
    model_budget_block_reason,
    start_timer,
)
from app.models import ErrorCluster, ErrorEvent, LearnerProfile, SessionSummary, VoiceSessionStatus
from app.providers.summary import (
    MockSummaryProvider,
    SummaryProviderError,
    SummaryRequest,
    build_summary_provider,
)
from app.routes.voice import get_owned_voice_session
from app.schemas import SessionSummaryOutput

router = APIRouter(prefix="/api/v1/voice/sessions", tags=["learning-memory"])


def _get_summary(
    database_session: SessionDependency, user: CurrentUser, voice_session_id: str
) -> SessionSummary | None:
    return database_session.scalar(
        select(SessionSummary).where(
            SessionSummary.session_id == voice_session_id,
            SessionSummary.user_id == user.id,
        )
    )


@router.get("/{voice_session_id}/summary", response_model=SessionSummaryOutput | None)
def get_session_summary(
    voice_session_id: str,
    database_session: SessionDependency,
    user: CurrentUser,
) -> SessionSummary | None:
    get_owned_voice_session(database_session, user, voice_session_id)
    return _get_summary(database_session, user, voice_session_id)


@router.post(
    "/{voice_session_id}/summary",
    response_model=SessionSummaryOutput,
    status_code=201,
)
def generate_session_summary(
    voice_session_id: str,
    request: Request,
    database_session: SessionDependency,
    user: CurrentUser,
) -> SessionSummary:
    voice_session = get_owned_voice_session(database_session, user, voice_session_id)
    existing = _get_summary(database_session, user, voice_session_id)
    if existing is not None:
        return existing
    if voice_session.status != VoiceSessionStatus.COMPLETED:
        raise HTTPException(status_code=409, detail="Voice session must be completed first")

    profile = database_session.get(LearnerProfile, user.id)
    clusters = list(
        database_session.scalars(
            select(ErrorCluster)
            .where(ErrorCluster.user_id == user.id, ErrorCluster.status == "active")
            .order_by(ErrorCluster.last_seen_at.desc())
            .limit(8)
        )
    )
    settings = request.app.state.settings
    provider = build_summary_provider(settings)
    reliable_utterances = [
        utterance
        for utterance in voice_session.utterances
        if utterance.transcript_status == "final"
    ]
    if not any(utterance.speaker == "user" for utterance in reliable_utterances):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "no_reliable_transcript",
                "message": "No complete learner transcript is available for a learning report",
                "retryable": False,
            },
        )
    summary_request = SummaryRequest(
        session_id=voice_session.id,
        objective=str(voice_session.context_pack.get("objective", "完成中文对话练习")),
        learner_profile=(
            {
                "estimated_hsk_band": profile.estimated_hsk_band,
                "native_language": profile.native_language,
                "support_language": profile.support_language,
                "skill_estimates": profile.skill_estimates,
            }
            if profile
            else {}
        ),
        utterances=[
            {
                "id": utterance.id,
                "speaker": utterance.speaker,
                "text": utterance.transcript,
                "source": utterance.source,
                "is_final": utterance.is_final,
            }
            for utterance in reliable_utterances
        ],
        recalled_errors=[
            {
                "canonical_key": cluster.canonical_key,
                "error_type": cluster.error_type,
                "subtype": cluster.subtype,
                "corrected_example": cluster.corrected_example,
                "occurrence_count": cluster.occurrence_count,
            }
            for cluster in clusters
        ],
        skill_version=voice_session.skill_version,
    )
    request_tokens = estimate_tokens(
        {
            "objective": summary_request.objective,
            "learner_profile": summary_request.learner_profile,
            "utterances": summary_request.utterances,
            "recalled_errors": summary_request.recalled_errors,
        }
    )
    fallback_from: str | None = None
    block_reason = model_budget_block_reason(
        database_session,
        user.id,
        provider.provider,
        settings,
        reserved_input_tokens=request_tokens,
        reserved_output_tokens=1800,
    )
    if block_reason:
        add_model_run(
            database_session,
            settings,
            user_id=user.id,
            task="conversation_summary",
            provider=provider.provider,
            model=provider.model,
            status="blocked",
            latency_ms=0,
            input_tokens=request_tokens,
            output_tokens=0,
            error_code=block_reason,
        )
        fallback_from = provider.provider
        provider = MockSummaryProvider()

    started_at = start_timer()
    try:
        generated = provider.generate(summary_request)
    except SummaryProviderError as error:
        add_model_run(
            database_session,
            settings,
            user_id=user.id,
            task="conversation_summary",
            provider=provider.provider,
            model=provider.model,
            status="failed",
            latency_ms=elapsed_ms(started_at),
            input_tokens=request_tokens,
            output_tokens=0,
            error_code="provider_error",
        )
        if provider.provider == "local":
            raise HTTPException(status_code=502, detail=str(error)) from error
        fallback_from = provider.provider
        provider = MockSummaryProvider()
        started_at = start_timer()
        generated = provider.generate(summary_request)

    add_model_run(
        database_session,
        settings,
        user_id=user.id,
        task="conversation_summary",
        provider=provider.provider,
        model=provider.model,
        status="succeeded",
        latency_ms=elapsed_ms(started_at),
        input_tokens=request_tokens,
        output_tokens=estimate_tokens(generated.model_dump(mode="json")),
        fallback_from=fallback_from,
    )

    summary = SessionSummary(
        session_id=voice_session.id,
        user_id=user.id,
        task_status=generated.task_result.status,
        task_explanation=generated.task_result.explanation,
        highlights=generated.highlights,
        next_step=generated.next_step,
        provider=provider.provider,
        model=provider.model,
        skill_version=generated.skill_version,
    )
    database_session.add(summary)
    database_session.flush()
    for candidate in generated.candidate_errors:
        evidence_utterance_id = next(
            (
                utterance.id
                for utterance in reliable_utterances
                if utterance.speaker == "user"
                and candidate.evidence_span in utterance.transcript
            ),
            None,
        )
        summary.candidate_errors.append(
            ErrorEvent(
                session_id=voice_session.id,
                user_id=user.id,
                evidence_utterance_id=evidence_utterance_id,
                source_type=candidate.source_type,
                source_id=candidate.source_id,
                learner_text=candidate.learner_text,
                corrected_text=candidate.corrected_text,
                explanation=candidate.explanation,
                error_type=candidate.error_type,
                subtype=candidate.subtype,
                severity=candidate.severity,
                confidence=candidate.confidence,
                status="candidate",
                evidence_span=candidate.evidence_span,
                canonical_key=candidate.canonical_key,
                hsk_tags=candidate.hsk_tags,
                model_version=candidate.model_version,
                skill_version=candidate.skill_version,
                observed_at=candidate.observed_at,
            )
        )

    workspace = voice_session.workspace
    workspace.state = {
        **workspace.state,
        "summary_id": summary.id,
        "summary_highlights": generated.highlights,
        "next_step": generated.next_step,
        "candidate_error_count": len(generated.candidate_errors),
        "summary_provider": provider.provider,
    }
    workspace.status = "review_due" if generated.candidate_errors else "completed"
    try:
        database_session.commit()
    except IntegrityError:
        database_session.rollback()
        duplicate = _get_summary(database_session, user, voice_session_id)
        if duplicate is not None:
            return duplicate
        raise
    database_session.refresh(summary)
    return summary
