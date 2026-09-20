from datetime import datetime, time
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Response
from fsrs import Card
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from app.auth import CurrentUser, SessionDependency
from app.models import (
    ReviewAttempt,
    ReviewCard,
    ReviewLog,
    ReviewPreference,
    ReviewReminder,
    utc_now,
)
from app.review_schemas import (
    ReviewAttemptInput,
    ReviewAttemptOutput,
    ReviewCardOutput,
    ReviewDashboard,
    ReviewPreferencesInput,
    ReviewRatingInput,
    ReviewReceipt,
    ReviewReminderOutput,
)
from app.reviews import (
    RATINGS,
    SKILL_VERSION,
    active_cards,
    as_utc,
    attempt_output,
    exercise_for,
    planned_due,
    preferences_for,
    reminder_is_visible,
    review_feedback,
    scheduler_for,
)

router = APIRouter(prefix="/api/v1", tags=["reviews"])


@router.get("/review-preferences", response_model=ReviewPreferencesInput)
def get_preferences(session: SessionDependency, user: CurrentUser):
    return preferences_for(session, user.id)


@router.put("/review-preferences", response_model=ReviewPreferencesInput)
def save_preferences(
    payload: ReviewPreferencesInput, session: SessionDependency, user: CurrentUser
):
    stored = session.get(ReviewPreference, user.id)
    if stored is None:
        stored = ReviewPreference(user_id=user.id)
        session.add(stored)
    for key, value in payload.model_dump().items():
        setattr(stored, key, value)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(409, "设置刚被另一窗口更新，请刷新后重试") from exc
    return payload


@router.get("/reviews", response_model=ReviewDashboard)
def dashboard(session: SessionDependency, user: CurrentUser):
    now = utc_now()
    preferences = preferences_for(session, user.id)
    base = active_cards(user.id)
    due = base.where(ReviewCard.due_at <= now)
    due_count = session.scalar(select(func.count()).select_from(due.subquery())) or 0
    active_count = session.scalar(select(func.count()).select_from(base.subquery())) or 0
    cards = list(session.scalars(due.order_by(ReviewCard.due_at, ReviewCard.id).limit(20)))
    upcoming = list(
        session.scalars(
            base.where(ReviewCard.due_at > now).order_by(ReviewCard.due_at, ReviewCard.id).limit(5)
        )
    )
    pending = {
        attempt.card_id: attempt
        for attempt in session.scalars(
            select(ReviewAttempt)
            .join(ReviewCard)
            .outerjoin(ReviewLog, ReviewLog.attempt_id == ReviewAttempt.id)
            .where(
                ReviewAttempt.user_id == user.id,
                ReviewAttempt.card_revision == ReviewCard.revision,
                ReviewLog.id.is_(None),
            )
        )
    }

    def public_card(card: ReviewCard) -> ReviewCardOutput:
        exercise = exercise_for(card)
        attempt = pending.get(card.id)
        return ReviewCardOutput(
            id=card.id,
            error_cluster_id=card.error_cluster_id,
            title=exercise["title"],
            prompt=exercise["prompt"],
            revision=card.revision,
            due_at=as_utc(card.due_at),
            pending_attempt=attempt_output(attempt) if attempt else None,
        )

    local = now.astimezone(ZoneInfo(preferences.timezone))
    day_start = datetime.combine(local.date(), time.min, local.tzinfo)
    reviewed_today = (
        session.scalar(
            select(func.count(ReviewLog.id)).where(
                ReviewLog.user_id == user.id, ReviewLog.reviewed_at >= as_utc(day_start)
            )
        )
        or 0
    )
    history = list(
        session.scalars(
            select(ReviewLog)
            .where(ReviewLog.user_id == user.id)
            .order_by(ReviewLog.reviewed_at.desc())
            .limit(10)
        )
    )
    reminder = None
    if due_count and reminder_is_visible(preferences, now):
        reminder = session.scalar(
            select(ReviewReminder).where(
                ReviewReminder.user_id == user.id,
                ReviewReminder.local_date == local.date(),
                ReviewReminder.dismissed_at.is_(None),
            )
        )
    return ReviewDashboard(
        preferences=preferences,
        due_count=due_count,
        active_count=active_count,
        reviewed_today=reviewed_today,
        cards=[public_card(card) for card in cards],
        upcoming=[public_card(card) for card in upcoming],
        history=[receipt(log) for log in history],
        reminder=ReviewReminderOutput(
            id=reminder.id, due_count=due_count, scheduled_at=as_utc(reminder.scheduled_at)
        )
        if reminder
        else None,
    )


