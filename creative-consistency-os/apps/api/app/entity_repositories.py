from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import EntityAliasModel, EntityMentionModel, EntityRelationModel


class EntityIntelligenceRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_aliases(self, project_id: UUID) -> list[dict[str, object]]:
        rows = self.session.scalars(
            select(EntityAliasModel)
            .where(EntityAliasModel.project_id == str(project_id))
            .order_by(EntityAliasModel.alias)
        ).all()
        return [self._alias_to_dict(row) for row in rows]

    def create_alias(
        self,
        project_id: UUID,
        entity_id: UUID,
        *,
        alias: str,
        normalized_alias: str,
        alias_type: str,
        language_id: str | None,
    ) -> dict[str, object]:
        existing = self.session.scalar(
            select(EntityAliasModel).where(
                EntityAliasModel.entity_id == str(entity_id),
                EntityAliasModel.normalized_alias == normalized_alias,
            )
        )
        if existing is not None:
            return self._alias_to_dict(existing)

        row = EntityAliasModel(
            project_id=str(project_id),
            entity_id=str(entity_id),
            alias=alias,
            normalized_alias=normalized_alias,
            alias_type=alias_type,
            language_id=language_id,
        )
        self.session.add(row)
        self.session.flush()
        return self._alias_to_dict(row)

    def list_mentions(self, project_id: UUID, document_id: UUID) -> list[dict[str, object]]:
        rows = self.session.scalars(
            select(EntityMentionModel)
            .where(
                EntityMentionModel.project_id == str(project_id),
                EntityMentionModel.document_id == str(document_id),
            )
            .order_by(EntityMentionModel.start_offset, EntityMentionModel.end_offset)
        ).all()
        return [self._mention_to_dict(row) for row in rows]

    def replace_mentions(
        self,
        project_id: UUID,
        document_id: UUID,
        mentions: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        self.session.execute(
            delete(EntityMentionModel).where(
                EntityMentionModel.project_id == str(project_id),
                EntityMentionModel.document_id == str(document_id),
            )
        )
        rows: list[EntityMentionModel] = []
        for item in mentions:
            row = EntityMentionModel(
                project_id=str(project_id),
                document_id=str(document_id),
                entity_id=item.get("entity_id"),
                mention_text=str(item["mention_text"]),
                normalized_text=str(item["normalized_text"]),
                start_offset=int(item["start_offset"]),
                end_offset=int(item["end_offset"]),
                resolver_state=str(item["resolver_state"]),
                confidence=int(item["confidence"]),
                candidate_ids_json=json.dumps(item.get("candidate_ids", []), ensure_ascii=False),
                revision_no=int(item["revision_no"]),
                resolution_note=item.get("resolution_note"),
            )
            self.session.add(row)
            rows.append(row)
        self.session.flush()
        return [self._mention_to_dict(row) for row in rows]

    def get_mention(self, project_id: UUID, mention_id: UUID) -> dict[str, object] | None:
        row = self.session.get(EntityMentionModel, str(mention_id))
        if row is None or row.project_id != str(project_id):
            return None
        return self._mention_to_dict(row)

    def resolve_mention(
        self,
        project_id: UUID,
        mention_id: UUID,
        *,
        entity_id: str | None,
        resolver_state: str,
        confidence: int,
        candidate_ids: list[str],
        resolution_note: str | None,
    ) -> dict[str, object] | None:
        row = self.session.get(EntityMentionModel, str(mention_id))
        if row is None or row.project_id != str(project_id):
            return None
        row.entity_id = entity_id
        row.resolver_state = resolver_state
        row.confidence = confidence
        row.candidate_ids_json = json.dumps(candidate_ids, ensure_ascii=False)
        row.resolution_note = resolution_note
        self.session.flush()
        return self._mention_to_dict(row)

    def list_relations(self, project_id: UUID) -> list[dict[str, object]]:
        rows = self.session.scalars(
            select(EntityRelationModel)
            .where(EntityRelationModel.project_id == str(project_id))
            .order_by(EntityRelationModel.relation_type, EntityRelationModel.created_at)
        ).all()
        return [self._relation_to_dict(row) for row in rows]

    def create_relation(
        self,
        project_id: UUID,
        *,
        source_entity_id: UUID,
        target_entity_id: UUID,
        relation_type: str,
        label: str,
        canon_state: str,
        source_type: str,
        attributes: dict[str, object],
    ) -> dict[str, object]:
        row = EntityRelationModel(
            project_id=str(project_id),
            source_entity_id=str(source_entity_id),
            target_entity_id=str(target_entity_id),
            relation_type=relation_type,
            label=label,
            canon_state=canon_state,
            source_type=source_type,
            attributes_json=json.dumps(attributes, ensure_ascii=False),
        )
        self.session.add(row)
        self.session.flush()
        return self._relation_to_dict(row)

    @staticmethod
    def _alias_to_dict(row: EntityAliasModel) -> dict[str, object]:
        return {
            "id": row.id,
            "project_id": row.project_id,
            "entity_id": row.entity_id,
            "alias": row.alias,
            "normalized_alias": row.normalized_alias,
            "alias_type": row.alias_type,
            "language_id": row.language_id,
            "created_at": row.created_at,
        }

    @staticmethod
    def _mention_to_dict(row: EntityMentionModel) -> dict[str, object]:
        return {
            "id": row.id,
            "project_id": row.project_id,
            "document_id": row.document_id,
            "entity_id": row.entity_id,
            "mention_text": row.mention_text,
            "normalized_text": row.normalized_text,
            "start_offset": row.start_offset,
            "end_offset": row.end_offset,
            "resolver_state": row.resolver_state,
            "confidence": row.confidence,
            "candidate_ids": json.loads(row.candidate_ids_json),
            "revision_no": row.revision_no,
            "resolution_note": row.resolution_note,
            "created_at": row.created_at,
        }

    @staticmethod
    def _relation_to_dict(row: EntityRelationModel) -> dict[str, object]:
        return {
            "id": row.id,
            "project_id": row.project_id,
            "source_entity_id": row.source_entity_id,
            "target_entity_id": row.target_entity_id,
            "relation_type": row.relation_type,
            "label": row.label,
            "canon_state": row.canon_state,
            "source_type": row.source_type,
            "attributes": json.loads(row.attributes_json),
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
