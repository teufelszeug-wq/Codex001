import { listProjects, type Project } from "../../lib/api";

export default async function ProjectsPage() {
  let projects: Project[] = [];
  let error = false;
  try {
    projects = await listProjects();
  } catch {
    error = true;
  }

  return (
    <main className="shell narrow">
      <p className="eyebrow">PROJECTS</p>
      <h1>作品を開く</h1>
      {error ? (
        <p className="notice">APIに接続できません。ローカルAPIを起動してください。</p>
      ) : projects.length === 0 ? (
        <p>まだ作品がありません。</p>
      ) : (
        <div className="list">
          {projects.map((project) => (
            <article className="row" key={project.id}>
              <strong>{project.title}</strong>
              <small>schema v{project.schema_version}</small>
            </article>
          ))}
        </div>
      )}
    </main>
  );
}
