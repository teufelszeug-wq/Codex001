from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


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


@dataclass(frozen=True, slots=True)
class Project:
    id: UUID
    title: str
    schema_version: int
    created_at: datetime
    updated_at: datetime
