"""Change Impact Engine.

Revision ID: 0007_change_impact_engine
Revises: 0006_core_lint_engine
"""
from alembic import op
import sqlalchemy as sa

revision = "0007_change_impact_engine"
down_revision = "0006_core_lint_engine"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dependency_edges",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.String(length=120), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.String(length=120), nullable=False),
        sa.Column("edge_type", sa.String(length=64), nullable=False),
        sa.Column("detail_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("refreshed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "project_id",
            "source_type",
            "source_id",
            "target_type",
            "target_id",
            "edge_type",
            name="uq_dependency_edge",
        ),
    )
    for name, column in [
        ("ix_dependency_edges_project_id", "project_id"),
        ("ix_dependency_edges_source_type", "source_type"),
        ("ix_dependency_edges_source_id", "source_id"),
        ("ix_dependency_edges_target_type", "target_type"),
        ("ix_dependency_edges_target_id", "target_id"),
        ("ix_dependency_edges_edge_type", "edge_type"),
    ]:
        op.create_index(name, "dependency_edges", [column])

    op.create_table(
        "impact_invalidations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False, server_default="BibleEntity"),
        sa.Column("source_id", sa.String(length=120), nullable=False),
        sa.Column("change_kind", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="PENDING"),
        sa.Column("detail_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("result_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_impact_invalidations_project_id", "impact_invalidations", ["project_id"])
    op.create_index("ix_impact_invalidations_source_id", "impact_invalidations", ["source_id"])
    op.create_index("ix_impact_invalidations_status", "impact_invalidations", ["status"])
    op.execute("UPDATE projects SET schema_version = 7")


def downgrade() -> None:
    op.drop_index("ix_impact_invalidations_status", table_name="impact_invalidations")
    op.drop_index("ix_impact_invalidations_source_id", table_name="impact_invalidations")
    op.drop_index("ix_impact_invalidations_project_id", table_name="impact_invalidations")
    op.drop_table("impact_invalidations")
    for name in [
        "ix_dependency_edges_edge_type",
        "ix_dependency_edges_target_id",
        "ix_dependency_edges_target_type",
        "ix_dependency_edges_source_id",
        "ix_dependency_edges_source_type",
        "ix_dependency_edges_project_id",
    ]:
        op.drop_index(name, table_name="dependency_edges")
    op.drop_table("dependency_edges")
    op.execute("UPDATE projects SET schema_version = 6")
