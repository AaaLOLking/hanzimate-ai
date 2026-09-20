"""Evidence-first reviews. FSRS state, user preferences and delivery are separate."""

import asyncio
import logging
import re
from datetime import UTC, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from fsrs import Card, Rating, Scheduler
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    ErrorCluster,
    ReviewAttempt,
    ReviewCard,
    ReviewPreference,
    ReviewReminder,
    User,
    new_id,
    utc_now,
)
from app.review_schemas import ReviewAttemptOutput, ReviewPreferencesInput

LOGGER = logging.getLogger(__name__)
RATINGS = {"again": Rating.Again, "hard": Rating.Hard, "good": Rating.Good, "easy": Rating.Easy}
SKILL_VERSION = "0.3.0"


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def preferences_for(session: Session, user_id: str) -> ReviewPreferencesInput:
    stored = session.get(ReviewPreference, user_id)
    return ReviewPreferencesInput.model_validate(stored) if stored else ReviewPreferencesInput()


def active_cards(user_id: str):
    return (
        select(ReviewCard)
        .join(ErrorCluster)
        .where(
            ReviewCard.user_id == user_id,
            ReviewCard.status == "active",
            ErrorCluster.user_id == user_id,
            ErrorCluster.status == "active",
        )
    )


def ensure_review_card(session: Session, cluster: ErrorCluster) -> ReviewCard:
    card = session.scalar(select(ReviewCard).where(ReviewCard.error_cluster_id == cluster.id))
    if card is not None:
        if card.status == "suspended" and cluster.status == "active":
            card.status = "active"
            card.due_at = utc_now()
            # Any answer revealed before suspension cannot be rated after resumption.
            card.revision += 1
        return card
    now = utc_now()
    card_id = new_id()
    state = Card(card_id=UUID(card_id).int % (2**53), due=now)
    card = ReviewCard(
        id=card_id,
        user_id=cluster.user_id,
        error_cluster_id=cluster.id,
        fsrs_state=state.to_dict(),
        due_at=now,
        algorithm_due_at=now,
    )
    try:
        with session.begin_nested():
            session.add(card)
            session.flush()
    except IntegrityError:
        card = session.scalar(select(ReviewCard).where(ReviewCard.error_cluster_id == cluster.id))
        if card is None:
            raise
    return card


def backfill_review_cards(session: Session) -> None:
    """Upgrade already-confirmed memories without changing their evidence or decisions."""
    missing = select(ErrorCluster).where(
        ErrorCluster.status == "active",
        ~select(ReviewCard.id).where(ReviewCard.error_cluster_id == ErrorCluster.id).exists(),
    )
    for cluster in session.scalars(missing):
        ensure_review_card(session, cluster)
    session.commit()


def exercise_for(card: ReviewCard) -> dict:
    cluster = card.cluster
    variant = card.revision % 3
    key = cluster.canonical_key
    if key == "lexical:measure-word:水:瓶":
        counts = ["两", "三", "四"]
        count = counts[variant]
        return {
            "title": "买水时选对量词",
            "prompt": f"在校园商店为同学买{count}份独立瓶装饮用水。请用一句中文向店员提出请求。",
            "reference_answer": f"你好，请给我{count}瓶水。",
            "explanation": "装在瓶子里的水，可以按‘瓶’来数。数量和物品也要说清楚。",
            "pattern": f"{count}瓶(?:矿泉)?水",
            "forbidden": [f"{count}个水"],
            "skill_version": SKILL_VERSION,
        }
    if key == "lexical:measure-word:朋友:个":
        count = ["两", "四", "五"][variant]
        place = ["摄影社", "图书馆", "运动会"][variant]
        return {
            "title": "介绍新认识的朋友",
            "prompt": f"你在{place}认识了{count}位新朋友。用日常中文介绍人数和朋友关系。",
            "reference_answer": f"我在{place}认识了{count}个朋友。",
            "explanation": "日常表达可以说‘几个朋友’，不在量词后再加‘人’；‘位’也可用于礼貌表达。",
            "pattern": f"{count}(?:个|位)(?:新)?朋友",
            "forbidden": ["个人朋友"],
            "skill_version": SKILL_VERSION,
        }
    if key == "grammar:ba-construction:result-complement":
        obj, verb = [("作业", "写"), ("邮件", "看"), ("报告", "读")][variant]
        return {
            "title": "把完成的结果说清楚",
            "prompt": f"同学问你的{obj}处理好了没有。请用把字句说明你已经{verb}完。",
            "reference_answer": f"我把{obj}{verb}完了。",
            "explanation": "结果‘完’紧跟动词，‘了’放在结果后面。",
            "pattern": f"把{obj}(?:已经)?{verb}完了",
            "forbidden": [f"{verb}了完"],
            "skill_version": SKILL_VERSION,
        }
    return {
        "title": "换个场景，重新表达",
        "prompt": (
            f"本次回顾：{cluster.subtype}。请在"
            f"{['校园办事', '社团活动', '与同学聊天'][variant]}场景里重新写一句话，"
            "尝试避开过去确认的问题。提交后可查看原来的示例并自评。"
        ),
        "reference_answer": cluster.corrected_example,
        "explanation": cluster.explanation,
        "pattern": None,
        "forbidden": [],
        "skill_version": SKILL_VERSION,
    }


