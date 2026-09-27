from uuid import UUID

from sqlalchemy.orm import Session

from app.domain import CanonState, SourceType
from app.repositories import ChangeLogRepository, SqlAlchemyProjectRepository
from app.writing_repositories import BibleRepository, ManuscriptRepository, TimelineRepository


ENTITY_TYPES = {
    "character",
    "place",
    "organization",
    "item",
    "concept",
    "spell",
    "faction",
    "creature",
    "event",
    "other",
}
DOCUMENT_STATUSES = {"draft", "revised", "final", "archived"}
CANON_TRANSITIONS = {
    CanonState.DRAFT.value: {CanonState.PLAN.value, CanonState.CANON.value, CanonState.REJECTED.value, CanonState.ARCHIVED.value},
    CanonState.PLAN.value: {CanonState.CANON.value, CanonState.DEPRECATED.value, CanonState.REJECTED.value},
    CanonState.INFERENCE.value: {CanonState.DRAFT.value, CanonState.PLAN.value, CanonState.CANON.value, CanonState.REJECTED.value},
    CanonState.DISPUTED.value: {CanonState.CANON.value, CanonState.DEPRECATED.value, CanonState.REJECTED.value},
    CanonState.CANON.value: {CanonState.DISPUTED.value, CanonState.DEPRECATED.value, CanonState.ARCHIVED.value},
    CanonState.DEPRECATED.value: {CanonState.CANON.value, CanonState.ARCHIVED.value},
    CanonState.REJECTED.value: {CanonState.DRAFT.value, CanonState.ARCHIVED.value},
    CanonState.ARCHIVED.value: {CanonState.DRAFT.value},
}


