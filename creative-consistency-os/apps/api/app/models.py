from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base
from .domain import CURRENT_PROJECT_SCHEMA_VERSION


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ProjectModel(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=CURRENT_PROJECT_SCHEMA_VERSION)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class WorldBuilderProfileModel(Base):
    __tablename__ = "world_builder_profiles"

    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )
    setup_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    selected_genres_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    genre_weights_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    custom_genres_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    section_modes_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    section_notes_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    import_format: Mapped[str | None] = mapped_column(String(32), nullable=True)
    import_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    recommendations_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    wizard_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class LanguageCultureConfigModel(Base):
    __tablename__ = "language_culture_configs"

    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )
    languages_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    cultures_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    contacts_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    root_lexicon_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    display_policy_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    earth_term_policy_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    common_language_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    builder_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class BibleEntityModel(Base):
    __tablename__ = "bible_entities"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    canonical_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    attributes_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    canon_state: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT", index=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default="AUTHOR")
    source_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class ManuscriptDocumentModel(Base):
    __tablename__ = "manuscript_documents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    current_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class ManuscriptRevisionModel(Base):
    __tablename__ = "manuscript_revisions"
    __table_args__ = (UniqueConstraint("document_id", "revision_no", name="uq_document_revision"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("manuscript_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[str] = mapped_column(String(120), nullable=False, default="save")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class TimelineEventModel(Base):
    __tablename__ = "timeline_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    start_label: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    end_label: Mapped[str | None] = mapped_column(String(160), nullable=True)
    sort_key: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    participant_ids_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    canon_state: Mapped[str] = mapped_column(String(32), nullable=False, default="PLAN")
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default="AUTHOR")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class EntityAliasModel(Base):
    __tablename__ = "entity_aliases"
    __table_args__ = (UniqueConstraint("entity_id", "normalized_alias", name="uq_entity_alias_normalized"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(36), ForeignKey("bible_entities.id", ondelete="CASCADE"), nullable=False, index=True)
    alias: Mapped[str] = mapped_column(String(200), nullable=False)
    normalized_alias: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    alias_type: Mapped[str] = mapped_column(String(40), nullable=False, default="alternate")
    language_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class EntityMentionModel(Base):
    __tablename__ = "entity_mentions"
    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "revision_no",
            "start_offset",
            "end_offset",
            name="uq_entity_mention_span_revision",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("manuscript_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("bible_entities.id", ondelete="SET NULL"), nullable=True, index=True)
    mention_text: Mapped[str] = mapped_column(String(240), nullable=False)
    normalized_text: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    start_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    end_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    resolver_state: Mapped[str] = mapped_column(String(32), nullable=False, default="unresolved", index=True)
    confidence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    candidate_ids_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class EntityRelationModel(Base):
    __tablename__ = "entity_relations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    source_entity_id: Mapped[str] = mapped_column(String(36), ForeignKey("bible_entities.id", ondelete="CASCADE"), nullable=False, index=True)
    target_entity_id: Mapped[str] = mapped_column(String(36), ForeignKey("bible_entities.id", ondelete="CASCADE"), nullable=False, index=True)
    relation_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(240), nullable=False, default="")
    canon_state: Mapped[str] = mapped_column(String(32), nullable=False, default="PLAN")
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default="AUTHOR")
    attributes_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class IsekaiPackConfigModel(Base):
    __tablename__ = "isekai_pack_configs"
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    strictness: Mapped[str] = mapped_column(String(32), nullable=False, default="standard")
    enabled_categories_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    allow_terms_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    custom_terms_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    replacements_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    require_world_mapping: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    travel_routes_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    magic_policy_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    economy_policy_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    healing_policy_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    pack_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class LNGenrePackConfigModel(Base):
    __tablename__ = "ln_genre_pack_configs"
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )
    enabled_packs_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    noble_lady_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    palace_harem_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    romcom_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    pack_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class LintProjectConfigModel(Base):
    __tablename__ = "lint_project_configs"
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )
    rules_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    config_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class LintRunModel(Base):
    __tablename__ = "lint_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("manuscript_documents.id", ondelete="CASCADE"), nullable=True, index=True)
    scope: Mapped[str] = mapped_column(String(32), nullable=False, default="document")
    document_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ruleset_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="completed")
    summary_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class LintFindingModel(Base):
    __tablename__ = "lint_findings"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("lint_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("manuscript_documents.id", ondelete="CASCADE"), nullable=True, index=True)
    entity_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("bible_entities.id", ondelete="SET NULL"), nullable=True, index=True)
    rule_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="warning", index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    start_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evidence_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    finding_state: Mapped[str] = mapped_column(String(24), nullable=False, default="OPEN", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class DependencyEdgeModel(Base):
    __tablename__ = "dependency_edges"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "source_type",
            "source_id",
            "target_type",
            "target_id",
            "edge_type",
            name="uq_dependency_edge",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    edge_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    detail_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    refreshed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class ImpactInvalidationModel(Base):
    __tablename__ = "impact_invalidations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, default="BibleEntity")
    source_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    change_kind: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="PENDING", index=True)
    detail_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    result_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ChangeLogModel(Base):
    __tablename__ = "change_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    before_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    after_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
