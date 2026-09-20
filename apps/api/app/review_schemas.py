from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator

ReviewRating = Literal["again", "hard", "good", "easy"]


class ReviewPreferencesInput(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    timezone: str = Field(default="Asia/Shanghai", max_length=80)
    study_days: list[Annotated[int, Field(ge=0, le=6)]] = Field(
        default_factory=lambda: list(range(7)), min_length=1, max_length=7
    )
    reminder_time: str = Field(default="19:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    reminder_enabled: bool = False
    schedule_mode: Literal["adaptive", "fixed"] = "adaptive"
    fixed_interval_days: int = Field(default=3, ge=1, le=60)
    desired_retention: float = Field(default=0.9, ge=0.8, le=0.97)

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("请选择有效的时区") from exc
        return value

    @field_validator("study_days")
    @classmethod
    def unique_days(cls, value: list[int]) -> list[int]:
        if len(value) != len(set(value)):
            raise ValueError("学习日不能重复")
        return sorted(value)


class ReviewAttemptInput(BaseModel):
    request_id: UUID
    card_revision: int = Field(ge=0)
    response: str = Field(min_length=1, max_length=2000)

    @field_validator("response")
    @classmethod
    def nonblank_response(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("请先尝试作答；想不起来可以输入‘不会’")
        return value.strip()


class ReviewRatingInput(BaseModel):
    rating: ReviewRating


class ReviewAttemptOutput(BaseModel):
    id: str
    card_id: str
    response: str
    prompt: str
    reference_answer: str
    explanation: str
    feedback: str
    rule_matched: bool | None
    created_at: datetime


class ReviewCardOutput(BaseModel):
    id: str
    error_cluster_id: str
    title: str
    prompt: str
    revision: int
    due_at: datetime
    pending_attempt: ReviewAttemptOutput | None = None


class ReviewReceipt(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    card_id: str
    attempt_id: str
    rating: ReviewRating
    due_at: datetime
    algorithm_due_at: datetime
    reviewed_at: datetime


class ReviewReminderOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    due_count: int
    scheduled_at: datetime


class ReviewDashboard(BaseModel):
    preferences: ReviewPreferencesInput
    due_count: int
    active_count: int
    reviewed_today: int
    cards: list[ReviewCardOutput]
    upcoming: list[ReviewCardOutput]
    history: list[ReviewReceipt]
    reminder: ReviewReminderOutput | None
