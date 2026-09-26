"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import {
  getLanguageCulture,
  getLanguageCultureCatalog,
  getProject,
  previewLanguageNames,
  saveLanguageCulture,
  type CultureProfile,
  type LanguageContact,
  type LanguageCultureCatalog,
  type LanguageCultureWrite,
  type LanguageProfile,
  type Project,
  type RootLexiconEntry,
} from "../../../../lib/api";

const emptyConfig: LanguageCultureWrite = {
  languages: [],
  cultures: [],
  contacts: [],
  root_lexicon: [],
  display_policy: {
    mode: "translated",
    first_mention: "original_with_reading",
    later_mentions: "translated",
    ruby_policy: "project_choice",
    notes: "",
  },
  earth_term_policy: {
    mode: "warn",
    replacement_mode: "both",
    allowed_contexts: [],
    notes: "",
  },
  common_language_id: null,
  status: "draft",
};

function csv(value: string): string[] {
  return value.split(",").map((item) => item.trim()).filter(Boolean);
}

function csvKeepEmpty(value: string): string[] {
  return value.split(",").map((item) => item.trim());
}

function joinCsv(value: string[]): string {
  return value.join(", ");
}

function stableId(prefix: string): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return `${prefix}-${crypto.randomUUID()}`;
  return `${prefix}-${Date.now()}-${Math.floor(Math.random() * 100000)}`;
}

function newLanguage(): LanguageProfile {
  return {
    id: stableId("lang"),
    name: "新しい言語",
    role: "regional",
    regions: [],
    inspirations: [],
    parent_language_id: null,
    era_label: "",
    phonology: {
      onsets: ["m", "n", "r", "s", "t", "k", "v", "l"],
      nuclei: ["a", "e", "i", "o", "u"],
      codas: ["", "n", "r", "s"],
      forbidden_sequences: [],
      syllables_min: 2,
      syllables_max: 3,
      separator: "",
      capitalize: true,
    },
    naming: {
      prefixes: { person: [""], place: [""], item: [""], title: [""] },
      suffixes: { person: [""], place: [""], item: [""], title: [""] },
      notes: "",
    },
    script: { name: "", type: "alphabetic", direction: "ltr", notes: "" },
    notes: "",
  };
}

function newCulture(languageId: string | null): CultureProfile {
  return {
    id: stableId("culture"),
    name: "新しい文化",
    regions: [],
    language_ids: languageId ? [languageId] : [],
    tags: [],
    institutions: [],
    etiquette: "",
    taboos: [],
    festivals: [],
    material_culture: "",
    notes: "",
  };
}

