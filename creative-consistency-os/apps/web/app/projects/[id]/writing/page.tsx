"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  createBible,
  createManuscript,
  createTimeline,
  getManuscript,
  getProject,
  listBible,
  listManuscriptRevisions,
  listManuscripts,
  listTimeline,
  restoreManuscriptRevision,
  saveManuscript,
  transitionBibleCanon,
  type BibleEntity,
  type ManuscriptDocument,
  type ManuscriptRevision,
  type Project,
  type TimelineEvent,
} from "../../../../lib/api";

type Draft = {
  title: string;
  content: string;
  order_index: number;
  status: string;
};

export default function WritingRoomPage() {
  const params = useParams<{ id: string }>();
  const projectId = String(params.id);
  const [project, setProject] = useState<Project | null>(null);
  const [documents, setDocuments] = useState<ManuscriptDocument[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [draft, setDraft] = useState<Draft>({ title: "", content: "", order_index: 0, status: "draft" });
  const [revisions, setRevisions] = useState<ManuscriptRevision[]>([]);
  const [bible, setBible] = useState<BibleEntity[]>([]);
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [message, setMessage] = useState("");
  const [saveState, setSaveState] = useState("未保存");
  const [newEntity, setNewEntity] = useState({ type: "character", name: "", summary: "" });
  const [newEvent, setNewEvent] = useState({ title: "", start: "" });
  const lastSaved = useRef("");

  useEffect(() => {
    let active = true;
    Promise.all([
      getProject(projectId),
      listManuscripts(projectId),
      listBible(projectId),
      listTimeline(projectId),
    ]).then(([p, docs, entities, events]) => {
      if (!active) return;
      setProject(p);
      setDocuments(docs);
      setBible(entities);
      setTimeline(events);
      if (docs.length > 0) setSelectedId(docs[0].id);
    }).catch((error) => setMessage(error instanceof Error ? error.message : "読み込みに失敗しました。"));
    return () => { active = false; };
  }, [projectId]);

  useEffect(() => {
    if (!selectedId) return;
    let active = true;
    Promise.all([
      getManuscript(projectId, selectedId),
      listManuscriptRevisions(projectId, selectedId),
    ]).then(([doc, revs]) => {
      if (!active) return;
      const next = {
        title: doc.title,
        content: doc.content ?? "",
        order_index: doc.order_index,
        status: doc.status,
      };
      setDraft(next);
      lastSaved.current = JSON.stringify(next);
      setRevisions(revs);
      setSaveState("保存済み");
    }).catch((error) => setMessage(error instanceof Error ? error.message : "原稿を開けませんでした。"));
    return () => { active = false; };
  }, [projectId, selectedId]);

  useEffect(() => {
    if (!selectedId) return;
    const signature = JSON.stringify(draft);
    if (signature === lastSaved.current) return;
    setSaveState("入力中…");
    const timer = window.setTimeout(async () => {
      setSaveState("保存中…");
      try {
        const saved = await saveManuscript(projectId, selectedId, { ...draft, reason: "autosave" });
        lastSaved.current = signature;
        setDocuments((current) => current.map((item) => item.id === saved.id ? { ...item, ...saved } : item));
        setRevisions(await listManuscriptRevisions(projectId, selectedId));
        setSaveState("自動保存済み");
      } catch (error) {
        setSaveState("保存エラー");
        setMessage(error instanceof Error ? error.message : "自動保存できませんでした。");
      }
    }, 1200);
    return () => window.clearTimeout(timer);
  }, [draft, projectId, selectedId]);

  const charCount = draft.content.length;
  const lineCount = useMemo(() => draft.content ? draft.content.split(/\n/).length : 0, [draft.content]);

  async function addDocument() {
    try {
      const created = await createManuscript(projectId, {
        title: `新規章 ${documents.length + 1}`,
        content: "",
        order_index: documents.length,
        status: "draft",
      });
      setDocuments((current) => [...current, created]);
      setSelectedId(created.id);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "章を作成できませんでした。");
    }
  }

  async function addBibleEntity() {
    if (!newEntity.name.trim()) return;
    try {
      const created = await createBible(projectId, {
        entity_type: newEntity.type,
        canonical_name: newEntity.name.trim(),
        summary: newEntity.summary,
        attributes: {},
        canon_state: "DRAFT",
        source_type: "AUTHOR",
      });
      setBible((current) => [...current, created]);
      setNewEntity({ type: "character", name: "", summary: "" });
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "設定を登録できませんでした。");
    }
  }

  async function promote(entity: BibleEntity) {
    try {
      const updated = await transitionBibleCanon(
        projectId,
        entity.id,
        "CANON",
        "Writing Roomで作者が明示的に承認",
      );
      setBible((current) => current.map((item) => item.id === updated.id ? updated : item));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Canonへ昇格できませんでした。");
    }
  }

  async function addTimelineEvent() {
    if (!newEvent.title.trim()) return;
    try {
      const created = await createTimeline(projectId, {
        title: newEvent.title.trim(),
        start_label: newEvent.start,
        sort_key: timeline.length * 10,
        participant_ids: [],
        canon_state: "PLAN",
        source_type: "AUTHOR",
      });
      setTimeline((current) => [...current, created]);
      setNewEvent({ title: "", start: "" });
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "時系列イベントを追加できませんでした。");
    }
  }

  async function restore(revision: ManuscriptRevision) {
    if (!selectedId) return;
    try {
      const restored = await restoreManuscriptRevision(projectId, selectedId, revision.id);
      const next = {
        title: restored.title,
        content: restored.content ?? "",
        order_index: restored.order_index,
        status: restored.status,
      };
      setDraft(next);
      lastSaved.current = JSON.stringify(next);
      setRevisions(await listManuscriptRevisions(projectId, selectedId));
      setSaveState(`Revision ${revision.revision_no} を復元`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Revisionを復元できませんでした。");
    }
  }

  if (!project) {
    return <main className="shell narrow"><p>{message || "Writing Roomを準備しています…"}</p></main>;
  }

  return (
    <main className="shell writing-shell">
      <div className="overview-head">
        <div>
          <p className="eyebrow">M3 · BIBLE + WRITING ROOM</p>
          <h1>{project.title}</h1>
          <p>本文・設定・時系列を同じ作品コンテキストで管理します。生成・抽出候補は作者の承認なしにCanonへ入りません。</p>
        </div>
        <Link className="text-link" href={`/projects/${projectId}`}>← 作品概要</Link>
      </div>

      {message && <p className="notice">{message}</p>}

      <section className="writing-layout">
        <aside className="document-sidebar">
          <div className="section-heading compact">
            <h2>原稿</h2>
            <button onClick={addDocument} type="button">＋</button>
          </div>
          <div className="document-list">
            {documents.map((document) => (
              <button
                className={`document-item ${selectedId === document.id ? "active" : ""}`}
                key={document.id}
                onClick={() => setSelectedId(document.id)}
                type="button"
              >
                <strong>{document.title}</strong>
                <small>rev.{document.current_revision} · {document.status}</small>
              </button>
            ))}
          </div>
        </aside>

        <article className="editor-panel">
          {selectedId ? (
            <>
              <div className="editor-meta">
                <input
                  className="editor-title"
                  value={draft.title}
                  onChange={(event) => setDraft((current) => ({ ...current, title: event.target.value }))}
                />
                <select value={draft.status} onChange={(event) => setDraft((current) => ({ ...current, status: event.target.value }))}>
                  <option value="draft">Draft</option>
                  <option value="revised">Revised</option>
                  <option value="final">Final</option>
                  <option value="archived">Archived</option>
                </select>
                <span className="save-state">{saveState}</span>
              </div>
              <textarea
                className="manuscript-editor"
                value={draft.content}
                onChange={(event) => setDraft((current) => ({ ...current, content: event.target.value }))}
                placeholder="ここから本文を書き始めます。"
              />
              <div className="editor-footer">
                <span>{charCount.toLocaleString()}文字</span>
                <span>{lineCount.toLocaleString()}行</span>
                <span>1.2秒後に自動保存</span>
              </div>
              <details className="revision-panel">
                <summary>Revision履歴 ({revisions.length})</summary>
                <div className="revision-list">
                  {revisions.map((revision) => (
                    <div className="revision-row" key={revision.id}>
                      <span>rev.{revision.revision_no}</span>
                      <span>{revision.reason}</span>
                      <button className="secondary" onClick={() => restore(revision)} type="button">復元</button>
                    </div>
                  ))}
                </div>
              </details>
            </>
          ) : (
            <div className="empty-state">左の＋から最初の章を作成してください。</div>
          )}
        </article>
      </section>

      <section className="m3-grid">
        <article className="builder-section">
          <p className="eyebrow">STORY BIBLE</p>
          <h2>設定Bible</h2>
          <div className="form-grid two">
            <label>種類
              <select value={newEntity.type} onChange={(event) => setNewEntity((current) => ({ ...current, type: event.target.value }))}>
                {["character","place","organization","item","concept","spell","faction","creature","event","other"].map((type) => <option key={type} value={type}>{type}</option>)}
              </select>
            </label>
            <label>正式名称
              <input value={newEntity.name} onChange={(event) => setNewEntity((current) => ({ ...current, name: event.target.value }))} />
            </label>
          </div>
          <textarea value={newEntity.summary} onChange={(event) => setNewEntity((current) => ({ ...current, summary: event.target.value }))} placeholder="要約・設定" />
          <button onClick={addBibleEntity} type="button">DRAFTとして登録</button>

          <div className="bible-list">
            {bible.map((entity) => (
              <div className="bible-row" key={entity.id}>
                <div>
                  <strong>{entity.canonical_name}</strong>
                  <small>{entity.entity_type} · {entity.canon_state}</small>
                  <p>{entity.summary || "説明なし"}</p>
                </div>
                {entity.canon_state !== "CANON" && entity.canon_state !== "ARCHIVED" && (
                  <button onClick={() => promote(entity)} type="button">作者承認 → CANON</button>
                )}
              </div>
            ))}
          </div>
        </article>

        <article className="builder-section">
          <p className="eyebrow">TIMELINE</p>
          <h2>基本時系列</h2>
          <div className="form-grid two">
            <label>イベント<input value={newEvent.title} onChange={(event) => setNewEvent((current) => ({ ...current, title: event.target.value }))} /></label>
            <label>時点<input value={newEvent.start} onChange={(event) => setNewEvent((current) => ({ ...current, start: event.target.value }))} placeholder="第3日 / 王暦102年…" /></label>
          </div>
          <button onClick={addTimelineEvent} type="button">PLANとして追加</button>
          <div className="timeline-list">
            {timeline.map((event) => (
              <div className="timeline-row" key={event.id}>
                <span>{event.start_label || "未設定"}</span>
                <div><strong>{event.title}</strong><small>{event.canon_state}</small></div>
              </div>
            ))}
          </div>
        </article>
      </section>
    </main>
  );
}
