"""Bible and Writing Room.

Revision ID: 0004_bible_writing_room
Revises: 0003_language_culture_builder
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_bible_writing_room"
down_revision = "0003_language_culture_builder"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bible_entities",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("canonical_name", sa.String(length=200), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("attributes_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("canon_state", sa.String(length=32), nullable=False, server_default="DRAFT"),
        sa.Column("source_type", sa.String(length=32), nullable=False, server_default="AUTHOR"),
        sa.Column("source_ref", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_bible_entities_project_id", "bible_entities", ["project_id"])
    op.create_index("ix_bible_entities_entity_type", "bible_entities", ["entity_type"])
    op.create_index("ix_bible_entities_canonical_name", "bible_entities", ["canonical_name"])
    op.create_index("ix_bible_entities_canon_state", "bible_entities", ["canon_state"])

    op.create_table(
        "manuscript_documents",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("content_hash", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("current_revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_manuscript_documents_project_id", "manuscript_documents", ["project_id"])

    op.create_table(
        "manuscript_revisions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("document_id", sa.String(length=36), sa.ForeignKey("manuscript_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("reason", sa.String(length=120), nullable=False, server_default="save"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("document_id", "revision_no", name="uq_document_revision"),
    )
    op.create_index("ix_manuscript_revisions_document_id", "manuscript_revisions", ["document_id"])

    op.create_table(
        "timeline_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("start_label", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("end_label", sa.String(length=160), nullable=True),
        sa.Column("sort_key", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("participant_ids_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("canon_state", sa.String(length=32), nullable=False, server_default="PLAN"),
        sa.Column("source_type", sa.String(length=32), nullable=False, server_default="AUTHOR"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_timeline_events_project_id", "timeline_events", ["project_id"])
    op.create_index("ix_timeline_events_sort_key", "timeline_events", ["sort_key"])
    op.execute("UPDATE projects SET schema_version = 4")


def downgrade() -> None:
    op.drop_index("ix_timeline_events_sort_key", table_name="timeline_events")
    op.drop_index("ix_timeline_events_project_id", table_name="timeline_events")
    op.drop_table("timeline_events")
    op.drop_index("ix_manuscript_revisions_document_id", table_name="manuscript_revisions")
    op.drop_table("manuscript_revisions")
    op.drop_index("ix_manuscript_documents_project_id", table_name="manuscript_documents")
    op.drop_table("manuscript_documents")
    op.drop_index("ix_bible_entities_canon_state", table_name="bible_entities")
    op.drop_index("ix_bible_entities_canonical_name", table_name="bible_entities")
    op.drop_index("ix_bible_entities_entity_type", table_name="bible_entities")
    op.drop_index("ix_bible_entities_project_id", table_name="bible_entities")
    op.drop_table("bible_entities")
    op.execute("UPDATE projects SET schema_version = 3")
