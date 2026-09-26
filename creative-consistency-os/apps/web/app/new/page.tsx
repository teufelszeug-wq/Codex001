"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  createProject,
  getWorldBuilderCatalog,
  saveWorldBuilder,
  type CustomGenre,
  type WorldBuilderCatalog,
} from "../../lib/api";

const DRAFT_KEY = "ccos-world-builder-draft-v1";

type Draft = {
  step: number;
  selectedGenres: string[];
  genreWeights: Record<string, number>;
  customGenres: CustomGenre[];
  setupMode: string;
  sectionModes: Record<string, string>;
  sectionNotes: Record<string, string>;
  importFormat: string;
  importNotes: string;
  title: string;
};

const emptyDraft: Draft = {
  step: 1,
  selectedGenres: [],
  genreWeights: {},
  customGenres: [],
  setupMode: "guided",
  sectionModes: {},
  sectionNotes: {},
  importFormat: "",
  importNotes: "",
  title: "",
};

function defaultModeForSetup(setupMode: string) {
  if (setupMode === "full") return "manual";
  if (setupMode === "blank") return "skip";
  return "auto";
}

export default function NewProjectPage() {
  const router = useRouter();
  const [catalog, setCatalog] = useState<WorldBuilderCatalog | null>(null);
  const [draft, setDraft] = useState<Draft>(emptyDraft);
  const [customName, setCustomName] = useState("");
  const [customWeight, setCustomWeight] = useState(50);
  const [hydrated, setHydrated] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    const raw = localStorage.getItem(DRAFT_KEY);
    if (raw) {
      try {
        setDraft({ ...emptyDraft, ...JSON.parse(raw) });
      } catch {
        localStorage.removeItem(DRAFT_KEY);
      }
    }
    setHydrated(true);
    getWorldBuilderCatalog().then(setCatalog).catch(() => setMessage("APIからWorld Builder設定を取得できません。"));
  }, []);

  useEffect(() => {
    if (hydrated) localStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
  }, [draft, hydrated]);

  const canLeaveGenre = draft.selectedGenres.length > 0 || draft.customGenres.length > 0;
  const selectedLabels = useMemo(() => {
    if (!catalog) return draft.selectedGenres;
    const labelMap = Object.fromEntries(catalog.genres.map((item) => [item.key, item.label]));
    return draft.selectedGenres.map((key) => labelMap[key] ?? key);
  }, [catalog, draft.selectedGenres]);

  function toggleGenre(key: string) {
    setDraft((current) => {
      const selected = current.selectedGenres.includes(key);
      const selectedGenres = selected
        ? current.selectedGenres.filter((item) => item !== key)
        : [...current.selectedGenres, key];
      const genreWeights = { ...current.genreWeights };
      if (selected) delete genreWeights[key];
      else genreWeights[key] = 50;
      return { ...current, selectedGenres, genreWeights };
    });
  }

  function chooseSetupMode(mode: string) {
    if (!catalog) return;
    const defaultMode = defaultModeForSetup(mode);
    setDraft((current) => ({
      ...current,
      setupMode: mode,
      sectionModes: Object.fromEntries(catalog.world_dna_sections.map((section) => [section.key, defaultMode])),
    }));
  }

  function addCustomGenre() {
    const name = customName.trim();
    if (!name) return;
    setDraft((current) => {
      if (current.customGenres.some((item) => item.name.toLocaleLowerCase() === name.toLocaleLowerCase())) return current;
      return { ...current, customGenres: [...current.customGenres, { name, weight: customWeight }] };
    });
    setCustomName("");
    setCustomWeight(50);
  }

  async function finish() {
    if (!catalog || !draft.title.trim()) return;
    setBusy(true);
    setMessage("");
    try {
      const project = await createProject(draft.title.trim());
      const normalizedModes = Object.fromEntries(
        catalog.world_dna_sections.map((section) => [
          section.key,
          draft.sectionModes[section.key] ?? defaultModeForSetup(draft.setupMode),
        ]),
      );
      await saveWorldBuilder(project.id, {
        setup_mode: draft.setupMode,
        selected_genres: draft.selectedGenres,
        genre_weights: draft.genreWeights,
        custom_genres: draft.customGenres,
        section_modes: normalizedModes,
        section_notes: draft.sectionNotes,
        import_format: draft.setupMode === "import" ? draft.importFormat || null : null,
        import_notes: draft.setupMode === "import" ? draft.importNotes || null : null,
        status: "configured",
      });
      localStorage.removeItem(DRAFT_KEY);
      router.push(`/projects/${project.id}`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "作品を作成できませんでした。");
    } finally {
      setBusy(false);
    }
  }

  if (!catalog) {
    return (
      <main className="shell narrow">
        <p className="eyebrow">M2 · WORLD BUILDER ALPHA</p>
        <h1>新しい作品を作る</h1>
        <p>{message || "World Builderを準備しています…"}</p>
      </main>
    );
  }

  return (
    <main className="shell wizard-shell">
      <div className="wizard-head">
        <div>
          <p className="eyebrow">M2 · WORLD BUILDER ALPHA</p>
          <h1>新しい作品を作る</h1>
        </div>
        <div className="step-counter">STEP {draft.step} / 4</div>
      </div>

      <div className="progress-track"><span style={{ width: `${draft.step * 25}%` }} /></div>

      {draft.step === 1 && (
        <section className="wizard-panel">
          <h2>1. 小説ジャンルを選ぶ</h2>
          <p>複数選択できます。主ジャンルは必須ではありません。あとで変更できます。</p>
          <div className="choice-grid">
            {catalog.genres.map((genre) => {
              const selected = draft.selectedGenres.includes(genre.key);
              return (
                <button
                  className={`choice-card ${selected ? "selected" : ""}`}
                  key={genre.key}
                  onClick={() => toggleGenre(genre.key)}
                  type="button"
                >
                  <strong>{genre.label}</strong>
                  <span>{genre.description}</span>
                </button>
              );
            })}
          </div>

          {draft.selectedGenres.length > 0 && (
            <div className="weight-stack">
              <h3>ジャンルの重み</h3>
              {draft.selectedGenres.map((key) => {
                const genre = catalog.genres.find((item) => item.key === key);
                return (
                  <label className="range-row" key={key}>
                    <span>{genre?.label ?? key}</span>
                    <input
                      max={100}
                      min={0}
                      onChange={(event) =>
                        setDraft((current) => ({
                          ...current,
                          genreWeights: { ...current.genreWeights, [key]: Number(event.target.value) },
                        }))
                      }
                      type="range"
                      value={draft.genreWeights[key] ?? 50}
                    />
                    <b>{draft.genreWeights[key] ?? 50}</b>
                  </label>
                );
              })}
            </div>
          )}

          <div className="custom-genre">
            <h3>独自ジャンルを追加</h3>
            <div className="inline-fields">
              <input
                maxLength={80}
                onChange={(event) => setCustomName(event.target.value)}
                placeholder="例：旅と群像劇"
                value={customName}
              />
              <input
                aria-label="独自ジャンルの重み"
                max={100}
                min={0}
                onChange={(event) => setCustomWeight(Number(event.target.value))}
                type="number"
                value={customWeight}
              />
              <button onClick={addCustomGenre} type="button">追加</button>
            </div>
            {draft.customGenres.length > 0 && (
              <div className="chip-row">
                {draft.customGenres.map((item) => (
                  <button
                    className="chip"
                    key={item.name}
                    onClick={() =>
                      setDraft((current) => ({
                        ...current,
                        customGenres: current.customGenres.filter((genre) => genre.name !== item.name),
                      }))
                    }
                    type="button"
                  >
                    {item.name} · {item.weight} ×
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="wizard-actions end">
            <button disabled={!canLeaveGenre} onClick={() => setDraft((current) => ({ ...current, step: 2 }))} type="button">
              次へ
            </button>
          </div>
        </section>
      )}

      {draft.step === 2 && (
        <section className="wizard-panel">
          <h2>2. 作り方を選ぶ</h2>
          <p>自動化の強さを決めます。どのモードでも後から各項目を個別変更できます。</p>
          <div className="choice-grid setup-grid">
            {catalog.setup_modes.map((mode) => (
              <button
                className={`choice-card ${draft.setupMode === mode.key ? "selected" : ""}`}
                key={mode.key}
                onClick={() => chooseSetupMode(mode.key)}
                type="button"
              >
                <strong>{mode.label}</strong>
                <span>{mode.description}</span>
              </button>
            ))}
          </div>

          {draft.setupMode === "import" && (
            <div className="import-box">
              <label>
                取り込む資料形式
                <select onChange={(event) => setDraft((current) => ({ ...current, importFormat: event.target.value }))} value={draft.importFormat}>
                  <option value="">選択してください</option>
                  {catalog.import_formats.map((format) => (
                    <option key={format.key} value={format.key}>{format.label}</option>
                  ))}
                </select>
              </label>
              <label>
                資料についてのメモ
                <textarea
                  maxLength={2000}
                  onChange={(event) => setDraft((current) => ({ ...current, importNotes: event.target.value }))}
                  placeholder="既存設定集、執筆済み原稿など"
                  value={draft.importNotes}
                />
              </label>
              <p className="helper">M2では取り込み方針を保存します。実ファイル解析は後続工程で安全なImport処理として実装します。</p>
            </div>
          )}

          <div className="wizard-actions">
            <button className="secondary" onClick={() => setDraft((current) => ({ ...current, step: 1 }))} type="button">戻る</button>
            <button
              disabled={draft.setupMode === "import" && !draft.importFormat}
              onClick={() => setDraft((current) => ({ ...current, step: 3 }))}
              type="button"
            >
              次へ
            </button>
          </div>
        </section>
      )}

      {draft.step === 3 && (
        <section className="wizard-panel">
          <h2>3. World DNA</h2>
          <p>AUTO / MANUAL / SKIPを項目ごとに選択します。プリセットは開始点であり、固定ではありません。</p>
          <div className="dna-stack">
            {catalog.world_dna_sections.map((section) => {
              const mode = draft.sectionModes[section.key] ?? defaultModeForSetup(draft.setupMode);
              return (
                <article className="dna-row" key={section.key}>
                  <div className="dna-copy">
                    <strong>{section.label}</strong>
                    <span>{section.description}</span>
                  </div>
                  <div className="segmented">
                    {catalog.section_modes.map((item) => (
                      <button
                        className={mode === item.key ? "active" : ""}
                        key={item.key}
                        onClick={() =>
                          setDraft((current) => ({
                            ...current,
                            sectionModes: { ...current.sectionModes, [section.key]: item.key },
                          }))
                        }
                        type="button"
                      >
                        {item.label}
                      </button>
                    ))}
                  </div>
                  <textarea
                    maxLength={2000}
                    onChange={(event) =>
                      setDraft((current) => ({
                        ...current,
                        sectionNotes: { ...current.sectionNotes, [section.key]: event.target.value },
                      }))
                    }
                    placeholder={`${section.label}について既に決めていることがあれば入力`}
                    value={draft.sectionNotes[section.key] ?? ""}
                  />
                </article>
              );
            })}
          </div>
          <div className="wizard-actions">
            <button className="secondary" onClick={() => setDraft((current) => ({ ...current, step: 2 }))} type="button">戻る</button>
            <button onClick={() => setDraft((current) => ({ ...current, step: 4 }))} type="button">確認へ</button>
          </div>
        </section>
      )}

      {draft.step === 4 && (
        <section className="wizard-panel">
          <h2>4. 確認して作品を作る</h2>
          <div className="review-grid">
            <div className="review-card">
              <span>ジャンル</span>
              <strong>{[...selectedLabels, ...draft.customGenres.map((item) => item.name)].join(" × ")}</strong>
            </div>
            <div className="review-card">
              <span>制作モード</span>
              <strong>{catalog.setup_modes.find((item) => item.key === draft.setupMode)?.label}</strong>
            </div>
          </div>
          <label className="title-field">
            作品名
            <input
              autoFocus
              maxLength={200}
              onChange={(event) => setDraft((current) => ({ ...current, title: event.target.value }))}
              placeholder="作品タイトル"
              value={draft.title}
            />
          </label>
          <p className="helper">作成後もジャンル・重み・World DNAを編集できます。AIが自動的にCanonへ確定することはありません。</p>
          {message && <p className="notice">{message}</p>}
          <div className="wizard-actions">
            <button className="secondary" onClick={() => setDraft((current) => ({ ...current, step: 3 }))} type="button">戻る</button>
            <button disabled={busy || !draft.title.trim()} onClick={finish} type="button">{busy ? "作成中…" : "作品を作成"}</button>
          </div>
        </section>
      )}
    </main>
  );
}