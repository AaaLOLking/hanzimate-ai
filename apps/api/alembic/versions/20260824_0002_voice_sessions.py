"""Create realtime voice sessions and transcript events."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260824_0002"
down_revision: str | Sequence[str] | None = "20260824_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("correction_mode", sa.String(24), nullable=False),
        sa.Column("speech_speed", sa.String(16), nullable=False),
        sa.Column("provider", sa.String(80), nullable=False),
        sa.Column("model", sa.String(120), nullable=False),
        sa.Column("voice", sa.String(80), nullable=False),
        sa.Column("connection_mode", sa.String(24), nullable=False),
        sa.Column("skill_version", sa.String(32), nullable=False),
        sa.Column("context_pack", sa.JSON(), nullable=False),
        sa.Column("max_duration_seconds", sa.Integer(), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=False),
        sa.Column("failure_reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_sessions_workspace_id", "sessions", ["workspace_id"])
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
    op.create_index("ix_sessions_user_started", "sessions", ["user_id", "started_at"])
    op.create_table(
        "utterances",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("client_event_id", sa.String(80), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("speaker", sa.String(16), nullable=False),
        sa.Column("transcript", sa.Text(), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("is_final", sa.Boolean(), nullable=False),
        sa.Column("started_ms", sa.Integer()),
        sa.Column("ended_ms", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("session_id", "client_event_id", name="uq_utterance_client_event"),
        sa.UniqueConstraint("session_id", "sequence_no", name="uq_utterance_sequence"),
    )
    op.create_index("ix_utterances_session_id", "utterances", ["session_id"])


def downgrade() -> None:
    op.drop_table("utterances")
    op.drop_table("sessions")
