"""Add account controls and model run observability."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260902_0007"
down_revision: str | Sequence[str] | None = "20260831_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "model_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("task", sa.String(40), nullable=False),
        sa.Column("provider", sa.String(80), nullable=False),
        sa.Column("model", sa.String(120), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_cost_yuan", sa.Float(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(80), nullable=True),
        sa.Column("fallback_from", sa.String(80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_model_runs_user_id", "model_runs", ["user_id"])
    op.create_index("ix_model_runs_user_created", "model_runs", ["user_id", "created_at"])
    op.create_index(
        "ix_model_runs_provider_status", "model_runs", ["provider", "status"]
    )
    op.create_table(
        "account_deletion_receipts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("deleted_records", sa.JSON(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("account_deletion_receipts")
    op.drop_index("ix_model_runs_provider_status", table_name="model_runs")
    op.drop_index("ix_model_runs_user_created", table_name="model_runs")
    op.drop_index("ix_model_runs_user_id", table_name="model_runs")
    op.drop_table("model_runs")