class WritingService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.projects = SqlAlchemyProjectRepository(session)
        self.bible = BibleRepository(session)
        self.manuscripts = ManuscriptRepository(session)
        self.timeline = TimelineRepository(session)
        self.change_log = ChangeLogRepository(session)

    def _project_exists(self, project_id: UUID) -> None:
        if self.projects.get(project_id) is None:
            raise LookupError("Project not found")

    def list_bible(self, project_id: UUID) -> list[dict[str, object]]:
        self._project_exists(project_id)
        return self.bible.list(project_id)

    def get_bible(self, project_id: UUID, entity_id: UUID) -> dict[str, object]:
        self._project_exists(project_id)
        entity = self.bible.get(project_id, entity_id)
        if entity is None:
            raise LookupError("Bible entity not found")
        return entity

    def create_bible(
        self,
        project_id: UUID,
        *,
        entity_type: str,
        canonical_name: str,
        summary: str,
        attributes: dict[str, object],
        canon_state: str,
        source_type: str,
        source_ref: str | None,
    ) -> dict[str, object]:
        self._project_exists(project_id)
        entity_type = entity_type.strip().lower()
        canonical_name = canonical_name.strip()
        if entity_type not in ENTITY_TYPES:
            raise ValueError("Unknown Bible entity type")
        if not canonical_name or len(canonical_name) > 200:
            raise ValueError("Canonical name must be 1-200 characters")
        if canon_state not in {state.value for state in CanonState}:
            raise ValueError("Unknown canon state")
        if source_type not in {source.value for source in SourceType}:
            raise ValueError("Unknown source type")
        entity = self.bible.create(
            project_id,
            entity_type=entity_type,
            canonical_name=canonical_name,
            summary=summary.strip()[:12000],
            attributes=attributes,
            canon_state=canon_state,
            source_type=source_type,
            source_ref=source_ref.strip()[:2000] if source_ref else None,
        )
        self.change_log.record(
            project_id=project_id,
            event_type="BIBLE_ENTITY_CREATED",
            entity_type="BibleEntity",
            entity_id=UUID(str(entity["id"])),
            before=None,
            after=entity,
            reason="Story Bible create",
        )
        self.session.commit()
        return entity

    def update_bible(self, project_id: UUID, entity_id: UUID, **values: object) -> dict[str, object]:
        before = self.get_bible(project_id, entity_id)
        if "entity_type" in values:
            value = str(values["entity_type"]).strip().lower()
            if value not in ENTITY_TYPES:
                raise ValueError("Unknown Bible entity type")
            values["entity_type"] = value
        if "canonical_name" in values:
            name = str(values["canonical_name"]).strip()
            if not name or len(name) > 200:
                raise ValueError("Canonical name must be 1-200 characters")
            values["canonical_name"] = name
        if "canon_state" in values and str(values["canon_state"]) != str(before["canon_state"]):
            raise ValueError("Use the explicit Canon transition endpoint to change canon state")
        if "source_type" in values and str(values["source_type"]) not in {source.value for source in SourceType}:
            raise ValueError("Unknown source type")
        updated = self.bible.update(project_id, entity_id, **values)
        if updated is None:
            raise LookupError("Bible entity not found")
        self.change_log.record(
            project_id=project_id,
            event_type="BIBLE_ENTITY_UPDATED",
            entity_type="BibleEntity",
            entity_id=entity_id,
            before=before,
            after=updated,
            reason="Story Bible edit",
        )
        self.session.commit()
        return updated

    def transition_canon(self, project_id: UUID, entity_id: UUID, *, target_state: str, reason: str) -> dict[str, object]:
        before = self.get_bible(project_id, entity_id)
        current = str(before["canon_state"])
        if target_state not in {state.value for state in CanonState}:
            raise ValueError("Unknown target canon state")
        if target_state == current:
            return before
        if target_state not in CANON_TRANSITIONS.get(current, set()):
            raise ValueError(f"Canon transition {current} -> {target_state} is not allowed")
        cleaned_reason = reason.strip()
        if not cleaned_reason:
            raise ValueError("Canon transition requires an author reason")
        updated = self.bible.update(project_id, entity_id, canon_state=target_state)
        if updated is None:
            raise LookupError("Bible entity not found")
        self.change_log.record(
            project_id=project_id,
            event_type="CANON_STATE_CHANGED",
            entity_type="BibleEntity",
            entity_id=entity_id,
            before=before,
            after=updated,
            reason=cleaned_reason[:2000],
        )
        self.session.commit()
        return updated

    def list_documents(self, project_id: UUID) -> list[dict[str, object]]:
        self._project_exists(project_id)
        return self.manuscripts.list(project_id)

    def get_document(self, project_id: UUID, document_id: UUID) -> dict[str, object]:
        self._project_exists(project_id)
        document = self.manuscripts.get(project_id, document_id)
        if document is None:
            raise LookupError("Manuscript document not found")
        return document

    def create_document(
        self,
        project_id: UUID,
        *,
        title: str,
        content: str,
        order_index: int,
        status: str,
    ) -> dict[str, object]:
        self._project_exists(project_id)
        title = title.strip()
        if not title or len(title) > 240:
            raise ValueError("Document title must be 1-240 characters")
        if status not in DOCUMENT_STATUSES:
            raise ValueError("Unknown document status")
        document = self.manuscripts.create(
            project_id,
            title=title,
            content=content,
            order_index=order_index,
            status=status,
        )
        self.change_log.record(
            project_id=project_id,
            event_type="MANUSCRIPT_CREATED",
            entity_type="ManuscriptDocument",
            entity_id=UUID(str(document["id"])),
            before=None,
            after={key: value for key, value in document.items() if key != "content"},
            reason="Writing Room create",
        )
        self.session.commit()
        return document

    def save_document(
        self,
        project_id: UUID,
        document_id: UUID,
        *,
        title: str,
        content: str,
        order_index: int,
        status: str,
        reason: str,
    ) -> dict[str, object]:
        before = self.get_document(project_id, document_id)
        title = title.strip()
        if not title or len(title) > 240:
            raise ValueError("Document title must be 1-240 characters")
        if status not in DOCUMENT_STATUSES:
            raise ValueError("Unknown document status")
        saved, changed = self.manuscripts.save(
            project_id,
            document_id,
            title=title,
            content=content,
            order_index=order_index,
            status=status,
            reason=reason.strip()[:120] or "autosave",
        )
        if saved is None:
            raise LookupError("Manuscript document not found")
        if changed:
            self.change_log.record(
                project_id=project_id,
                event_type="MANUSCRIPT_REVISION_CREATED",
                entity_type="ManuscriptDocument",
                entity_id=document_id,
                before={key: value for key, value in before.items() if key != "content"},
                after={key: value for key, value in saved.items() if key != "content"},
                reason=reason.strip()[:2000] or "autosave",
            )
        self.session.commit()
        return saved

    def list_revisions(self, project_id: UUID, document_id: UUID) -> list[dict[str, object]]:
        self.get_document(project_id, document_id)
        return self.manuscripts.list_revisions(project_id, document_id)

    def restore_revision(self, project_id: UUID, document_id: UUID, revision_id: UUID) -> dict[str, object]:
        before = self.get_document(project_id, document_id)
        restored = self.manuscripts.restore(project_id, document_id, revision_id)
        if restored is None:
            raise LookupError("Revision not found")
        self.change_log.record(
            project_id=project_id,
            event_type="MANUSCRIPT_REVISION_RESTORED",
            entity_type="ManuscriptDocument",
            entity_id=document_id,
            before={key: value for key, value in before.items() if key != "content"},
            after={key: value for key, value in restored.items() if key != "content"},
            reason=f"Restore revision {revision_id}",
        )
        self.session.commit()
        return restored

    def list_timeline(self, project_id: UUID) -> list[dict[str, object]]:
        self._project_exists(project_id)
        return self.timeline.list(project_id)

    def create_timeline(self, project_id: UUID, **values: object) -> dict[str, object]:
        self._project_exists(project_id)
        values = self._validate_timeline_values(values)
        event = self.timeline.create(project_id, **values)
        self.change_log.record(
            project_id=project_id,
            event_type="TIMELINE_EVENT_CREATED",
            entity_type="TimelineEvent",
            entity_id=UUID(str(event["id"])),
            before=None,
            after=event,
            reason="Timeline create",
        )
        self.session.commit()
        return event

    def update_timeline(self, project_id: UUID, event_id: UUID, **values: object) -> dict[str, object]:
        self._project_exists(project_id)
        existing = next((item for item in self.timeline.list(project_id) if item["id"] == str(event_id)), None)
        if existing is None:
            raise LookupError("Timeline event not found")
        values = self._validate_timeline_values({**existing, **values})
        updated = self.timeline.update(project_id, event_id, **values)
        if updated is None:
            raise LookupError("Timeline event not found")
        self.change_log.record(
            project_id=project_id,
            event_type="TIMELINE_EVENT_UPDATED",
            entity_type="TimelineEvent",
            entity_id=event_id,
            before=existing,
            after=updated,
            reason="Timeline edit",
        )
        self.session.commit()
        return updated

    def _validate_timeline_values(self, values: dict[str, object]) -> dict[str, object]:
        title = str(values.get("title", "")).strip()
        if not title or len(title) > 240:
            raise ValueError("Timeline title must be 1-240 characters")
        canon_state = str(values.get("canon_state", CanonState.PLAN.value))
        source_type = str(values.get("source_type", SourceType.AUTHOR.value))
        if canon_state not in {state.value for state in CanonState}:
            raise ValueError("Unknown canon state")
        if source_type not in {source.value for source in SourceType}:
            raise ValueError("Unknown source type")
        participants = values.get("participant_ids", [])
        if not isinstance(participants, list):
            raise ValueError("Timeline participants must be a list")
        for participant_id in participants:
            try:
                UUID(str(participant_id))
            except ValueError as exc:
                raise ValueError("Timeline participant id must be UUID") from exc
        return {
            "title": title,
            "start_label": str(values.get("start_label", ""))[:160],
            "end_label": str(values["end_label"])[:160] if values.get("end_label") else None,
            "sort_key": int(values.get("sort_key", 0)),
            "description": str(values.get("description", ""))[:12000],
            "participant_ids": [str(item) for item in participants],
            "canon_state": canon_state,
            "source_type": source_type,
        }
