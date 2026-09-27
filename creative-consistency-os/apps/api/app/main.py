from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_session
from app.domain import Project, WorldBuilderProfile
from app.language_services import LanguageCultureService
from app.services import ProjectService, WorldBuilderService
from app.writing_services import WritingService


class ProjectCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class ProjectRead(BaseModel):
    id: UUID
    title: str
    schema_version: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, project: Project) -> "ProjectRead":
        return cls(
            id=project.id,
            title=project.title,
            schema_version=project.schema_version,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )


class CustomGenreInput(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    weight: int = Field(default=50, ge=0, le=100)


class WorldBuilderWrite(BaseModel):
    setup_mode: str
    selected_genres: list[str] = Field(default_factory=list)
    genre_weights: dict[str, int] = Field(default_factory=dict)
    custom_genres: list[CustomGenreInput] = Field(default_factory=list)
    section_modes: dict[str, str] = Field(default_factory=dict)
    section_notes: dict[str, str] = Field(default_factory=dict)
    import_format: str | None = None
    import_notes: str | None = Field(default=None, max_length=2000)
    status: str = "configured"


class WorldBuilderRead(BaseModel):
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

    @classmethod
    def from_domain(cls, profile: WorldBuilderProfile) -> "WorldBuilderRead":
        return cls(
            project_id=profile.project_id,
            setup_mode=profile.setup_mode,
            selected_genres=profile.selected_genres,
            genre_weights=profile.genre_weights,
            custom_genres=profile.custom_genres,
            section_modes=profile.section_modes,
            section_notes=profile.section_notes,
            import_format=profile.import_format,
            import_notes=profile.import_notes,
            status=profile.status,
            recommendations=profile.recommendations,
            wizard_version=profile.wizard_version,
            created_at=profile.created_at,
            updated_at=profile.updated_at,
        )


class LanguageCultureWrite(BaseModel):
    languages: list[dict[str, object]] = Field(default_factory=list)
    cultures: list[dict[str, object]] = Field(default_factory=list)
    contacts: list[dict[str, object]] = Field(default_factory=list)
    root_lexicon: list[dict[str, object]] = Field(default_factory=list)
    display_policy: dict[str, object] = Field(default_factory=dict)
    earth_term_policy: dict[str, object] = Field(default_factory=dict)
    common_language_id: str | None = None
    status: str = "configured"


class NamePreviewRequest(BaseModel):
    kind: str = "person"
    count: int = Field(default=10, ge=1, le=30)
    seed: int = 1


class BibleWrite(BaseModel):
    entity_type: str
    canonical_name: str = Field(min_length=1, max_length=200)
    summary: str = Field(default="", max_length=12000)
    attributes: dict[str, object] = Field(default_factory=dict)
    canon_state: str = "DRAFT"
    source_type: str = "AUTHOR"
    source_ref: str | None = Field(default=None, max_length=2000)


class BibleUpdate(BaseModel):
    entity_type: str | None = None
    canonical_name: str | None = Field(default=None, min_length=1, max_length=200)
    summary: str | None = Field(default=None, max_length=12000)
    attributes: dict[str, object] | None = None
    canon_state: str | None = None
    source_type: str | None = None
    source_ref: str | None = Field(default=None, max_length=2000)


class CanonTransitionRequest(BaseModel):
    target_state: str
    reason: str = Field(min_length=1, max_length=2000)


class ManuscriptCreate(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    content: str = ""
    order_index: int = 0
    status: str = "draft"


class ManuscriptWrite(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    content: str = ""
    order_index: int = 0
    status: str = "draft"
    reason: str = Field(default="autosave", max_length=120)


class TimelineWrite(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    start_label: str = Field(default="", max_length=160)
    end_label: str | None = Field(default=None, max_length=160)
    sort_key: int = 0
    description: str = Field(default="", max_length=12000)
    participant_ids: list[str] = Field(default_factory=list)
    canon_state: str = "PLAN"
    source_type: str = "AUTHOR"


app = FastAPI(title=settings.app_name, version=settings.app_version)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "OPTIONS"],
    allow_headers=["*"],
)

api = APIRouter(prefix=settings.api_prefix)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name, "version": settings.app_version}


@api.get("/catalog/world-builder", tags=["world-builder"])
def world_builder_catalog() -> dict[str, object]:
    return WorldBuilderService.catalog()


@api.get("/catalog/language-culture", tags=["language-culture"])
def language_culture_catalog() -> dict[str, object]:
    return LanguageCultureService.catalog()


@api.get("/projects", response_model=list[ProjectRead], tags=["projects"])
def list_projects(session: Session = Depends(get_session)) -> list[ProjectRead]:
    return [ProjectRead.from_domain(project) for project in ProjectService(session).list_projects()]


@api.post("/projects", response_model=ProjectRead, status_code=status.HTTP_201_CREATED, tags=["projects"])
def create_project(payload: ProjectCreate, session: Session = Depends(get_session)) -> ProjectRead:
    try:
        project = ProjectService(session).create_project(payload.title)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return ProjectRead.from_domain(project)


@api.get("/projects/{project_id}", response_model=ProjectRead, tags=["projects"])
def get_project(project_id: UUID, session: Session = Depends(get_session)) -> ProjectRead:
    project = ProjectService(session).get_project(project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return ProjectRead.from_domain(project)


@api.get("/projects/{project_id}/world-builder", response_model=WorldBuilderRead, tags=["world-builder"])
def get_world_builder(project_id: UUID, session: Session = Depends(get_session)) -> WorldBuilderRead:
    try:
        profile = WorldBuilderService(session).get_profile(project_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="World Builder profile not found")
    return WorldBuilderRead.from_domain(profile)


@api.put("/projects/{project_id}/world-builder", response_model=WorldBuilderRead, tags=["world-builder"])
def save_world_builder(
    project_id: UUID,
    payload: WorldBuilderWrite,
    session: Session = Depends(get_session),
) -> WorldBuilderRead:
    try:
        profile = WorldBuilderService(session).save_profile(
            project_id,
            setup_mode=payload.setup_mode,
            selected_genres=payload.selected_genres,
            genre_weights=payload.genre_weights,
            custom_genres=[item.model_dump() for item in payload.custom_genres],
            section_modes=payload.section_modes,
            section_notes=payload.section_notes,
            import_format=payload.import_format,
            import_notes=payload.import_notes,
            status=payload.status,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return WorldBuilderRead.from_domain(profile)


@api.get("/projects/{project_id}/language-culture", tags=["language-culture"])
def get_language_culture(project_id: UUID, session: Session = Depends(get_session)) -> dict[str, object]:
    try:
        config = LanguageCultureService(session).get_config(project_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Language & Culture configuration not found")
    return config


@api.put("/projects/{project_id}/language-culture", tags=["language-culture"])
def save_language_culture(
    project_id: UUID,
    payload: LanguageCultureWrite,
    session: Session = Depends(get_session),
) -> dict[str, object]:
    try:
        return LanguageCultureService(session).save_config(
            project_id,
            languages=payload.languages,
            cultures=payload.cultures,
            contacts=payload.contacts,
            root_lexicon=payload.root_lexicon,
            display_policy=payload.display_policy,
            earth_term_policy=payload.earth_term_policy,
            common_language_id=payload.common_language_id,
            status=payload.status,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@api.post("/projects/{project_id}/language-culture/languages/{language_id}/preview-names", tags=["language-culture"])
def preview_language_names(
    project_id: UUID,
    language_id: str,
    payload: NamePreviewRequest,
    session: Session = Depends(get_session),
) -> dict[str, object]:
    try:
        names = LanguageCultureService(session).preview_names(
            project_id,
            language_id,
            kind=payload.kind,
            count=payload.count,
            seed=payload.seed,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return {"language_id": language_id, "kind": payload.kind, "seed": payload.seed, "names": names}


@api.get("/projects/{project_id}/bible", tags=["writing-room"])
def list_bible(project_id: UUID, session: Session = Depends(get_session)) -> list[dict[str, object]]:
    try:
        return WritingService(session).list_bible(project_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@api.post("/projects/{project_id}/bible", tags=["writing-room"], status_code=status.HTTP_201_CREATED)
def create_bible(project_id: UUID, payload: BibleWrite, session: Session = Depends(get_session)) -> dict[str, object]:
    try:
        return WritingService(session).create_bible(project_id, **payload.model_dump())
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@api.get("/projects/{project_id}/bible/{entity_id}", tags=["writing-room"])
def get_bible(project_id: UUID, entity_id: UUID, session: Session = Depends(get_session)) -> dict[str, object]:
    try:
        return WritingService(session).get_bible(project_id, entity_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@api.put("/projects/{project_id}/bible/{entity_id}", tags=["writing-room"])
def update_bible(project_id: UUID, entity_id: UUID, payload: BibleUpdate, session: Session = Depends(get_session)) -> dict[str, object]:
    try:
        return WritingService(session).update_bible(project_id, entity_id, **payload.model_dump(exclude_unset=True))
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@api.post("/projects/{project_id}/bible/{entity_id}/canon", tags=["writing-room"])
def transition_bible_canon(project_id: UUID, entity_id: UUID, payload: CanonTransitionRequest, session: Session = Depends(get_session)) -> dict[str, object]:
    try:
        return WritingService(session).transition_canon(project_id, entity_id, target_state=payload.target_state, reason=payload.reason)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@api.get("/projects/{project_id}/manuscripts", tags=["writing-room"])
def list_manuscripts(project_id: UUID, session: Session = Depends(get_session)) -> list[dict[str, object]]:
    try:
        return WritingService(session).list_documents(project_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@api.post("/projects/{project_id}/manuscripts", tags=["writing-room"], status_code=status.HTTP_201_CREATED)
def create_manuscript(project_id: UUID, payload: ManuscriptCreate, session: Session = Depends(get_session)) -> dict[str, object]:
    try:
        return WritingService(session).create_document(project_id, **payload.model_dump())
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@api.get("/projects/{project_id}/manuscripts/{document_id}", tags=["writing-room"])
def get_manuscript(project_id: UUID, document_id: UUID, session: Session = Depends(get_session)) -> dict[str, object]:
    try:
        return WritingService(session).get_document(project_id, document_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@api.put("/projects/{project_id}/manuscripts/{document_id}", tags=["writing-room"])
def save_manuscript(project_id: UUID, document_id: UUID, payload: ManuscriptWrite, session: Session = Depends(get_session)) -> dict[str, object]:
    try:
        return WritingService(session).save_document(project_id, document_id, **payload.model_dump())
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@api.get("/projects/{project_id}/manuscripts/{document_id}/revisions", tags=["writing-room"])
def list_manuscript_revisions(project_id: UUID, document_id: UUID, session: Session = Depends(get_session)) -> list[dict[str, object]]:
    try:
        return WritingService(session).list_revisions(project_id, document_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@api.post("/projects/{project_id}/manuscripts/{document_id}/revisions/{revision_id}/restore", tags=["writing-room"])
def restore_manuscript_revision(project_id: UUID, document_id: UUID, revision_id: UUID, session: Session = Depends(get_session)) -> dict[str, object]:
    try:
        return WritingService(session).restore_revision(project_id, document_id, revision_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@api.get("/projects/{project_id}/timeline", tags=["writing-room"])
def list_timeline(project_id: UUID, session: Session = Depends(get_session)) -> list[dict[str, object]]:
    try:
        return WritingService(session).list_timeline(project_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@api.post("/projects/{project_id}/timeline", tags=["writing-room"], status_code=status.HTTP_201_CREATED)
def create_timeline(project_id: UUID, payload: TimelineWrite, session: Session = Depends(get_session)) -> dict[str, object]:
    try:
        return WritingService(session).create_timeline(project_id, **payload.model_dump())
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@api.put("/projects/{project_id}/timeline/{event_id}", tags=["writing-room"])
def update_timeline(project_id: UUID, event_id: UUID, payload: TimelineWrite, session: Session = Depends(get_session)) -> dict[str, object]:
    try:
        return WritingService(session).update_timeline(project_id, event_id, **payload.model_dump())
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


app.include_router(api)
