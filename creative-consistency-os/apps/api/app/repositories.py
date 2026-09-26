import json
from abc import ABC, abstractmethod
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain import CURRENT_PROJECT_SCHEMA_VERSION, Project, WorldBuilderProfile
from app.models import ChangeLogModel, ProjectModel, WorldBuilderProfileModel, utcnow


class ProjectRepository(ABC):
    @abstractmethod
    def list(self) -> list[Project]: ...

    @abstractmethod
    def get(self, project_id: UUID) -> Project | None: ...

    @abstractmethod
    def create(self, title: str) -> Project: ...


class SqlAlchemyProjectRepository(ProjectRepository):
    def __init__(self, session: Session) -> None:
        self.session = session

    def list(self) -> list[Project]:
        rows = self.session.scalars(select(ProjectModel).order_by(ProjectModel.updated_at.desc())).all()
        return [self._to_domain(row) for row in rows]

    def get(self, project_id: UUID) -> Project | None:
        row = self.session.get(ProjectModel, str(project_id))
        return self._to_domain(row) if row else None

    def create(self, title: str) -> Project:
        row = ProjectModel(title=title.strip(), schema_version=CURRENT_PROJECT_SCHEMA_VERSION)
        self.session.add(row)
        self.session.flush()
        return self._to_domain(row)

    @staticmethod
    def _to_domain(row: ProjectModel) -> Project:
        return Project(
            id=UUID(row.id),
            title=row.title,
            schema_version=row.schema_version,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )


class WorldBuilderRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, project_id: UUID) -> WorldBuilderProfile | None:
        row = self.session.get(WorldBuilderProfileModel, str(project_id))
        return self._to_domain(row) if row else None

    def upsert(
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
        recommendations: dict[str, dict[str, object]],
    ) -> WorldBuilderProfile:
        row = self.session.get(WorldBuilderProfileModel, str(project_id))
        if row is None:
            row = WorldBuilderProfileModel(project_id=str(project_id), setup_mode=setup_mode)
            self.session.add(row)

        row.setup_mode = setup_mode
        row.selected_genres_json = json.dumps(selected_genres, ensure_ascii=False)
        row.genre_weights_json = json.dumps(genre_weights, ensure_ascii=False)
        row.custom_genres_json = json.dumps(custom_genres, ensure_ascii=False)
        row.section_modes_json = json.dumps(section_modes, ensure_ascii=False)
        row.section_notes_json = json.dumps(section_notes, ensure_ascii=False)
        row.import_format = import_format
        row.import_notes = import_notes
        row.status = status
        row.recommendations_json = json.dumps(recommendations, ensure_ascii=False)
        row.wizard_version = 1
        row.updated_at = utcnow()
        self.session.flush()
        return self._to_domain(row)

    @staticmethod
    def _to_domain(row: WorldBuilderProfileModel) -> WorldBuilderProfile:
        return WorldBuilderProfile(
            project_id=UUID(row.project_id),
            setup_mode=row.setup_mode,
            selected_genres=json.loads(row.selected_genres_json),
            genre_weights=json.loads(row.genre_weights_json),
            custom_genres=json.loads(row.custom_genres_json),
            section_modes=json.loads(row.section_modes_json),
            section_notes=json.loads(row.section_notes_json),
            import_format=row.import_format,
            import_notes=row.import_notes,
            status=row.status,
            recommendations=json.loads(row.recommendations_json),
            wizard_version=row.wizard_version,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )


class ChangeLogRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def record(
        self,
        *,
        project_id: UUID,
        event_type: str,
        entity_type: str,
        entity_id: UUID,
        before: object | None,
        after: object | None,
        reason: str,
    ) -> None:
        self.session.add(
            ChangeLogModel(
                project_id=str(project_id),
                event_type=event_type,
                entity_type=entity_type,
                entity_id=str(entity_id),
                before_json=json.dumps(before, ensure_ascii=False, default=str) if before is not None else None,
                after_json=json.dumps(after, ensure_ascii=False, default=str) if after is not None else None,
                reason=reason,
            )
        )

    def record_project_created(self, project_id: UUID, title: str) -> None:
        self.record(
            project_id=project_id,
            event_type="PROJECT_CREATED",
            entity_type="Project",
            entity_id=project_id,
            before=None,
            after={"title": title},
            reason="Project creation",
        )
