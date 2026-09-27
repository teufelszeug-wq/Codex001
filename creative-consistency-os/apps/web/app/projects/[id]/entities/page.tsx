"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import {
  addEntityAlias,
  createEntityFromMention,
  createEntityRelation,
  getProject,
  ignoreEntityMention,
  listBible,
  listEntityAliases,
  listEntityMentions,
  listEntityRelations,
  listManuscripts,
  refreshEntityMentions,
  resolveEntityMention,
  resolveEntityReference,
  type BibleEntity,
  type EntityAlias,
  type EntityMention,
  type EntityRelation,
  type ManuscriptDocument,
  type Project,
  type ReferenceResolution,
} from "../../../../lib/api";

const ENTITY_TYPES = ["character","place","organization","item","concept","spell","faction","creature","event","other"];
const RELATION_TYPES = ["family","friend","rival","enemy","romance","member_of","serves","owns","located_in","created_by","uses","knows","allied_with","opposes","custom"];

export default function EntityIntelligencePage() {
  const params = useParams<{ id: string }>();
  const projectId = String(params.id);
  const [project, setProject] = useState<Project | null>(null);
  const [entities, setEntities] = useState<BibleEntity[]>([]);
  const [aliases, setAliases] = useState<EntityAlias[]>([]);
  const [documents, setDocuments] = useState<ManuscriptDocument[]>([]);
  const [selectedDocument, setSelectedDocument] = useState("");
  const [mentions, setMentions] = useState<EntityMention[]>([]);
  const [relations, setRelations] = useState<EntityRelation[]>([]);
  const [message, setMessage] = useState("");
  const [scanning, setScanning] = useState(false);
  const [aliasForm, setAliasForm] = useState({ entityId: "", alias: "", type: "alternate" });
  const [relationForm, setRelationForm] = useState({ source: "", target: "", type: "member_of", label: "" });
  const [resolutionTargets, setResolutionTargets] = useState<Record<string, string>>({});
  const [candidateTypes, setCandidateTypes] = useState<Record<string, string>>({});
  const [query, setQuery] = useState("");
  const [resolution, setResolution] = useState<ReferenceResolution | null>(null);

  useEffect(() => {
    let active = true;
    Promise.all([
      getProject(projectId),
      listBible(projectId),
      listEntityAliases(projectId),
      listManuscripts(projectId),
      listEntityRelations(projectId),
    ]).then(([p, bible, aliasRows, docs, relationRows]) => {
      if (!active) return;
      setProject(p);
      setEntities(bible);
      setAliases(aliasRows);
      setDocuments(docs);
      const firstEntity = bible[0]?.id ?? "";
      setAliasForm((current) => ({ ...current, entityId: current.entityId || firstEntity }));
      setRelationForm((current) => ({
        ...current,
        source: current.source || firstEntity,
        target: current.target || bible[1]?.id || firstEntity,
      }));
      if (docs[0]) setSelectedDocument(docs[0].id);
    }).catch((error) => setMessage(error instanceof Error ? error.message : "読み込みに失敗しました。"));
    return () => { active = false; };
  }, [projectId]);

  useEffect(() => {
    if (!selectedDocument) {
      setMentions([]);
      return;
    }
    listEntityMentions(projectId, selectedDocument)
      .then(setMentions)
      .catch(() => setMentions([]));
  }, [projectId, selectedDocument]);

  const entityMap = useMemo(
    () => Object.fromEntries(entities.map((entity) => [entity.id, entity])),
    [entities],
  );

  async function addAlias() {
    if (!aliasForm.entityId || !aliasForm.alias.trim()) return;
    try {
      const created = await addEntityAlias(projectId, aliasForm.entityId, {
        alias: aliasForm.alias.trim(),
        alias_type: aliasForm.type,
      });
      setAliases((current) => current.some((item) => item.id === created.id) ? current : [...current, created]);
      setAliasForm((current) => ({ ...current, alias: "" }));
      setMessage("別名を登録しました。次回の本文スキャンから解決候補に使われます。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "別名を登録できませんでした。");
    }
  }

  async function scan() {
    if (!selectedDocument) return;
    setScanning(true);
    try {
      setMentions(await refreshEntityMentions(projectId, selectedDocument, true));
      setMessage("現在のRevisionを基準に本文中の固有表現を再解析しました。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "本文を解析できませんでした。");
    } finally {
      setScanning(false);
    }
  }

  async function resolveMention(mention: EntityMention) {
    const entityId = resolutionTargets[mention.id] || mention.candidate_ids[0] || entities[0]?.id;
    if (!entityId) return;
    try {
      const updated = await resolveEntityMention(projectId, mention.id, entityId, "Entity Intelligence画面で作者が解決");
      setMentions((current) => current.map((item) => item.id === updated.id ? updated : item));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "参照を解決できませんでした。");
    }
  }

  async function ignoreMention(mention: EntityMention) {
    try {
      const updated = await ignoreEntityMention(projectId, mention.id, "作者が固有エンティティではないと判断");
      setMentions((current) => current.map((item) => item.id === updated.id ? updated : item));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "候補を無視できませんでした。");
    }
  }

  async function createFromMention(mention: EntityMention) {
    try {
      const created = await createEntityFromMention(
        projectId,
        mention.id,
        candidateTypes[mention.id] || "other",
        "本文中の未解決候補から作者操作で作成。",
      );
      setEntities((current) => [...current, created]);
      if (selectedDocument) setMentions(await listEntityMentions(projectId, selectedDocument));
      setMessage(`${created.canonical_name} をINFERENCEとしてBibleへ追加しました。Canonではありません。`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "候補から設定を作れませんでした。");
    }
  }

  async function addRelation() {
    if (!relationForm.source || !relationForm.target) return;
    try {
      const created = await createEntityRelation(projectId, {
        source_entity_id: relationForm.source,
        target_entity_id: relationForm.target,
        relation_type: relationForm.type,
        label: relationForm.label,
        canon_state: "PLAN",
        source_type: "AUTHOR",
        attributes: {},
      });
      setRelations((current) => [...current, created]);
      setRelationForm((current) => ({ ...current, label: "" }));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "関係を作成できませんでした。");
    }
  }

  async function quickResolve() {
    if (!query.trim()) return;
    try {
      setResolution(await resolveEntityReference(projectId, query.trim()));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "参照候補を検索できませんでした。");
    }
  }

  if (!project) {
    return <main className="shell narrow"><p>{message || "Entity Intelligenceを準備しています…"}</p></main>;
  }

  return (
    <main className="shell entity-shell">
      <div className="overview-head">
        <div>
          <p className="eyebrow">M3.5 · ENTITY INTELLIGENCE</p>
          <h1>{project.title}</h1>
          <p>名称・別名・本文中の出現箇所・曖昧参照・関係グラフを管理します。未解決候補から作る設定はINFERENCEで止まり、作者承認なしにCanonへ昇格しません。</p>
        </div>
        <Link className="text-link" href={`/projects/${projectId}`}>← 作品概要</Link>
      </div>

      {message && <p className="notice">{message}</p>}

      <section className="entity-dashboard">
        <article className="builder-section">
          <p className="eyebrow">ALIASES</p>
          <h2>名称・別名辞書</h2>
          {entities.length === 0 ? (
            <p className="empty-state">先にWriting RoomのStory Bibleへエンティティを登録してください。</p>
          ) : (
            <>
              <div className="form-grid three">
                <label>対象
                  <select value={aliasForm.entityId} onChange={(event) => setAliasForm((current) => ({ ...current, entityId: event.target.value }))}>
                    {entities.map((entity) => <option key={entity.id} value={entity.id}>{entity.canonical_name}</option>)}
                  </select>
                </label>
                <label>別名
                  <input value={aliasForm.alias} onChange={(event) => setAliasForm((current) => ({ ...current, alias: event.target.value }))} placeholder="愛称・旧名・称号・翻訳名…" />
                </label>
                <label>種別
                  <select value={aliasForm.type} onChange={(event) => setAliasForm((current) => ({ ...current, type: event.target.value }))}>
                    {["alternate","nickname","title","former_name","translation","epithet","abbreviation","other"].map((type) => <option key={type} value={type}>{type}</option>)}
                  </select>
                </label>
              </div>
              <button onClick={addAlias} type="button">別名を追加</button>
            </>
          )}
          <div className="alias-list">
            {aliases.map((alias) => (
              <div className="alias-row" key={alias.id}>
                <strong>{alias.alias}</strong>
                <span>→ {entityMap[alias.entity_id]?.canonical_name ?? "不明"}</span>
                <small>{alias.alias_type}</small>
              </div>
            ))}
          </div>
        </article>

        <article className="builder-section">
          <p className="eyebrow">REFERENCE RESOLVER</p>
          <h2>参照を即時確認</h2>
          <div className="inline-fields resolver-input">
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="本文中の呼び名を入力" />
            <button onClick={quickResolve} type="button">照合</button>
          </div>
          {resolution && (
            <div className={`resolution-card ${resolution.resolver_state}`}>
              <strong>{resolution.text}</strong>
              <span>{resolution.resolver_state} · confidence {resolution.confidence}</span>
              <small>{resolution.candidates.map((item) => item.canonical_name).join(" / ") || "候補なし"}</small>
            </div>
          )}
        </article>
      </section>

      <section className="builder-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">MENTION GRAPH</p>
            <h2>本文エンティティ検出</h2>
          </div>
          <button disabled={!selectedDocument || scanning} onClick={scan} type="button">{scanning ? "解析中…" : "現在Revisionをスキャン"}</button>
        </div>
        <label className="block-label">原稿
          <select value={selectedDocument} onChange={(event) => setSelectedDocument(event.target.value)}>
            <option value="">原稿を選択</option>
            {documents.map((document) => <option key={document.id} value={document.id}>{document.title} · rev.{document.current_revision}</option>)}
          </select>
        </label>
        <p className="helper">既知の正式名称・別名は決定論的に照合します。未知語は《括弧語》、長めのカタカナ語、Latin proper nameを低信頼候補として提示します。</p>

        <div className="mention-list">
          {mentions.map((mention) => (
            <article className={`mention-row ${mention.resolver_state}`} key={mention.id}>
              <div className="mention-main">
                <strong>{mention.mention_text}</strong>
                <small>offset {mention.start_offset}–{mention.end_offset} · rev.{mention.revision_no}</small>
                <span>{mention.resolver_state} · confidence {mention.confidence}</span>
                {mention.entity_id && <b>→ {entityMap[mention.entity_id]?.canonical_name ?? mention.entity_id}</b>}
              </div>
              {(mention.resolver_state === "unresolved" || mention.resolver_state === "ambiguous") && (
                <div className="mention-actions">
                  <select
                    value={resolutionTargets[mention.id] || mention.candidate_ids[0] || ""}
                    onChange={(event) => setResolutionTargets((current) => ({ ...current, [mention.id]: event.target.value }))}
                  >
                    <option value="">既存設定へリンク…</option>
                    {entities.map((entity) => <option key={entity.id} value={entity.id}>{entity.canonical_name}</option>)}
                  </select>
                  <button className="secondary" onClick={() => resolveMention(mention)} type="button">リンク</button>
                  <select
                    value={candidateTypes[mention.id] || "other"}
                    onChange={(event) => setCandidateTypes((current) => ({ ...current, [mention.id]: event.target.value }))}
                  >
                    {ENTITY_TYPES.map((type) => <option key={type} value={type}>{type}</option>)}
                  </select>
                  <button className="secondary" onClick={() => createFromMention(mention)} type="button">INFERENCE作成</button>
                  <button className="danger-lite" onClick={() => ignoreMention(mention)} type="button">無視</button>
                </div>
              )}
            </article>
          ))}
        </div>
      </section>

      <section className="builder-section">
        <p className="eyebrow">RELATION GRAPH</p>
        <h2>エンティティ関係</h2>
        {entities.length >= 2 ? (
          <div className="relation-form">
            <select value={relationForm.source} onChange={(event) => setRelationForm((current) => ({ ...current, source: event.target.value }))}>
              {entities.map((entity) => <option key={entity.id} value={entity.id}>{entity.canonical_name}</option>)}
            </select>
            <span>→</span>
            <select value={relationForm.target} onChange={(event) => setRelationForm((current) => ({ ...current, target: event.target.value }))}>
              {entities.map((entity) => <option key={entity.id} value={entity.id}>{entity.canonical_name}</option>)}
            </select>
            <select value={relationForm.type} onChange={(event) => setRelationForm((current) => ({ ...current, type: event.target.value }))}>
              {RELATION_TYPES.map((type) => <option key={type} value={type}>{type}</option>)}
            </select>
            <input value={relationForm.label} onChange={(event) => setRelationForm((current) => ({ ...current, label: event.target.value }))} placeholder="表示ラベル" />
            <button onClick={addRelation} type="button">PLANとして追加</button>
          </div>
        ) : <p className="empty-state">関係を作るにはBibleエンティティが2件以上必要です。</p>}

        <div className="relation-list">
          {relations.map((relation) => (
            <div className="relation-row" key={relation.id}>
              <strong>{entityMap[relation.source_entity_id]?.canonical_name ?? "?"}</strong>
              <span>{relation.label || relation.relation_type}</span>
              <strong>{entityMap[relation.target_entity_id]?.canonical_name ?? "?"}</strong>
              <small>{relation.relation_type} · {relation.canon_state}</small>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
