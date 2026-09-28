"""LN genre packs.

Revision ID: 0009_ln_genre_packs
Revises: 0008_isekai_pack
"""
from alembic import op
import sqlalchemy as sa

revision = "0009_ln_genre_packs"
down_revision = "0008_isekai_pack"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ln_genre_pack_configs",
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("enabled_packs_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("noble_lady_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("palace_harem_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("romcom_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("pack_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.execute("UPDATE projects SET schema_version = 9")


def downgrade() -> None:
    op.drop_table("ln_genre_pack_configs")
    op.execute("UPDATE projects SET schema_version = 8")
