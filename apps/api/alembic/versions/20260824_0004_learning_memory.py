"""Add structured session summaries and confirmed error memory."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260824_0004"
down_revision: str | Sequence[str] | None = "20260824_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "session_summaries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("task_status", sa.String(32), nullable=False),
        sa.Column("task_explanation", sa.Text(), nullable=False),
        sa.Column("highlights", sa.JSON(), nullable=False),
        sa.Column("next_step", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(80), nullable=False),
        sa.Column("model", sa.String(120), nullable=False),
        sa.Column("skill_version", sa.String(32), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_session_summaries_session_id",
        "session_summaries",
        ["session_id"],
        unique=True,
    )
    op.create_index("ix_session_summaries_user_id", "session_summaries", ["user_id"])

    op.create_table(
        "error_clusters",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("canonical_key", sa.String(160), nullable=False),
        sa.Column("error_type", sa.String(40), nullable=False),
        sa.Column("subtype", sa.String(80), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("corrected_example", sa.Text(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("occurrence_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "canonical_key", name="uq_error_cluster_user_key"),
    )
    op.create_index("ix_error_clusters_user_id", "error_clusters", ["user_id"])
    op.create_index(
        "ix_error_clusters_user_status_last",
        "error_clusters",
        ["user_id", "status", "last_seen_at"],
    )

    op.create_table(
        "error_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "summary_id", sa.String(36), sa.ForeignKey("session_summaries.id"), nullable=False
        ),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("cluster_id", sa.String(36), sa.ForeignKey("error_clusters.id")),
        sa.Column("evidence_utterance_id", sa.String(36), sa.ForeignKey("utterances.id")),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("source_id", sa.String(36), nullable=False),
        sa.Column("learner_text", sa.Text(), nullable=False),
        sa.Column("corrected_text", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("error_type", sa.String(40), nullable=False),
        sa.Column("subtype", sa.String(80), nullable=False),
        sa.Column("severity", sa.String(24), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("evidence_span", sa.Text(), nullable=False),
        sa.Column("canonical_key", sa.String(160), nullable=False),
        sa.Column("hsk_tags", sa.JSON(), nullable=False),
        sa.Column("model_version", sa.String(120), nullable=False),
        sa.Column("skill_version", sa.String(32), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "session_id",
            "canonical_key",
            "evidence_span",
            name="uq_error_event_session_evidence",
        ),
    )
    op.create_index("ix_error_events_summary_id", "error_events", ["summary_id"])
    op.create_index("ix_error_events_session_id", "error_events", ["session_id"])
    op.create_index("ix_error_events_user_id", "error_events", ["user_id"])
    op.create_index("ix_error_events_cluster_id", "error_events", ["cluster_id"])
    op.create_index(
        "ix_error_events_user_status_observed",
        "error_events",
        ["user_id", "status", "observed_at"],
    )


def downgrade() -> None:
    op.drop_table("error_events")
    op.drop_table("error_clusters")
    op.drop_table("session_summaries")
