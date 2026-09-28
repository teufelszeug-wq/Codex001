"""Isekai Pack.

Revision ID: 0008_isekai_pack
Revises: 0007_change_impact_engine
"""
from alembic import op
import sqlalchemy as sa

revision = "0008_isekai_pack"
down_revision = "0007_change_impact_engine"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "isekai_pack_configs",
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("strictness", sa.String(length=32), nullable=False, server_default="standard"),
        sa.Column("enabled_categories_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("allow_terms_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("custom_terms_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("replacements_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("require_world_mapping", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("travel_routes_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("magic_policy_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("economy_policy_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("healing_policy_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("pack_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.execute("UPDATE projects SET schema_version = 8")


def downgrade() -> None:
    op.drop_table("isekai_pack_configs")
    op.execute("UPDATE projects SET schema_version = 7")
