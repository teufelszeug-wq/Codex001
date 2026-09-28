"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import {
  getIsekaiCatalog,
  getIsekaiPack,
  getProject,
  listBible,
  previewIsekaiReplacement,
  saveIsekaiPack,
  type BibleEntity,
  type IsekaiCatalog,
  type IsekaiPackConfig,
  type IsekaiPackWrite,
  type IsekaiReplacementPreview,
  type Project,
} from "../../../../lib/api";

function toWrite(config: IsekaiPackConfig): IsekaiPackWrite {
  return {
    enabled: config.enabled,
    strictness: config.strictness,
    enabled_categories: config.enabled_categories,
    allow_terms: config.allow_terms,
    custom_terms: config.custom_terms,
    replacements: config.replacements,
    require_world_mapping: config.require_world_mapping,
    travel_routes: config.travel_routes,
    magic_policy: config.magic_policy,
    economy_policy: config.economy_policy,
    healing_policy: config.healing_policy,
    status: config.status,
  };
}

export default function IsekaiPage() {
  const params = useParams<{ id: string }>();
  const projectId = String(params.id);
  const [project, setProject] = useState<Project | null>(null);
  const [catalog, setCatalog] = useState<IsekaiCatalog | null>(null);
  const [config, setConfig] = useState<IsekaiPackConfig | null>(null);
  const [entities, setEntities] = useState<BibleEntity[]>([]);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [allowText, setAllowText] = useState("");
  const [search, setSearch] = useState("");
  const [previewTerm, setPreviewTerm] = useState("ダージリン");
  const [preview, setPreview] = useState<IsekaiReplacementPreview | null>(null);
  const [newReplacement, setNewReplacement] = useState({ earth_term: "", world_term: "", source_place_entity_id: "" });
  const [newRoute, setNewRoute] = useState({ from_entity_id: "", to_entity_id: "", mode: "horse", min_hours: 1, max_hours: 8 });
  const [newBand, setNewBand] = useState({ category: "meal", currency: "", min_price: 1, max_price: 20 });
  const [newCustom, setNewCustom] = useState({ term: "", category: "earth_culture_food", generic_replacement: "" });

  useEffect(() => {
    let active = true;
    Promise.all([
      getProject(projectId),
      getIsekaiCatalog(),
      getIsekaiPack(projectId),
      listBible(projectId),
    ]).then(([p, cat, cfg, bible]) => {
      if (!active) return;
      setProject(p);
      setCatalog(cat);
      setConfig(cfg);
      setEntities(bible);
      setAllowText(cfg.allow_terms.join("\n"));
      const places = bible.filter((item) => item.entity_type === "place");
      if (places[0]) {
        setNewRoute((current) => ({ ...current, from_entity_id: places[0].id }));
        setNewReplacement((current) => ({ ...current, source_place_entity_id: places[0].id }));
      }
      if (places[1]) setNewRoute((current) => ({ ...current, to_entity_id: places[1].id }));
    }).catch((error) => setMessage(error instanceof Error ? error.message : "Isekai Guardを読み込めませんでした。"));
    return () => { active = false; };
  }, [projectId]);

  const places = useMemo(
    () => entities.filter((item) => item.entity_type === "place"),
    [entities],
  );
  const filteredTerms = useMemo(() => {
    if (!catalog) return [];
    const needle = search.trim().toLowerCase();
    if (!needle) return catalog.earth_terms;
    return catalog.earth_terms.filter((item) =>
      [item.term, item.category, item.concept_key, item.generic_replacement]
        .join(" ")
        .toLowerCase()
        .includes(needle),
    );
  }, [catalog, search]);

  function updateConfig(patch: Partial<IsekaiPackConfig>) {
    setConfig((current) => current ? ({ ...current, ...patch }) : current);
  }

  function parseList(value: string) {
    return value.split(/[\n,]/).map((item) => item.trim()).filter(Boolean);
  }

  async function save() {
    if (!config) return;
    setBusy(true);
    try {
      const payload = toWrite({
        ...config,
        allow_terms: parseList(allowText),
      });
      const saved = await saveIsekaiPack(projectId, payload);
      setConfig(saved);
      setAllowText(saved.allow_terms.join("\n"));
      setMessage("M5 Isekai Guard設定を保存しました。変更影響はM4.5 Invalidation Queueへ登録されています。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Isekai Guard設定を保存できませんでした。");
    } finally {
      setBusy(false);
    }
  }

  async function runPreview() {
    try {
      setPreview(await previewIsekaiReplacement(projectId, previewTerm));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "置換候補を確認できませんでした。");
    }
  }

  function addReplacement() {
    if (!config || !newReplacement.earth_term.trim() || !newReplacement.world_term.trim()) return;
    updateConfig({
      replacements: [
        ...config.replacements,
        {
          earth_term: newReplacement.earth_term.trim(),
          world_term: newReplacement.world_term.trim(),
          source_place_entity_id: newReplacement.source_place_entity_id || null,
          notes: "",
        },
      ],
    });
    setNewReplacement({ earth_term: "", world_term: "", source_place_entity_id: places[0]?.id ?? "" });
  }

  function addRoute() {
    if (!config || !newRoute.from_entity_id || !newRoute.to_entity_id || !newRoute.mode.trim()) return;
    updateConfig({
      travel_routes: [
        ...config.travel_routes,
        {
          id: "route-" + Date.now(),
          from_entity_id: newRoute.from_entity_id,
          to_entity_id: newRoute.to_entity_id,
          mode: newRoute.mode.trim(),
          min_hours: Number(newRoute.min_hours),
          max_hours: Number(newRoute.max_hours),
          bidirectional: true,
          notes: "",
        },
      ],
    });
  }

  function addBand() {
    if (!config || !newBand.category.trim() || !newBand.currency.trim()) return;
    updateConfig({
      economy_policy: {
        ...config.economy_policy,
        price_bands: [
          ...config.economy_policy.price_bands,
          {
            id: "band-" + Date.now(),
            category: newBand.category.trim(),
            currency: newBand.currency.trim(),
            min_price: Number(newBand.min_price),
            max_price: Number(newBand.max_price),
            notes: "",
          },
        ],
      },
    });
  }

  function addCustomTerm() {
    if (!config || !newCustom.term.trim()) return;
    updateConfig({
      custom_terms: [
        ...config.custom_terms,
        {
          id: "custom-earth-" + Date.now(),
          term: newCustom.term.trim(),
          category: newCustom.category,
          concept_key: "custom",
          generic_replacement: newCustom.generic_replacement.trim(),
          severity: null,
          enabled: true,
        },
      ],
    });
    setNewCustom({ term: "", category: "earth_culture_food", generic_replacement: "" });
  }

  if (!project || !catalog || !config) {
    return <main className="shell narrow"><p>{message || "Isekai Guardを準備しています…"}</p></main>;
  }

  return (
    <main className="shell isekai-shell">
      <div className="overview-head">
        <div>
          <p className="eyebrow">M5 · ISEKAI PACK</p>
          <h1>{project.title}</h1>
          <p>地球由来語・世界内名称・移動時間・魔法コスト・物価・治癒上限を、作品ごとの設定で検査します。すべて任意設定で、ジャンル選択だけでは自動有効化しません。</p>
        </div>
        <Link className="text-link" href={"/projects/" + projectId}>← 作品概要</Link>
      </div>

      {message && <p className="notice">{message}</p>}

      <section className="isekai-hero-grid">
        <article className="builder-section">
          <p className="eyebrow">PACK POLICY</p>
          <h2>異世界感ガード</h2>
          <label className="guard-toggle">
            <input
              type="checkbox"
              checked={config.enabled}
              onChange={(event) => updateConfig({ enabled: event.target.checked })}
            />
            <span><strong>この作品でM5を有効化</strong><br /><small>OFFならM5ルールはLintへ一切追加されません。</small></span>
          </label>
          <div className="form-grid two" style={{ marginTop: 14 }}>
            <label>Strictness
              <select value={config.strictness} onChange={(event) => updateConfig({ strictness: event.target.value })}>
                {catalog.strictness.map((item) => <option key={item} value={item}>{item}</option>)}
              </select>
            </label>
            <label>Status
              <select value={config.status} onChange={(event) => updateConfig({ status: event.target.value as "draft" | "configured" })}>
                <option value="draft">draft</option>
                <option value="configured">configured</option>
              </select>
            </label>
          </div>
          <label className="guard-toggle" style={{ marginTop: 12 }}>
            <input
              type="checkbox"
              checked={config.require_world_mapping}
              onChange={(event) => updateConfig({ require_world_mapping: event.target.checked })}
            />
            <span><strong>世界内名称の登録を要求</strong><br /><small>検出語にWorld Replacementが無い場合、別Findingを出します。</small></span>
          </label>
        </article>

        <article className="builder-section">
          <p className="eyebrow">REPLACEMENT PREVIEW</p>
          <h2>語の扱いを確認</h2>
          <div className="inline-fields resolver-input">
            <input value={previewTerm} onChange={(event) => setPreviewTerm(event.target.value)} placeholder="例：ダージリン" />
            <button onClick={runPreview} type="button">確認</button>
          </div>
          {preview && (
            <div className="preview-result">
              <strong>{preview.term}</strong>
              <span>{preview.matched ? "Earth-Origin辞書一致" : "辞書未登録"}</span>
              <small>category: {preview.category ?? "—"}</small>
              <small>generic: {preview.generic_replacement ?? "—"}</small>
              <small>world: {preview.world_replacement ?? "未登録"}</small>
              <small>{preview.allowed ? "Allowlist対象" : preview.needs_author_decision ? "作者判断待ち" : "世界内名称登録済み"}</small>
            </div>
          )}
        </article>
      </section>

      <section className="builder-section">
        <p className="eyebrow">EARTH-ORIGIN GUARD</p>
        <h2>カテゴリと例外</h2>
        <div className="category-grid">
          {catalog.categories.map((category) => (
            <article className="category-card" key={category.key}>
              <label>
                <input
                  type="checkbox"
                  checked={config.enabled_categories[category.key] ?? true}
                  onChange={(event) => updateConfig({
                    enabled_categories: {
                      ...config.enabled_categories,
                      [category.key]: event.target.checked,
                    },
                  })}
                />
                {category.label}
              </label>
              <small>{category.description}</small>
            </article>
          ))}
        </div>
        <label className="block-label" style={{ marginTop: 18 }}>Allowlist（改行またはカンマ区切り）
          <textarea value={allowText} onChange={(event) => setAllowText(event.target.value)} placeholder={"例外として許可する語\nスマホ"} />
        </label>

        <h3>カスタム地球由来語</h3>
        <div className="replacement-row">
          <input value={newCustom.term} onChange={(event) => setNewCustom((current) => ({ ...current, term: event.target.value }))} placeholder="語" />
          <span>→</span>
          <select value={newCustom.category} onChange={(event) => setNewCustom((current) => ({ ...current, category: event.target.value }))}>
            {catalog.categories.map((category) => <option key={category.key} value={category.key}>{category.label}</option>)}
          </select>
          <input value={newCustom.generic_replacement} onChange={(event) => setNewCustom((current) => ({ ...current, generic_replacement: event.target.value }))} placeholder="一般化候補" />
          <button className="secondary" onClick={addCustomTerm} type="button">追加</button>
        </div>
        <div className="chip-row">
          {config.custom_terms.map((term) => (
            <button
              className="chip"
              key={term.id}
              onClick={() => updateConfig({ custom_terms: config.custom_terms.filter((item) => item.id !== term.id) })}
              type="button"
            >
              {term.term} · {term.category} ×
            </button>
          ))}
        </div>

        <h3>内蔵Earth-Origin辞書</h3>
        <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="辞書検索" />
        <div className="term-browser">
          {filteredTerms.map((term, index) => (
            <div className="term-browser-row" key={term.term + index}>
              <strong>{term.term}</strong>
              <span>{term.category}</span>
              <span>→ {term.generic_replacement}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="builder-section">
        <p className="eyebrow">WORLD-ORIGIN MAPPING</p>
        <h2>世界内名称</h2>
        <p className="helper">置換は自動適用しません。作者が承認した対応表として保存し、Lint Findingの候補に表示します。</p>
        <div className="replacement-row">
          <input value={newReplacement.earth_term} onChange={(event) => setNewReplacement((current) => ({ ...current, earth_term: event.target.value }))} placeholder="地球語" />
          <span>→</span>
          <input value={newReplacement.world_term} onChange={(event) => setNewReplacement((current) => ({ ...current, world_term: event.target.value }))} placeholder="世界内名称" />
          <select value={newReplacement.source_place_entity_id} onChange={(event) => setNewReplacement((current) => ({ ...current, source_place_entity_id: event.target.value }))}>
            <option value="">産地なし</option>
            {places.map((place) => <option key={place.id} value={place.id}>{place.canonical_name}</option>)}
          </select>
          <button className="secondary" onClick={addReplacement} type="button">追加</button>
        </div>
        <div className="replacement-list">
          {config.replacements.map((item, index) => (
            <div className="replacement-row" key={item.earth_term + index}>
              <strong>{item.earth_term}</strong>
              <span>→</span>
              <strong>{item.world_term}</strong>
              <small>{places.find((place) => place.id === item.source_place_entity_id)?.canonical_name ?? "産地未指定"}</small>
              <button className="danger-lite" onClick={() => updateConfig({ replacements: config.replacements.filter((_, i) => i !== index) })} type="button">削除</button>
            </div>
          ))}
        </div>
      </section>

      <section className="builder-section">
        <p className="eyebrow">STRUCTURED WORLD CONSTRAINTS</p>
        <h2>魔法・経済・治癒</h2>
        <div className="policy-grid">
          <article className="policy-card">
            <h3>Magic Cost</h3>
            <label><input type="checkbox" checked={config.magic_policy.enabled} onChange={(event) => updateConfig({ magic_policy: { ...config.magic_policy, enabled: event.target.checked } })} />有効</label>
            <label><input type="checkbox" checked={config.magic_policy.require_cost} onChange={(event) => updateConfig({ magic_policy: { ...config.magic_policy, require_cost: event.target.checked } })} />コスト必須</label>
            <input
              value={config.magic_policy.allowed_cost_types.join(", ")}
              onChange={(event) => updateConfig({ magic_policy: { ...config.magic_policy, allowed_cost_types: parseList(event.target.value) } })}
              placeholder="mana, stamina, blood"
            />
            <input
              value={config.magic_policy.costless_tiers.join(", ")}
              onChange={(event) => updateConfig({ magic_policy: { ...config.magic_policy, costless_tiers: parseList(event.target.value) } })}
              placeholder="コスト不要Tier"
            />
          </article>

          <article className="policy-card">
            <h3>Economy</h3>
            <label><input type="checkbox" checked={config.economy_policy.enabled} onChange={(event) => updateConfig({ economy_policy: { ...config.economy_policy, enabled: event.target.checked } })} />有効</label>
            <input
              value={config.economy_policy.currencies.join(", ")}
              onChange={(event) => updateConfig({ economy_policy: { ...config.economy_policy, currencies: parseList(event.target.value) } })}
              placeholder="クラウン, 銀貨"
            />
            <small>Story Bible item.attributes.economy を検査</small>
          </article>

          <article className="policy-card">
            <h3>Healing Limit</h3>
            <label><input type="checkbox" checked={config.healing_policy.enabled} onChange={(event) => updateConfig({ healing_policy: { ...config.healing_policy, enabled: event.target.checked } })} />有効</label>
            <label><input type="checkbox" checked={config.healing_policy.resurrection_allowed} onChange={(event) => updateConfig({ healing_policy: { ...config.healing_policy, resurrection_allowed: event.target.checked } })} />死者蘇生を許可</label>
            <label><input type="checkbox" checked={config.healing_policy.limb_regrowth_allowed} onChange={(event) => updateConfig({ healing_policy: { ...config.healing_policy, limb_regrowth_allowed: event.target.checked } })} />欠損再生を許可</label>
          </article>
        </div>

        <h3>価格帯</h3>
        <div className="band-row">
          <input value={newBand.category} onChange={(event) => setNewBand((current) => ({ ...current, category: event.target.value }))} placeholder="meal" />
          <input value={newBand.currency} onChange={(event) => setNewBand((current) => ({ ...current, currency: event.target.value }))} placeholder="クラウン" />
          <input type="number" value={newBand.min_price} onChange={(event) => setNewBand((current) => ({ ...current, min_price: Number(event.target.value) }))} />
          <input type="number" value={newBand.max_price} onChange={(event) => setNewBand((current) => ({ ...current, max_price: Number(event.target.value) }))} />
          <button className="secondary" onClick={addBand} type="button">追加</button>
        </div>
        <div className="band-list">
          {config.economy_policy.price_bands.map((band, index) => (
            <div className="band-row" key={band.id}>
              <strong>{band.category}</strong><span>{band.currency}</span><span>{band.min_price}</span><span>{band.max_price}</span>
              <button className="danger-lite" onClick={() => updateConfig({ economy_policy: { ...config.economy_policy, price_bands: config.economy_policy.price_bands.filter((_, i) => i !== index) } })} type="button">削除</button>
            </div>
          ))}
        </div>
      </section>

      <section className="builder-section">
        <p className="eyebrow">TRAVEL CONSISTENCY</p>
        <h2>移動ルート</h2>
        <p className="helper">Story Bibleのevent.attributes.isekai_travelと照合します。ルートが無い場合と、所要時間が範囲外の場合を別々に診断します。</p>
        {places.length < 2 ? (
          <p className="empty-state">ルート設定にはStory Bibleのplaceを2件以上登録してください。</p>
        ) : (
          <>
            <div className="route-row">
              <select value={newRoute.from_entity_id} onChange={(event) => setNewRoute((current) => ({ ...current, from_entity_id: event.target.value }))}>
                {places.map((place) => <option key={place.id} value={place.id}>{place.canonical_name}</option>)}
              </select>
              <span>→</span>
              <select value={newRoute.to_entity_id} onChange={(event) => setNewRoute((current) => ({ ...current, to_entity_id: event.target.value }))}>
                {places.map((place) => <option key={place.id} value={place.id}>{place.canonical_name}</option>)}
              </select>
              <input value={newRoute.mode} onChange={(event) => setNewRoute((current) => ({ ...current, mode: event.target.value }))} placeholder="horse" />
              <input type="number" value={newRoute.min_hours} onChange={(event) => setNewRoute((current) => ({ ...current, min_hours: Number(event.target.value) }))} />
              <input type="number" value={newRoute.max_hours} onChange={(event) => setNewRoute((current) => ({ ...current, max_hours: Number(event.target.value) }))} />
              <button className="secondary" onClick={addRoute} type="button">追加</button>
            </div>
            <div className="route-list">
              {config.travel_routes.map((route, index) => (
                <div className="route-row" key={route.id}>
                  <strong>{entities.find((item) => item.id === route.from_entity_id)?.canonical_name ?? route.from_entity_id}</strong>
                  <span>→</span>
                  <strong>{entities.find((item) => item.id === route.to_entity_id)?.canonical_name ?? route.to_entity_id}</strong>
                  <span>{route.mode}</span>
                  <span>{route.min_hours}h</span>
                  <span>{route.max_hours}h</span>
                  <button className="danger-lite" onClick={() => updateConfig({ travel_routes: config.travel_routes.filter((_, i) => i !== index) })} type="button">削除</button>
                </div>
              ))}
            </div>
          </>
        )}
      </section>

      <div className="save-wide">
        <span>保存するとM4.5へPack Policy変更のInvalidationを発行します。</span>
        <button disabled={busy} onClick={save} type="button">{busy ? "保存中…" : "M5設定を保存"}</button>
      </div>
    </main>
  );
}