@router.post("/reviews/{card_id}/attempts", response_model=ReviewAttemptOutput, status_code=201)
def submit_attempt(
    card_id: str, payload: ReviewAttemptInput, session: SessionDependency, user: CurrentUser
):
    request_id = str(payload.request_id)
    existing = session.scalar(
        select(ReviewAttempt).where(
            ReviewAttempt.user_id == user.id, ReviewAttempt.request_id == request_id
        )
    )
    if existing:
        if (existing.card_id, existing.card_revision, existing.response) != (
            card_id,
            payload.card_revision,
            payload.response,
        ):
            raise HTTPException(409, "这次提交编号已经用于另一份答案")
        return attempt_output(existing)
    card = session.scalar(active_cards(user.id).where(ReviewCard.id == card_id))
    if card is None:
        raise HTTPException(404, "复习项不存在或已归档")
    if card.revision != payload.card_revision or as_utc(card.due_at) > utc_now():
        raise HTTPException(409, "这道题已经更新或还未到期，请刷新复习列表")
    exercise = exercise_for(card)
    matched, feedback = review_feedback(exercise, payload.response)
    attempt = ReviewAttempt(
        user_id=user.id,
        card_id=card.id,
        request_id=request_id,
        card_revision=card.revision,
        response=payload.response,
        exercise=exercise,
        rule_matched=matched,
        feedback=feedback,
    )
    session.add(attempt)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        same = session.scalar(
            select(ReviewAttempt).where(
                ReviewAttempt.user_id == user.id, ReviewAttempt.request_id == request_id
            )
        )
        if same and (same.card_id, same.card_revision, same.response) == (
            card_id,
            payload.card_revision,
            payload.response,
        ):
            return attempt_output(same)
        raise HTTPException(409, "本题已有待自评的作答，请刷新后继续") from exc
    return attempt_output(attempt)


def receipt(log: ReviewLog) -> ReviewReceipt:
    return ReviewReceipt(
        id=log.id,
        card_id=log.card_id,
        attempt_id=log.attempt_id,
        rating=log.rating,
        due_at=as_utc(log.due_at),
        algorithm_due_at=as_utc(log.algorithm_due_at),
        reviewed_at=as_utc(log.reviewed_at),
    )


@router.post("/review-attempts/{attempt_id}/rating", response_model=ReviewReceipt)
def rate_attempt(
    attempt_id: str, payload: ReviewRatingInput, session: SessionDependency, user: CurrentUser
):
    attempt = session.scalar(
        select(ReviewAttempt).where(
            ReviewAttempt.id == attempt_id, ReviewAttempt.user_id == user.id
        )
    )
    if attempt is None:
        raise HTTPException(404, "找不到这次作答")
    existing = session.scalar(select(ReviewLog).where(ReviewLog.attempt_id == attempt.id))
    if existing:
        if existing.rating != payload.rating:
            raise HTTPException(409, "这次自评已保存，不能覆盖历史记录")
        return receipt(existing)
    card = session.scalar(active_cards(user.id).where(ReviewCard.id == attempt.card_id))
    if card is None:
        raise HTTPException(404, "复习项已归档")
    if card.revision != attempt.card_revision:
        raise HTTPException(409, "复习项已更新，请刷新后继续")
    now = utc_now()
    preferences = preferences_for(session, user.id)
    scheduler = scheduler_for(preferences)
    before = card.fsrs_state
    after, fsrs_log = scheduler.review_card(
        Card.from_dict(before), RATINGS[payload.rating], review_datetime=now
    )
    due_at = planned_due(after.due, now, payload.rating, preferences)
    changed = session.execute(
        update(ReviewCard)
        .where(
            ReviewCard.id == card.id,
            ReviewCard.user_id == user.id,
            ReviewCard.revision == attempt.card_revision,
            ReviewCard.status == "active",
        )
        .values(
            fsrs_state=after.to_dict(),
            algorithm_due_at=after.due,
            due_at=due_at,
            revision=attempt.card_revision + 1,
        )
    )
    if changed.rowcount != 1:
        session.rollback()
        raced = session.scalar(select(ReviewLog).where(ReviewLog.attempt_id == attempt.id))
        if raced and raced.rating == payload.rating:
            return receipt(raced)
        raise HTTPException(409, "另一窗口已更新本题，请刷新")
    log = ReviewLog(
        user_id=user.id,
        card_id=card.id,
        attempt_id=attempt.id,
        rating=payload.rating,
        before_state=before,
        after_state=after.to_dict(),
        fsrs_log=fsrs_log.to_dict(),
        scheduler_config={
            "fsrs_version": "6.3.2",
            "skill_version": SKILL_VERSION,
            "scheduler": scheduler.to_dict(),
            "preferences": preferences.model_dump(),
        },
        algorithm_due_at=after.due,
        due_at=due_at,
        reviewed_at=now,
    )
    session.add(log)
    session.commit()
    return receipt(log)


@router.patch("/review-reminders/{reminder_id}/dismiss", status_code=204)
def dismiss_reminder(reminder_id: str, session: SessionDependency, user: CurrentUser):
    reminder = session.scalar(
        select(ReviewReminder).where(
            ReviewReminder.id == reminder_id, ReviewReminder.user_id == user.id
        )
    )
    if reminder is None:
        raise HTTPException(404, "找不到这条提醒")
    reminder.dismissed_at = reminder.dismissed_at or utc_now()
    session.commit()
    return Response(status_code=204)
