from __future__ import annotations

import difflib
import hashlib
import json
import unicodedata
from collections import Counter, defaultdict
from uuid import UUID

from sqlalchemy.orm import Session

from app.domain import CanonState
from app.entity_repositories import EntityIntelligenceRepository
from app.lint_repositories import LintRepository
from app.repositories import ChangeLogRepository, SqlAlchemyProjectRepository
from app.writing_repositories import BibleRepository, ManuscriptRepository, TimelineRepository


SEVERITIES = {"hint", "info", "warning", "error"}
FINDING_STATES = {"OPEN", "ACKNOWLEDGED", "IGNORED", "RESOLVED"}

BUILTIN_RULES: dict[str, dict[str, object]] = {
    "mention_index_missing": {
        "category": "entity",
        "default_severity": "info",
        "description": "本文があるのにEntity Mention indexがまだ作られていない。",
    },
    "mention_freshness": {
        "category": "entity",
        "default_severity": "warning",
        "description": "Entity Mentionが現在の本文Revisionより古い。",
    },
    "mention_span_mismatch": {
        "category": "integrity",
        "default_severity": "error",
        "description": "現在RevisionのMention spanと本文文字列が一致しない。",
    },
    "unresolved_mention": {
        "category": "entity",
        "default_severity": "warning",
        "description": "現在Revisionに未解決の固有表現候補がある。",
    },
    "ambiguous_mention": {
        "category": "entity",
        "default_severity": "warning",
        "description": "本文中の呼称が複数エンティティに一致する。",
    },
    "reference_inference": {
        "category": "canon",
        "default_severity": "info",
        "description": "本文がINFERENCE状態の設定を参照している。",
    },
    "reference_disputed": {
        "category": "canon",
        "default_severity": "error",
        "description": "本文がDISPUTED状態の設定を参照している。",
    },
    "reference_deprecated": {
        "category": "canon",
        "default_severity": "warning",
        "description": "本文がDEPRECATED状態の設定を参照している。",
    },
    "reference_inactive": {
        "category": "canon",
        "default_severity": "error",
        "description": "本文がARCHIVED/REJECTED状態の設定を参照している。",
    },
    "canonical_name_collision": {
        "category": "naming",
        "default_severity": "warning",
        "description": "同一正規化名を持つBibleエンティティが複数ある。",
    },
    "alias_collision": {
        "category": "naming",
        "default_severity": "warning",
        "description": "同じ別名が複数エンティティへ割り当てられている。",
    },
    "canon_timeline_noncanon_participant": {
        "category": "timeline",
        "default_severity": "warning",
        "description": "CANON時系列イベントが非CANON参加者を参照している。",
    },
    "canon_relation_noncanon_endpoint": {
        "category": "relation",
        "default_severity": "warning",
        "description": "CANON関係の端点が非CANONエンティティになっている。",
    },
    "possible_name_drift": {
        "category": "semantic",
        "default_severity": "hint",
        "description": "未解決呼称が既知の正式名・別名の表記揺れ候補かを字面類似度から提示する。",
    },
}


def normalize_key(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().strip().split())


