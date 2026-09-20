from typing import Any

from fastapi import APIRouter, status
from sqlalchemy import func, select

from app.auth import CurrentUser, SessionDependency
from app.models import BetaFeedback, LessonProgress, ReviewLog, VoiceSession
from app.schemas import BetaDashboardOutput, BetaFeedbackInput, BetaFeedbackOutput

router = APIRouter(prefix="/api/v1/beta", tags=["beta"])


def _count(session: SessionDependency, model: type[Any], *conditions: Any) -> int:
    return int(session.scalar(select(func.count()).select_from(model).where(*conditions)) or 0)


def _milestone(current: int, target: int) -> dict[str, int | bool]:
    return {"current": current, "target": target, "complete": current >= target}


@router.get("", response_model=BetaDashboardOutput)
def get_beta_dashboard(
    session: SessionDependency,
    user: CurrentUser,
) -> dict[str, Any]:
    progress = {
        "conversations": _milestone(
            _count(
                session,
                VoiceSession,
                VoiceSession.user_id == user.id,
                VoiceSession.status == "completed",
            ),
            3,
        ),
        "lessons": _milestone(
            _count(
                session,
                LessonProgress,
                LessonProgress.user_id == user.id,
                LessonProgress.status == "completed",
            ),
            2,
        ),
        "reviews": _milestone(
            _count(session, ReviewLog, ReviewLog.user_id == user.id),
            2,
        ),
        "feedback": _milestone(
            _count(session, BetaFeedback, BetaFeedback.user_id == user.id),
            1,
        ),
    }
    feedback = list(
        session.scalars(
            select(BetaFeedback)
            .where(BetaFeedback.user_id == user.id)
            .order_by(BetaFeedback.created_at.desc())
            .limit(20)
        )
    )
    return {
        "progress": progress,
        "ready_for_exit": all(item["complete"] for item in progress.values()),
        "feedback": feedback,
    }


@router.post(
    "/feedback",
    response_model=BetaFeedbackOutput,
    status_code=status.HTTP_201_CREATED,
)
def create_beta_feedback(
    payload: BetaFeedbackInput,
    session: SessionDependency,
    user: CurrentUser,
) -> BetaFeedback:
    feedback = BetaFeedback(user_id=user.id, **payload.model_dump())
    session.add(feedback)
    session.commit()
    session.refresh(feedback)
    return feedback
