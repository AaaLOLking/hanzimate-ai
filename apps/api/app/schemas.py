from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

HskBand = Literal["not_sure", "HSK1", "HSK2", "HSK3", "HSK4", "HSK5", "HSK6"]
Priority = Literal["daily_life", "campus", "hsk_exam", "internship", "social"]


class ConsentInput(BaseModel):
    policy_version: str = Field(default="2026-08", min_length=1, max_length=32)
    privacy_acknowledged: Literal[True]
    learning_memory: bool = True
    audio_retention: bool = False


class MissionInput(BaseModel):
    why: str = Field(min_length=3, max_length=500)
    success_looks_like: list[Annotated[str, Field(min_length=2, max_length=160)]] = Field(
        min_length=1, max_length=5
    )
    constraints: list[Annotated[str, Field(min_length=2, max_length=160)]] = Field(
        default_factory=list, max_length=5
    )
    out_of_scope: list[Annotated[str, Field(min_length=2, max_length=160)]] = Field(
        default_factory=list, max_length=5
    )
    priorities: list[Priority] = Field(min_length=1, max_length=3)
    weekly_minutes: int = Field(ge=30, le=1200)
    deadline: date | None = None

    @field_validator("priorities")
    @classmethod
    def priorities_are_unique(cls, values: list[Priority]) -> list[Priority]:
        if len(values) != len(set(values)):
            raise ValueError("priorities must be unique")
        return values


class ProfileInput(BaseModel):
    native_language: str = Field(min_length=2, max_length=80)
    support_language: str = Field(min_length=2, max_length=80)
    current_hsk_band: HskBand
    self_assessment: dict[Literal["listening", "speaking", "reading", "writing"], int]
    correction_mode: Literal["instant", "turn_end", "session_end"] = "turn_end"
    speech_speed: Literal["slow", "normal"] = "normal"
    show_pinyin: bool = True
    english_first: bool = False
    review_interval_days: int = Field(default=3, ge=1, le=30)

    @field_validator("self_assessment")
    @classmethod
    def assessment_is_complete_and_bounded(cls, values: dict[str, int]) -> dict[str, int]:
        required = {"listening", "speaking", "reading", "writing"}
        if set(values) != required:
            raise ValueError(
                "self_assessment must contain listening, speaking, reading and writing"
            )
        if any(score < 1 or score > 5 for score in values.values()):
            raise ValueError("self-assessment scores must be between 1 and 5")
        return values


class OnboardingInput(BaseModel):
    display_name: str = Field(min_length=1, max_length=120)
    locale: str = Field(default="zh-CN", min_length=2, max_length=20)
    consent: ConsentInput
    mission: MissionInput
    profile: ProfileInput


class UserOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    display_name: str
    locale: str


class ConsentOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    policy_version: str
    privacy_acknowledged: bool
    learning_memory: bool
    audio_retention: bool
    granted_at: datetime


class MissionOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    why: str
    success_looks_like: list[str]
    constraints: list[str]
    out_of_scope: list[str]
    priorities: list[str]
    weekly_minutes: int
    deadline: date | None


class ProfileOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    native_language: str
    support_language: str
    estimated_hsk_band: str
    skill_estimates: dict[str, int]
    preferences: dict[str, Any]
    projection_version: int
    updated_at: datetime


class WorkspaceCreate(BaseModel):
    kind: Literal["conversation", "lesson", "review"]
    title: str = Field(min_length=1, max_length=160)
    state: dict[str, Any] = Field(default_factory=dict)


class WorkspaceUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    status: Literal["active", "processing", "review_due", "completed", "archived"] | None = None
    state: dict[str, Any] | None = None


class WorkspaceOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    kind: str
    title: str
    status: str
    state: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    last_opened_at: datetime


class OnboardingOutput(BaseModel):
    complete: bool
    user: UserOutput
    consent: ConsentOutput | None = None
    mission: MissionOutput | None = None
    profile: ProfileOutput | None = None
    recommended_workspace: WorkspaceOutput | None = None


class ModelOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    provider: str
    model: str
    display_name: str
    capabilities: list[str]
    enabled: bool


class ModelRunOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    task: str
    provider: str
    model: str
    status: str
    latency_ms: int | None
    input_tokens: int
    output_tokens: int
    estimated_cost_yuan: float
    error_code: str | None
    fallback_from: str | None
    created_at: datetime


class ModelUsageOutput(BaseModel):
    date: date
    total_calls: int
    external_calls: int
    failed_calls: int
    blocked_calls: int
    estimated_cost_yuan: float
    daily_external_call_limit: int
    remaining_external_calls: int
    pricing_configured: bool
    recent_runs: list[ModelRunOutput] = Field(default_factory=list)


class AccountStatsOutput(BaseModel):
    workspaces: int
    conversations: int
    lessons_started: int
    lessons_completed: int
    active_memories: int
    review_attempts: int


class AccountOverviewOutput(BaseModel):
    user: UserOutput
    consent: ConsentOutput | None = None
    mission: MissionOutput | None = None
    profile: ProfileOutput | None = None
    stats: AccountStatsOutput
    model_usage: ModelUsageOutput


class AccountDeleteInput(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    confirmation: Literal["删除我的账户"]


class AccountDeleteOutput(BaseModel):
    receipt_id: str
    deleted_at: datetime
    deleted_records: dict[str, int]


class BetaFeedbackInput(BaseModel):
    area: Literal["conversation", "course", "review", "overall"]
    issue_type: Literal[
        "praise",
        "wrong_correction",
        "confusing",
        "slow",
        "bug",
        "idea",
        "other",
    ]
    rating: int = Field(ge=1, le=5)
    is_blocking: bool = False
    message: str = Field(min_length=3, max_length=1200)
    page_path: str | None = Field(default=None, max_length=240)

    @field_validator("page_path")
    @classmethod
    def page_path_is_safe(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value.startswith("/") or "://" in value or "?" in value or "#" in value:
            raise ValueError("page_path must be a relative path without query or fragment")
        return value


class BetaFeedbackOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    area: str
    issue_type: str
    rating: int
    is_blocking: bool
    message: str
    page_path: str | None
    created_at: datetime


class BetaMilestoneOutput(BaseModel):
    current: int
    target: int
    complete: bool


class BetaDashboardOutput(BaseModel):
    progress: dict[str, BetaMilestoneOutput]
    ready_for_exit: bool
    feedback: list[BetaFeedbackOutput] = Field(default_factory=list)


class UtteranceInput(BaseModel):
    client_event_id: str = Field(min_length=1, max_length=80)
    sequence_no: int = Field(ge=1)
    connection_epoch: int = Field(default=0, ge=0)
    provider_item_id: str | None = Field(default=None, min_length=1, max_length=120)
    provider_response_id: str | None = Field(default=None, min_length=1, max_length=120)
    content_index: int = Field(default=0, ge=0)
    speaker: Literal["user", "assistant"]
    transcript: str = Field(min_length=1, max_length=4000)
    source: Literal["provider", "browser_speech", "browser_text", "mock"]
    is_final: bool = True
    transcript_status: Literal["partial", "final", "incomplete"] = "final"
    playback_status: Literal["not_applicable", "unknown", "completed", "interrupted"] = (
        "not_applicable"
    )
    started_ms: int | None = Field(default=None, ge=0)
    ended_ms: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def statuses_are_consistent(self):
        if self.transcript_status == "partial":
            raise ValueError("partial transcripts are not persisted")
        if self.is_final != (self.transcript_status == "final"):
            raise ValueError("is_final must match transcript_status")
        if self.speaker == "user" and self.playback_status != "not_applicable":
            raise ValueError("user utterances do not have playback status")
        if self.speaker == "assistant" and self.playback_status == "not_applicable":
            self.playback_status = "unknown"
        if self.ended_ms is not None and self.started_ms is not None:
            if self.ended_ms < self.started_ms:
                raise ValueError("ended_ms must not be before started_ms")
        return self


class UtteranceOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    client_event_id: str
    sequence_no: int
    connection_epoch: int
    provider_item_id: str | None
    provider_response_id: str | None
    content_index: int
    speaker: str
    transcript: str
    source: str
    is_final: bool
    transcript_status: str
    playback_status: str
    started_ms: int | None
    ended_ms: int | None
    created_at: datetime


class VoiceSessionCreate(BaseModel):
    continuous: bool = False
    practice_mode: Literal["scenario", "free", "custom"] = "scenario"
    custom_objective: str | None = Field(default=None, max_length=500)
    client_session_id: str | None = Field(default=None, min_length=1, max_length=80)
    protocol_version: Literal["legacy", "live-v1"] = "legacy"
    workspace_id: str | None = None
    scenario_id: str | None = Field(default=None, min_length=1, max_length=80)
    scenario: str = Field(default="校园问路", min_length=1, max_length=160)
    correction_mode: Literal["immersion", "coach", "exam"] = "coach"
    speech_speed: Literal["slow", "normal"] = "normal"
    patience: Literal["normal", "patient"] = "patient"

    @model_validator(mode="after")
    def live_sessions_have_idempotency_key(self):
        if self.custom_objective is not None:
            self.custom_objective = self.custom_objective.strip()
        if self.practice_mode == "custom" and not self.custom_objective:
            raise ValueError("Custom practice requires a learning objective")
        if self.practice_mode != "custom" and self.custom_objective:
            raise ValueError("custom_objective is only allowed for custom practice")
        if self.practice_mode != "scenario" and self.scenario_id:
            raise ValueError("scenario_id is only allowed for scenario practice")
        if self.protocol_version == "live-v1" and not self.client_session_id:
            raise ValueError("live-v1 requires client_session_id")
        return self


class VoiceSessionStatusInput(BaseModel):
    status: Literal["connecting", "reconnecting", "active", "ending", "completed", "failed"]
    failure_reason: str | None = Field(default=None, max_length=500)
    connection_epoch: int | None = Field(default=None, ge=0)
    end_reason: (
        Literal[
            "user_ended",
            "cancelled_start",
            "practice_limit",
            "connection_failed",
            "client_abandoned",
            "save_incomplete",
        ]
        | None
    ) = None
    closing_manifest: dict[str, Any] | None = None


class ExpectedUtterance(BaseModel):
    client_event_id: str = Field(min_length=1, max_length=80)
    transcript_status: Literal["final", "incomplete"]
    playback_status: Literal["not_applicable", "unknown", "completed", "interrupted"]


class VoiceSessionFinalizeInput(BaseModel):
    duration_seconds: int | None = Field(default=None, ge=0, le=2147483647)
    allow_incomplete: bool = False
    expected_utterances: list[ExpectedUtterance] = Field(default_factory=list, max_length=10000)
    missing_client_event_ids: list[str] = Field(default_factory=list, max_length=10000)


class VoiceSessionPreferencesInput(BaseModel):
    expected_config_revision: int = Field(ge=1)
    speech_speed: Literal["slow", "normal"] | None = None
    patience: Literal["normal", "patient"] | None = None

    @model_validator(mode="after")
    def includes_a_change(self):
        if self.speech_speed is None and self.patience is None:
            raise ValueError("at least one preference must be provided")
        return self


class VoiceSessionPreferencesOutput(BaseModel):
    config_revision: int
    applied_config_revision: int | None
    requested_config: dict[str, Any]
    session_update: dict[str, Any]


class UtterancePlaybackInput(BaseModel):
    connection_epoch: int = Field(ge=0)
    playback_status: Literal["completed", "interrupted"]


class VoiceSessionOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    client_session_id: str | None
    status: str
    protocol_version: str
    correction_mode: str
    speech_speed: str
    patience: str
    provider: str
    model: str
    voice: str
    connection_mode: str
    skill_version: str
    context_pack: dict[str, Any]
    requested_config: dict[str, Any]
    config_revision: int
    applied_config_revision: int | None
    connection_epoch: int
    transport_status: str
    deadline_at: datetime | None
    max_duration_seconds: int
    duration_seconds: int
    reconnect_count: int
    interruption_count: int
    first_response_latency_ms: int | None
    last_event_at: datetime | None
    failure_reason: str | None
    created_at: datetime
    started_at: datetime | None
    ending_at: datetime | None
    ended_at: datetime | None
    end_reason: str | None
    closing_manifest: dict[str, Any] | None
    utterances: list[UtteranceOutput] = Field(default_factory=list)


class RealtimeConnectionOutput(BaseModel):
    mode: Literal["webrtc", "mock"]
    provider: str
    model: str
    voice: str
    max_duration_seconds: int
    fallback_reason: str | None = None
    session_update: dict[str, Any]
    capabilities: dict[str, Literal["verified", "unsupported", "unverified"]] = Field(
        default_factory=dict
    )


class VoiceSessionCreateOutput(BaseModel):
    session: VoiceSessionOutput
    connection: RealtimeConnectionOutput


class SdpOfferInput(BaseModel):
    sdp: str = Field(min_length=20, max_length=100_000)
    connection_epoch: int | None = Field(default=None, ge=1)


class SdpAnswerOutput(BaseModel):
    sdp: str
    connection_epoch: int = 0


SessionEventType = Literal[
    "connection_attempt",
    "connection_established",
    "connection_lost",
    "reconnect_attempt",
    "segment_continued",
    "reconnect_succeeded",
    "reconnect_failed",
    "interruption",
    "provider_first_response",
    "budget_warning",
    "fallback_activated",
    "provider_error",
    "config_applied",
    "user_speech_started",
    "user_speech_stopped",
    "output_started",
    "output_stopped",
    "transcript_save_failed",
    "session_heartbeat",
    "session_timeout",
    "save_incomplete",
]


class SessionEventInput(BaseModel):
    client_event_id: str = Field(min_length=1, max_length=80)
    event_type: SessionEventType
    elapsed_ms: int | None = Field(default=None, ge=0, le=3_600_000)
    event_payload: dict[str, Any] = Field(default_factory=dict)


class SessionEventOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    client_event_id: str
    event_type: str
    elapsed_ms: int | None
    event_payload: dict[str, Any]
    created_at: datetime


class ConversationScenarioOutput(BaseModel):
    id: str
    title: str
    category: str
    level: str
    objective: str
    opening_line: str
    prompt_starters: list[str]
    safety_note: str | None


class GeneratedTaskResult(BaseModel):
    status: Literal["completed", "partially-completed", "not-completed"]
    explanation: str = Field(min_length=1, max_length=500)


class GeneratedErrorEvent(BaseModel):
    source_type: Literal["conversation"] = "conversation"
    source_id: str = Field(min_length=1)
    learner_text: str = Field(min_length=1, max_length=1000)
    corrected_text: str = Field(min_length=1, max_length=1000)
    explanation: str = Field(default="", max_length=1000)
    error_type: Literal[
        "pronunciation",
        "lexical",
        "grammar",
        "character-writing",
        "listening",
        "pragmatics",
    ]
    subtype: str = Field(min_length=1, max_length=80)
    severity: Literal["blocking", "major", "minor", "optional"]
    confidence: float = Field(ge=0.5, le=1)
    status: Literal["candidate"] = "candidate"
    evidence_span: str = Field(min_length=1, max_length=1000)
    canonical_key: str = Field(min_length=1, max_length=160)
    hsk_tags: list[str] = Field(default_factory=list, max_length=10)
    observed_at: datetime
    model_version: str = Field(min_length=1, max_length=120)
    skill_version: str = Field(min_length=1, max_length=32)


class GeneratedSessionSummary(BaseModel):
    session_id: str = Field(min_length=1)
    task_result: GeneratedTaskResult
    highlights: list[Annotated[str, Field(min_length=1, max_length=300)]] = Field(
        default_factory=list, max_length=3
    )
    candidate_errors: list[GeneratedErrorEvent] = Field(default_factory=list, max_length=3)
    next_step: str = Field(min_length=1, max_length=500)
    model_version: str = Field(min_length=1, max_length=120)
    skill_version: str = Field(min_length=1, max_length=32)


class ErrorEventOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    cluster_id: str | None
    learner_text: str
    corrected_text: str
    explanation: str
    error_type: str
    subtype: str
    severity: str
    confidence: float
    status: str
    evidence_span: str
    canonical_key: str
    hsk_tags: list[str]
    model_version: str
    skill_version: str
    observed_at: datetime
    created_at: datetime


class SessionSummaryOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    task_status: str
    task_explanation: str
    highlights: list[str]
    next_step: str
    provider: str
    model: str
    skill_version: str
    generated_at: datetime
    candidate_errors: list[ErrorEventOutput] = Field(default_factory=list)


class ErrorDecisionInput(BaseModel):
    status: Literal["confirmed", "rejected"]
    corrected_text: str | None = Field(default=None, min_length=1, max_length=1000)


class ErrorClusterUpdateInput(BaseModel):
    explanation: str = Field(min_length=2, max_length=1000)
    corrected_example: str = Field(min_length=1, max_length=1000)


class ErrorClusterOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    canonical_key: str
    error_type: str
    subtype: str
    explanation: str
    corrected_example: str
    status: str
    occurrence_count: int
    first_seen_at: datetime
    last_seen_at: datetime
    updated_at: datetime
    next_review_at: datetime | None


class LessonProgressOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    status: str
    current_step: int
    attempt_count: int
    best_score: float
    started_at: datetime
    completed_at: datetime | None
    updated_at: datetime


class CourseLessonOutput(BaseModel):
    id: str
    slug: str
    position: int
    title: str
    track: Literal["daily-life", "hsk"]
    level: str
    objective: str
    estimated_minutes: int
    targets: list[str]
    progress: LessonProgressOutput | None = None


class CourseOutput(BaseModel):
    id: str
    slug: str
    version: int
    title: str
    description: str
    framework: str
    level: str
    lessons: list[CourseLessonOutput]


class LessonMessageOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    role: str
    content: str
    provider: str
    model: str
    citations: list[dict[str, Any]]
    created_at: datetime


class LessonDetailOutput(BaseModel):
    id: str
    course_id: str
    course_title: str
    course_version: int
    slug: str
    version: int
    position: int
    title: str
    framework: str
    level: str
    objective: str
    estimated_minutes: int
    targets: list[str]
    sources: list[dict[str, Any]]
    content: dict[str, Any]
    context_pack: dict[str, Any]
    skill_version: str
    progress: LessonProgressOutput | None = None
    messages: list[LessonMessageOutput] = Field(default_factory=list)


class LessonQuestionInput(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


class LessonQuestionOutput(BaseModel):
    user_message: LessonMessageOutput
    assistant_message: LessonMessageOutput


class LessonAttemptInput(BaseModel):
    activity: Literal["guided", "retrieval", "transfer"]
    response: str = Field(min_length=1, max_length=2000)


class LearningEvidenceOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    evidence_type: str
    response: str
    passed: bool
    score: float
    feedback: str
    skill_version: str
    observed_at: datetime


class LessonAttemptOutput(BaseModel):
    passed: bool
    score: float
    feedback: str
    missing_targets: list[str]
    next_activity: Literal["guided", "retrieval", "transfer", "completed"]
    progress: LessonProgressOutput
    evidence: LearningEvidenceOutput
