"""Add realtime reliability events and aggregate metrics."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260824_0003"
down_revision: str | Sequence[str] | None = "20260824_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sessions", sa.Column("reconnect_count", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column(
        "sessions",
        sa.Column("interruption_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("sessions", sa.Column("first_response_latency_ms", sa.Integer()))
    op.add_column("sessions", sa.Column("last_event_at", sa.DateTime(timezone=True)))
    op.create_table(
        "session_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("client_event_id", sa.String(80), nullable=False),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("elapsed_ms", sa.Integer()),
        sa.Column("event_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("session_id", "client_event_id", name="uq_session_event_client_event"),
    )
    op.create_index("ix_session_events_session_id", "session_events", ["session_id"])
    op.create_index(
        "ix_session_events_session_created", "session_events", ["session_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_table("session_events")
    op.drop_column("sessions", "last_event_at")
    op.drop_column("sessions", "first_response_latency_ms")
    op.drop_column("sessions", "interruption_count")
    op.drop_column("sessions", "reconnect_count")
