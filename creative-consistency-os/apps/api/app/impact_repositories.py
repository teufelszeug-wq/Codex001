from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import DependencyEdgeModel, ImpactInvalidationModel, utcnow


class ImpactRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def replace_edges(self, project_id: UUID, edges: list[dict[str, object]]) -> list[dict[str, object]]:
        self.session.execute(
            delete(DependencyEdgeModel).where(DependencyEdgeModel.project_id == str(project_id))
        )
        rows: list[DependencyEdgeModel] = []
        for item in edges:
            row = DependencyEdgeModel(
                project_id=str(project_id),
                source_type=str(item["source_type"]),
                source_id=str(item["source_id"]),
                target_type=str(item["target_type"]),
                target_id=str(item["target_id"]),
                edge_type=str(item["edge_type"]),
                detail_json=json.dumps(item.get("detail", {}), ensure_ascii=False, default=str),
                refreshed_at=utcnow(),
            )
            self.session.add(row)
            rows.append(row)
        self.session.flush()
        return [self._edge_to_dict(row) for row in rows]

    def list_edges(self, project_id: UUID) -> list[dict[str, object]]:
        rows = self.session.scalars(
            select(DependencyEdgeModel)
            .where(DependencyEdgeModel.project_id == str(project_id))
            .order_by(
                DependencyEdgeModel.source_type,
                DependencyEdgeModel.source_id,
                DependencyEdgeModel.edge_type,
            )
        ).all()
        return [self._edge_to_dict(row) for row in rows]

    def queue_invalidation(
        self,
        project_id: UUID,
        *,
        source_type: str,
        source_id: str,
        change_kind: str,
        detail: dict[str, object] | None = None,
    ) -> dict[str, object]:
        row = ImpactInvalidationModel(
            project_id=str(project_id),
            source_type=source_type,
            source_id=source_id,
            change_kind=change_kind,
            status="PENDING",
            detail_json=json.dumps(detail or {}, ensure_ascii=False, default=str),
            result_json="{}",
        )
        self.session.add(row)
        self.session.flush()
        return self._invalidation_to_dict(row)

    def list_invalidations(
        self,
        project_id: UUID,
        *,
        status: str | None = None,
    ) -> list[dict[str, object]]:
        statement = select(ImpactInvalidationModel).where(
            ImpactInvalidationModel.project_id == str(project_id)
        )
        if status:
            statement = statement.where(ImpactInvalidationModel.status == status)
        rows = self.session.scalars(
            statement.order_by(ImpactInvalidationModel.created_at.desc())
        ).all()
        return [self._invalidation_to_dict(row) for row in rows]

    def get_invalidation(
        self,
        project_id: UUID,
        invalidation_id: UUID,
    ) -> dict[str, object] | None:
        row = self.session.get(ImpactInvalidationModel, str(invalidation_id))
        if row is None or row.project_id != str(project_id):
            return None
        return self._invalidation_to_dict(row)

    def resolve_invalidation(
        self,
        project_id: UUID,
        invalidation_id: UUID,
        *,
        status: str,
        result: dict[str, object],
    ) -> dict[str, object] | None:
        row = self.session.get(ImpactInvalidationModel, str(invalidation_id))
        if row is None or row.project_id != str(project_id):
            return None
        row.status = status
        row.result_json = json.dumps(result, ensure_ascii=False, default=str)
        row.resolved_at = datetime.now(timezone.utc)
        self.session.flush()
        return self._invalidation_to_dict(row)

    @staticmethod
    def _edge_to_dict(row: DependencyEdgeModel) -> dict[str, object]:
        return {
            "id": row.id,
            "project_id": row.project_id,
            "source_type": row.source_type,
            "source_id": row.source_id,
            "target_type": row.target_type,
            "target_id": row.target_id,
            "edge_type": row.edge_type,
            "detail": json.loads(row.detail_json),
            "refreshed_at": row.refreshed_at,
        }

    @staticmethod
    def _invalidation_to_dict(row: ImpactInvalidationModel) -> dict[str, object]:
        return {
            "id": row.id,
            "project_id": row.project_id,
            "source_type": row.source_type,
            "source_id": row.source_id,
            "change_kind": row.change_kind,
            "status": row.status,
            "detail": json.loads(row.detail_json),
            "result": json.loads(row.result_json),
            "created_at": row.created_at,
            "resolved_at": row.resolved_at,
        }
