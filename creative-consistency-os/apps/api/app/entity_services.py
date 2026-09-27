import re
import unicodedata
from collections import defaultdict
from uuid import UUID

from sqlalchemy.orm import Session

from app.domain import CanonState, SourceType
from app.entity_repositories import EntityIntelligenceRepository
from app.impact_repositories import ImpactRepository
from app.repositories import ChangeLogRepository, SqlAlchemyProjectRepository
from app.writing_repositories import BibleRepository, ManuscriptRepository
from app.writing_services import WritingService


ALIAS_TYPES = {
    "alternate",
    "nickname",
    "title",
    "former_name",
    "translation",
    "epithet",
    "abbreviation",
    "other",
}
RESOLVER_STATES = {"resolved", "ambiguous", "unresolved", "ignored"}
RELATION_TYPES = {
    "family",
    "friend",
    "rival",
    "enemy",
    "romance",
    "member_of",
    "serves",
    "owns",
    "located_in",
    "created_by",
    "uses",
    "knows",
    "allied_with",
    "opposes",
    "custom",
}


def normalize_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold().strip()
    return " ".join(normalized.split())


class EntityIntelligenceService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.projects = SqlAlchemyProjectRepository(session)
        self.bible = BibleRepository(session)
        self.manuscripts = ManuscriptRepository(session)
        self.entities = EntityIntelligenceRepository(session)
        self.change_log = ChangeLogRepository(session)
        self.impact = ImpactRepository(session)

    def _project_exists(self, project_id: UUID) -> None:
        if self.projects.get(project_id) is None:
            raise LookupError("Project not found")

    def list_aliases(self, project_id: UUID) -> list[dict[str, object]]:
        self._project_exists(project_id)
        return self.entities.list_aliases(project_id)

    def add_alias(
        self,
        project_id: UUID,
        entity_id: UUID,
        *,
        alias: str,
        alias_type: str,
        language_id: str | None,
    ) -> dict[str, object]:
        self._project_exists(project_id)
        entity = self.bible.get(project_id, entity_id)
        if entity is None:
            raise LookupError("Bible entity not found")
        alias = alias.strip()
        if not alias or len(alias) > 200:
            raise ValueError("Alias must be 1-200 characters")
        if alias_type not in ALIAS_TYPES:
            raise ValueError("Unknown alias type")
        normalized = normalize_key(alias)
        created = self.entities.create_alias(
            project_id,
            entity_id,
            alias=alias,
            normalized_alias=normalized,
            alias_type=alias_type,
            language_id=language_id.strip()[:120] if language_id else None,
        )
        self.change_log.record(
            project_id=project_id,
            event_type="ENTITY_ALIAS_ADDED",
            entity_type="BibleEntity",
            entity_id=entity_id,
            before=None,
            after=created,
            reason="Entity Intelligence alias",
        )
        self.impact.queue_invalidation(
            project_id,
            source_type="BibleEntity",
            source_id=str(entity_id),
            change_kind="ENTITY_ALIAS_ADDED",
            detail={"alias": created["alias"], "alias_type": created["alias_type"]},
        )
        self.session.commit()
        return created

    def resolve_text(self, project_id: UUID, text: str) -> dict[str, object]:
        self._project_exists(project_id)
        normalized = normalize_key(text)
        if not normalized:
            raise ValueError("Reference text must not be empty")
        index, entities_by_id, _ = self._build_index(project_id)
        candidate_ids = sorted(index.get(normalized, set()))
        if len(candidate_ids) == 1:
            state = "resolved"
            confidence = 100
        elif len(candidate_ids) > 1:
            state = "ambiguous"
            confidence = 60
        else:
            state = "unresolved"
            confidence = 0
        return {
            "text": text,
            "normalized_text": normalized,
            "resolver_state": state,
            "confidence": confidence,
            "candidate_ids": candidate_ids,
            "candidates": [entities_by_id[item] for item in candidate_ids if item in entities_by_id],
        }

    def refresh_mentions(
        self,
        project_id: UUID,
        document_id: UUID,
        *,
        include_candidates: bool,
    ) -> list[dict[str, object]]:
        self._project_exists(project_id)
        document = self.manuscripts.get(project_id, document_id)
        if document is None:
            raise LookupError("Manuscript document not found")
        content = str(document.get("content", ""))
        revision_no = int(document.get("current_revision", 0))
        index, _, forms = self._build_index(project_id)

        occurrences: dict[tuple[int, int, str], dict[str, object]] = {}
        for surface, details in forms.items():
            if not surface:
                continue
            flags = re.IGNORECASE if surface.isascii() else 0
            for match in re.finditer(re.escape(surface), content, flags):
                key = (match.start(), match.end(), match.group(0))
                entry = occurrences.setdefault(
                    key,
                    {"candidate_ids": set(), "has_canonical": False},
                )
                entry["candidate_ids"].update(details["entity_ids"])
                entry["has_canonical"] = bool(entry["has_canonical"] or details["has_canonical"])

        selected: list[dict[str, object]] = []
        occupied: list[tuple[int, int]] = []
        ordered = sorted(occurrences.items(), key=lambda item: (item[0][0], -(item[0][1] - item[0][0])))
        for (start, end, surface), details in ordered:
            if any(start < used_end and end > used_start for used_start, used_end in occupied):
                continue
            candidate_ids = sorted(details["candidate_ids"])
            state = "resolved" if len(candidate_ids) == 1 else "ambiguous"
            selected.append(
                {
                    "entity_id": candidate_ids[0] if len(candidate_ids) == 1 else None,
                    "mention_text": surface,
                    "normalized_text": normalize_key(surface),
                    "start_offset": start,
                    "end_offset": end,
                    "resolver_state": state,
                    "confidence": 100 if len(candidate_ids) == 1 and details["has_canonical"] else (95 if len(candidate_ids) == 1 else 60),
                    "candidate_ids": candidate_ids,
                    "revision_no": revision_no,
                    "resolution_note": "deterministic canonical/alias match",
                }
            )
            occupied.append((start, end))

        if include_candidates:
            candidate_spans = self._extract_candidate_spans(content)
            for start, end, surface, confidence, note in candidate_spans:
                if any(start < used_end and end > used_start for used_start, used_end in occupied):
                    continue
                normalized = normalize_key(surface)
                if not normalized or normalized in index:
                    continue
                selected.append(
                    {
                        "entity_id": None,
                        "mention_text": surface,
                        "normalized_text": normalized,
                        "start_offset": start,
                        "end_offset": end,
                        "resolver_state": "unresolved",
                        "confidence": confidence,
                        "candidate_ids": [],
                        "revision_no": revision_no,
                        "resolution_note": note,
                    }
                )
                occupied.append((start, end))

        selected.sort(key=lambda item: (int(item["start_offset"]), int(item["end_offset"])))
        saved = self.entities.replace_mentions(project_id, document_id, selected)
        self.change_log.record(
            project_id=project_id,
            event_type="ENTITY_MENTIONS_REFRESHED",
            entity_type="ManuscriptDocument",
            entity_id=document_id,
            before=None,
            after={"revision_no": revision_no, "mention_count": len(saved)},
            reason="M3.5 deterministic entity scan",
        )
        self.session.commit()
        return saved

    def list_mentions(self, project_id: UUID, document_id: UUID) -> list[dict[str, object]]:
        self._project_exists(project_id)
        if self.manuscripts.get(project_id, document_id) is None:
            raise LookupError("Manuscript document not found")
        return self.entities.list_mentions(project_id, document_id)

    def resolve_mention(
        self,
        project_id: UUID,
        mention_id: UUID,
        *,
        entity_id: UUID,
        note: str,
    ) -> dict[str, object]:
        self._project_exists(project_id)
        mention = self.entities.get_mention(project_id, mention_id)
        if mention is None:
            raise LookupError("Entity mention not found")
        if self.bible.get(project_id, entity_id) is None:
            raise LookupError("Bible entity not found")
        updated = self.entities.resolve_mention(
            project_id,
            mention_id,
            entity_id=str(entity_id),
            resolver_state="resolved",
            confidence=100,
            candidate_ids=[str(entity_id)],
            resolution_note=note.strip()[:2000] or "author resolved",
        )
        if updated is None:
            raise LookupError("Entity mention not found")
        self.change_log.record(
            project_id=project_id,
            event_type="ENTITY_MENTION_RESOLVED",
            entity_type="EntityMention",
            entity_id=mention_id,
            before=mention,
            after=updated,
            reason=note.strip()[:2000] or "Author resolution",
        )
        self.session.commit()
        return updated

    def ignore_mention(self, project_id: UUID, mention_id: UUID, *, note: str) -> dict[str, object]:
        self._project_exists(project_id)
        mention = self.entities.get_mention(project_id, mention_id)
        if mention is None:
            raise LookupError("Entity mention not found")
        updated = self.entities.resolve_mention(
            project_id,
            mention_id,
            entity_id=None,
            resolver_state="ignored",
            confidence=100,
            candidate_ids=[],
            resolution_note=note.strip()[:2000] or "author ignored",
        )
        if updated is None:
            raise LookupError("Entity mention not found")
        self.change_log.record(
            project_id=project_id,
            event_type="ENTITY_MENTION_IGNORED",
            entity_type="EntityMention",
            entity_id=mention_id,
            before=mention,
            after=updated,
            reason=note.strip()[:2000] or "Author ignored candidate",
        )
        self.session.commit()
        return updated

    def create_entity_from_mention(
        self,
        project_id: UUID,
        mention_id: UUID,
        *,
        entity_type: str,
        summary: str,
    ) -> dict[str, object]:
        self._project_exists(project_id)
        mention = self.entities.get_mention(project_id, mention_id)
        if mention is None:
            raise LookupError("Entity mention not found")
        if mention["resolver_state"] == "ignored":
            raise ValueError("Ignored mention cannot create an entity without resolving it first")

        created = WritingService(self.session).create_bible(
            project_id,
            entity_type=entity_type,
            canonical_name=str(mention["mention_text"]),
            summary=summary,
            attributes={},
            canon_state=CanonState.INFERENCE.value,
            source_type=SourceType.MANUSCRIPT.value,
            source_ref=f"document:{mention['document_id']}@{mention['start_offset']}:{mention['end_offset']}",
        )
        self.entities.resolve_mention(
            project_id,
            mention_id,
            entity_id=str(created["id"]),
            resolver_state="resolved",
            confidence=100,
            candidate_ids=[str(created["id"])],
            resolution_note="author created INFERENCE entity from manuscript mention",
        )
        self.session.commit()
        return created

    def list_relations(self, project_id: UUID) -> list[dict[str, object]]:
        self._project_exists(project_id)
        return self.entities.list_relations(project_id)

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
        self._project_exists(project_id)
        if source_entity_id == target_entity_id:
            raise ValueError("Entity relation cannot point to itself")
        if self.bible.get(project_id, source_entity_id) is None or self.bible.get(project_id, target_entity_id) is None:
            raise LookupError("Relation entity not found")
        relation_type = relation_type.strip().lower()
        if relation_type not in RELATION_TYPES:
            raise ValueError("Unknown relation type")
        if canon_state not in {state.value for state in CanonState}:
            raise ValueError("Unknown canon state")
        if source_type not in {source.value for source in SourceType}:
            raise ValueError("Unknown source type")
        relation = self.entities.create_relation(
            project_id,
            source_entity_id=source_entity_id,
            target_entity_id=target_entity_id,
            relation_type=relation_type,
            label=label.strip()[:240],
            canon_state=canon_state,
            source_type=source_type,
            attributes=attributes,
        )
        self.change_log.record(
            project_id=project_id,
            event_type="ENTITY_RELATION_CREATED",
            entity_type="EntityRelation",
            entity_id=UUID(str(relation["id"])),
            before=None,
            after=relation,
            reason="Entity Intelligence relation",
        )
        self.impact.queue_invalidation(
            project_id,
            source_type="BibleEntity",
            source_id=str(source_entity_id),
            change_kind="ENTITY_RELATION_CREATED",
            detail={"relation_id": relation["id"], "role": "source"},
        )
        self.impact.queue_invalidation(
            project_id,
            source_type="BibleEntity",
            source_id=str(target_entity_id),
            change_kind="ENTITY_RELATION_CREATED",
            detail={"relation_id": relation["id"], "role": "target"},
        )
        self.session.commit()
        return relation

    def _build_index(
        self,
        project_id: UUID,
    ) -> tuple[dict[str, set[str]], dict[str, dict[str, object]], dict[str, dict[str, object]]]:
        bible_entities = self.bible.list(project_id)
        aliases = self.entities.list_aliases(project_id)
        index: dict[str, set[str]] = defaultdict(set)
        entities_by_id = {str(item["id"]): item for item in bible_entities}
        forms: dict[str, dict[str, object]] = {}

        for entity in bible_entities:
            entity_id = str(entity["id"])
            surface = str(entity["canonical_name"])
            normalized = normalize_key(surface)
            if normalized:
                index[normalized].add(entity_id)
                bucket = forms.setdefault(surface, {"entity_ids": set(), "has_canonical": False})
                bucket["entity_ids"].add(entity_id)
                bucket["has_canonical"] = True

        for alias in aliases:
            entity_id = str(alias["entity_id"])
            surface = str(alias["alias"])
            normalized = normalize_key(surface)
            if normalized:
                index[normalized].add(entity_id)
                bucket = forms.setdefault(surface, {"entity_ids": set(), "has_canonical": False})
                bucket["entity_ids"].add(entity_id)

        return index, entities_by_id, forms

    @staticmethod
    def _extract_candidate_spans(content: str) -> list[tuple[int, int, str, int, str]]:
        candidates: dict[tuple[int, int], tuple[int, int, str, int, str]] = {}

        for match in re.finditer(r"《([^》]{2,40})》", content):
            start, end = match.span(1)
            surface = match.group(1).strip()
            if surface:
                candidates[(start, end)] = (start, end, surface, 60, "bracketed term candidate")

        for match in re.finditer(r"(?<![ァ-ヴー])([ァ-ヴー][ァ-ヴー・＝ー\-]{2,39})(?![ァ-ヴー])", content):
            start, end = match.span(1)
            surface = match.group(1).strip("・＝ー-")
            if len(surface) >= 3:
                adjusted_end = start + len(surface)
                candidates.setdefault(
                    (start, adjusted_end),
                    (start, adjusted_end, surface, 35, "katakana proper-noun candidate"),
                )

        for match in re.finditer(r"\b([A-Z][A-Za-z][A-Za-z'\-]{1,39})\b", content):
            start, end = match.span(1)
            surface = match.group(1)
            candidates.setdefault(
                (start, end),
                (start, end, surface, 30, "latin proper-noun candidate"),
            )

        return sorted(candidates.values(), key=lambda item: (item[0], -(item[1] - item[0])))
