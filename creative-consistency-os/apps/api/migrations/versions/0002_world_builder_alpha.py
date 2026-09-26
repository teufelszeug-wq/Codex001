"""World Builder Alpha

Revision ID: 0002_world_builder_alpha
Revises: 0001_m1_baseline
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_world_builder_alpha"
down_revision = "0001_m1_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "world_builder_profiles",
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("setup_mode", sa.String(length=32), nullable=False),
        sa.Column("selected_genres_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("genre_weights_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("custom_genres_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("section_modes_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("section_notes_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("import_format", sa.String(length=32), nullable=True),
        sa.Column("import_notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("recommendations_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("wizard_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.execute("UPDATE projects SET schema_version = 2")


def downgrade() -> None:
    op.drop_table("world_builder_profiles")
    op.execute("UPDATE projects SET schema_version = 1")
