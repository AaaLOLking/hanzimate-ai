"""Add the closed beta feedback loop."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260904_0008"
down_revision: str | Sequence[str] | None = "20260902_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "beta_feedback",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("area", sa.String(24), nullable=False),
        sa.Column("issue_type", sa.String(32), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("is_blocking", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("page_path", sa.String(240), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_beta_feedback_user_id", "beta_feedback", ["user_id"])
    op.create_index(
        "ix_beta_feedback_user_created", "beta_feedback", ["user_id", "created_at"]
    )
    op.create_index(
        "ix_beta_feedback_area_blocking", "beta_feedback", ["area", "is_blocking"]
    )


def downgrade() -> None:
    op.drop_index("ix_beta_feedback_area_blocking", table_name="beta_feedback")
    op.drop_index("ix_beta_feedback_user_created", table_name="beta_feedback")
    op.drop_index("ix_beta_feedback_user_id", table_name="beta_feedback")
    op.drop_table("beta_feedback")