def review_feedback(exercise: dict, response: str) -> tuple[bool | None, str]:
    pattern = exercise["pattern"]
    if pattern is None:
        return None, "此类表达暂不自动判分。请对照原示例检查目标规则，再如实选择记忆情况。"
    normalized = re.sub(r"\s+", "", response)
    matched = bool(re.search(pattern, normalized)) and not any(
        forbidden in normalized for forbidden in exercise["forbidden"]
    )
    return matched, (
        "已匹配本题目标句式。这里只检查目标结构，不代表整句话或中文能力已完全掌握。"
        if matched
        else "暂未匹配本题已验证的句式。请对照示例检查；其他正确说法也可能未被规则识别。"
    )


def attempt_output(attempt: ReviewAttempt) -> ReviewAttemptOutput:
    return ReviewAttemptOutput(
        id=attempt.id,
        card_id=attempt.card_id,
        response=attempt.response,
        prompt=attempt.exercise["prompt"],
        reference_answer=attempt.exercise["reference_answer"],
        explanation=attempt.exercise["explanation"],
        feedback=attempt.feedback,
        rule_matched=attempt.rule_matched,
        created_at=as_utc(attempt.created_at),
    )


def scheduler_for(preferences: ReviewPreferencesInput) -> Scheduler:
    # Day-scale production tasks, not minute-scale flashcards. Keep deterministic replay.
    return Scheduler(
        desired_retention=preferences.desired_retention,
        learning_steps=(),
        relearning_steps=(),
        maximum_interval=365,
        enable_fuzzing=False,
    )


def planned_due(
    algorithm_due: datetime, now: datetime, rating: str, preferences: ReviewPreferencesInput
) -> datetime:
    due = as_utc(algorithm_due)
    if preferences.schedule_mode == "fixed":
        days = 1 if rating == "again" else preferences.fixed_interval_days
        due = as_utc(now) + timedelta(days=days)
    # Never schedule earlier than the raw due instant. Availability is a separate layer.
    local = due.astimezone(ZoneInfo(preferences.timezone))
    for _ in range(7):
        if local.weekday() in preferences.study_days:
            return local.astimezone(UTC)
        local += timedelta(days=1)
    raise ValueError("At least one study day is required")


def reminder_is_visible(preferences: ReviewPreferencesInput, now: datetime) -> bool:
    local = as_utc(now).astimezone(ZoneInfo(preferences.timezone))
    return (
        preferences.reminder_enabled
        and local.weekday() in preferences.study_days
        and local.strftime("%H:%M") >= preferences.reminder_time
    )


def enqueue_due_reminders(session: Session, now: datetime | None = None) -> int:
    now = as_utc(now or utc_now())
    created = 0
    stored_preferences = session.scalars(
        select(ReviewPreference)
        .join(User)
        .where(ReviewPreference.reminder_enabled.is_(True), User.deleted_at.is_(None))
    )
    for stored in stored_preferences:
        preferences = ReviewPreferencesInput.model_validate(stored)
        if not reminder_is_visible(preferences, now):
            continue
        local = now.astimezone(ZoneInfo(preferences.timezone))
        existing = session.scalar(
            select(ReviewReminder.id).where(
                ReviewReminder.user_id == stored.user_id,
                ReviewReminder.local_date == local.date(),
            )
        )
        if existing:
            continue
        due_count = (
            session.scalar(
                select(func.count()).select_from(
                    active_cards(stored.user_id).where(ReviewCard.due_at <= now).subquery()
                )
            )
            or 0
        )
        if not due_count:
            continue
        scheduled = datetime.combine(
            local.date(),
            time.fromisoformat(preferences.reminder_time),
            ZoneInfo(preferences.timezone),
        ).astimezone(UTC)
        try:
            with session.begin_nested():
                session.add(
                    ReviewReminder(
                        user_id=stored.user_id,
                        local_date=local.date(),
                        due_count=due_count,
                        scheduled_at=scheduled,
                        created_at=now,
                    )
                )
                session.flush()
            created += 1
        except IntegrityError:
            # Multiple API workers may tick together; the daily unique key wins.
            continue
    session.commit()
    return created


async def reminder_worker(database) -> None:
    def tick() -> None:
        with database.session_factory() as session:
            enqueue_due_reminders(session)

    while True:
        try:
            await asyncio.to_thread(tick)
        except Exception:
            LOGGER.exception("Review reminder tick failed; retrying on next tick")
        await asyncio.sleep(60)
