"""Add immutable course lessons, progress, evidence, and scoped tutor messages."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260824_0005"
down_revision: str | Sequence[str] | None = "20260824_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "courses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("slug", sa.String(120), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_courses_slug", "courses", ["slug"], unique=True)

    op.create_table(
        "course_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("course_id", sa.String(36), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("framework", sa.String(40), nullable=False),
        sa.Column("level", sa.String(40), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("source_metadata", sa.JSON(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("course_id", "version", name="uq_course_version_number"),
    )
    op.create_index("ix_course_versions_course_id", "course_versions", ["course_id"])

    op.create_table(
        "lesson_versions",
        sa.Column(
            "course_version_id",
            sa.String(36),
            sa.ForeignKey("course_versions.id"),
            nullable=False,
        ),
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("slug", sa.String(120), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("framework", sa.String(40), nullable=False),
        sa.Column("level", sa.String(40), nullable=False),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("estimated_minutes", sa.Integer(), nullable=False),
        sa.Column("targets", sa.JSON(), nullable=False),
        sa.Column("sources", sa.JSON(), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("assessment_config", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("skill_version", sa.String(32), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "course_version_id",
            "slug",
            "version",
            name="uq_lesson_version_slug",
        ),
    )
    op.create_index(
        "ix_lesson_versions_course_version_id", "lesson_versions", ["course_version_id"]
    )
    op.create_index("ix_lesson_versions_slug", "lesson_versions", ["slug"])
    op.create_index(
        "ix_lesson_versions_course_position",
        "lesson_versions",
        ["course_version_id", "position"],
    )

    op.create_table(
        "lesson_progress",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "lesson_version_id",
            sa.String(36),
            sa.ForeignKey("lesson_versions.id"),
            nullable=False,
        ),
        sa.Column(
            "workspace_id", sa.String(36), sa.ForeignKey("workspaces.id"), nullable=False
        ),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("current_step", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("best_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "user_id", "lesson_version_id", name="uq_lesson_progress_user_lesson"
        ),
    )
    op.create_index("ix_lesson_progress_user_id", "lesson_progress", ["user_id"])
    op.create_index(
        "ix_lesson_progress_lesson_version_id", "lesson_progress", ["lesson_version_id"]
    )
    op.create_index(
        "ix_lesson_progress_workspace_id", "lesson_progress", ["workspace_id"], unique=True
    )
    op.create_index(
        "ix_lesson_progress_user_updated", "lesson_progress", ["user_id", "updated_at"]
    )

    op.create_table(
        "learning_evidence",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "lesson_progress_id",
            sa.String(36),
            sa.ForeignKey("lesson_progress.id"),
            nullable=False,
        ),
        sa.Column(
            "lesson_version_id",
            sa.String(36),
            sa.ForeignKey("lesson_versions.id"),
            nullable=False,
        ),
        sa.Column("evidence_type", sa.String(32), nullable=False),
        sa.Column("response", sa.Text(), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("feedback", sa.Text(), nullable=False),
        sa.Column("answer_rule", sa.Text(), nullable=False),
        sa.Column("skill_version", sa.String(32), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_learning_evidence_user_id", "learning_evidence", ["user_id"])
    op.create_index(
        "ix_learning_evidence_lesson_progress_id", "learning_evidence", ["lesson_progress_id"]
    )
    op.create_index(
        "ix_learning_evidence_lesson_version_id", "learning_evidence", ["lesson_version_id"]
    )
    op.create_index(
        "ix_learning_evidence_user_observed",
        "learning_evidence",
        ["user_id", "observed_at"],
    )

    op.create_table(
        "lesson_messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "lesson_progress_id",
            sa.String(36),
            sa.ForeignKey("lesson_progress.id"),
            nullable=False,
        ),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(80), nullable=False),
        sa.Column("model", sa.String(120), nullable=False),
        sa.Column("citations", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_lesson_messages_lesson_progress_id", "lesson_messages", ["lesson_progress_id"]
    )
    op.create_index("ix_lesson_messages_user_id", "lesson_messages", ["user_id"])
    op.create_index(
        "ix_lesson_messages_progress_created",
        "lesson_messages",
        ["lesson_progress_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("lesson_messages")
    op.drop_table("learning_evidence")
    op.drop_table("lesson_progress")
    op.drop_table("lesson_versions")
    op.drop_table("course_versions")
    op.drop_table("courses")
