from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


CURRENT_PROJECT_SCHEMA_VERSION = 4


class CanonState(StrEnum):
    DRAFT = "DRAFT"
    PLAN = "PLAN"
    CANON = "CANON"
    INFERENCE = "INFERENCE"
    DISPUTED = "DISPUTED"
    DEPRECATED = "DEPRECATED"
    ARCHIVED = "ARCHIVED"
    REJECTED = "REJECTED"


class SourceType(StrEnum):
    AUTHOR = "AUTHOR"
    IMPORT = "IMPORT"
    MANUSCRIPT = "MANUSCRIPT"
    AI_EXTRACTION = "AI_EXTRACTION"
    AI_SUGGESTION = "AI_SUGGESTION"
    SYSTEM = "SYSTEM"
    COLLABORATOR = "COLLABORATOR"


class SetupMode(StrEnum):
    QUICK = "quick"
    GUIDED = "guided"
    FULL = "full"
    BLANK = "blank"
    IMPORT = "import"


class SectionMode(StrEnum):
    AUTO = "auto"
    MANUAL = "manual"
    SKIP = "skip"


class WorldBuilderStatus(StrEnum):
    DRAFT = "draft"
    CONFIGURED = "configured"


@dataclass(frozen=True, slots=True)
class Project:
    id: UUID
    title: str
    schema_version: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class WorldBuilderProfile:
    project_id: UUID
    setup_mode: str
    selected_genres: list[str]
    genre_weights: dict[str, int]
    custom_genres: list[dict[str, object]]
    section_modes: dict[str, str]
    section_notes: dict[str, str]
    import_format: str | None
    import_notes: str | None
    status: str
    recommendations: dict[str, dict[str, object]]
    wizard_version: int
    created_at: datetime
    updated_at: datetime
