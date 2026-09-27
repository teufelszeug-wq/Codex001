"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import {
  getLintCatalog,
  getLintConfig,
  getLintRun,
  getProject,
  listLintRuns,
  listManuscripts,
  runDocumentLint,
  runProjectLint,
  saveLintConfig,
  setLintFindingState,
  type LintCatalog,
  type LintConfig,
  type LintFinding,
  type LintRun,
  type ManuscriptDocument,
  type Project,
} from "../../../../lib/api";

const severityOrder = ["error", "warning", "info", "hint"];

export default function LintPage() {
  const params = useParams<{ id: string }>();
  const projectId = String(params.id);
  const [project, setProject] = useState<Project | null>(null);
  const [catalog, setCatalog] = useState<LintCatalog | null>(null);
  const [config, setConfig] = useState<LintConfig | null>(null);
  const [documents, setDocuments] = useState<ManuscriptDocument[]>([]);
  const [selectedDocument, setSelectedDocument] = useState("");
  const [runs, setRuns] = useState<LintRun[]>([]);
  const [activeRun, setActiveRun] = useState<LintRun | null>(null);
  const [severityFilter, setSeverityFilter] = useState("all");
  const [stateFilter, setStateFilter] = useState("all");
  const [newTerm, setNewTerm] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    let active = true;
    Promise.all([
      getProject(projectId),
      getLintCatalog(),
      getLintConfig(projectId),
      listManuscripts(projectId),
      listLintRuns(projectId),
    ]).then(([p, cat, cfg, docs, history]) => {
      if (!active) return;
      setProject(p);
      setCatalog(cat);
      setConfig(cfg);
      setDocuments(docs);
      if (docs[0]) setSelectedDocument(docs[0].id);
      setRuns(history);
      if (history[0]) getLintRun(projectId, history[0].id).then(setActiveRun).catch(() => {});
    }).catch((error) => setMessage(error instanceof Error ? error.message : "Lintを読み込めませんでした。"));
    return () => { active = false; };
  }, [projectId]);

  const findings = useMemo(() => {
    const source = activeRun?.findings ?? [];
    return source
      .filter((item) => severityFilter === "all" || item.severity === severityFilter)
      .filter((item) => stateFilter === "all" || item.finding_state === stateFilter)
      .sort((a, b) => severityOrder.indexOf(a.severity) - severityOrder.indexOf(b.severity));
  }, [activeRun, severityFilter, stateFilter]);

  async function run(scope: "project" | "document") {
    if (scope === "document" && !selectedDocument) return;
    setBusy(true);
    setMessage("");
    try {
      const result = scope === "project"
        ? await runProjectLint(projectId)
        : await runDocumentLint(projectId, selectedDocument);
      setActiveRun(result);
      setRuns(await listLintRuns(projectId));
      setMessage(scope === "project" ? "作品全体のLintが完了しました。" : "選択原稿のLintが完了しました。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Lintを実行できませんでした。");
    } finally {
      setBusy(false);
    }
  }

  async function openRun(runId: string) {
    try {
      setActiveRun(await getLintRun(projectId, runId));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Lint Runを開けませんでした。");
    }
  }

  function builtinConfig(ruleId: string) {
    if (!config || !catalog) return { enabled: true, severity: "warning" };
    const explicit = config.rules.builtins[ruleId];
    const spec = catalog.builtins.find((item) => item.rule_id === ruleId);
    return {
      enabled: explicit?.enabled ?? true,
      severity: explicit?.severity ?? spec?.default_severity ?? "warning",
    };
  }

  async function updateBuiltin(ruleId: string, patch: { enabled?: boolean; severity?: string }) {
    if (!config) return;
    const current = builtinConfig(ruleId);
    const rules: LintConfig["rules"] = {
      ...config.rules,
      builtins: {
        ...config.rules.builtins,
        [ruleId]: { ...current, ...patch },
      },
    };
    try {
      setConfig(await saveLintConfig(projectId, rules));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Lint設定を保存できませんでした。");
    }
  }

  async function addCustomTerm() {
    if (!config || !newTerm.trim()) return;
    const term = newTerm.trim();
    const rules: LintConfig["rules"] = {
      ...config.rules,
      custom_terms: [
        ...config.rules.custom_terms,
        {
          id: `term-${Date.now()}`,
          term,
          severity: "warning",
          enabled: true,
          case_sensitive: false,
          message: `「${term}」を確認してください。`,
        },
      ],
    };
    try {
      setConfig(await saveLintConfig(projectId, rules));
      setNewTerm("");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "禁止語を追加できませんでした。");
    }
  }

  async function removeCustomTerm(id: string) {
    if (!config) return;
    const rules = {
      ...config.rules,
      custom_terms: config.rules.custom_terms.filter((item) => item.id !== id),
    };
    try {
      setConfig(await saveLintConfig(projectId, rules));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "禁止語を削除できませんでした。");
    }
  }

  async function triage(finding: LintFinding, state: LintFinding["finding_state"]) {
    try {
      const updated = await setLintFindingState(projectId, finding.id, state);
      if (activeRun?.findings) {
        setActiveRun({
          ...activeRun,
          findings: activeRun.findings.map((item) => item.id === updated.id ? updated : item),
        });
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Finding状態を変更できませんでした。");
    }
  }

  if (!project || !catalog || !config) {
    return <main className="shell narrow"><p>{message || "Consistency Inspectorを準備しています…"}</p></main>;
  }

  return (
    <main className="shell lint-shell">
      <div className="overview-head">
        <div>
          <p className="eyebrow">M4 · CORE LINT ENGINE</p>
          <h1>{project.title}</h1>
          <p>本文とCanonを診断します。Findingは警告であり、自動修正やCanon変更は行いません。</p>
        </div>
        <Link className="text-link" href={`/projects/${projectId}`}>← 作品概要</Link>
      </div>

      {message && <p className="notice">{message}</p>}

      <section className="lint-runbar">
        <button disabled={busy} onClick={() => run("project")} type="button">作品全体をLint</button>
        <select value={selectedDocument} onChange={(event) => setSelectedDocument(event.target.value)}>
          <option value="">原稿を選択</option>
          {documents.map((doc) => <option key={doc.id} value={doc.id}>{doc.title} · rev.{doc.current_revision}</option>)}
        </select>
        <button className="secondary" disabled={busy || !selectedDocument} onClick={() => run("document")} type="button">選択原稿だけLint</button>
      </section>

      {activeRun && (
        <section className="lint-summary">
          <article><span>Total</span><strong>{activeRun.summary.total}</strong></article>
          {severityOrder.map((severity) => (
            <article key={severity}>
              <span>{severity}</span>
              <strong>{activeRun.summary.by_severity[severity] ?? 0}</strong>
            </article>
          ))}
        </section>
      )}

      <section className="lint-layout">
        <aside className="lint-history">
          <h2>Runs</h2>
          {runs.map((run) => (
            <button className={activeRun?.id === run.id ? "active" : ""} key={run.id} onClick={() => openRun(run.id)} type="button">
              <strong>{run.scope}</strong>
              <small>{run.summary.total} findings</small>
            </button>
          ))}
        </aside>

        <article className="builder-section lint-findings">
          <div className="section-heading">
            <div><p className="eyebrow">DIAGNOSTICS</p><h2>Findings</h2></div>
            <div className="lint-filters">
              <select value={severityFilter} onChange={(event) => setSeverityFilter(event.target.value)}>
                <option value="all">全Severity</option>
                {severityOrder.map((item) => <option key={item} value={item}>{item}</option>)}
              </select>
              <select value={stateFilter} onChange={(event) => setStateFilter(event.target.value)}>
                <option value="all">全状態</option>
                {catalog.finding_states.map((item) => <option key={item} value={item}>{item}</option>)}
              </select>
            </div>
          </div>
          {!activeRun && <p className="empty-state">Lintを実行すると診断結果がここに表示されます。</p>}
          <div className="finding-list">
            {findings.map((finding) => (
              <article className={`finding-row severity-${finding.severity}`} key={finding.id}>
                <div className="finding-copy">
                  <div className="finding-meta">
                    <span>{finding.severity}</span>
                    <span>{finding.category}</span>
                    <span>{finding.rule_id}</span>
                    <span>{finding.finding_state}</span>
                  </div>
                  <strong>{finding.message}</strong>
                  {finding.start_offset !== null && <small>text offset {finding.start_offset}–{finding.end_offset}</small>}
                </div>
                <div className="finding-actions">
                  <button className="secondary" onClick={() => triage(finding, "ACKNOWLEDGED")} type="button">確認済み</button>
                  <button className="secondary" onClick={() => triage(finding, "RESOLVED")} type="button">解決済み</button>
                  <button className="danger-lite" onClick={() => triage(finding, "IGNORED")} type="button">無視</button>
                </div>
              </article>
            ))}
          </div>
        </article>
      </section>

      <section className="builder-section">
        <p className="eyebrow">RULE POLICY</p>
        <h2>ルール設定</h2>
        <div className="rule-list">
          {catalog.builtins.map((rule) => {
            const current = builtinConfig(rule.rule_id);
            return (
              <div className="rule-row" key={rule.rule_id}>
                <label className="rule-toggle">
                  <input type="checkbox" checked={current.enabled} onChange={(event) => updateBuiltin(rule.rule_id, { enabled: event.target.checked })} />
                  <strong>{rule.rule_id}</strong>
                </label>
                <div><span>{rule.category}</span><p>{rule.description}</p></div>
                <select value={current.severity} onChange={(event) => updateBuiltin(rule.rule_id, { severity: event.target.value })}>
                  {catalog.severities.map((severity) => <option key={severity} value={severity}>{severity}</option>)}
                </select>
              </div>
            );
          })}
        </div>

        <div className="subpanel">
          <h3>プロジェクト禁止語</h3>
          <p className="helper">M5のEarth-Origin GuardもこのCore Lintの拡張ポイントを利用できます。</p>
          <div className="inline-fields resolver-input">
            <input value={newTerm} onChange={(event) => setNewTerm(event.target.value)} placeholder="例：ダージリン" />
            <button onClick={addCustomTerm} type="button">追加</button>
          </div>
          <div className="chip-row">
            {config.rules.custom_terms.map((term) => (
              <button className="chip" key={term.id} onClick={() => removeCustomTerm(term.id)} type="button">
                {term.term} · {term.severity} ×
              </button>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}
