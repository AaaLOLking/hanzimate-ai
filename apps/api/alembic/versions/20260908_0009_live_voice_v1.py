"""Add live voice v1 lifecycle and transcript fields.

Revision ID: 20260908_0009
Revises: 20260904_0008
Create Date: 2026-09-08
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260908_0009"
down_revision: str | None = "20260904_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("sessions") as batch_op:
        batch_op.add_column(sa.Column("client_session_id", sa.String(length=80), nullable=True))
        batch_op.add_column(
            sa.Column(
                "protocol_version", sa.String(length=24), server_default="legacy", nullable=False
            )
        )
        batch_op.add_column(
            sa.Column("patience", sa.String(length=16), server_default="patient", nullable=False)
        )
        batch_op.add_column(sa.Column("requested_config", sa.JSON(), nullable=True))
        batch_op.add_column(
            sa.Column("config_revision", sa.Integer(), server_default="1", nullable=False)
        )
        batch_op.add_column(sa.Column("applied_config_revision", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("connection_epoch", sa.Integer(), server_default="0", nullable=False)
        )
        batch_op.add_column(
            sa.Column(
                "transport_status", sa.String(length=24), server_default="idle", nullable=False
            )
        )
        batch_op.add_column(sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("ending_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("end_reason", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("closing_manifest", sa.JSON(), nullable=True))
        batch_op.create_unique_constraint(
            "uq_sessions_user_client_session", ["user_id", "client_session_id"]
        )

    op.execute(
        sa.text("UPDATE sessions SET requested_config = '{}' WHERE requested_config IS NULL")
    )
    with op.batch_alter_table("sessions") as batch_op:
        batch_op.alter_column("requested_config", existing_type=sa.JSON(), nullable=False)

    with op.batch_alter_table("utterances") as batch_op:
        batch_op.add_column(
            sa.Column("connection_epoch", sa.Integer(), server_default="0", nullable=False)
        )
        batch_op.add_column(sa.Column("provider_item_id", sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column("provider_response_id", sa.String(length=120), nullable=True))
        batch_op.add_column(
            sa.Column("content_index", sa.Integer(), server_default="0", nullable=False)
        )
        batch_op.add_column(
            sa.Column(
                "transcript_status", sa.String(length=16), server_default="final", nullable=False
            )
        )
        batch_op.add_column(
            sa.Column(
                "playback_status",
                sa.String(length=24),
                server_default="not_applicable",
                nullable=False,
            )
        )
        batch_op.create_unique_constraint(
            "uq_utterance_provider_item",
            [
                "session_id",
                "connection_epoch",
                "provider_item_id",
                "content_index",
                "speaker",
            ],
        )


def downgrade() -> None:
    with op.batch_alter_table("utterances") as batch_op:
        batch_op.drop_constraint("uq_utterance_provider_item", type_="unique")
        batch_op.drop_column("playback_status")
        batch_op.drop_column("transcript_status")
        batch_op.drop_column("content_index")
        batch_op.drop_column("provider_response_id")
        batch_op.drop_column("provider_item_id")
        batch_op.drop_column("connection_epoch")

    with op.batch_alter_table("sessions") as batch_op:
        batch_op.drop_constraint("uq_sessions_user_client_session", type_="unique")
        batch_op.drop_column("closing_manifest")
        batch_op.drop_column("end_reason")
        batch_op.drop_column("ending_at")
        batch_op.drop_column("deadline_at")
        batch_op.drop_column("transport_status")
        batch_op.drop_column("connection_epoch")
        batch_op.drop_column("applied_config_revision")
        batch_op.drop_column("config_revision")
        batch_op.drop_column("requested_config")
        batch_op.drop_column("patience")
        batch_op.drop_column("protocol_version")
        batch_op.drop_column("client_session_id")