def fingerprint(parts: list[object]) -> str:
    payload = json.dumps(parts, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class LintService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.projects = SqlAlchemyProjectRepository(session)
        self.bible = BibleRepository(session)
        self.manuscripts = ManuscriptRepository(session)
        self.timeline = TimelineRepository(session)
        self.entities = EntityIntelligenceRepository(session)
        self.lint = LintRepository(session)
        self.change_log = ChangeLogRepository(session)

    @staticmethod
    def catalog() -> dict[str, object]:
        return {
            "builtins": [
                {
                    "rule_id": rule_id,
                    "category": spec["category"],
                    "default_severity": spec["default_severity"],
                    "description": spec["description"],
                }
                for rule_id, spec in BUILTIN_RULES.items()
            ],
            "severities": ["hint", "info", "warning", "error"],
            "finding_states": ["OPEN", "ACKNOWLEDGED", "IGNORED", "RESOLVED"],
            "config_version": 1,
        }

    def _project_exists(self, project_id: UUID) -> None:
        if self.projects.get(project_id) is None:
            raise LookupError("Project not found")

    def get_config(self, project_id: UUID) -> dict[str, object]:
        self._project_exists(project_id)
        stored = self.lint.get_config(project_id)
        return stored or {
            "project_id": str(project_id),
            "rules": {"builtins": {}, "custom_terms": []},
            "config_version": 1,
            "updated_at": None,
        }

    def save_config(self, project_id: UUID, rules: dict[str, object]) -> dict[str, object]:
        self._project_exists(project_id)
        cleaned = self._validate_config(rules)
        before = self.lint.get_config(project_id)
        saved = self.lint.upsert_config(project_id, cleaned)
        self.change_log.record(
            project_id=project_id,
            event_type="LINT_CONFIG_UPDATED",
            entity_type="LintConfig",
            entity_id=project_id,
            before=before,
            after=saved,
            reason="M4 lint policy update",
        )
        self.session.commit()
        return saved

    def run_document(self, project_id: UUID, document_id: UUID) -> dict[str, object]:
        self._project_exists(project_id)
        document = self.manuscripts.get(project_id, document_id)
        if document is None:
            raise LookupError("Manuscript document not found")
        config = self.get_config(project_id)["rules"]
        findings = self._document_findings(project_id, document, config)
        summary = self._summary(findings)
        run = self.lint.create_run(
            project_id,
            document_id=document_id,
            scope="document",
            document_revision=int(document["current_revision"]),
            findings=findings,
            summary=summary,
        )
        self.change_log.record(
            project_id=project_id,
            event_type="LINT_RUN_COMPLETED",
            entity_type="ManuscriptDocument",
            entity_id=document_id,
            before=None,
            after={"run_id": run["id"], "summary": summary},
            reason="M4 document lint",
        )
        self.session.commit()
        return run

    def run_project(self, project_id: UUID) -> dict[str, object]:
        self._project_exists(project_id)
        config = self.get_config(project_id)["rules"]
        findings: list[dict[str, object]] = []
        for document in self.manuscripts.list(project_id):
            full = self.manuscripts.get(project_id, UUID(str(document["id"])))
            if full is not None:
                findings.extend(self._document_findings(project_id, full, config))
        findings.extend(self._project_findings(project_id, config))
        summary = self._summary(findings)
        run = self.lint.create_run(
            project_id,
            document_id=None,
            scope="project",
            document_revision=None,
            findings=findings,
            summary=summary,
        )
        self.change_log.record(
            project_id=project_id,
            event_type="LINT_RUN_COMPLETED",
            entity_type="Project",
            entity_id=project_id,
            before=None,
            after={"run_id": run["id"], "summary": summary},
            reason="M4 project lint",
        )
        self.session.commit()
        return run

    def list_runs(self, project_id: UUID) -> list[dict[str, object]]:
        self._project_exists(project_id)
        return self.lint.list_runs(project_id)

    def get_run(self, project_id: UUID, run_id: UUID) -> dict[str, object]:
        self._project_exists(project_id)
        run = self.lint.get_run(project_id, run_id)
        if run is None:
            raise LookupError("Lint run not found")
        return run

    def set_finding_state(self, project_id: UUID, finding_id: UUID, state: str) -> dict[str, object]:
        self._project_exists(project_id)
        if state not in FINDING_STATES:
            raise ValueError("Unknown finding state")
        updated = self.lint.set_finding_state(project_id, finding_id, state)
        if updated is None:
            raise LookupError("Lint finding not found")
        self.change_log.record(
            project_id=project_id,
            event_type="LINT_FINDING_STATE_CHANGED",
            entity_type="LintFinding",
            entity_id=finding_id,
            before=None,
            after={"state": state},
            reason="Author lint triage",
        )
        self.session.commit()
        return updated

    def _document_findings(
        self,
        project_id: UUID,
        document: dict[str, object],
        config: dict[str, object],
    ) -> list[dict[str, object]]:
        document_id = str(document["id"])
        revision = int(document["current_revision"])
        content = str(document.get("content", ""))
        mentions = self.entities.list_mentions(project_id, UUID(document_id))
        current_mentions = [item for item in mentions if int(item["revision_no"]) == revision]
        findings: list[dict[str, object]] = []

        if content and not mentions:
            self._append(
                findings,
                config,
                rule_id="mention_index_missing",
                document_id=document_id,
                message="本文は存在しますがEntity Mention indexがありません。Entity Intelligenceで現在Revisionをスキャンしてください。",
                evidence={"document_revision": revision},
            )
        elif mentions and not current_mentions:
            scanned_revisions = sorted({int(item["revision_no"]) for item in mentions})
            self._append(
                findings,
                config,
                rule_id="mention_freshness",
                document_id=document_id,
                message=f"Entity Mentionは旧Revision {scanned_revisions[-1]} の解析結果です。現在はRevision {revision}です。",
                evidence={"document_revision": revision, "mention_revisions": scanned_revisions},
            )

        bible_by_id = {str(item["id"]): item for item in self.bible.list(project_id)}
        known_surfaces: list[tuple[str, str, str]] = []
        for entity in bible_by_id.values():
            known_surfaces.append((
                str(entity["canonical_name"]),
                normalize_key(str(entity["canonical_name"])),
                str(entity["id"]),
            ))
        for alias in self.entities.list_aliases(project_id):
            known_surfaces.append((
                str(alias["alias"]),
                normalize_key(str(alias["alias"])),
                str(alias["entity_id"]),
            ))

        for mention in current_mentions:
            state = str(mention["resolver_state"])
            mention_start = int(mention["start_offset"])
            mention_end = int(mention["end_offset"])
            surface = str(mention["mention_text"])
            current_slice = content[mention_start:mention_end] if 0 <= mention_start <= mention_end <= len(content) else None
            if current_slice != surface:
                self._append(
                    findings,
                    config,
                    rule_id="mention_span_mismatch",
                    document_id=document_id,
                    message=f"現在RevisionのMention spanが本文「{surface}」と一致しません。再スキャンが必要です。",
                    start_offset=mention_start,
                    end_offset=mention_end,
                    evidence={
                        "mention_id": mention["id"],
                        "stored_surface": surface,
                        "current_slice": current_slice,
                        "revision_no": revision,
                    },
                )

            common = {
                "document_id": document_id,
                "start_offset": int(mention["start_offset"]),
                "end_offset": int(mention["end_offset"]),
                "evidence": {
                    "mention_id": mention["id"],
                    "mention_text": mention["mention_text"],
                    "confidence": mention["confidence"],
                    "candidate_ids": mention["candidate_ids"],
                    "revision_no": revision,
                },
            }
            if state == "unresolved":
                self._append(
                    findings,
                    config,
                    rule_id="unresolved_mention",
                    message=f"未解決の固有表現候補「{mention['mention_text']}」があります。",
                    **common,
                )
                normalized_surface = normalize_key(surface)
                best: tuple[float, str, str] | None = None
                for known_surface, normalized_known, entity_id in known_surfaces:
                    if not normalized_surface or not normalized_known or normalized_surface == normalized_known:
                        continue
                    score = difflib.SequenceMatcher(None, normalized_surface, normalized_known).ratio()
                    if score >= 0.82 and (best is None or score > best[0]):
                        best = (score, known_surface, entity_id)
                if best is not None:
                    self._append(
                        findings,
                        config,
                        rule_id="possible_name_drift",
                        document_id=document_id,
                        entity_id=best[2],
                        message=f"「{surface}」は既知名「{best[1]}」の表記揺れ候補です。",
                        start_offset=mention_start,
                        end_offset=mention_end,
                        evidence={
                            "mention_id": mention["id"],
                            "candidate_entity_id": best[2],
                            "candidate_surface": best[1],
                            "similarity": round(best[0], 4),
                            "provider": "deterministic_lexical_similarity_v1",
                        },
                    )
            elif state == "ambiguous":
                self._append(
                    findings,
                    config,
                    rule_id="ambiguous_mention",
                    message=f"「{mention['mention_text']}」は複数のエンティティ候補に一致します。",
                    **common,
                )
            elif state == "resolved" and mention.get("entity_id"):
                entity = bible_by_id.get(str(mention["entity_id"]))
                if entity is None:
                    continue
                canon_state = str(entity["canon_state"])
                common["entity_id"] = str(entity["id"])
                common["evidence"] = {
                    **common["evidence"],
                    "entity_name": entity["canonical_name"],
                    "canon_state": canon_state,
                }
                if canon_state == CanonState.INFERENCE.value:
                    self._append(
                        findings,
                        config,
                        rule_id="reference_inference",
                        message=f"「{entity['canonical_name']}」はINFERENCEのまま本文から参照されています。",
                        **common,
                    )
                elif canon_state == CanonState.DISPUTED.value:
                    self._append(
                        findings,
                        config,
                        rule_id="reference_disputed",
                        message=f"「{entity['canonical_name']}」はDISPUTED状態です。",
                        **common,
                    )
                elif canon_state == CanonState.DEPRECATED.value:
                    self._append(
                        findings,
                        config,
                        rule_id="reference_deprecated",
                        message=f"「{entity['canonical_name']}」はDEPRECATED状態です。",
                        **common,
                    )
                elif canon_state in {CanonState.ARCHIVED.value, CanonState.REJECTED.value}:
                    self._append(
                        findings,
                        config,
                        rule_id="reference_inactive",
                        message=f"「{entity['canonical_name']}」は{canon_state}状態ですが本文から参照されています。",
                        **common,
                    )

        custom_terms = config.get("custom_terms", [])
        if isinstance(custom_terms, list):
            folded_content = content.casefold()
            for index, item in enumerate(custom_terms):
                if not isinstance(item, dict) or item.get("enabled", True) is False:
                    continue
                term = str(item.get("term", "")).strip()
                if not term:
                    continue
                case_sensitive = bool(item.get("case_sensitive", False))
                haystack = content if case_sensitive else folded_content
                needle = term if case_sensitive else term.casefold()
                start = 0
                while True:
                    found = haystack.find(needle, start)
                    if found < 0:
                        break
                    end = found + len(term)
                    rule_id = f"custom_term:{item.get('id') or index}"
                    severity = str(item.get("severity", "warning"))
                    if severity not in SEVERITIES:
                        severity = "warning"
                    findings.append(
                        self._finding(
                            rule_id=rule_id,
                            category="custom",
                            severity=severity,
                            document_id=document_id,
                            entity_id=None,
                            message=str(item.get("message") or f"カスタム禁止語「{term}」が本文に含まれています。"),
                            start_offset=found,
                            end_offset=end,
                            evidence={"term": term, "case_sensitive": case_sensitive},
                        )
                    )
                    start = max(end, found + 1)

        return findings

    def _project_findings(
        self,
        project_id: UUID,
        config: dict[str, object],
    ) -> list[dict[str, object]]:
        findings: list[dict[str, object]] = []
        bible = self.bible.list(project_id)
        bible_by_id = {str(item["id"]): item for item in bible}

        names: dict[str, list[dict[str, object]]] = defaultdict(list)
        for entity in bible:
            names[normalize_key(str(entity["canonical_name"]))].append(entity)
        for normalized, group in names.items():
            if normalized and len(group) > 1:
                ids = [str(item["id"]) for item in group]
                self._append(
                    findings,
                    config,
                    rule_id="canonical_name_collision",
                    message="同一の正規化正式名称を持つBibleエンティティが複数あります: " + " / ".join(str(item["canonical_name"]) for item in group),
                    evidence={"normalized_name": normalized, "entity_ids": ids},
                )

        aliases: dict[str, set[str]] = defaultdict(set)
        alias_surfaces: dict[str, set[str]] = defaultdict(set)
        for alias in self.entities.list_aliases(project_id):
            normalized = str(alias["normalized_alias"])
            aliases[normalized].add(str(alias["entity_id"]))
            alias_surfaces[normalized].add(str(alias["alias"]))
        for normalized, ids in aliases.items():
            if normalized and len(ids) > 1:
                self._append(
                    findings,
                    config,
                    rule_id="alias_collision",
                    message="同じ別名が複数エンティティへ割り当てられています: " + " / ".join(sorted(alias_surfaces[normalized])),
                    evidence={"normalized_alias": normalized, "entity_ids": sorted(ids)},
                )

        for event in self.timeline.list(project_id):
            if str(event["canon_state"]) != CanonState.CANON.value:
                continue
            noncanon = []
            for participant_id in event["participant_ids"]:
                entity = bible_by_id.get(str(participant_id))
                if entity is not None and str(entity["canon_state"]) != CanonState.CANON.value:
                    noncanon.append({"id": entity["id"], "name": entity["canonical_name"], "state": entity["canon_state"]})
            if noncanon:
                self._append(
                    findings,
                    config,
                    rule_id="canon_timeline_noncanon_participant",
                    message=f"CANON時系列「{event['title']}」が非CANON参加者を参照しています。",
                    evidence={"timeline_event_id": event["id"], "participants": noncanon},
                )

        for relation in self.entities.list_relations(project_id):
            if str(relation["canon_state"]) != CanonState.CANON.value:
                continue
            endpoints = [
                bible_by_id.get(str(relation["source_entity_id"])),
                bible_by_id.get(str(relation["target_entity_id"])),
            ]
            noncanon = [
                {"id": item["id"], "name": item["canonical_name"], "state": item["canon_state"]}
                for item in endpoints
                if item is not None and str(item["canon_state"]) != CanonState.CANON.value
            ]
            if noncanon:
                self._append(
                    findings,
                    config,
                    rule_id="canon_relation_noncanon_endpoint",
                    message=f"CANON関係「{relation['label'] or relation['relation_type']}」の端点に非CANON設定があります。",
                    evidence={"relation_id": relation["id"], "endpoints": noncanon},
                )

        return findings

    def _append(
        self,
        findings: list[dict[str, object]],
        config: dict[str, object],
        *,
        rule_id: str,
        message: str,
        document_id: str | None = None,
        entity_id: str | None = None,
        start_offset: int | None = None,
        end_offset: int | None = None,
        evidence: dict[str, object] | None = None,
    ) -> None:
        rule_config = {}
        builtins = config.get("builtins", {})
        if isinstance(builtins, dict):
            candidate = builtins.get(rule_id, {})
            if isinstance(candidate, dict):
                rule_config = candidate
        if rule_config.get("enabled", True) is False:
            return
        spec = BUILTIN_RULES[rule_id]
        severity = str(rule_config.get("severity", spec["default_severity"]))
        if severity not in SEVERITIES:
            severity = str(spec["default_severity"])
        findings.append(
            self._finding(
                rule_id=rule_id,
                category=str(spec["category"]),
                severity=severity,
                document_id=document_id,
                entity_id=entity_id,
                message=message,
                start_offset=start_offset,
                end_offset=end_offset,
                evidence=evidence or {},
            )
        )

    @staticmethod
    def _finding(
        *,
        rule_id: str,
        category: str,
        severity: str,
        document_id: str | None,
        entity_id: str | None,
        message: str,
        start_offset: int | None,
        end_offset: int | None,
        evidence: dict[str, object],
    ) -> dict[str, object]:
        return {
            "rule_id": rule_id,
            "category": category,
            "severity": severity,
            "document_id": document_id,
            "entity_id": entity_id,
            "message": message,
            "start_offset": start_offset,
            "end_offset": end_offset,
            "evidence": evidence,
            "fingerprint": fingerprint([
                rule_id,
                document_id,
                entity_id,
                start_offset,
                end_offset,
                evidence,
            ]),
        }

    @staticmethod
    def _summary(findings: list[dict[str, object]]) -> dict[str, object]:
        severities = Counter(str(item["severity"]) for item in findings)
        categories = Counter(str(item["category"]) for item in findings)
        return {
            "total": len(findings),
            "by_severity": dict(severities),
            "by_category": dict(categories),
        }

    @staticmethod
    def _validate_config(rules: dict[str, object]) -> dict[str, object]:
        builtins = rules.get("builtins", {})
        custom_terms = rules.get("custom_terms", [])
        if not isinstance(builtins, dict):
            raise ValueError("rules.builtins must be an object")
        if not isinstance(custom_terms, list):
            raise ValueError("rules.custom_terms must be a list")

        cleaned_builtins: dict[str, object] = {}
        for rule_id, value in builtins.items():
            if rule_id not in BUILTIN_RULES:
                raise ValueError(f"Unknown builtin lint rule: {rule_id}")
            if not isinstance(value, dict):
                raise ValueError("Builtin lint rule config must be an object")
            severity = str(value.get("severity", BUILTIN_RULES[rule_id]["default_severity"]))
            if severity not in SEVERITIES:
                raise ValueError(f"Unknown lint severity: {severity}")
            cleaned_builtins[rule_id] = {
                "enabled": bool(value.get("enabled", True)),
                "severity": severity,
            }

        cleaned_terms: list[dict[str, object]] = []
        for index, item in enumerate(custom_terms):
            if not isinstance(item, dict):
                raise ValueError("Custom term rule must be an object")
            term = str(item.get("term", "")).strip()
            if not term or len(term) > 200:
                raise ValueError("Custom term must be 1-200 characters")
            severity = str(item.get("severity", "warning"))
            if severity not in SEVERITIES:
                raise ValueError(f"Unknown lint severity: {severity}")
            cleaned_terms.append({
                "id": str(item.get("id") or f"term-{index + 1}")[:100],
                "term": term,
                "severity": severity,
                "enabled": bool(item.get("enabled", True)),
                "case_sensitive": bool(item.get("case_sensitive", False)),
                "message": str(item.get("message", ""))[:1000],
            })

        return {"builtins": cleaned_builtins, "custom_terms": cleaned_terms}
