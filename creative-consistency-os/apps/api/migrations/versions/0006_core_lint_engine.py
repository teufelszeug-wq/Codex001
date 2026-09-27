"""Core Lint Engine.

Revision ID: 0006_core_lint_engine
Revises: 0005_entity_intelligence
"""
from alembic import op
import sqlalchemy as sa

revision = "0006_core_lint_engine"
down_revision = "0005_entity_intelligence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lint_project_configs",
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("rules_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("config_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "lint_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_id", sa.String(length=36), sa.ForeignKey("manuscript_documents.id", ondelete="CASCADE"), nullable=True),
        sa.Column("scope", sa.String(length=32), nullable=False, server_default="document"),
        sa.Column("document_revision", sa.Integer(), nullable=True),
        sa.Column("ruleset_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="completed"),
        sa.Column("summary_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_lint_runs_project_id", "lint_runs", ["project_id"])
    op.create_index("ix_lint_runs_document_id", "lint_runs", ["document_id"])

    op.create_table(
        "lint_findings",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey("lint_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_id", sa.String(length=36), sa.ForeignKey("manuscript_documents.id", ondelete="CASCADE"), nullable=True),
        sa.Column("entity_id", sa.String(length=36), sa.ForeignKey("bible_entities.id", ondelete="SET NULL"), nullable=True),
        sa.Column("rule_id", sa.String(length=100), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False, server_default="warning"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("start_offset", sa.Integer(), nullable=True),
        sa.Column("end_offset", sa.Integer(), nullable=True),
        sa.Column("evidence_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("finding_state", sa.String(length=24), nullable=False, server_default="OPEN"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    for name, column in [
        ("ix_lint_findings_run_id", "run_id"),
        ("ix_lint_findings_project_id", "project_id"),
        ("ix_lint_findings_document_id", "document_id"),
        ("ix_lint_findings_entity_id", "entity_id"),
        ("ix_lint_findings_rule_id", "rule_id"),
        ("ix_lint_findings_category", "category"),
        ("ix_lint_findings_severity", "severity"),
        ("ix_lint_findings_fingerprint", "fingerprint"),
        ("ix_lint_findings_finding_state", "finding_state"),
    ]:
        op.create_index(name, "lint_findings", [column])

    op.execute("UPDATE projects SET schema_version = 6")


def downgrade() -> None:
    for name in [
        "ix_lint_findings_finding_state",
        "ix_lint_findings_fingerprint",
        "ix_lint_findings_severity",
        "ix_lint_findings_category",
        "ix_lint_findings_rule_id",
        "ix_lint_findings_entity_id",
        "ix_lint_findings_document_id",
        "ix_lint_findings_project_id",
        "ix_lint_findings_run_id",
    ]:
        op.drop_index(name, table_name="lint_findings")
    op.drop_table("lint_findings")
    op.drop_index("ix_lint_runs_document_id", table_name="lint_runs")
    op.drop_index("ix_lint_runs_project_id", table_name="lint_runs")
    op.drop_table("lint_runs")
    op.drop_table("lint_project_configs")
    op.execute("UPDATE projects SET schema_version = 5")
