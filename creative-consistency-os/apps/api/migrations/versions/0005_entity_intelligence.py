"""Entity Intelligence.

Revision ID: 0005_entity_intelligence
Revises: 0004_bible_writing_room
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_entity_intelligence"
down_revision = "0004_bible_writing_room"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "entity_aliases",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_id", sa.String(length=36), sa.ForeignKey("bible_entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("alias", sa.String(length=200), nullable=False),
        sa.Column("normalized_alias", sa.String(length=200), nullable=False),
        sa.Column("alias_type", sa.String(length=40), nullable=False, server_default="alternate"),
        sa.Column("language_id", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("entity_id", "normalized_alias", name="uq_entity_alias_normalized"),
    )
    op.create_index("ix_entity_aliases_project_id", "entity_aliases", ["project_id"])
    op.create_index("ix_entity_aliases_entity_id", "entity_aliases", ["entity_id"])
    op.create_index("ix_entity_aliases_normalized_alias", "entity_aliases", ["normalized_alias"])

    op.create_table(
        "entity_mentions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_id", sa.String(length=36), sa.ForeignKey("manuscript_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_id", sa.String(length=36), sa.ForeignKey("bible_entities.id", ondelete="SET NULL"), nullable=True),
        sa.Column("mention_text", sa.String(length=240), nullable=False),
        sa.Column("normalized_text", sa.String(length=240), nullable=False),
        sa.Column("start_offset", sa.Integer(), nullable=False),
        sa.Column("end_offset", sa.Integer(), nullable=False),
        sa.Column("resolver_state", sa.String(length=32), nullable=False, server_default="unresolved"),
        sa.Column("confidence", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("candidate_ids_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("revision_no", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "document_id",
            "revision_no",
            "start_offset",
            "end_offset",
            name="uq_entity_mention_span_revision",
        ),
    )
    op.create_index("ix_entity_mentions_project_id", "entity_mentions", ["project_id"])
    op.create_index("ix_entity_mentions_document_id", "entity_mentions", ["document_id"])
    op.create_index("ix_entity_mentions_entity_id", "entity_mentions", ["entity_id"])
    op.create_index("ix_entity_mentions_normalized_text", "entity_mentions", ["normalized_text"])
    op.create_index("ix_entity_mentions_resolver_state", "entity_mentions", ["resolver_state"])

    op.create_table(
        "entity_relations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_entity_id", sa.String(length=36), sa.ForeignKey("bible_entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_entity_id", sa.String(length=36), sa.ForeignKey("bible_entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("relation_type", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=240), nullable=False, server_default=""),
        sa.Column("canon_state", sa.String(length=32), nullable=False, server_default="PLAN"),
        sa.Column("source_type", sa.String(length=32), nullable=False, server_default="AUTHOR"),
        sa.Column("attributes_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_entity_relations_project_id", "entity_relations", ["project_id"])
    op.create_index("ix_entity_relations_source_entity_id", "entity_relations", ["source_entity_id"])
    op.create_index("ix_entity_relations_target_entity_id", "entity_relations", ["target_entity_id"])
    op.create_index("ix_entity_relations_relation_type", "entity_relations", ["relation_type"])
    op.execute("UPDATE projects SET schema_version = 5")


def downgrade() -> None:
    op.drop_index("ix_entity_relations_relation_type", table_name="entity_relations")
    op.drop_index("ix_entity_relations_target_entity_id", table_name="entity_relations")
    op.drop_index("ix_entity_relations_source_entity_id", table_name="entity_relations")
    op.drop_index("ix_entity_relations_project_id", table_name="entity_relations")
    op.drop_table("entity_relations")

    op.drop_index("ix_entity_mentions_resolver_state", table_name="entity_mentions")
    op.drop_index("ix_entity_mentions_normalized_text", table_name="entity_mentions")
    op.drop_index("ix_entity_mentions_entity_id", table_name="entity_mentions")
    op.drop_index("ix_entity_mentions_document_id", table_name="entity_mentions")
    op.drop_index("ix_entity_mentions_project_id", table_name="entity_mentions")
    op.drop_table("entity_mentions")

    op.drop_index("ix_entity_aliases_normalized_alias", table_name="entity_aliases")
    op.drop_index("ix_entity_aliases_entity_id", table_name="entity_aliases")
    op.drop_index("ix_entity_aliases_project_id", table_name="entity_aliases")
    op.drop_table("entity_aliases")
    op.execute("UPDATE projects SET schema_version = 4")
