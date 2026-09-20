from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return str(uuid4())


class WorkspaceKind(StrEnum):
    CONVERSATION = "conversation"
    LESSON = "lesson"
    REVIEW = "review"


class WorkspaceStatus(StrEnum):
    ACTIVE = "active"
    PROCESSING = "processing"
    REVIEW_DUE = "review_due"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class VoiceSessionStatus(StrEnum):
    CREATED = "created"
    CONNECTING = "connecting"
    RECONNECTING = "reconnecting"
    ACTIVE = "active"
    ENDING = "ending"
    COMPLETED = "completed"
    FAILED = "failed"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120), default="Learner")
    locale: Mapped[str] = mapped_column(String(20), default="zh-CN")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    consents: Mapped[list["Consent"]] = relationship(back_populates="user")
    missions: Mapped[list["LearnerMission"]] = relationship(back_populates="user")
    profile: Mapped["LearnerProfile | None"] = relationship(back_populates="user")
    workspaces: Mapped[list["Workspace"]] = relationship(back_populates="user")
    voice_sessions: Mapped[list["VoiceSession"]] = relationship(back_populates="user")
    session_summaries: Mapped[list["SessionSummary"]] = relationship(back_populates="user")
    error_events: Mapped[list["ErrorEvent"]] = relationship(back_populates="user")
    error_clusters: Mapped[list["ErrorCluster"]] = relationship(back_populates="user")
    lesson_progress: Mapped[list["LessonProgress"]] = relationship(back_populates="user")
    learning_evidence: Mapped[list["LearningEvidence"]] = relationship(back_populates="user")
    lesson_messages: Mapped[list["LessonMessage"]] = relationship(back_populates="user")
    model_runs: Mapped[list["ModelRun"]] = relationship(back_populates="user")
    beta_feedback: Mapped[list["BetaFeedback"]] = relationship(back_populates="user")


class Consent(Base):
    __tablename__ = "consents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    policy_version: Mapped[str] = mapped_column(String(32))
    privacy_acknowledged: Mapped[bool] = mapped_column(Boolean)
    learning_memory: Mapped[bool] = mapped_column(Boolean, default=True)
    audio_retention: Mapped[bool] = mapped_column(Boolean, default=False)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    user: Mapped[User] = relationship(back_populates="consents")


class LearnerMission(Base):
    __tablename__ = "learner_missions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    why: Mapped[str] = mapped_column(Text)
    success_looks_like: Mapped[list[str]] = mapped_column(JSON)
    constraints: Mapped[list[str]] = mapped_column(JSON, default=list)
    out_of_scope: Mapped[list[str]] = mapped_column(JSON, default=list)
    priorities: Mapped[list[str]] = mapped_column(JSON, default=list)
    weekly_minutes: Mapped[int] = mapped_column(Integer)
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    user: Mapped[User] = relationship(back_populates="missions")


class LearnerProfile(Base):
    __tablename__ = "learner_profiles"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    native_language: Mapped[str] = mapped_column(String(80))
    support_language: Mapped[str] = mapped_column(String(80))
    estimated_hsk_band: Mapped[str] = mapped_column(String(24))
    skill_estimates: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    preferences: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    projection_version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    user: Mapped[User] = relationship(back_populates="profile")


