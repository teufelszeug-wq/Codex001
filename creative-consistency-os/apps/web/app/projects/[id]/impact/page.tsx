"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import {
  dismissImpact,
  getProject,
  listBible,
  listImpactEdges,
  listImpactInvalidations,
  listManuscripts,
  previewEntityImpact,
  refreshImpactGraph,
  revalidateImpact,
  type BibleEntity,
  type ImpactEdge,
  type ImpactInvalidation,
  type ImpactPreview,
  type ManuscriptDocument,
  type Project,
} from "../../../../lib/api";

export default function ImpactPage() {
  const params = useParams<{ id: string }>();
  const projectId = String(params.id);
  const [project, setProject] = useState<Project | null>(null);
  const [entities, setEntities] = useState<BibleEntity[]>([]);
  const [documents, setDocuments] = useState<ManuscriptDocument[]>([]);
  const [edges, setEdges] = useState<ImpactEdge[]>([]);
  const [invalidations, setInvalidations] = useState<ImpactInvalidation[]>([]);
  const [selectedEntity, setSelectedEntity] = useState("");
  const [preview, setPreview] = useState<ImpactPreview | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    let active = true;
    Promise.all([
      getProject(projectId),
      listBible(projectId),
      listManuscripts(projectId),
      listImpactEdges(projectId),
      listImpactInvalidations(projectId),
    ]).then(([p, bible, docs, graphEdges, queue]) => {
      if (!active) return;
      setProject(p);
      setEntities(bible);
      setDocuments(docs);
      setEdges(graphEdges);
      setInvalidations(queue);
      if (bible[0]) setSelectedEntity(bible[0].id);
    }).catch((error) => setMessage(error instanceof Error ? error.message : "Change Impactを読み込めませんでした。"));
    return () => { active = false; };
  }, [projectId]);

  const entityMap = useMemo(() => Object.fromEntries(entities.map((item) => [item.id, item])), [entities]);
  const docMap = useMemo(() => Object.fromEntries(documents.map((item) => [item.id, item])), [documents]);
  const pending = invalidations.filter((item) => item.status === "PENDING");

  async function refreshGraph() {
    setBusy(true);
    try {
      const result = await refreshImpactGraph(projectId);
      setEdges(result.edges);
      setMessage(`Dependency Graphを更新しました（${result.edge_count} edges）。`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Graphを更新できませんでした。");
    } finally {
      setBusy(false);
    }
  }

  async function analyze() {
    if (!selectedEntity) return;
    setBusy(true);
    try {
      setPreview(await previewEntityImpact(projectId, selectedEntity, 4));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "影響範囲を計算できませんでした。");
    } finally {
      setBusy(false);
    }
  }

  async function reloadInvalidations() {
    setInvalidations(await listImpactInvalidations(projectId));
  }

  async function revalidate(item: ImpactInvalidation) {
    setBusy(true);
    try {
      await revalidateImpact(projectId, item.id, 4);
      await reloadInvalidations();
      setMessage("影響範囲の原稿だけを再Lintしました。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "再検証できませんでした。");
    } finally {
      setBusy(false);
    }
  }

  async function dismiss(item: ImpactInvalidation) {
    setBusy(true);
    try {
      await dismissImpact(projectId, item.id, "作者が今回の変更は再検証不要と判断");
      await reloadInvalidations();
      setMessage("Invalidationを作者判断でDISMISSEDにしました。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Dismissできませんでした。");
    } finally {
      setBusy(false);
    }
  }

  if (!project) {
    return <main className="shell narrow"><p>{message || "Change Impact Engineを準備しています…"}</p></main>;
  }

  return (
    <main className="shell impact-shell">
      <div className="overview-head">
        <div>
          <p className="eyebrow">M4.5 · CHANGE IMPACT ENGINE</p>
          <h1>{project.title}</h1>
          <p>設定変更の依存先を追跡し、影響する原稿だけを選択的に再検証します。</p>
        </div>
        <Link className="text-link" href={`/projects/${projectId}`}>← 作品概要</Link>
      </div>

      {message && <p className="notice">{message}</p>}

      <section className="impact-summary">
        <article><span>Edges</span><strong>{edges.length}</strong></article>
        <article><span>Pending</span><strong>{pending.length}</strong></article>
        <article><span>Entities</span><strong>{entities.length}</strong></article>
        <article><span>Documents</span><strong>{documents.length}</strong></article>
      </section>

      <section className="builder-section">
        <div className="section-heading">
          <div><p className="eyebrow">DEPENDENCY GRAPH</p><h2>影響プレビュー</h2></div>
          <button className="secondary" disabled={busy} onClick={refreshGraph} type="button">Graph更新</button>
        </div>
        <div className="impact-controls">
          <select value={selectedEntity} onChange={(event) => setSelectedEntity(event.target.value)}>
            <option value="">変更元エンティティを選択</option>
            {entities.map((entity) => <option key={entity.id} value={entity.id}>{entity.canonical_name} · {entity.canon_state}</option>)}
          </select>
          <button disabled={busy || !selectedEntity} onClick={analyze} type="button">影響範囲を解析</button>
        </div>

        {preview && (
          <div className="impact-preview">
            <div className="impact-root"><strong>{preview.source.name}</strong><span>{preview.source.canon_state}</span></div>
            <div className="impact-columns">
              <div><h3>影響する原稿</h3>{preview.affected_document_ids.map((id) => <p key={id}>{docMap[id]?.title ?? id}</p>)}</div>
              <div><h3>関連エンティティ</h3>{preview.related_entity_ids.map((id) => <p key={id}>{entityMap[id]?.canonical_name ?? id}</p>)}</div>
              <div><h3>Timeline</h3>{preview.affected_timeline_event_ids.map((id) => <p key={id}>{id}</p>)}</div>
            </div>
            <details className="impact-details">
              <summary>Traversal ({preview.edges.length} edges)</summary>
              <div className="edge-list">
                {preview.edges.map((edge, index) => (
                  <div className="edge-row" key={`${edge.id}-${index}`}>
                    <span>{edge.source_type}</span>
                    <strong>{edge.edge_type}</strong>
                    <span>{edge.target_type}</span>
                    <small>depth {edge.depth}</small>
                  </div>
                ))}
              </div>
            </details>
          </div>
        )}
      </section>

      <section className="builder-section">
        <p className="eyebrow">INVALIDATION QUEUE</p>
        <h2>変更後の再検証</h2>
        <p className="helper">Story Bible・Canon・Alias・Relationの変更から自動作成された再検証候補です。作者が実行またはDismissします。</p>
        <div className="invalidation-list">
          {invalidations.map((item) => (
            <article className={`invalidation-row state-${item.status.toLowerCase()}`} key={item.id}>
              <div>
                <strong>{entityMap[item.source_id]?.canonical_name ?? item.source_id}</strong>
                <span>{item.change_kind}</span>
                <small>{item.status}</small>
              </div>
              {item.status === "PENDING" && (
                <div className="invalidation-actions">
                  <button disabled={busy} onClick={() => revalidate(item)} type="button">影響先だけ再Lint</button>
                  <button className="danger-lite" disabled={busy} onClick={() => dismiss(item)} type="button">Dismiss</button>
                </div>
              )}
            </article>
          ))}
          {invalidations.length === 0 && <p className="empty-state">まだInvalidationはありません。</p>}
        </div>
      </section>
    </main>
  );
}
