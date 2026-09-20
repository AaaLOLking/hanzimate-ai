"""Create learner identity, workspace and model registry tables."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260824_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("locale", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_table(
        "model_registry",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("provider", sa.String(80), nullable=False),
        sa.Column("model", sa.String(120), nullable=False),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("capabilities", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_models_provider_model", "model_registry", ["provider", "model"], unique=True
    )
    op.create_table(
        "consents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("policy_version", sa.String(32), nullable=False),
        sa.Column("privacy_acknowledged", sa.Boolean(), nullable=False),
        sa.Column("learning_memory", sa.Boolean(), nullable=False),
        sa.Column("audio_retention", sa.Boolean(), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_consents_user_id", "consents", ["user_id"])
    op.create_table(
        "learner_missions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("why", sa.Text(), nullable=False),
        sa.Column("success_looks_like", sa.JSON(), nullable=False),
        sa.Column("constraints", sa.JSON(), nullable=False),
        sa.Column("out_of_scope", sa.JSON(), nullable=False),
        sa.Column("priorities", sa.JSON(), nullable=False),
        sa.Column("weekly_minutes", sa.Integer(), nullable=False),
        sa.Column("deadline", sa.Date()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_learner_missions_user_id", "learner_missions", ["user_id"])
    op.create_table(
        "learner_profiles",
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("native_language", sa.String(80), nullable=False),
        sa.Column("support_language", sa.String(80), nullable=False),
        sa.Column("estimated_hsk_band", sa.String(24), nullable=False),
        sa.Column("skill_estimates", sa.JSON(), nullable=False),
        sa.Column("preferences", sa.JSON(), nullable=False),
        sa.Column("projection_version", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "workspaces",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("state", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_opened_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_workspaces_user_id", "workspaces", ["user_id"])
    op.create_index("ix_workspaces_user_last_opened", "workspaces", ["user_id", "last_opened_at"])


def downgrade() -> None:
    op.drop_table("workspaces")
    op.drop_table("learner_profiles")
    op.drop_table("learner_missions")
    op.drop_table("consents")
    op.drop_table("model_registry")
    op.drop_table("users")
