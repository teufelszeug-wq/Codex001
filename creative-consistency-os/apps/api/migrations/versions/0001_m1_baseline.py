"""M1 baseline

Revision ID: 0001_m1_baseline
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_m1_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "change_log",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("entity_id", sa.String(length=36), nullable=False),
        sa.Column("before_json", sa.Text(), nullable=True),
        sa.Column("after_json", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_change_log_project_id", "change_log", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_change_log_project_id", table_name="change_log")
    op.drop_table("change_log")
    op.drop_table("projects")
