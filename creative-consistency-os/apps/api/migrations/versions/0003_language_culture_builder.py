"""Language & Culture Builder

Revision ID: 0003_language_culture_builder
Revises: 0002_world_builder_alpha
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_language_culture_builder"
down_revision = "0002_world_builder_alpha"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "language_culture_configs",
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("languages_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("cultures_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("contacts_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("root_lexicon_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("display_policy_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("earth_term_policy_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("common_language_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("builder_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.execute("UPDATE projects SET schema_version = 3")


def downgrade() -> None:
    op.drop_table("language_culture_configs")
    op.execute("UPDATE projects SET schema_version = 2")
