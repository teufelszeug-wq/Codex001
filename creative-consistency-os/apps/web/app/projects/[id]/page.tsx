import Link from "next/link";
import { getProject, getWorldBuilder, getWorldBuilderCatalog, type WorldBuilderProfile } from "../../../lib/api";

export default async function ProjectOverview({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const project = await getProject(id);

  let profile: WorldBuilderProfile | null = null;
  try {
    profile = await getWorldBuilder(id);
  } catch {
    profile = null;
  }

  const catalog = await getWorldBuilderCatalog();
  const genreLabels = Object.fromEntries(catalog.genres.map((item) => [item.key, item.label]));
  const sectionLabels = Object.fromEntries(catalog.world_dna_sections.map((item) => [item.key, item.label]));

  return (
    <main className="shell">
      <p className="eyebrow">PROJECT OVERVIEW</p>
      <div className="overview-head">
        <div>
          <h1>{project.title}</h1>
          <p>Project schema v{project.schema_version}</p>
        </div>
        <Link className="text-link" href="/projects">← 作品一覧</Link>
      </div>

      <section className="tool-strip">
        <Link className="tool-card" href={`/projects/${id}/language-culture`}>
          <span>M2.5</span>
          <strong>言語・文化を設計</strong>
          <small>Language DNA / Culture / Loanwords / Etymology</small>
        </Link>
        <Link className="tool-card" href={`/projects/${id}/writing`}>
          <span>M3</span>
          <strong>Writing Room</strong>
          <small>Story Bible / Manuscript / Revision / Timeline</small>
        </Link>
      </section>

      {!profile ? (
        <section className="wizard-panel">
          <h2>World Builder未設定</h2>
          <p>この作品にはまだWorld Builder Profileがありません。</p>
        </section>
      ) : (
        <>
          <section className="summary-grid">
            <article className="summary-card">
              <span>ジャンル</span>
              <strong>
                {[
                  ...profile.selected_genres.map((key) => genreLabels[key] ?? key),
                  ...profile.custom_genres.map((item) => String(item.name)),
                ].join(" × ")}
              </strong>
            </article>
            <article className="summary-card">
              <span>制作モード</span>
              <strong>{catalog.setup_modes.find((item) => item.key === profile.setup_mode)?.label ?? profile.setup_mode}</strong>
            </article>
            <article className="summary-card">
              <span>設定状態</span>
              <strong>{profile.status}</strong>
            </article>
          </section>

          <section className="wizard-panel">
            <h2>World DNA</h2>
            <div className="dna-summary">
              {catalog.world_dna_sections.map((section) => (
                <div className="dna-summary-row" key={section.key}>
                  <span>{section.label}</span>
                  <b>{profile.section_modes[section.key]?.toUpperCase()}</b>
                  <small>{profile.section_notes[section.key] || "メモなし"}</small>
                </div>
              ))}
            </div>
          </section>

          <section className="wizard-panel">
            <h2>ジャンル構成からの初期優先度</h2>
            <p>これは命令ではなく、World Builderがどこを詳しく聞くか決めるための提案値です。</p>
            <div className="priority-grid">
              {Object.entries(profile.recommendations)
                .sort((a, b) => b[1].score - a[1].score)
                .map(([key, recommendation]) => (
                  <article className={`priority-card ${recommendation.priority}`} key={key}>
                    <span>{sectionLabels[key] ?? key}</span>
                    <strong>{recommendation.score}</strong>
                    <small>{recommendation.priority}</small>
                  </article>
                ))}
            </div>
          </section>
        </>
      )}
    </main>
  );
}