export default function LanguageCultureBuilderPage() {
  const params = useParams<{ id: string }>();
  const projectId = String(params.id);
  const draftKey = `ccos-language-culture-draft-${projectId}`;
  const [project, setProject] = useState<Project | null>(null);
  const [catalog, setCatalog] = useState<LanguageCultureCatalog | null>(null);
  const [config, setConfig] = useState<LanguageCultureWrite>(emptyConfig);
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [customInspiration, setCustomInspiration] = useState<Record<string, string>>({});
  const [previews, setPreviews] = useState<Record<string, string[]>>({});

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const [nextProject, nextCatalog] = await Promise.all([
          getProject(projectId),
          getLanguageCultureCatalog(),
        ]);
        if (!active) return;
        setProject(nextProject);
        setCatalog(nextCatalog);

        const local = localStorage.getItem(draftKey);
        if (local) {
          try {
            setConfig({ ...emptyConfig, ...JSON.parse(local) });
            setMessage("端末に残っていた編集中の言語・文化設定を復元しました。");
            setLoaded(true);
            return;
          } catch {
            localStorage.removeItem(draftKey);
          }
        }

        try {
          const saved = await getLanguageCulture(projectId);
          if (active) setConfig(saved);
        } catch {
          if (active) setConfig(emptyConfig);
        }
      } catch (error) {
        if (active) setMessage(error instanceof Error ? error.message : "読み込みに失敗しました。");
      } finally {
        if (active) setLoaded(true);
      }
    }
    load();
    return () => { active = false; };
  }, [draftKey, projectId]);

  useEffect(() => {
    if (loaded) localStorage.setItem(draftKey, JSON.stringify(config));
  }, [config, draftKey, loaded]);

  const languageMap = useMemo(
    () => Object.fromEntries(config.languages.map((language) => [language.id, language.name])),
    [config.languages],
  );

  function updateLanguage(id: string, updater: (language: LanguageProfile) => LanguageProfile) {
    setConfig((current) => ({
      ...current,
      languages: current.languages.map((language) => language.id === id ? updater(language) : language),
    }));
  }

  function removeLanguage(id: string) {
    setConfig((current) => ({
      ...current,
      languages: current.languages.filter((language) => language.id !== id),
      cultures: current.cultures.map((culture) => ({
        ...culture,
        language_ids: culture.language_ids.filter((languageId) => languageId !== id),
      })),
      contacts: current.contacts.filter((contact) => contact.from_language_id !== id && contact.to_language_id !== id),
      root_lexicon: current.root_lexicon.filter((entry) => entry.language_id !== id),
      common_language_id: current.common_language_id === id ? null : current.common_language_id,
    }));
  }

  function addPresetInspiration(languageId: string, source: string) {
    if (!source) return;
    updateLanguage(languageId, (language) => {
      if (language.inspirations.some((item) => item.source === source)) return language;
      return { ...language, inspirations: [...language.inspirations, { source, weight: 50 }] };
    });
  }

  function addCustomInspiration(languageId: string) {
    const text = (customInspiration[languageId] ?? "").trim();
    if (!text) return;
    addPresetInspiration(languageId, `custom:${text}`);
    setCustomInspiration((current) => ({ ...current, [languageId]: "" }));
  }

  function updateCulture(id: string, updater: (culture: CultureProfile) => CultureProfile) {
    setConfig((current) => ({
      ...current,
      cultures: current.cultures.map((culture) => culture.id === id ? updater(culture) : culture),
    }));
  }

  function updateContact(index: number, next: LanguageContact) {
    setConfig((current) => ({
      ...current,
      contacts: current.contacts.map((contact, i) => i === index ? next : contact),
    }));
  }

  function updateLexicon(id: string, updater: (entry: RootLexiconEntry) => RootLexiconEntry) {
    setConfig((current) => ({
      ...current,
      root_lexicon: current.root_lexicon.map((entry) => entry.id === id ? updater(entry) : entry),
    }));
  }

  async function save(status: "draft" | "configured" = "configured") {
    setBusy(true);
    setMessage("");
    try {
      const saved = await saveLanguageCulture(projectId, { ...config, status });
      setConfig(saved);
      localStorage.setItem(draftKey, JSON.stringify(saved));
      setMessage(status === "configured" ? "言語・文化設定を保存しました。" : "下書きを保存しました。");
      return true;
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "保存できませんでした。");
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function preview(languageId: string, kind: "person" | "place" | "item" | "title") {
    const saved = await save("draft");
    if (!saved) return;
    try {
      const names = await previewLanguageNames(projectId, languageId, kind, 10, 42);
      setPreviews((current) => ({ ...current, [`${languageId}:${kind}`]: names }));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "名前プレビューを生成できませんでした。");
    }
  }

  if (!loaded || !catalog || !project) {
    return (
      <main className="shell narrow">
        <p className="eyebrow">M2.5 · LANGUAGE & CULTURE BUILDER</p>
        <h1>言語・文化設計</h1>
        <p>{message || "読み込んでいます…"}</p>
      </main>
    );
  }

  return (
    <main className="shell language-shell">
      <div className="overview-head">
        <div>
          <p className="eyebrow">M2.5 · LANGUAGE & CULTURE BUILDER</p>
          <h1>{project.title}</h1>
          <p>プリセットは着想の候補です。実在言語を選ぶことも、複数を混ぜることも、完全オリジナルにすることもできます。</p>
        </div>
        <Link className="text-link" href={`/projects/${projectId}`}>← 作品概要</Link>
      </div>

      {message && <p className="notice">{message}</p>}

      <section className="builder-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">LANGUAGE DNA</p>
            <h2>言語を追加・設計</h2>
          </div>
          <button onClick={() => setConfig((current) => ({ ...current, languages: [...current.languages, newLanguage()] }))} type="button">＋ 言語を追加</button>
        </div>
        {config.languages.length === 0 && <p className="empty-state">まだ言語がありません。共通語を作る必要もありません。必要な言語だけ追加してください。</p>}

        <div className="language-stack">
          {config.languages.map((language) => (
            <details className="language-card" key={language.id} open>
              <summary>
                <span><strong>{language.name}</strong><small>{catalog.language_roles.find((item) => item.key === language.role)?.label ?? language.role}</small></span>
                <span>{language.inspirations.length} influences</span>
              </summary>
              <div className="language-body">
                <div className="form-grid two">
                  <label>言語名<input value={language.name} onChange={(event) => updateLanguage(language.id, (item) => ({ ...item, name: event.target.value }))} /></label>
                  <label>役割<select value={language.role} onChange={(event) => updateLanguage(language.id, (item) => ({ ...item, role: event.target.value }))}>{catalog.language_roles.map((role) => <option key={role.key} value={role.key}>{role.label}</option>)}</select></label>
                  <label>地域<input value={joinCsv(language.regions)} onChange={(event) => updateLanguage(language.id, (item) => ({ ...item, regions: csv(event.target.value) }))} placeholder="北部王国, 港湾都市" /></label>
                  <label>時代・世代<input value={language.era_label} onChange={(event) => updateLanguage(language.id, (item) => ({ ...item, era_label: event.target.value }))} placeholder="現代語 / 古語 / 第三王朝期" /></label>
                  <label>祖語・親言語<select value={language.parent_language_id ?? ""} onChange={(event) => updateLanguage(language.id, (item) => ({ ...item, parent_language_id: event.target.value || null }))}><option value="">なし / 未設定</option>{config.languages.filter((candidate) => candidate.id !== language.id).map((candidate) => <option key={candidate.id} value={candidate.id}>{candidate.name}</option>)}</select></label>
                </div>

                <div className="subpanel">
                  <h3>着想源ミキサー</h3>
                  <p className="helper">選択肢は固定ではありません。複数の着想源を0〜100で混ぜ、自由入力も追加できます。</p>
                  <div className="inline-fields">
                    <select defaultValue="" onChange={(event) => { addPresetInspiration(language.id, event.target.value); event.target.value = ""; }}>
                      <option value="">プリセットを追加…</option>
                      {catalog.inspirations.map((inspiration) => <option key={inspiration.key} value={inspiration.key}>{inspiration.label}</option>)}
                    </select>
                    <input value={customInspiration[language.id] ?? ""} onChange={(event) => setCustomInspiration((current) => ({ ...current, [language.id]: event.target.value }))} placeholder="自由な着想源" />
                    <button className="secondary" onClick={() => addCustomInspiration(language.id)} type="button">自由入力を追加</button>
                  </div>
                  <div className="influence-stack">
                    {language.inspirations.map((influence, index) => {
                      const catalogItem = catalog.inspirations.find((item) => item.key === influence.source);
                      return (
                        <div className="influence-row" key={`${influence.source}-${index}`}>
                          <div><strong>{catalogItem?.label ?? influence.source.replace("custom:", "")}</strong>{catalogItem?.note && <small>{catalogItem.note}</small>}</div>
                          <input type="range" min={0} max={100} value={influence.weight} onChange={(event) => updateLanguage(language.id, (item) => ({ ...item, inspirations: item.inspirations.map((entry, i) => i === index ? { ...entry, weight: Number(event.target.value) } : entry) }))} />
                          <b>{influence.weight}</b>
                          <button className="danger-lite" onClick={() => updateLanguage(language.id, (item) => ({ ...item, inspirations: item.inspirations.filter((_, i) => i !== index) }))} type="button">削除</button>
                        </div>
                      );
                    })}
                  </div>
                </div>

                <div className="subpanel">
                  <h3>音韻・音節</h3>
                  <div className="form-grid three">
                    <label>語頭候補<input value={joinCsv(language.phonology.onsets)} onChange={(event) => updateLanguage(language.id, (item) => ({ ...item, phonology: { ...item.phonology, onsets: csv(event.target.value) } }))} /></label>
                    <label>母音核<input value={joinCsv(language.phonology.nuclei)} onChange={(event) => updateLanguage(language.id, (item) => ({ ...item, phonology: { ...item.phonology, nuclei: csv(event.target.value) } }))} /></label>
                    <label>語末候補<input value={joinCsv(language.phonology.codas)} onChange={(event) => updateLanguage(language.id, (item) => ({ ...item, phonology: { ...item.phonology, codas: csvKeepEmpty(event.target.value) } }))} placeholder="空欄, n, r" /></label>
                    <label>最小音節<input type="number" min={1} max={6} value={language.phonology.syllables_min} onChange={(event) => updateLanguage(language.id, (item) => ({ ...item, phonology: { ...item.phonology, syllables_min: Number(event.target.value) } }))} /></label>
                    <label>最大音節<input type="number" min={1} max={8} value={language.phonology.syllables_max} onChange={(event) => updateLanguage(language.id, (item) => ({ ...item, phonology: { ...item.phonology, syllables_max: Number(event.target.value) } }))} /></label>
                    <label>禁止連続<input value={joinCsv(language.phonology.forbidden_sequences)} onChange={(event) => updateLanguage(language.id, (item) => ({ ...item, phonology: { ...item.phonology, forbidden_sequences: csv(event.target.value) } }))} /></label>
                  </div>
                </div>

                <div className="subpanel">
                  <h3>命名規則</h3>
                  <div className="form-grid two">
                    {(["person", "place", "item", "title"] as const).map((kind) => (
                      <label key={`suffix-${kind}`}>{kind} 語尾<input value={joinCsv(language.naming.suffixes[kind] ?? [])} onChange={(event) => updateLanguage(language.id, (item) => ({ ...item, naming: { ...item.naming, suffixes: { ...item.naming.suffixes, [kind]: csvKeepEmpty(event.target.value) } } }))} /></label>
                    ))}
                  </div>
                  <textarea value={language.naming.notes} onChange={(event) => updateLanguage(language.id, (item) => ({ ...item, naming: { ...item.naming, notes: event.target.value } }))} placeholder="家名、地名、称号などの命名ルール" />
                  <div className="preview-actions">
                    {(["person", "place", "item", "title"] as const).map((kind) => <button className="secondary" key={kind} onClick={() => preview(language.id, kind)} type="button">{kind} を保存してプレビュー</button>)}
                  </div>
                  {Object.entries(previews).filter(([key]) => key.startsWith(`${language.id}:`)).map(([key, names]) => <div className="name-preview" key={key}><b>{key.split(":")[1]}</b><span>{names.join(" · ")}</span></div>)}
                </div>

                <div className="subpanel">
                  <h3>文字体系</h3>
                  <div className="form-grid three">
                    <label>文字体系名<input value={language.script.name} onChange={(event) => updateLanguage(language.id, (item) => ({ ...item, script: { ...item.script, name: event.target.value } }))} /></label>
                    <label>種別<input value={language.script.type} onChange={(event) => updateLanguage(language.id, (item) => ({ ...item, script: { ...item.script, type: event.target.value } }))} placeholder="alphabetic / syllabic / logographic..." /></label>
                    <label>筆記方向<select value={language.script.direction} onChange={(event) => updateLanguage(language.id, (item) => ({ ...item, script: { ...item.script, direction: event.target.value } }))}>{catalog.writing_directions.map((direction) => <option key={direction.key} value={direction.key}>{direction.label}</option>)}</select></label>
                  </div>
                  <textarea value={language.script.notes} onChange={(event) => updateLanguage(language.id, (item) => ({ ...item, script: { ...item.script, notes: event.target.value } }))} placeholder="碑文、看板、写本、魔法陣などの使われ方" />
                </div>

                <label className="block-label">言語メモ<textarea value={language.notes} onChange={(event) => updateLanguage(language.id, (item) => ({ ...item, notes: event.target.value }))} /></label>
                <button className="danger-lite" onClick={() => removeLanguage(language.id)} type="button">この言語を削除</button>
              </div>
            </details>
          ))}
        </div>
      </section>

      <section className="builder-section">
        <div className="section-heading">
          <div><p className="eyebrow">CULTURE</p><h2>文化圏</h2></div>
          <button onClick={() => setConfig((current) => ({ ...current, cultures: [...current.cultures, newCulture(current.languages[0]?.id ?? null)] }))} type="button">＋ 文化を追加</button>
        </div>
        <div className="culture-grid">
          {config.cultures.map((culture) => (
            <article className="culture-card" key={culture.id}>
              <div className="section-heading compact"><input className="card-title-input" value={culture.name} onChange={(event) => updateCulture(culture.id, (item) => ({ ...item, name: event.target.value }))} /><button className="danger-lite" onClick={() => setConfig((current) => ({ ...current, cultures: current.cultures.filter((item) => item.id !== culture.id) }))} type="button">削除</button></div>
              <label>地域<input value={joinCsv(culture.regions)} onChange={(event) => updateCulture(culture.id, (item) => ({ ...item, regions: csv(event.target.value) }))} /></label>
              <div className="checkbox-group"><span>使用言語</span>{config.languages.map((language) => <label key={language.id}><input type="checkbox" checked={culture.language_ids.includes(language.id)} onChange={(event) => updateCulture(culture.id, (item) => ({ ...item, language_ids: event.target.checked ? [...item.language_ids, language.id] : item.language_ids.filter((id) => id !== language.id) }))} />{language.name}</label>)}</div>
              <label>文化タグ<input value={joinCsv(culture.tags)} onChange={(event) => updateCulture(culture.id, (item) => ({ ...item, tags: csv(event.target.value) }))} /></label>
              <label>制度・組織<input value={joinCsv(culture.institutions)} onChange={(event) => updateCulture(culture.id, (item) => ({ ...item, institutions: csv(event.target.value) }))} /></label>
              <label>作法<textarea value={culture.etiquette} onChange={(event) => updateCulture(culture.id, (item) => ({ ...item, etiquette: event.target.value }))} /></label>
              <label>禁忌<input value={joinCsv(culture.taboos)} onChange={(event) => updateCulture(culture.id, (item) => ({ ...item, taboos: csv(event.target.value) }))} /></label>
              <label>祭礼<input value={joinCsv(culture.festivals)} onChange={(event) => updateCulture(culture.id, (item) => ({ ...item, festivals: csv(event.target.value) }))} /></label>
              <label>物質文化<textarea value={culture.material_culture} onChange={(event) => updateCulture(culture.id, (item) => ({ ...item, material_culture: event.target.value }))} /></label>
            </article>
          ))}
        </div>
      </section>

      <section className="builder-section">
        <div className="section-heading">
          <div><p className="eyebrow">CONTACT & LOANWORDS</p><h2>言語接触</h2></div>
          <button disabled={config.languages.length < 2} onClick={() => setConfig((current) => ({ ...current, contacts: [...current.contacts, { from_language_id: current.languages[0].id, to_language_id: current.languages[1].id, intensity: 50, domains: ["trade"], borrowing_policy: "adapt", notes: "" }] }))} type="button">＋ 接触関係</button>
        </div>
        {config.contacts.map((contact, index) => (
          <div className="contact-row" key={`${contact.from_language_id}-${contact.to_language_id}-${index}`}>
            <select value={contact.from_language_id} onChange={(event) => updateContact(index, { ...contact, from_language_id: event.target.value })}>{config.languages.map((language) => <option key={language.id} value={language.id}>{language.name}</option>)}</select>
            <span>→</span>
            <select value={contact.to_language_id} onChange={(event) => updateContact(index, { ...contact, to_language_id: event.target.value })}>{config.languages.map((language) => <option key={language.id} value={language.id}>{language.name}</option>)}</select>
            <label>強度 <input type="range" min={0} max={100} value={contact.intensity} onChange={(event) => updateContact(index, { ...contact, intensity: Number(event.target.value) })} /> {contact.intensity}</label>
            <input value={joinCsv(contact.domains)} onChange={(event) => updateContact(index, { ...contact, domains: csv(event.target.value) })} placeholder="trade, religion..." />
            <input value={contact.borrowing_policy} onChange={(event) => updateContact(index, { ...contact, borrowing_policy: event.target.value })} placeholder="adapt / preserve / calque" />
            <button className="danger-lite" onClick={() => setConfig((current) => ({ ...current, contacts: current.contacts.filter((_, i) => i !== index) }))} type="button">削除</button>
          </div>
        ))}
      </section>

      <section className="builder-section">
        <div className="section-heading">
          <div><p className="eyebrow">ETYMOLOGY</p><h2>語根・語源台帳</h2></div>
          <button disabled={config.languages.length === 0} onClick={() => setConfig((current) => ({ ...current, root_lexicon: [...current.root_lexicon, { id: stableId("root"), language_id: current.languages[0].id, form: "", meaning: "", tags: [], origin: "native", notes: "" }] }))} type="button">＋ 語根</button>
        </div>
        <div className="lexicon-stack">
          {config.root_lexicon.map((entry) => (
            <div className="lexicon-row" key={entry.id}>
              <select value={entry.language_id} onChange={(event) => updateLexicon(entry.id, (item) => ({ ...item, language_id: event.target.value }))}>{config.languages.map((language) => <option key={language.id} value={language.id}>{language.name}</option>)}</select>
              <input value={entry.form} onChange={(event) => updateLexicon(entry.id, (item) => ({ ...item, form: event.target.value }))} placeholder="語根" />
              <input value={entry.meaning} onChange={(event) => updateLexicon(entry.id, (item) => ({ ...item, meaning: event.target.value }))} placeholder="意味" />
              <input value={joinCsv(entry.tags)} onChange={(event) => updateLexicon(entry.id, (item) => ({ ...item, tags: csv(event.target.value) }))} placeholder="地名, 天候..." />
              <input value={entry.origin} onChange={(event) => updateLexicon(entry.id, (item) => ({ ...item, origin: event.target.value }))} placeholder="native / loan / calque" />
              <button className="danger-lite" onClick={() => setConfig((current) => ({ ...current, root_lexicon: current.root_lexicon.filter((item) => item.id !== entry.id) }))} type="button">削除</button>
            </div>
          ))}
        </div>
      </section>

      <section className="builder-section">
        <p className="eyebrow">READER LAYER & EARTH-ORIGIN POLICY</p>
        <h2>読者向け表示と言葉の出自</h2>
        <div className="form-grid two">
          <label>共通語<select value={config.common_language_id ?? ""} onChange={(event) => setConfig((current) => ({ ...current, common_language_id: event.target.value || null }))}><option value="">設定しない</option>{config.languages.map((language) => <option key={language.id} value={language.id}>{language.name}</option>)}</select></label>
          <label>読者向け表示<select value={String(config.display_policy.mode ?? "translated")} onChange={(event) => setConfig((current) => ({ ...current, display_policy: { ...current.display_policy, mode: event.target.value } }))}>{catalog.display_modes.map((mode) => <option key={mode.key} value={mode.key}>{mode.label}</option>)}</select></label>
          <label>初出表示<select value={String(config.display_policy.first_mention ?? "original_with_reading")} onChange={(event) => setConfig((current) => ({ ...current, display_policy: { ...current.display_policy, first_mention: event.target.value } }))}><option value="original_with_reading">原語＋読み</option><option value="translated">翻訳名</option><option value="original">原語のみ</option><option value="custom">カスタム</option></select></label>
          <label>2回目以降<select value={String(config.display_policy.later_mentions ?? "translated")} onChange={(event) => setConfig((current) => ({ ...current, display_policy: { ...current.display_policy, later_mentions: event.target.value } }))}><option value="translated">翻訳名</option><option value="reading">読みのみ</option><option value="original">原語のみ</option><option value="custom">カスタム</option></select></label>
          <label>地球由来語ガード<select value={String(config.earth_term_policy.mode ?? "warn")} onChange={(event) => setConfig((current) => ({ ...current, earth_term_policy: { ...current.earth_term_policy, mode: event.target.value } }))}>{catalog.earth_term_modes.map((mode) => <option key={mode.key} value={mode.key}>{mode.label}</option>)}</select></label>
          <label>置換提案<select value={String(config.earth_term_policy.replacement_mode ?? "both")} onChange={(event) => setConfig((current) => ({ ...current, earth_term_policy: { ...current.earth_term_policy, replacement_mode: event.target.value } }))}>{catalog.replacement_modes.map((mode) => <option key={mode.key} value={mode.key}>{mode.label}</option>)}</select></label>
          <label>許可する文脈<input value={joinCsv(Array.isArray(config.earth_term_policy.allowed_contexts) ? config.earth_term_policy.allowed_contexts.map(String) : [])} onChange={(event) => setConfig((current) => ({ ...current, earth_term_policy: { ...current.earth_term_policy, allowed_contexts: csv(event.target.value) } }))} placeholder="転生者の内心, 引用..." /></label>
        </div>
        <p className="helper">M2.5では警告方針と世界内語彙への置換基盤までを保存します。実際の大規模な地球由来語辞書と本文LintはM5で接続します。</p>
      </section>

      <section className="save-bar">
        <div><strong>{config.languages.length}</strong> languages · <strong>{config.cultures.length}</strong> cultures · <strong>{config.root_lexicon.length}</strong> roots</div>
        <div className="save-actions"><button className="secondary" disabled={busy} onClick={() => save("draft")} type="button">下書き保存</button><button disabled={busy} onClick={() => save("configured")} type="button">{busy ? "保存中…" : "設定を確定して保存"}</button></div>
      </section>
    </main>
  );
}