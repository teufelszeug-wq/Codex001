import hashlib
import json
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import BibleEntityModel, ManuscriptDocumentModel, ManuscriptRevisionModel, TimelineEventModel, utcnow


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class BibleRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list(self, project_id: UUID) -> list[dict[str, object]]:
        rows = self.session.scalars(
            select(BibleEntityModel)
            .where(BibleEntityModel.project_id == str(project_id))
            .order_by(BibleEntityModel.entity_type, BibleEntityModel.canonical_name)
        ).all()
        return [self._to_dict(row) for row in rows]

    def get(self, project_id: UUID, entity_id: UUID) -> dict[str, object] | None:
        row = self.session.get(BibleEntityModel, str(entity_id))
        if row is None or row.project_id != str(project_id):
            return None
        return self._to_dict(row)

    def create(self, project_id: UUID, **values: object) -> dict[str, object]:
        row = BibleEntityModel(
            project_id=str(project_id),
            entity_type=str(values["entity_type"]),
            canonical_name=str(values["canonical_name"]),
            summary=str(values.get("summary", "")),
            attributes_json=json.dumps(values.get("attributes", {}), ensure_ascii=False),
            canon_state=str(values.get("canon_state", "DRAFT")),
            source_type=str(values.get("source_type", "AUTHOR")),
            source_ref=values.get("source_ref"),
        )
        self.session.add(row)
        self.session.flush()
        return self._to_dict(row)

    def update(self, project_id: UUID, entity_id: UUID, **values: object) -> dict[str, object] | None:
        row = self.session.get(BibleEntityModel, str(entity_id))
        if row is None or row.project_id != str(project_id):
            return None
        if "entity_type" in values:
            row.entity_type = str(values["entity_type"])
        if "canonical_name" in values:
            row.canonical_name = str(values["canonical_name"])
        if "summary" in values:
            row.summary = str(values["summary"])
        if "attributes" in values:
            row.attributes_json = json.dumps(values["attributes"], ensure_ascii=False)
        if "canon_state" in values:
            row.canon_state = str(values["canon_state"])
        if "source_type" in values:
            row.source_type = str(values["source_type"])
        if "source_ref" in values:
            row.source_ref = None if values["source_ref"] is None else str(values["source_ref"])
        row.updated_at = utcnow()
        self.session.flush()
        return self._to_dict(row)

    @staticmethod
    def _to_dict(row: BibleEntityModel) -> dict[str, object]:
        return {
            "id": row.id,
            "project_id": row.project_id,
            "entity_type": row.entity_type,
            "canonical_name": row.canonical_name,
            "summary": row.summary,
            "attributes": json.loads(row.attributes_json),
            "canon_state": row.canon_state,
            "source_type": row.source_type,
            "source_ref": row.source_ref,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }


class ManuscriptRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list(self, project_id: UUID) -> list[dict[str, object]]:
        rows = self.session.scalars(
            select(ManuscriptDocumentModel)
            .where(ManuscriptDocumentModel.project_id == str(project_id))
            .order_by(ManuscriptDocumentModel.order_index, ManuscriptDocumentModel.created_at)
        ).all()
        return [self._to_dict(row, include_content=False) for row in rows]

    def get(self, project_id: UUID, document_id: UUID) -> dict[str, object] | None:
        row = self.session.get(ManuscriptDocumentModel, str(document_id))
        if row is None or row.project_id != str(project_id):
            return None
        return self._to_dict(row, include_content=True)

    def create(self, project_id: UUID, *, title: str, content: str, order_index: int, status: str) -> dict[str, object]:
        digest = _sha256(content)
        row = ManuscriptDocumentModel(
            project_id=str(project_id),
            title=title,
            content=content,
            content_hash=digest,
            order_index=order_index,
            status=status,
            current_revision=1,
        )
        self.session.add(row)
        self.session.flush()
        self._add_revision(row, "create")
        return self._to_dict(row, include_content=True)

    def save(
        self,
        project_id: UUID,
        document_id: UUID,
        *,
        title: str,
        content: str,
        order_index: int,
        status: str,
        reason: str,
    ) -> tuple[dict[str, object] | None, bool]:
        row = self.session.get(ManuscriptDocumentModel, str(document_id))
        if row is None or row.project_id != str(project_id):
            return None, False
        digest = _sha256(content)
        changed = digest != row.content_hash or title != row.title
        row.title = title
        row.content = content
        row.content_hash = digest
        row.order_index = order_index
        row.status = status
        row.updated_at = utcnow()
        if changed:
            row.current_revision += 1
            self._add_revision(row, reason)
        self.session.flush()
        return self._to_dict(row, include_content=True), changed

    def list_revisions(self, project_id: UUID, document_id: UUID) -> list[dict[str, object]]:
        document = self.session.get(ManuscriptDocumentModel, str(document_id))
        if document is None or document.project_id != str(project_id):
            return []
        rows = self.session.scalars(
            select(ManuscriptRevisionModel)
            .where(ManuscriptRevisionModel.document_id == str(document_id))
            .order_by(ManuscriptRevisionModel.revision_no.desc())
        ).all()
        return [self._revision_to_dict(row) for row in rows]

    def restore(self, project_id: UUID, document_id: UUID, revision_id: UUID) -> dict[str, object] | None:
        document = self.session.get(ManuscriptDocumentModel, str(document_id))
        revision = self.session.get(ManuscriptRevisionModel, str(revision_id))
        if document is None or document.project_id != str(project_id) or revision is None or revision.document_id != str(document_id):
            return None
        document.title = revision.title
        document.content = revision.content
        document.content_hash = revision.content_hash
        document.current_revision += 1
        document.updated_at = utcnow()
        self._add_revision(document, f"restore:{revision.revision_no}")
        self.session.flush()
        return self._to_dict(document, include_content=True)

    def _add_revision(self, document: ManuscriptDocumentModel, reason: str) -> None:
        self.session.add(
            ManuscriptRevisionModel(
                document_id=document.id,
                revision_no=document.current_revision,
                title=document.title,
                content=document.content,
                content_hash=document.content_hash,
                reason=reason[:120] or "save",
            )
        )

    @staticmethod
    def _to_dict(row: ManuscriptDocumentModel, *, include_content: bool) -> dict[str, object]:
        result = {
            "id": row.id,
            "project_id": row.project_id,
            "title": row.title,
            "order_index": row.order_index,
            "status": row.status,
            "content_hash": row.content_hash,
            "current_revision": row.current_revision,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
        if include_content:
            result["content"] = row.content
        return result

    @staticmethod
    def _revision_to_dict(row: ManuscriptRevisionModel) -> dict[str, object]:
        return {
            "id": row.id,
            "document_id": row.document_id,
            "revision_no": row.revision_no,
            "title": row.title,
            "content": row.content,
            "content_hash": row.content_hash,
            "reason": row.reason,
            "created_at": row.created_at,
        }


class TimelineRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list(self, project_id: UUID) -> list[dict[str, object]]:
        rows = self.session.scalars(
            select(TimelineEventModel)
            .where(TimelineEventModel.project_id == str(project_id))
            .order_by(TimelineEventModel.sort_key, TimelineEventModel.created_at)
        ).all()
        return [self._to_dict(row) for row in rows]

    def create(self, project_id: UUID, **values: object) -> dict[str, object]:
        row = TimelineEventModel(
            project_id=str(project_id),
            title=str(values["title"]),
            start_label=str(values.get("start_label", "")),
            end_label=values.get("end_label"),
            sort_key=int(values.get("sort_key", 0)),
            description=str(values.get("description", "")),
            participant_ids_json=json.dumps(values.get("participant_ids", []), ensure_ascii=False),
            canon_state=str(values.get("canon_state", "PLAN")),
            source_type=str(values.get("source_type", "AUTHOR")),
        )
        self.session.add(row)
        self.session.flush()
        return self._to_dict(row)

    def update(self, project_id: UUID, event_id: UUID, **values: object) -> dict[str, object] | None:
        row = self.session.get(TimelineEventModel, str(event_id))
        if row is None or row.project_id != str(project_id):
            return None
        for key in ("title", "start_label", "description", "canon_state", "source_type"):
            if key in values:
                setattr(row, key, str(values[key]))
        if "end_label" in values:
            row.end_label = None if values["end_label"] is None else str(values["end_label"])
        if "sort_key" in values:
            row.sort_key = int(values["sort_key"])
        if "participant_ids" in values:
            row.participant_ids_json = json.dumps(values["participant_ids"], ensure_ascii=False)
        row.updated_at = utcnow()
        self.session.flush()
        return self._to_dict(row)

    @staticmethod
    def _to_dict(row: TimelineEventModel) -> dict[str, object]:
        return {
            "id": row.id,
            "project_id": row.project_id,
            "title": row.title,
            "start_label": row.start_label,
            "end_label": row.end_label,
            "sort_key": row.sort_key,
            "description": row.description,
            "participant_ids": json.loads(row.participant_ids_json),
            "canon_state": row.canon_state,
            "source_type": row.source_type,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
