"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import {
  getLNGenreCatalog,
  getLNGenrePack,
  getProject,
  listBible,
  runStructureLint,
  saveLNGenrePack,
  type BibleEntity,
  type LNGenreCatalog,
  type LNGenrePackConfig,
  type LNGenrePackKey,
  type LNGenrePackWrite,
  type LintRun,
  type Project,
} from "../../../../lib/api";

function parseList(value: string): string[] {
  return value.split(/[\n,]/).map((item) => item.trim()).filter(Boolean);
}

function toWrite(config: LNGenrePackConfig): LNGenrePackWrite {
  return {
    enabled_packs: config.enabled_packs,
    noble_lady: config.noble_lady,
    palace_harem: config.palace_harem,
    romcom: config.romcom,
    status: config.status,
  };
}

export default function LNGenrePage() {
  const params = useParams<{ id: string }>();
  const projectId = String(params.id);
  const [project, setProject] = useState<Project | null>(null);
  const [catalog, setCatalog] = useState<LNGenreCatalog | null>(null);
  const [config, setConfig] = useState<LNGenrePackConfig | null>(null);
  const [entities, setEntities] = useState<BibleEntity[]>([]);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [lintRun, setLintRun] = useState<LintRun | null>(null);

  const [titleDraft, setTitleDraft] = useState({ rank: "", titles: "" });
  const [addressDraft, setAddressDraft] = useState({ rank: "", addresses: "" });
  const [areaDraft, setAreaDraft] = useState({ place: "", minRank: "", factions: "" });
  const [infoDraft, setInfoDraft] = useState({ fact: "", minRank: "", factions: "" });
  const [ritualDraft, setRitualDraft] = useState({ key: "", steps: "" });

  useEffect(() => {
    let active = true;
    Promise.all([
      getProject(projectId),
      getLNGenreCatalog(),
      getLNGenrePack(projectId),
      listBible(projectId),
    ]).then(([p, cat, cfg, bible]) => {
      if (!active) return;
      setProject(p);
      setCatalog(cat);
      setConfig(cfg);
      setEntities(bible);
      setTitleDraft((current) => ({ ...current, rank: cfg.noble_lady.rank_order[0] ?? "" }));
      setAddressDraft((current) => ({ ...current, rank: cfg.noble_lady.rank_order[0] ?? "" }));
      setAreaDraft((current) => ({
        ...current,
        place: bible.find((item) => item.entity_type === "place")?.id ?? "",
        minRank: cfg.palace_harem.rank_order[0] ?? "",
      }));
      setInfoDraft((current) => ({ ...current, minRank: cfg.palace_harem.rank_order[0] ?? "" }));
    }).catch((error) => {
      setMessage(error instanceof Error ? error.message : "LN Genre Packsを読み込めませんでした。");
    });
    return () => { active = false; };
  }, [projectId]);

  const places = useMemo(
    () => entities.filter((item) => item.entity_type === "place"),
    [entities],
  );
  const factions = useMemo(
    () => entities.filter((item) => ["organization", "faction", "house"].includes(item.entity_type)),
    [entities],
  );

  function togglePack(key: LNGenrePackKey, enabled: boolean) {
    setConfig((current) => current ? ({
      ...current,
      enabled_packs: { ...current.enabled_packs, [key]: enabled },
    }) : current);
  }

  function setNoble(patch: Partial<LNGenrePackConfig["noble_lady"]>) {
    setConfig((current) => current ? ({
      ...current,
      noble_lady: { ...current.noble_lady, ...patch },
    }) : current);
  }

  function setPalace(patch: Partial<LNGenrePackConfig["palace_harem"]>) {
    setConfig((current) => current ? ({
      ...current,
      palace_harem: { ...current.palace_harem, ...patch },
    }) : current);
  }

  function setRomcom(patch: Partial<LNGenrePackConfig["romcom"]>) {
    setConfig((current) => current ? ({
      ...current,
      romcom: { ...current.romcom, ...patch },
    }) : current);
  }

  async function save() {
    if (!config) return;
    setBusy(true);
    try {
      const saved = await saveLNGenrePack(projectId, toWrite(config));
      setConfig(saved);
      setMessage("M6 Genre Pack設定を保存しました。M4.5へ再検証イベントを登録しました。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "M6設定を保存できませんでした。");
    } finally {
      setBusy(false);
    }
  }

  async function inspectStructure() {
    setBusy(true);
    try {
      const run = await runStructureLint(projectId);
      setLintRun(run);
      setMessage("Genre Packを含む構造Lintを実行しました。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "構造Lintを実行できませんでした。");
    } finally {
      setBusy(false);
    }
  }

  if (!project || !catalog || !config) {
    return <main className="shell narrow"><p>{message || "M6を準備しています…"}</p></main>;
  }

  return (
    <main className="shell ln-genre-shell">
      <div className="overview-head">
        <div>
          <p className="eyebrow">M6 · LN GENRE PACKS</p>
          <h1>{project.title}</h1>
          <p>令嬢・後宮・ラブコメを独立したPackとして組み合わせます。主ジャンルは必須ではなく、0〜3個を任意に有効化できます。</p>
        </div>
        <Link className="text-link" href={"/projects/" + projectId}>← 作品概要</Link>
      </div>

      {message && <p className="notice">{message}</p>}

      <section className="genre-pack-grid">
        {catalog.packs.map((pack) => (
          <article className={"genre-pack-card " + (config.enabled_packs[pack.key] ? "active" : "")} key={pack.key}>
            <label>
              <input
                type="checkbox"
                checked={config.enabled_packs[pack.key]}
                onChange={(event) => togglePack(pack.key, event.target.checked)}
              />
              {pack.label}
            </label>
            <small>{pack.description}</small>
            <span className="helper">{config.enabled_packs[pack.key] ? "ENABLED" : "DISABLED"}</span>
          </article>
        ))}
      </section>

      <section className="builder-section">
        <p className="eyebrow">NOBLE LADY</p>
        <h2>爵位・家・婚約・呼称</h2>
        <div className="genre-policy-grid">
          <div className="policy-section">
            <h3>爵位序列</h3>
            <textarea
              value={config.noble_lady.rank_order.join(", ")}
              onChange={(event) => setNoble({ rank_order: parseList(event.target.value) })}
            />
            <label className="guard-toggle" style={{ marginTop: 10 }}>
              <input
                type="checkbox"
                checked={config.noble_lady.allow_multiple_active_engagements}
                onChange={(event) => setNoble({ allow_multiple_active_engagements: event.target.checked })}
              />
              <span>複数の有効婚約を許可</span>
            </label>
            <label className="block-label" style={{ marginTop: 10 }}>婚約Relation Types
              <input
                value={config.noble_lady.engagement_relation_types.join(", ")}
                onChange={(event) => setNoble({ engagement_relation_types: parseList(event.target.value) })}
              />
            </label>
          </div>

          <div className="policy-section">
            <h3>爵位 → 公開称号</h3>
            <div className="config-row">
              <select value={titleDraft.rank} onChange={(event) => setTitleDraft((current) => ({ ...current, rank: event.target.value }))}>
                {config.noble_lady.rank_order.map((rank) => <option key={rank} value={rank}>{rank}</option>)}
              </select>
              <input value={titleDraft.titles} onChange={(event) => setTitleDraft((current) => ({ ...current, titles: event.target.value }))} placeholder="公爵令嬢, 公爵閣下" />
              <button
                className="secondary"
                type="button"
                onClick={() => {
                  if (!titleDraft.rank) return;
                  setNoble({
                    rank_title_map: {
                      ...config.noble_lady.rank_title_map,
                      [titleDraft.rank]: parseList(titleDraft.titles),
                    },
                  });
                }}
              >登録</button>
            </div>
            <div className="mini-list">
              {Object.entries(config.noble_lady.rank_title_map).map(([rank, titles]) => (
                <div className="mini-list-row" key={rank}>
                  <span><strong>{rank}</strong> → {titles.join(" / ")}</span>
                  <button
                    className="danger-lite"
                    type="button"
                    onClick={() => {
                      const next = { ...config.noble_lady.rank_title_map };
                      delete next[rank];
                      setNoble({ rank_title_map: next });
                    }}
                  >削除</button>
                </div>
              ))}
            </div>
          </div>

          <div className="policy-section">
            <h3>呼称規則</h3>
            <div className="config-row">
              <select value={addressDraft.rank} onChange={(event) => setAddressDraft((current) => ({ ...current, rank: event.target.value }))}>
                {config.noble_lady.rank_order.map((rank) => <option key={rank} value={rank}>{rank}</option>)}
              </select>
              <input value={addressDraft.addresses} onChange={(event) => setAddressDraft((current) => ({ ...current, addresses: event.target.value }))} placeholder="殿下, 王子殿下" />
              <button
                className="secondary"
                type="button"
                onClick={() => {
                  if (!addressDraft.rank) return;
                  setNoble({
                    address_rules: [
                      ...config.noble_lady.address_rules,
                      {
                        id: "address-" + Date.now(),
                        target_rank: addressDraft.rank,
                        allowed_addresses: parseList(addressDraft.addresses),
                      },
                    ],
                  });
                }}
              >追加</button>
            </div>
            <div className="mini-list">
              {config.noble_lady.address_rules.map((rule) => (
                <div className="mini-list-row" key={rule.id}>
                  <span>{rule.target_rank} → {rule.allowed_addresses.join(" / ")}</span>
                  <button className="danger-lite" type="button" onClick={() => setNoble({ address_rules: config.noble_lady.address_rules.filter((item) => item.id !== rule.id) })}>削除</button>
                </div>
              ))}
            </div>
          </div>

          <div className="policy-section">
            <h3>Story Bible契約</h3>
            <div className="contract-note">
              character.attributes.ln_noble = {"{ house_entity_id, rank, public_title }"}<br />
              event.attributes.ln_address = {"{ speaker_entity_id, target_entity_id, used_address }"}<br />
              engagement Relation attributes.status = active / ended
            </div>
          </div>
        </div>
      </section>

      <section className="builder-section">
        <p className="eyebrow">PALACE / HAREM</p>
        <h2>位階・派閥・立入・情報・儀礼</h2>
        <label className="block-label">位階序列
          <textarea
            value={config.palace_harem.rank_order.join(", ")}
            onChange={(event) => setPalace({ rank_order: parseList(event.target.value) })}
          />
        </label>

        <div className="genre-policy-grid">
          <div className="policy-section">
            <h3>立入制限</h3>
            <div className="config-row four">
              <select value={areaDraft.place} onChange={(event) => setAreaDraft((current) => ({ ...current, place: event.target.value }))}>
                <option value="">場所を選択</option>
                {places.map((place) => <option key={place.id} value={place.id}>{place.canonical_name}</option>)}
              </select>
              <select value={areaDraft.minRank} onChange={(event) => setAreaDraft((current) => ({ ...current, minRank: event.target.value }))}>
                {config.palace_harem.rank_order.map((rank) => <option key={rank} value={rank}>{rank}</option>)}
              </select>
              <input value={areaDraft.factions} onChange={(event) => setAreaDraft((current) => ({ ...current, factions: event.target.value }))} placeholder="許可派閥UUID（任意）" />
              <button
                className="secondary"
                type="button"
                onClick={() => {
                  if (!areaDraft.place) return;
                  setPalace({
                    restricted_areas: [
                      ...config.palace_harem.restricted_areas,
                      {
                        id: "area-" + Date.now(),
                        place_entity_id: areaDraft.place,
                        min_rank: areaDraft.minRank,
                        allowed_faction_entity_ids: parseList(areaDraft.factions),
                        exception_entity_ids: [],
                      },
                    ],
                  });
                }}
              >追加</button>
            </div>
            <div className="mini-list">
              {config.palace_harem.restricted_areas.map((rule) => (
                <div className="mini-list-row" key={rule.id}>
                  <span>{places.find((item) => item.id === rule.place_entity_id)?.canonical_name ?? rule.place_entity_id} · min {rule.min_rank}</span>
                  <button className="danger-lite" type="button" onClick={() => setPalace({ restricted_areas: config.palace_harem.restricted_areas.filter((item) => item.id !== rule.id) })}>削除</button>
                </div>
              ))}
            </div>
          </div>

          <div className="policy-section">
            <h3>情報アクセス</h3>
            <div className="config-row four">
              <input value={infoDraft.fact} onChange={(event) => setInfoDraft((current) => ({ ...current, fact: event.target.value }))} placeholder="fact_key" />
              <select value={infoDraft.minRank} onChange={(event) => setInfoDraft((current) => ({ ...current, minRank: event.target.value }))}>
                {config.palace_harem.rank_order.map((rank) => <option key={rank} value={rank}>{rank}</option>)}
              </select>
              <input value={infoDraft.factions} onChange={(event) => setInfoDraft((current) => ({ ...current, factions: event.target.value }))} placeholder="許可派閥UUID（任意）" />
              <button
                className="secondary"
                type="button"
                onClick={() => {
                  if (!infoDraft.fact.trim()) return;
                  setPalace({
                    information_rules: [
                      ...config.palace_harem.information_rules,
                      {
                        id: "info-" + Date.now(),
                        fact_key: infoDraft.fact.trim(),
                        min_rank: infoDraft.minRank,
                        allowed_faction_entity_ids: parseList(infoDraft.factions),
                      },
                    ],
                  });
                }}
              >追加</button>
            </div>
            <div className="mini-list">
              {config.palace_harem.information_rules.map((rule) => (
                <div className="mini-list-row" key={rule.id}>
                  <span>{rule.fact_key} · min {rule.min_rank}</span>
                  <button className="danger-lite" type="button" onClick={() => setPalace({ information_rules: config.palace_harem.information_rules.filter((item) => item.id !== rule.id) })}>削除</button>
                </div>
              ))}
            </div>
          </div>

          <div className="policy-section">
            <h3>儀礼順序</h3>
            <div className="config-row">
              <input value={ritualDraft.key} onChange={(event) => setRitualDraft((current) => ({ ...current, key: event.target.value }))} placeholder="audience" />
              <input value={ritualDraft.steps} onChange={(event) => setRitualDraft((current) => ({ ...current, steps: event.target.value }))} placeholder="bow, announce, offer" />
              <button
                className="secondary"
                type="button"
                onClick={() => {
                  if (!ritualDraft.key.trim()) return;
                  setPalace({
                    ritual_sequences: [
                      ...config.palace_harem.ritual_sequences,
                      {
                        id: "ritual-" + Date.now(),
                        ritual_key: ritualDraft.key.trim(),
                        steps: parseList(ritualDraft.steps),
                      },
                    ],
                  });
                }}
              >追加</button>
            </div>
            <div className="mini-list">
              {config.palace_harem.ritual_sequences.map((rule) => (
                <div className="mini-list-row" key={rule.id}>
                  <span>{rule.ritual_key} → {rule.steps.join(" → ")}</span>
                  <button className="danger-lite" type="button" onClick={() => setPalace({ ritual_sequences: config.palace_harem.ritual_sequences.filter((item) => item.id !== rule.id) })}>削除</button>
                </div>
              ))}
            </div>
          </div>

          <div className="policy-section">
            <h3>参照可能な派閥</h3>
            <div className="contract-note">
              {factions.length === 0 ? "Story Bibleにorganization/faction/houseを追加すると選択候補として使えます。" : factions.map((item) => item.canonical_name + " = " + item.id).join("\n")}
            </div>
          </div>
        </div>
      </section>

      <section className="builder-section">
        <p className="eyebrow">ROMANTIC COMEDY</p>
        <h2>関係段階・予定・誤解</h2>
        <div className="genre-policy-grid">
          <div className="policy-section">
            <h3>関係段階</h3>
            <textarea
              value={config.romcom.stages.join(", ")}
              onChange={(event) => setRomcom({ stages: parseList(event.target.value) })}
            />
            <label className="block-label" style={{ marginTop: 10 }}>1イベントで許可する最大進展段階
              <input
                type="number"
                min={1}
                value={config.romcom.max_stage_jump}
                onChange={(event) => setRomcom({ max_stage_jump: Number(event.target.value) })}
              />
            </label>
          </div>
          <div className="policy-section">
            <h3>遷移ポリシー</h3>
            <label className="guard-toggle">
              <input type="checkbox" checked={config.romcom.allow_regression} onChange={(event) => setRomcom({ allow_regression: event.target.checked })} />
              <span>関係段階の後退を許可</span>
            </label>
            <label className="guard-toggle" style={{ marginTop: 8 }}>
              <input type="checkbox" checked={config.romcom.require_reason_for_large_jump} onChange={(event) => setRomcom({ require_reason_for_large_jump: event.target.checked })} />
              <span>大きな段階ジャンプに理由を要求</span>
            </label>
            <label className="block-label" style={{ marginTop: 8 }}>未解決の誤解のSeverity
              <select value={config.romcom.unresolved_misunderstanding_severity} onChange={(event) => setRomcom({ unresolved_misunderstanding_severity: event.target.value })}>
                {["hint", "info", "warning", "error"].map((value) => <option key={value} value={value}>{value}</option>)}
              </select>
            </label>
          </div>
          <div className="policy-section">
            <h3>Story Bible契約</h3>
            <div className="contract-note">
              event.attributes.ln_relationship_transition<br />
              event.attributes.ln_schedule<br />
              event.attributes.ln_misunderstanding
            </div>
          </div>
          <div className="policy-section">
            <h3>設計意図</h3>
            <div className="contract-note">
              恋愛感情そのものをAIが断定するのではなく、作者が構造化した「段階変更」「予定」「誤解」を検査します。意図的な急展開はFindingを確認済みにできます。
            </div>
          </div>
        </div>
      </section>

      <section className="builder-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">STRUCTURAL LINT</p>
            <h2>M6検査結果</h2>
          </div>
          <button className="secondary" disabled={busy} onClick={inspectStructure} type="button">構造Lintを実行</button>
        </div>
        {!lintRun ? (
          <p className="empty-state">まだ実行していません。</p>
        ) : (
          <>
            <div className="lint-summary">
              <div className="metric-card"><strong>{lintRun.summary.total}</strong><small>total</small></div>
              <div className="metric-card"><strong>{lintRun.summary.by_severity.error ?? 0}</strong><small>error</small></div>
              <div className="metric-card"><strong>{lintRun.summary.by_severity.warning ?? 0}</strong><small>warning</small></div>
              <div className="metric-card"><strong>{lintRun.summary.by_severity.info ?? 0}</strong><small>info</small></div>
              <div className="metric-card"><strong>{lintRun.summary.by_severity.hint ?? 0}</strong><small>hint</small></div>
            </div>
            <div className="finding-list">
              {(lintRun.findings ?? []).filter((item) => ["noble_lady", "palace_harem", "romcom"].includes(String(item.evidence.pack ?? ""))).map((finding) => (
                <article className={"finding-row " + finding.severity} key={finding.id}>
                  <span className="finding-severity">{finding.severity}</span>
                  <div>
                    <strong>{finding.rule_id}</strong>
                    <span>{finding.message}</span>
                    <small>{String(finding.evidence.pack ?? "")}</small>
                  </div>
                </article>
              ))}
            </div>
          </>
        )}
      </section>

      <div className="save-wide">
        <span>Packは独立・併用可能です。保存しても本文・Canonは自動変更しません。</span>
        <button disabled={busy} onClick={save} type="button">{busy ? "保存中…" : "M6設定を保存"}</button>
      </div>
    </main>
  );
}
