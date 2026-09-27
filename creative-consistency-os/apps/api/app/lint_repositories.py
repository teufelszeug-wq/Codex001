from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LintFindingModel, LintProjectConfigModel, LintRunModel, utcnow


class LintRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_config(self, project_id: UUID) -> dict[str, object] | None:
        row = self.session.get(LintProjectConfigModel, str(project_id))
        if row is None:
            return None
        return {
            "project_id": row.project_id,
            "rules": json.loads(row.rules_json),
            "config_version": row.config_version,
            "updated_at": row.updated_at,
        }

    def upsert_config(self, project_id: UUID, rules: dict[str, object]) -> dict[str, object]:
        row = self.session.get(LintProjectConfigModel, str(project_id))
        if row is None:
            row = LintProjectConfigModel(project_id=str(project_id))
            self.session.add(row)
        row.rules_json = json.dumps(rules, ensure_ascii=False)
        row.config_version = 1
        row.updated_at = utcnow()
        self.session.flush()
        return {
            "project_id": row.project_id,
            "rules": rules,
            "config_version": row.config_version,
            "updated_at": row.updated_at,
        }

    def create_run(
        self,
        project_id: UUID,
        *,
        document_id: UUID | None,
        scope: str,
        document_revision: int | None,
        findings: list[dict[str, object]],
        summary: dict[str, object],
    ) -> dict[str, object]:
        run = LintRunModel(
            project_id=str(project_id),
            document_id=str(document_id) if document_id else None,
            scope=scope,
            document_revision=document_revision,
            ruleset_version=1,
            status="completed",
            summary_json=json.dumps(summary, ensure_ascii=False),
        )
        self.session.add(run)
        self.session.flush()

        rows: list[LintFindingModel] = []
        for item in findings:
            row = LintFindingModel(
                run_id=run.id,
                project_id=str(project_id),
                document_id=item.get("document_id"),
                entity_id=item.get("entity_id"),
                rule_id=str(item["rule_id"]),
                category=str(item["category"]),
                severity=str(item["severity"]),
                message=str(item["message"]),
                start_offset=item.get("start_offset"),
                end_offset=item.get("end_offset"),
                evidence_json=json.dumps(item.get("evidence", {}), ensure_ascii=False),
                fingerprint=str(item["fingerprint"]),
                finding_state="OPEN",
            )
            self.session.add(row)
            rows.append(row)
        self.session.flush()
        return self._run_to_dict(run, rows)

    def list_runs(self, project_id: UUID, limit: int = 30) -> list[dict[str, object]]:
        rows = self.session.scalars(
            select(LintRunModel)
            .where(LintRunModel.project_id == str(project_id))
            .order_by(LintRunModel.created_at.desc())
            .limit(limit)
        ).all()
        return [self._run_to_dict(row, None) for row in rows]

    def get_run(self, project_id: UUID, run_id: UUID) -> dict[str, object] | None:
        row = self.session.get(LintRunModel, str(run_id))
        if row is None or row.project_id != str(project_id):
            return None
        findings = self.session.scalars(
            select(LintFindingModel)
            .where(LintFindingModel.run_id == row.id)
            .order_by(LintFindingModel.severity, LintFindingModel.rule_id, LintFindingModel.start_offset)
        ).all()
        return self._run_to_dict(row, list(findings))

    def set_finding_state(
        self,
        project_id: UUID,
        finding_id: UUID,
        state: str,
    ) -> dict[str, object] | None:
        row = self.session.get(LintFindingModel, str(finding_id))
        if row is None or row.project_id != str(project_id):
            return None
        row.finding_state = state
        self.session.flush()
        return self._finding_to_dict(row)

    @staticmethod
    def _run_to_dict(run: LintRunModel, findings: list[LintFindingModel] | None) -> dict[str, object]:
        result: dict[str, object] = {
            "id": run.id,
            "project_id": run.project_id,
            "document_id": run.document_id,
            "scope": run.scope,
            "document_revision": run.document_revision,
            "ruleset_version": run.ruleset_version,
            "status": run.status,
            "summary": json.loads(run.summary_json),
            "created_at": run.created_at,
        }
        if findings is not None:
            result["findings"] = [LintRepository._finding_to_dict(row) for row in findings]
        return result

    @staticmethod
    def _finding_to_dict(row: LintFindingModel) -> dict[str, object]:
        return {
            "id": row.id,
            "run_id": row.run_id,
            "project_id": row.project_id,
            "document_id": row.document_id,
            "entity_id": row.entity_id,
            "rule_id": row.rule_id,
            "category": row.category,
            "severity": row.severity,
            "message": row.message,
            "start_offset": row.start_offset,
            "end_offset": row.end_offset,
            "evidence": json.loads(row.evidence_json),
            "fingerprint": row.fingerprint,
            "finding_state": row.finding_state,
            "created_at": row.created_at,
        }
