export type Project = {
  id: string;
  title: string;
  schema_version: number;
  created_at: string;
  updated_at: string;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export async function listProjects(): Promise<Project[]> {
  const response = await fetch(`${API_BASE}/api/v1/projects`, { cache: "no-store" });
  if (!response.ok) throw new Error("Failed to load projects");
  return response.json();
}

export async function createProject(title: string): Promise<Project> {
  const response = await fetch(`${API_BASE}/api/v1/projects`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
  if (!response.ok) throw new Error("Failed to create project");
  return response.json();
}
