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
  category?: string;
  note?: string;
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

export type LanguageInfluence = { source: string; weight: number };

export type LanguageProfile = {
  id: string;
  name: string;
  role: string;
  regions: string[];
  inspirations: LanguageInfluence[];
  parent_language_id: string | null;
  era_label: string;
  phonology: {
    onsets: string[];
    nuclei: string[];
    codas: string[];
    forbidden_sequences: string[];
    syllables_min: number;
    syllables_max: number;
    separator: string;
    capitalize: boolean;
  };
  naming: {
    prefixes: Record<string, string[]>;
    suffixes: Record<string, string[]>;
    notes: string;
  };
  script: { name: string; type: string; direction: string; notes: string };
  notes: string;
};

export type CultureProfile = {
  id: string;
  name: string;
  regions: string[];
  language_ids: string[];
  tags: string[];
  institutions: string[];
  etiquette: string;
  taboos: string[];
  festivals: string[];
  material_culture: string;
  notes: string;
};

export type LanguageContact = {
  from_language_id: string;
  to_language_id: string;
  intensity: number;
  domains: string[];
  borrowing_policy: string;
  notes: string;
};

export type RootLexiconEntry = {
  id: string;
  language_id: string;
  form: string;
  meaning: string;
  tags: string[];
  origin: string;
  notes: string;
};

export type LanguageCultureWrite = {
  languages: LanguageProfile[];
  cultures: CultureProfile[];
  contacts: LanguageContact[];
  root_lexicon: RootLexiconEntry[];
  display_policy: Record<string, unknown>;
  earth_term_policy: Record<string, unknown>;
  common_language_id: string | null;
  status: "draft" | "configured";
};

export type LanguageCultureConfig = LanguageCultureWrite & {
  project_id: string;
  builder_version: number;
  created_at: string;
  updated_at: string;
};

export type LanguageCultureCatalog = {
  inspirations: CatalogItem[];
  language_roles: CatalogItem[];
  writing_directions: CatalogItem[];
  display_modes: CatalogItem[];
  earth_term_modes: CatalogItem[];
  replacement_modes: CatalogItem[];
  contact_domains: CatalogItem[];
  catalog_version: number;
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

export async function getLanguageCultureCatalog(): Promise<LanguageCultureCatalog> {
  return expectJson(await fetch(`${API_BASE}/api/v1/catalog/language-culture`, { cache: "no-store" }));
}

export async function getLanguageCulture(projectId: string): Promise<LanguageCultureConfig> {
  return expectJson(
    await fetch(`${API_BASE}/api/v1/projects/${projectId}/language-culture`, { cache: "no-store" }),
  );
}

export async function saveLanguageCulture(projectId: string, payload: LanguageCultureWrite): Promise<LanguageCultureConfig> {
  return expectJson(
    await fetch(`${API_BASE}/api/v1/projects/${projectId}/language-culture`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  );
}

export async function previewLanguageNames(
  projectId: string,
  languageId: string,
  kind: "person" | "place" | "item" | "title",
  count = 10,
  seed = 1,
): Promise<string[]> {
  const payload = await expectJson<{ names: string[] }>(
    await fetch(`${API_BASE}/api/v1/projects/${projectId}/language-culture/languages/${languageId}/preview-names`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kind, count, seed }),
    }),
  );
  return payload.names;
}