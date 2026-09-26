from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
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
