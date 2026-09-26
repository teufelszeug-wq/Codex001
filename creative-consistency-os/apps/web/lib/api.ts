export type Project = {
  id: string;
  title: string;
  schema_version: number;
  created_at: string;
  updated_at: string;
};

export type CatalogItem = {
  key: string;
  label: string;
  description?: string;
  detail_milestone?: string;
};

export type WorldBuilderCatalog = {
  genres: CatalogItem[];
  setup_modes: CatalogItem[];
  section_modes: CatalogItem[];
  world_dna_sections: CatalogItem[];
  import_formats: CatalogItem[];
  catalog_version: number;
};

export type CustomGenre = { name: string; weight: number };

export type WorldBuilderWrite = {
  setup_mode: string;
  selected_genres: string[];
  genre_weights: Record<string, number>;
  custom_genres: CustomGenre[];
  section_modes: Record<string, string>;
  section_notes: Record<string, string>;
  import_format: string | null;
  import_notes: string | null;
  status: "draft" | "configured";
};

export type Recommendation = {
  score: number;
  priority: "high" | "standard" | "light";
  reason: string;
};

export type WorldBuilderProfile = WorldBuilderWrite & {
  project_id: string;
  recommendations: Record<string, Recommendation>;
  wizard_version: number;
  created_at: string;
  updated_at: string;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function expectJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = "Request failed";
    try {
      const payload = await response.json();
      detail = payload.detail ?? detail;
    } catch {
      // Keep generic message.
    }
    throw new Error(detail);
  }
  return response.json();
}

export async function listProjects(): Promise<Project[]> {
  return expectJson(await fetch(`${API_BASE}/api/v1/projects`, { cache: "no-store" }));
}

export async function getProject(projectId: string): Promise<Project> {
  return expectJson(await fetch(`${API_BASE}/api/v1/projects/${projectId}`, { cache: "no-store" }));
}

export async function createProject(title: string): Promise<Project> {
  return expectJson(
    await fetch(`${API_BASE}/api/v1/projects`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title }),
    }),
  );
}

export async function getWorldBuilderCatalog(): Promise<WorldBuilderCatalog> {
  return expectJson(await fetch(`${API_BASE}/api/v1/catalog/world-builder`, { cache: "no-store" }));
}

export async function saveWorldBuilder(projectId: string, payload: WorldBuilderWrite): Promise<WorldBuilderProfile> {
  return expectJson(
    await fetch(`${API_BASE}/api/v1/projects/${projectId}/world-builder`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  );
}

export async function getWorldBuilder(projectId: string): Promise<WorldBuilderProfile> {
  return expectJson(
    await fetch(`${API_BASE}/api/v1/projects/${projectId}/world-builder`, { cache: "no-store" }),
  );
}