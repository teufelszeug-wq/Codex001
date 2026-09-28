from __future__ import annotations

from collections import deque
import unicodedata
from uuid import UUID

from sqlalchemy.orm import Session

from app.entity_repositories import EntityIntelligenceRepository
from app.impact_repositories import ImpactRepository
from app.isekai_repositories import IsekaiPackRepository
from app.lint_services import LintService
from app.repositories import ChangeLogRepository, SqlAlchemyProjectRepository
from app.writing_repositories import BibleRepository, ManuscriptRepository, TimelineRepository


INVALIDATION_STATES = {"PENDING", "REVALIDATED", "DISMISSED"}


def normalize_surface(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


class ImpactService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.projects = SqlAlchemyProjectRepository(session)
        self.bible = BibleRepository(session)
        self.manuscripts = ManuscriptRepository(session)
        self.timeline = TimelineRepository(session)
        self.entities = EntityIntelligenceRepository(session)
        self.impact = ImpactRepository(session)
        self.isekai = IsekaiPackRepository(session)
        self.change_log = ChangeLogRepository(session)

    def _project_exists(self, project_id: UUID) -> None:
        if self.projects.get(project_id) is None:
            raise LookupError("Project not found")

    def refresh_graph(self, project_id: UUID) -> dict[str, object]:
        self._project_exists(project_id)
        edges: list[dict[str, object]] = []
        bible = self.bible.list(project_id)
        aliases = self.entities.list_aliases(project_id)
        isekai_pack = self.isekai.get(project_id)
        surface_index: list[tuple[str, str, str]] = []
        for entity in bible:
            surface_index.append((str(entity["id"]), str(entity["canonical_name"]), "canonical"))
        for alias in aliases:
            surface_index.append((str(alias["entity_id"]), str(alias["alias"]), "alias"))

        for alias in aliases:
            edges.append({
                "source_type": "BibleEntity",
                "source_id": alias["entity_id"],
                "target_type": "EntityAlias",
                "target_id": alias["id"],
                "edge_type": "has_alias",
                "detail": {"alias": alias["alias"], "alias_type": alias["alias_type"]},
            })

        for document in self.manuscripts.list(project_id):
            document_id = UUID(str(document["id"]))
            full_document = self.manuscripts.get(project_id, document_id)
            normalized_content = normalize_surface(str(full_document.get("content", ""))) if full_document else ""
            for entity_id, surface, surface_kind in surface_index:
                normalized_surface = normalize_surface(surface)
                if normalized_surface and normalized_surface in normalized_content:
                    edges.append({
                        "source_type": "BibleEntity",
                        "source_id": entity_id,
                        "target_type": "ManuscriptDocument",
                        "target_id": str(document_id),
                        "edge_type": "surface_reference",
                        "detail": {
                            "surface": surface,
                            "surface_kind": surface_kind,
                            "document_revision": document["current_revision"],
                        },
                    })
            if isekai_pack is not None:
                for index, replacement in enumerate(isekai_pack.get("replacements", [])):
                    if not isinstance(replacement, dict):
                        continue
                    source_place_id = replacement.get("source_place_entity_id")
                    world_term = str(replacement.get("world_term", "")).strip()
                    earth_term = str(replacement.get("earth_term", "")).strip()
                    replacement_id = f"isekai-replacement:{index}"
                    if source_place_id:
                        edges.append({
                            "source_type": "BibleEntity",
                            "source_id": str(source_place_id),
                            "target_type": "IsekaiReplacement",
                            "target_id": replacement_id,
                            "edge_type": "isekai_replacement_source",
                            "detail": {
                                "earth_term": earth_term,
                                "world_term": world_term,
                            },
                        })
                    normalized_doc = normalized_content
                    matched_surface = next(
                        (
                            surface for surface in (world_term, earth_term)
                            if surface and normalize_surface(surface) in normalized_doc
                        ),
                        None,
                    )
                    if matched_surface:
                        edges.append({
                            "source_type": "IsekaiReplacement",
                            "source_id": replacement_id,
                            "target_type": "ManuscriptDocument",
                            "target_id": str(document_id),
                            "edge_type": "isekai_replacement_usage",
                            "detail": {
                                "surface": matched_surface,
                                "earth_term": earth_term,
                                "world_term": world_term,
                                "document_revision": document["current_revision"],
                            },
                        })

            for mention in self.entities.list_mentions(project_id, document_id):
                if mention.get("entity_id"):
                    edges.append({
                        "source_type": "BibleEntity",
                        "source_id": mention["entity_id"],
                        "target_type": "EntityMention",
                        "target_id": mention["id"],
                        "edge_type": "resolved_mention",
                        "detail": {
                            "mention_text": mention["mention_text"],
                            "revision_no": mention["revision_no"],
                            "resolver_state": mention["resolver_state"],
                        },
                    })
                for candidate_id in mention.get("candidate_ids", []):
                    if candidate_id == mention.get("entity_id"):
                        continue
                    edges.append({
                        "source_type": "BibleEntity",
                        "source_id": candidate_id,
                        "target_type": "EntityMention",
                        "target_id": mention["id"],
                        "edge_type": "candidate_mention",
                        "detail": {
                            "mention_text": mention["mention_text"],
                            "revision_no": mention["revision_no"],
                            "resolver_state": mention["resolver_state"],
                        },
                    })
                edges.append({
                    "source_type": "EntityMention",
                    "source_id": mention["id"],
                    "target_type": "ManuscriptDocument",
                    "target_id": str(document_id),
                    "edge_type": "appears_in",
                    "detail": {
                        "revision_no": mention["revision_no"],
                        "start_offset": mention["start_offset"],
                        "end_offset": mention["end_offset"],
                    },
                })

        for event in self.timeline.list(project_id):
            for participant_id in event["participant_ids"]:
                edges.append({
                    "source_type": "BibleEntity",
                    "source_id": participant_id,
                    "target_type": "TimelineEvent",
                    "target_id": event["id"],
                    "edge_type": "participates_in",
                    "detail": {
                        "title": event["title"],
                        "canon_state": event["canon_state"],
                        "sort_key": event["sort_key"],
                    },
                })

        for relation in self.entities.list_relations(project_id):
            relation_id = relation["id"]
            source_id = relation["source_entity_id"]
            target_id = relation["target_entity_id"]
            edges.extend([
                {
                    "source_type": "BibleEntity",
                    "source_id": source_id,
                    "target_type": "EntityRelation",
                    "target_id": relation_id,
                    "edge_type": "relation_source",
                    "detail": {
                        "relation_type": relation["relation_type"],
                        "label": relation["label"],
                        "canon_state": relation["canon_state"],
                    },
                },
                {
                    "source_type": "BibleEntity",
                    "source_id": target_id,
                    "target_type": "EntityRelation",
                    "target_id": relation_id,
                    "edge_type": "relation_target",
                    "detail": {
                        "relation_type": relation["relation_type"],
                        "label": relation["label"],
                        "canon_state": relation["canon_state"],
                    },
                },
                {
                    "source_type": "EntityRelation",
                    "source_id": relation_id,
                    "target_type": "BibleEntity",
                    "target_id": source_id,
                    "edge_type": "relation_endpoint",
                    "detail": {"role": "source"},
                },
                {
                    "source_type": "EntityRelation",
                    "source_id": relation_id,
                    "target_type": "BibleEntity",
                    "target_id": target_id,
                    "edge_type": "relation_endpoint",
                    "detail": {"role": "target"},
                },
            ])

        # M6 structured-reference dependencies.
        # These edges are derived from author-authored Bible attributes and remain useful
        # even when the corresponding genre pack is temporarily disabled.
        for entity in bible:
            entity_id = str(entity["id"])
            attributes = entity.get("attributes", {})
            if not isinstance(attributes, dict):
                continue

            noble = attributes.get("ln_noble")
            if isinstance(noble, dict):
                house_id = str(noble.get("house_entity_id", "")).strip()
                if house_id:
                    edges.append({
                        "source_type": "BibleEntity",
                        "source_id": house_id,
                        "target_type": "BibleEntity",
                        "target_id": entity_id,
                        "edge_type": "noble_house_member",
                        "detail": {
                            "member_name": entity["canonical_name"],
                            "rank": noble.get("rank"),
                        },
                    })

            palace = attributes.get("ln_palace")
            if isinstance(palace, dict):
                faction_id = str(palace.get("faction_entity_id", "")).strip()
                if faction_id:
                    edges.append({
                        "source_type": "BibleEntity",
                        "source_id": faction_id,
                        "target_type": "BibleEntity",
                        "target_id": entity_id,
                        "edge_type": "palace_faction_member",
                        "detail": {
                            "member_name": entity["canonical_name"],
                            "rank": palace.get("rank"),
                        },
                    })

            access = attributes.get("ln_palace_access")
            if isinstance(access, dict):
                for source_key, edge_type in (
                    ("actor_entity_id", "palace_access_actor"),
                    ("place_entity_id", "palace_access_place"),
                ):
                    source_id = str(access.get(source_key, "")).strip()
                    if source_id:
                        edges.append({
                            "source_type": "BibleEntity",
                            "source_id": source_id,
                            "target_type": "BibleEntity",
                            "target_id": entity_id,
                            "edge_type": edge_type,
                            "detail": {"event_name": entity["canonical_name"]},
                        })

            info = attributes.get("ln_information_access")
            if isinstance(info, dict):
                actor_id = str(info.get("actor_entity_id", "")).strip()
                if actor_id:
                    edges.append({
                        "source_type": "BibleEntity",
                        "source_id": actor_id,
                        "target_type": "BibleEntity",
                        "target_id": entity_id,
                        "edge_type": "palace_information_actor",
                        "detail": {
                            "event_name": entity["canonical_name"],
                            "fact_key": info.get("fact_key"),
                        },
                    })

            transition = attributes.get("ln_relationship_transition")
            if isinstance(transition, dict):
                for source_key, edge_type in (
                    ("source_entity_id", "romcom_transition_source"),
                    ("target_entity_id", "romcom_transition_target"),
                ):
                    source_id = str(transition.get(source_key, "")).strip()
                    if source_id:
                        edges.append({
                            "source_type": "BibleEntity",
                            "source_id": source_id,
                            "target_type": "BibleEntity",
                            "target_id": entity_id,
                            "edge_type": edge_type,
                            "detail": {
                                "event_name": entity["canonical_name"],
                                "from_stage": transition.get("from_stage"),
                                "to_stage": transition.get("to_stage"),
                            },
                        })

            schedule = attributes.get("ln_schedule")
            if isinstance(schedule, dict) and isinstance(schedule.get("participant_ids"), list):
                for participant_id in schedule["participant_ids"]:
                    source_id = str(participant_id).strip()
                    if source_id:
                        edges.append({
                            "source_type": "BibleEntity",
                            "source_id": source_id,
                            "target_type": "BibleEntity",
                            "target_id": entity_id,
                            "edge_type": "romcom_schedule_participant",
                            "detail": {
                                "event_name": entity["canonical_name"],
                                "day_key": schedule.get("day_key"),
                                "start_minute": schedule.get("start_minute"),
                                "end_minute": schedule.get("end_minute"),
                            },
                        })

        unique: dict[tuple[str, str, str, str, str], dict[str, object]] = {}
        for edge in edges:
            key = (
                str(edge["source_type"]),
                str(edge["source_id"]),
                str(edge["target_type"]),
                str(edge["target_id"]),
                str(edge["edge_type"]),
            )
            unique[key] = edge

        saved = self.impact.replace_edges(project_id, list(unique.values()))
        self.change_log.record(
            project_id=project_id,
            event_type="DEPENDENCY_GRAPH_REFRESHED",
            entity_type="Project",
            entity_id=project_id,
            before=None,
            after={"edge_count": len(saved)},
            reason="M4.5 dependency graph refresh",
        )
        self.session.commit()
        return {"project_id": str(project_id), "edge_count": len(saved), "edges": saved}

    def list_edges(self, project_id: UUID) -> list[dict[str, object]]:
        self._project_exists(project_id)
        return self.impact.list_edges(project_id)

    def preview_entity(
        self,
        project_id: UUID,
        entity_id: UUID,
        *,
        max_depth: int = 4,
        refresh: bool = True,
    ) -> dict[str, object]:
        self._project_exists(project_id)
        entity = self.bible.get(project_id, entity_id)
        if entity is None:
            raise LookupError("Bible entity not found")
        if max_depth < 1 or max_depth > 6:
            raise ValueError("max_depth must be between 1 and 6")
        if refresh:
            self.refresh_graph(project_id)

        edges = self.impact.list_edges(project_id)
        adjacency: dict[tuple[str, str], list[dict[str, object]]] = {}
        for edge in edges:
            adjacency.setdefault(
                (str(edge["source_type"]), str(edge["source_id"])),
                [],
            ).append(edge)

        start = ("BibleEntity", str(entity_id))
        queue: deque[tuple[tuple[str, str], int]] = deque([(start, 0)])
        visited = {start}
        impacted_nodes: list[dict[str, object]] = []
        traversed_edges: list[dict[str, object]] = []

        while queue:
            node, depth = queue.popleft()
            if depth >= max_depth:
                continue
            for edge in adjacency.get(node, []):
                traversed_edges.append({**edge, "depth": depth + 1})
                target = (str(edge["target_type"]), str(edge["target_id"]))
                impacted_nodes.append({
                    "type": target[0],
                    "id": target[1],
                    "depth": depth + 1,
                    "via": edge["edge_type"],
                    "detail": edge["detail"],
                })
                if target not in visited and target[0] not in {"ManuscriptDocument", "TimelineEvent", "EntityAlias"}:
                    visited.add(target)
                    queue.append((target, depth + 1))

        affected_documents = sorted({
            str(item["id"])
            for item in impacted_nodes
            if item["type"] == "ManuscriptDocument"
        })
        affected_timeline = sorted({
            str(item["id"])
            for item in impacted_nodes
            if item["type"] == "TimelineEvent"
        })
        related_entities = sorted({
            str(item["id"])
            for item in impacted_nodes
            if item["type"] == "BibleEntity" and item["id"] != str(entity_id)
        })

        return {
            "project_id": str(project_id),
            "source": {
                "type": "BibleEntity",
                "id": str(entity_id),
                "name": entity["canonical_name"],
                "canon_state": entity["canon_state"],
            },
            "max_depth": max_depth,
            "affected_document_ids": affected_documents,
            "affected_timeline_event_ids": affected_timeline,
            "related_entity_ids": related_entities,
            "nodes": impacted_nodes,
            "edges": traversed_edges,
        }

    def list_invalidations(
        self,
        project_id: UUID,
        *,
        status: str | None = None,
    ) -> list[dict[str, object]]:
        self._project_exists(project_id)
        if status is not None and status not in INVALIDATION_STATES:
            raise ValueError("Unknown invalidation status")
        return self.impact.list_invalidations(project_id, status=status)

    def revalidate(
        self,
        project_id: UUID,
        invalidation_id: UUID,
        *,
        max_depth: int = 4,
    ) -> dict[str, object]:
        self._project_exists(project_id)
        invalidation = self.impact.get_invalidation(project_id, invalidation_id)
        if invalidation is None:
            raise LookupError("Impact invalidation not found")
        if invalidation["status"] != "PENDING":
            return invalidation

        if invalidation["source_type"] in {"IsekaiPackConfig", "LNGenrePackConfig"}:
            lint_service = LintService(self.session)
            run = lint_service.run_project(project_id)
            reason = (
                "Isekai Pack policy changed"
                if invalidation["source_type"] == "IsekaiPackConfig"
                else "LN Genre Pack policy changed"
            )
            result = {
                "scope": "project",
                "reason": reason,
                "lint_runs": [{
                    "run_id": run["id"],
                    "document_id": None,
                    "summary": run["summary"],
                }],
            }
            updated = self.impact.resolve_invalidation(
                project_id,
                invalidation_id,
                status="REVALIDATED",
                result=result,
            )
            if updated is None:
                raise LookupError("Impact invalidation not found")
            self.change_log.record(
                project_id=project_id,
                event_type="CHANGE_IMPACT_REVALIDATED",
                entity_type="ImpactInvalidation",
                entity_id=invalidation_id,
                before=invalidation,
                after=updated,
                reason="Genre pack global policy revalidation",
            )
            self.session.commit()
            return updated

        if invalidation["source_type"] != "BibleEntity":
            raise ValueError("Unsupported invalidation source type")

        preview = self.preview_entity(
            project_id,
            UUID(str(invalidation["source_id"])),
            max_depth=max_depth,
            refresh=True,
        )
        lint_runs: list[dict[str, object]] = []
        lint_service = LintService(self.session)
        for document_id in preview["affected_document_ids"]:
            run = lint_service.run_document(project_id, UUID(str(document_id)))
            lint_runs.append({
                "run_id": run["id"],
                "document_id": document_id,
                "summary": run["summary"],
            })

        structure_run = lint_service.run_structure(project_id)
        lint_runs.append({
            "run_id": structure_run["id"],
            "document_id": None,
            "scope": "structure",
            "summary": structure_run["summary"],
        })
        result = {
            "affected_document_ids": preview["affected_document_ids"],
            "affected_timeline_event_ids": preview["affected_timeline_event_ids"],
            "related_entity_ids": preview["related_entity_ids"],
            "lint_runs": lint_runs,
        }
        updated = self.impact.resolve_invalidation(
            project_id,
            invalidation_id,
            status="REVALIDATED",
            result=result,
        )
        if updated is None:
            raise LookupError("Impact invalidation not found")
        self.change_log.record(
            project_id=project_id,
            event_type="CHANGE_IMPACT_REVALIDATED",
            entity_type="ImpactInvalidation",
            entity_id=invalidation_id,
            before=invalidation,
            after=updated,
            reason="M4.5 selective revalidation",
        )
        self.session.commit()
        return updated

    def dismiss(
        self,
        project_id: UUID,
        invalidation_id: UUID,
        *,
        reason: str,
    ) -> dict[str, object]:
        self._project_exists(project_id)
        invalidation = self.impact.get_invalidation(project_id, invalidation_id)
        if invalidation is None:
            raise LookupError("Impact invalidation not found")
        if invalidation["status"] != "PENDING":
            return invalidation
        cleaned = reason.strip()
        if not cleaned:
            raise ValueError("Dismiss reason is required")
        updated = self.impact.resolve_invalidation(
            project_id,
            invalidation_id,
            status="DISMISSED",
            result={"reason": cleaned[:2000]},
        )
        if updated is None:
            raise LookupError("Impact invalidation not found")
        self.session.commit()
        return updated
