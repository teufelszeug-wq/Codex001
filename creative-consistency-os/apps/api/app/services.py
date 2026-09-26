from dataclasses import asdict
from uuid import UUID

from sqlalchemy.orm import Session

from app.catalog import GENRE_CATALOG, IMPORT_FORMATS, WORLD_DNA_SECTIONS, build_recommendations, get_world_builder_catalog
from app.domain import Project, SectionMode, SetupMode, WorldBuilderProfile, WorldBuilderStatus
from app.repositories import ChangeLogRepository, SqlAlchemyProjectRepository, WorldBuilderRepository


class ProjectService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.projects = SqlAlchemyProjectRepository(session)
        self.change_log = ChangeLogRepository(session)

    def list_projects(self) -> list[Project]:
        return self.projects.list()

    def get_project(self, project_id: UUID) -> Project | None:
        return self.projects.get(project_id)

    def create_project(self, title: str) -> Project:
        cleaned = title.strip()
        if not cleaned:
            raise ValueError("Project title must not be empty")
        if len(cleaned) > 200:
            raise ValueError("Project title must be 200 characters or fewer")

        project = self.projects.create(cleaned)
        self.change_log.record_project_created(project.id, project.title)
        self.session.commit()
        return project


class WorldBuilderService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.projects = SqlAlchemyProjectRepository(session)
        self.world_builder = WorldBuilderRepository(session)
        self.change_log = ChangeLogRepository(session)

    @staticmethod
    def catalog() -> dict[str, object]:
        return get_world_builder_catalog()

    def get_profile(self, project_id: UUID) -> WorldBuilderProfile | None:
        if self.projects.get(project_id) is None:
            raise LookupError("Project not found")
        return self.world_builder.get(project_id)

    def save_profile(
        self,
        project_id: UUID,
        *,
        setup_mode: str,
        selected_genres: list[str],
        genre_weights: dict[str, int],
        custom_genres: list[dict[str, object]],
        section_modes: dict[str, str],
        section_notes: dict[str, str],
        import_format: str | None,
        import_notes: str | None,
        status: str,
    ) -> WorldBuilderProfile:
        if self.projects.get(project_id) is None:
            raise LookupError("Project not found")

        allowed_genres = {item["key"] for item in GENRE_CATALOG}
        allowed_sections = {item["key"] for item in WORLD_DNA_SECTIONS}
        allowed_import_formats = {item["key"] for item in IMPORT_FORMATS}

        if setup_mode not in {mode.value for mode in SetupMode}:
            raise ValueError("Unknown setup mode")
        if status not in {item.value for item in WorldBuilderStatus}:
            raise ValueError("Unknown world builder status")

        selected_genres = list(dict.fromkeys(selected_genres))
        unknown_genres = set(selected_genres) - allowed_genres
        if unknown_genres:
            raise ValueError(f"Unknown genre: {sorted(unknown_genres)[0]}")

        cleaned_custom: list[dict[str, object]] = []
        seen_custom: set[str] = set()
        for item in custom_genres:
            name = str(item.get("name", "")).strip()
            weight = int(item.get("weight", 50))
            if not name or len(name) > 80:
                raise ValueError("Custom genre name must be 1-80 characters")
            if not 0 <= weight <= 100:
                raise ValueError("Genre weight must be between 0 and 100")
            lowered = name.casefold()
            if lowered in seen_custom:
                continue
            seen_custom.add(lowered)
            cleaned_custom.append({"name": name, "weight": weight})

        if not selected_genres and not cleaned_custom:
            raise ValueError("Select at least one genre or add a custom genre")

        if set(genre_weights) != set(selected_genres):
            raise ValueError("Genre weights must match selected genres")
        if any(not 0 <= int(weight) <= 100 for weight in genre_weights.values()):
            raise ValueError("Genre weight must be between 0 and 100")

        default_mode = {
            SetupMode.QUICK.value: SectionMode.AUTO.value,
            SetupMode.GUIDED.value: SectionMode.AUTO.value,
            SetupMode.FULL.value: SectionMode.MANUAL.value,
            SetupMode.BLANK.value: SectionMode.SKIP.value,
            SetupMode.IMPORT.value: SectionMode.AUTO.value,
        }[setup_mode]
        normalized_section_modes = {key: default_mode for key in allowed_sections}
        for key, mode in section_modes.items():
            if key not in allowed_sections:
                raise ValueError(f"Unknown World DNA section: {key}")
            if mode not in {item.value for item in SectionMode}:
                raise ValueError(f"Unknown section mode: {mode}")
            normalized_section_modes[key] = mode

        normalized_notes: dict[str, str] = {}
        for key, note in section_notes.items():
            if key not in allowed_sections:
                raise ValueError(f"Unknown World DNA section note: {key}")
            cleaned = note.strip()
            if len(cleaned) > 2000:
                raise ValueError("Section note must be 2000 characters or fewer")
            if cleaned:
                normalized_notes[key] = cleaned

        if setup_mode == SetupMode.IMPORT.value:
            if import_format not in allowed_import_formats:
                raise ValueError("Import mode requires a supported import format")
            import_notes = (import_notes or "").strip() or None
            if import_notes and len(import_notes) > 2000:
                raise ValueError("Import note must be 2000 characters or fewer")
        else:
            import_format = None
            import_notes = None

        recommendations = build_recommendations(selected_genres, genre_weights, cleaned_custom)
        before = self.world_builder.get(project_id)

        saved = self.world_builder.upsert(
            project_id,
            setup_mode=setup_mode,
            selected_genres=selected_genres,
            genre_weights={key: int(value) for key, value in genre_weights.items()},
            custom_genres=cleaned_custom,
            section_modes=normalized_section_modes,
            section_notes=normalized_notes,
            import_format=import_format,
            import_notes=import_notes,
            status=status,
            recommendations=recommendations,
        )

        self.change_log.record(
            project_id=project_id,
            event_type="WORLD_BUILDER_CONFIGURED" if before is None else "WORLD_BUILDER_UPDATED",
            entity_type="WorldBuilderProfile",
            entity_id=project_id,
            before=asdict(before) if before else None,
            after=asdict(saved),
            reason="M2 World Builder configuration",
        )
        self.session.commit()
        return saved