class Workspace(Base):
    __tablename__ = "workspaces"
    __table_args__ = (Index("ix_workspaces_user_last_opened", "user_id", "last_opened_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(24))
    title: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(24), default=WorkspaceStatus.ACTIVE)
    state: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    last_opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    user: Mapped[User] = relationship(back_populates="workspaces")
    voice_sessions: Mapped[list["VoiceSession"]] = relationship(back_populates="workspace")
    lesson_progress: Mapped["LessonProgress | None"] = relationship(
        back_populates="workspace", uselist=False
    )


class VoiceSession(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "client_session_id", name="uq_sessions_user_client_session"
        ),
        Index("ix_sessions_user_started", "user_id", "started_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    client_session_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    kind: Mapped[str] = mapped_column(String(24), default="voice")
    status: Mapped[str] = mapped_column(String(24), default=VoiceSessionStatus.CREATED)
    protocol_version: Mapped[str] = mapped_column(
        String(24), default="legacy", server_default="legacy"
    )
    correction_mode: Mapped[str] = mapped_column(String(24), default="coach")
    speech_speed: Mapped[str] = mapped_column(String(16), default="normal")
    patience: Mapped[str] = mapped_column(String(16), default="patient", server_default="patient")
    provider: Mapped[str] = mapped_column(String(80))
    model: Mapped[str] = mapped_column(String(120))
    voice: Mapped[str] = mapped_column(String(80))
    connection_mode: Mapped[str] = mapped_column(String(24))
    skill_version: Mapped[str] = mapped_column(String(32), default="0.1.0")
    context_pack: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    requested_config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    config_revision: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    applied_config_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    connection_epoch: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    transport_status: Mapped[str] = mapped_column(
        String(24), default="idle", server_default="idle"
    )
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    max_duration_seconds: Mapped[int] = mapped_column(Integer, default=480)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    reconnect_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    interruption_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    first_response_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ending_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    closing_manifest: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    workspace: Mapped[Workspace] = relationship(back_populates="voice_sessions")
    user: Mapped[User] = relationship(back_populates="voice_sessions")
    utterances: Mapped[list["Utterance"]] = relationship(
        back_populates="voice_session", order_by="Utterance.sequence_no"
    )
    events: Mapped[list["SessionEvent"]] = relationship(
        back_populates="voice_session", order_by="SessionEvent.created_at"
    )
    summary: Mapped["SessionSummary | None"] = relationship(
        back_populates="voice_session", uselist=False
    )
    error_events: Mapped[list["ErrorEvent"]] = relationship(back_populates="voice_session")


class Utterance(Base):
    __tablename__ = "utterances"
    __table_args__ = (
        UniqueConstraint("session_id", "client_event_id", name="uq_utterance_client_event"),
        UniqueConstraint("session_id", "sequence_no", name="uq_utterance_sequence"),
        UniqueConstraint(
            "session_id",
            "connection_epoch",
            "provider_item_id",
            "content_index",
            "speaker",
            name="uq_utterance_provider_item",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    client_event_id: Mapped[str] = mapped_column(String(80))
    sequence_no: Mapped[int] = mapped_column(Integer)
    connection_epoch: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    provider_item_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    provider_response_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    content_index: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    speaker: Mapped[str] = mapped_column(String(16))
    transcript: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(32))
    is_final: Mapped[bool] = mapped_column(Boolean, default=True)
    transcript_status: Mapped[str] = mapped_column(
        String(16), default="final", server_default="final"
    )
    playback_status: Mapped[str] = mapped_column(
        String(24), default="not_applicable", server_default="not_applicable"
    )
    started_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ended_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    voice_session: Mapped[VoiceSession] = relationship(back_populates="utterances")


class SessionEvent(Base):
    __tablename__ = "session_events"
    __table_args__ = (
        UniqueConstraint("session_id", "client_event_id", name="uq_session_event_client_event"),
        Index("ix_session_events_session_created", "session_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    client_event_id: Mapped[str] = mapped_column(String(80))
    event_type: Mapped[str] = mapped_column(String(40))
    elapsed_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    event_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    voice_session: Mapped[VoiceSession] = relationship(back_populates="events")


class SessionSummary(Base):
    __tablename__ = "session_summaries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.id"), unique=True, index=True
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    task_status: Mapped[str] = mapped_column(String(32))
    task_explanation: Mapped[str] = mapped_column(Text)
    highlights: Mapped[list[str]] = mapped_column(JSON, default=list)
    next_step: Mapped[str] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(String(80))
    model: Mapped[str] = mapped_column(String(120))
    skill_version: Mapped[str] = mapped_column(String(32), default="0.1.0")
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    voice_session: Mapped[VoiceSession] = relationship(back_populates="summary")
    user: Mapped[User] = relationship(back_populates="session_summaries")
    candidate_errors: Mapped[list["ErrorEvent"]] = relationship(
        back_populates="summary", order_by="ErrorEvent.created_at"
    )


class ErrorCluster(Base):
    __tablename__ = "error_clusters"
    __table_args__ = (
        UniqueConstraint("user_id", "canonical_key", name="uq_error_cluster_user_key"),
        Index("ix_error_clusters_user_status_last", "user_id", "status", "last_seen_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    canonical_key: Mapped[str] = mapped_column(String(160))
    error_type: Mapped[str] = mapped_column(String(40))
    subtype: Mapped[str] = mapped_column(String(80))
    explanation: Mapped[str] = mapped_column(Text)
    corrected_example: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="active")
    occurrence_count: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    user: Mapped[User] = relationship(back_populates="error_clusters")
    members: Mapped[list["ErrorEvent"]] = relationship(back_populates="cluster")
    review_card: Mapped["ReviewCard | None"] = relationship(
        back_populates="cluster", uselist=False
    )

    @property
    def next_review_at(self) -> datetime | None:
        if self.status != "active" or self.review_card is None:
            return None
        if self.review_card.status != "active":
            return None
        due = self.review_card.due_at
        return due.replace(tzinfo=UTC) if due.tzinfo is None else due.astimezone(UTC)


class ErrorEvent(Base):
    __tablename__ = "error_events"
    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "canonical_key",
            "evidence_span",
            name="uq_error_event_session_evidence",
        ),
        Index("ix_error_events_user_status_observed", "user_id", "status", "observed_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    summary_id: Mapped[str] = mapped_column(ForeignKey("session_summaries.id"), index=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    cluster_id: Mapped[str | None] = mapped_column(
        ForeignKey("error_clusters.id"), nullable=True, index=True
    )
    evidence_utterance_id: Mapped[str | None] = mapped_column(
        ForeignKey("utterances.id"), nullable=True
    )
    source_type: Mapped[str] = mapped_column(String(32), default="conversation")
    source_id: Mapped[str] = mapped_column(String(36))
    learner_text: Mapped[str] = mapped_column(Text)
    corrected_text: Mapped[str] = mapped_column(Text)
    explanation: Mapped[str] = mapped_column(Text)
    error_type: Mapped[str] = mapped_column(String(40))
    subtype: Mapped[str] = mapped_column(String(80))
    severity: Mapped[str] = mapped_column(String(24))
    confidence: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(24), default="candidate")
    evidence_span: Mapped[str] = mapped_column(Text)
    canonical_key: Mapped[str] = mapped_column(String(160))
    hsk_tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    model_version: Mapped[str] = mapped_column(String(120))
    skill_version: Mapped[str] = mapped_column(String(32), default="0.1.0")
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    summary: Mapped[SessionSummary] = relationship(back_populates="candidate_errors")
    voice_session: Mapped[VoiceSession] = relationship(back_populates="error_events")
    user: Mapped[User] = relationship(back_populates="error_events")
    cluster: Mapped[ErrorCluster | None] = relationship(back_populates="members")


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(24), default="published")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    versions: Mapped[list["CourseVersion"]] = relationship(
        back_populates="course", order_by="CourseVersion.version"
    )


class CourseVersion(Base):
    __tablename__ = "course_versions"
    __table_args__ = (
        UniqueConstraint("course_id", "version", name="uq_course_version_number"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text)
    framework: Mapped[str] = mapped_column(String(40))
    level: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(24), default="published")
    source_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    course: Mapped[Course] = relationship(back_populates="versions")
    lessons: Mapped[list["LessonVersion"]] = relationship(
        back_populates="course_version", order_by="LessonVersion.position"
    )


class LessonVersion(Base):
    __tablename__ = "lesson_versions"
    __table_args__ = (
        UniqueConstraint(
            "course_version_id",
            "slug",
            "version",
            name="uq_lesson_version_slug",
        ),
        Index("ix_lesson_versions_course_position", "course_version_id", "position"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    course_version_id: Mapped[str] = mapped_column(ForeignKey("course_versions.id"), index=True)
    slug: Mapped[str] = mapped_column(String(120), index=True)
    version: Mapped[int] = mapped_column(Integer)
    position: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(160))
    framework: Mapped[str] = mapped_column(String(40))
    level: Mapped[str] = mapped_column(String(40))
    objective: Mapped[str] = mapped_column(Text)
    estimated_minutes: Mapped[int] = mapped_column(Integer)
    targets: Mapped[list[str]] = mapped_column(JSON, default=list)
    sources: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    content: Mapped[dict[str, Any]] = mapped_column(JSON)
    assessment_config: Mapped[dict[str, Any]] = mapped_column(JSON)
    content_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24), default="published")
    skill_version: Mapped[str] = mapped_column(String(32), default="0.1.0")
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    course_version: Mapped[CourseVersion] = relationship(back_populates="lessons")
    progress_records: Mapped[list["LessonProgress"]] = relationship(
        back_populates="lesson_version"
    )
    evidence: Mapped[list["LearningEvidence"]] = relationship(
        back_populates="lesson_version"
    )


class LessonProgress(Base):
    __tablename__ = "lesson_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "lesson_version_id", name="uq_lesson_progress_user_lesson"),
        Index("ix_lesson_progress_user_updated", "user_id", "updated_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    lesson_version_id: Mapped[str] = mapped_column(ForeignKey("lesson_versions.id"), index=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(24), default="in_progress")
    current_step: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    best_score: Mapped[float] = mapped_column(Float, default=0, server_default="0")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    user: Mapped[User] = relationship(back_populates="lesson_progress")
    lesson_version: Mapped[LessonVersion] = relationship(back_populates="progress_records")
    workspace: Mapped[Workspace] = relationship(back_populates="lesson_progress")
    evidence: Mapped[list["LearningEvidence"]] = relationship(
        back_populates="lesson_progress", order_by="LearningEvidence.observed_at"
    )
    messages: Mapped[list["LessonMessage"]] = relationship(
        back_populates="lesson_progress", order_by="LessonMessage.created_at"
    )


class LearningEvidence(Base):
    __tablename__ = "learning_evidence"
    __table_args__ = (
        Index("ix_learning_evidence_user_observed", "user_id", "observed_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    lesson_progress_id: Mapped[str] = mapped_column(ForeignKey("lesson_progress.id"), index=True)
    lesson_version_id: Mapped[str] = mapped_column(ForeignKey("lesson_versions.id"), index=True)
    evidence_type: Mapped[str] = mapped_column(String(32))
    response: Mapped[str] = mapped_column(Text)
    passed: Mapped[bool] = mapped_column(Boolean)
    score: Mapped[float] = mapped_column(Float)
    feedback: Mapped[str] = mapped_column(Text)
    answer_rule: Mapped[str] = mapped_column(Text)
    skill_version: Mapped[str] = mapped_column(String(32))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    user: Mapped[User] = relationship(back_populates="learning_evidence")
    lesson_progress: Mapped[LessonProgress] = relationship(back_populates="evidence")
    lesson_version: Mapped[LessonVersion] = relationship(back_populates="evidence")


class LessonMessage(Base):
    __tablename__ = "lesson_messages"
    __table_args__ = (
        Index("ix_lesson_messages_progress_created", "lesson_progress_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    lesson_progress_id: Mapped[str] = mapped_column(ForeignKey("lesson_progress.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(String(80))
    model: Mapped[str] = mapped_column(String(120))
    citations: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    lesson_progress: Mapped[LessonProgress] = relationship(back_populates="messages")
    user: Mapped[User] = relationship(back_populates="lesson_messages")


class ModelRegistry(Base):
    __tablename__ = "model_registry"
    __table_args__ = (Index("ix_models_provider_model", "provider", "model", unique=True),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    provider: Mapped[str] = mapped_column(String(80))
    model: Mapped[str] = mapped_column(String(120))
    display_name: Mapped[str] = mapped_column(String(120))
    capabilities: Mapped[list[str]] = mapped_column(JSON, default=list)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ModelRun(Base):
    __tablename__ = "model_runs"
    __table_args__ = (
        Index("ix_model_runs_user_created", "user_id", "created_at"),
        Index("ix_model_runs_provider_status", "provider", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    task: Mapped[str] = mapped_column(String(40))
    provider: Mapped[str] = mapped_column(String(80))
    model: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(16))
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost_yuan: Mapped[float] = mapped_column(Float, default=0)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    fallback_from: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    user: Mapped[User] = relationship(back_populates="model_runs")


class AccountDeletionReceipt(Base):
    __tablename__ = "account_deletion_receipts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    deleted_records: Mapped[dict[str, int]] = mapped_column(JSON, default=dict)
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class BetaFeedback(Base):
    __tablename__ = "beta_feedback"
    __table_args__ = (
        Index("ix_beta_feedback_user_created", "user_id", "created_at"),
        Index("ix_beta_feedback_area_blocking", "area", "is_blocking"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    area: Mapped[str] = mapped_column(String(24))
    issue_type: Mapped[str] = mapped_column(String(32))
    rating: Mapped[int] = mapped_column(Integer)
    is_blocking: Mapped[bool] = mapped_column(Boolean, default=False)
    message: Mapped[str] = mapped_column(Text)
    page_path: Mapped[str | None] = mapped_column(String(240), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    user: Mapped[User] = relationship(back_populates="beta_feedback")


class ReviewPreference(Base):
    __tablename__ = "review_preferences"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    timezone: Mapped[str] = mapped_column(String(80), default="Asia/Shanghai")
    study_days: Mapped[list[int]] = mapped_column(JSON, default=lambda: list(range(7)))
    reminder_time: Mapped[str] = mapped_column(String(5), default="19:00")
    reminder_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    schedule_mode: Mapped[str] = mapped_column(String(16), default="adaptive")
    fixed_interval_days: Mapped[int] = mapped_column(Integer, default=3)
    desired_retention: Mapped[float] = mapped_column(Float, default=0.9)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class ReviewCard(Base):
    __tablename__ = "review_cards"
    __table_args__ = (Index("ix_review_cards_user_due", "user_id", "due_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    error_cluster_id: Mapped[str] = mapped_column(
        ForeignKey("error_clusters.id"), unique=True
    )
    fsrs_state: Mapped[dict[str, Any]] = mapped_column(JSON)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    algorithm_due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), default="active")
    revision: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    cluster: Mapped[ErrorCluster] = relationship(back_populates="review_card")


class ReviewAttempt(Base):
    __tablename__ = "review_attempts"
    __table_args__ = (
        UniqueConstraint("user_id", "request_id", name="uq_review_attempt_request"),
        UniqueConstraint("card_id", "card_revision", name="uq_review_attempt_revision"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    card_id: Mapped[str] = mapped_column(ForeignKey("review_cards.id"), index=True)
    request_id: Mapped[str] = mapped_column(String(36))
    card_revision: Mapped[int] = mapped_column(Integer)
    response: Mapped[str] = mapped_column(Text)
    exercise: Mapped[dict[str, Any]] = mapped_column(JSON)
    feedback: Mapped[str] = mapped_column(Text)
    rule_matched: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ReviewLog(Base):
    __tablename__ = "review_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    card_id: Mapped[str] = mapped_column(ForeignKey("review_cards.id"), index=True)
    attempt_id: Mapped[str] = mapped_column(ForeignKey("review_attempts.id"), unique=True)
    rating: Mapped[str] = mapped_column(String(16))
    before_state: Mapped[dict[str, Any]] = mapped_column(JSON)
    after_state: Mapped[dict[str, Any]] = mapped_column(JSON)
    scheduler_config: Mapped[dict[str, Any]] = mapped_column(JSON)
    fsrs_log: Mapped[dict[str, Any]] = mapped_column(JSON)
    algorithm_due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ReviewReminder(Base):
    __tablename__ = "review_reminders"
    __table_args__ = (
        UniqueConstraint("user_id", "local_date", name="uq_review_reminder_daily"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    local_date: Mapped[date] = mapped_column(Date)
    due_count: Mapped[int] = mapped_column(Integer)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
