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

export type BibleEntity = {
  id: string;
  project_id: string;
  entity_type: string;
  canonical_name: string;
  summary: string;
  attributes: Record<string, unknown>;
  canon_state: string;
  source_type: string;
  source_ref: string | null;
  created_at: string;
  updated_at: string;
};

export type ManuscriptDocument = {
  id: string;
  project_id: string;
  title: string;
  order_index: number;
  status: string;
  content?: string;
  content_hash: string;
  current_revision: number;
  created_at: string;
  updated_at: string;
};

export type ManuscriptRevision = {
  id: string;
  document_id: string;
  revision_no: number;
  title: string;
  content: string;
  content_hash: string;
  reason: string;
  created_at: string;
};

export type TimelineEvent = {
  id: string;
  project_id: string;
  title: string;
  start_label: string;
  end_label: string | null;
  sort_key: number;
  description: string;
  participant_ids: string[];
  canon_state: string;
  source_type: string;
  created_at: string;
  updated_at: string;
};

export async function listBible(projectId: string): Promise<BibleEntity[]> {
  return expectJson(await fetch(`${API_BASE}/api/v1/projects/${projectId}/bible`, { cache: "no-store" }));
}

export async function createBible(
  projectId: string,
  payload: {
    entity_type: string;
    canonical_name: string;
    summary?: string;
    attributes?: Record<string, unknown>;
    canon_state?: string;
    source_type?: string;
    source_ref?: string | null;
  },
): Promise<BibleEntity> {
  return expectJson(
    await fetch(`${API_BASE}/api/v1/projects/${projectId}/bible`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  );
}

export async function updateBible(
  projectId: string,
  entityId: string,
  payload: Partial<Pick<BibleEntity, "entity_type" | "canonical_name" | "summary" | "attributes" | "source_type" | "source_ref">>,
): Promise<BibleEntity> {
  return expectJson(
    await fetch(`${API_BASE}/api/v1/projects/${projectId}/bible/${entityId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  );
}

export async function transitionBibleCanon(
  projectId: string,
  entityId: string,
  targetState: string,
  reason: string,
): Promise<BibleEntity> {
  return expectJson(
    await fetch(`${API_BASE}/api/v1/projects/${projectId}/bible/${entityId}/canon`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target_state: targetState, reason }),
    }),
  );
}

export async function listManuscripts(projectId: string): Promise<ManuscriptDocument[]> {
  return expectJson(await fetch(`${API_BASE}/api/v1/projects/${projectId}/manuscripts`, { cache: "no-store" }));
}

export async function createManuscript(
  projectId: string,
  payload: { title: string; content?: string; order_index?: number; status?: string },
): Promise<ManuscriptDocument> {
  return expectJson(
    await fetch(`${API_BASE}/api/v1/projects/${projectId}/manuscripts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  );
}

export async function getManuscript(projectId: string, documentId: string): Promise<ManuscriptDocument> {
  return expectJson(
    await fetch(`${API_BASE}/api/v1/projects/${projectId}/manuscripts/${documentId}`, { cache: "no-store" }),
  );
}

export async function saveManuscript(
  projectId: string,
  documentId: string,
  payload: { title: string; content: string; order_index: number; status: string; reason?: string },
): Promise<ManuscriptDocument> {
  return expectJson(
    await fetch(`${API_BASE}/api/v1/projects/${projectId}/manuscripts/${documentId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  );
}

export async function listManuscriptRevisions(projectId: string, documentId: string): Promise<ManuscriptRevision[]> {
  return expectJson(
    await fetch(`${API_BASE}/api/v1/projects/${projectId}/manuscripts/${documentId}/revisions`, { cache: "no-store" }),
  );
}

export async function restoreManuscriptRevision(
  projectId: string,
  documentId: string,
  revisionId: string,
): Promise<ManuscriptDocument> {
  return expectJson(
    await fetch(`${API_BASE}/api/v1/projects/${projectId}/manuscripts/${documentId}/revisions/${revisionId}/restore`, {
      method: "POST",
    }),
  );
}

export async function listTimeline(projectId: string): Promise<TimelineEvent[]> {
  return expectJson(await fetch(`${API_BASE}/api/v1/projects/${projectId}/timeline`, { cache: "no-store" }));
}

export async function createTimeline(
  projectId: string,
  payload: {
    title: string;
    start_label?: string;
    end_label?: string | null;
    sort_key?: number;
    description?: string;
    participant_ids?: string[];
    canon_state?: string;
    source_type?: string;
  },
): Promise<TimelineEvent> {
  return expectJson(
    await fetch(`${API_BASE}/api/v1/projects/${projectId}/timeline`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  );
}


export type EntityAlias = {
  id: string;
  project_id: string;
  entity_id: string;
  alias: string;
  normalized_alias: string;
  alias_type: string;
  language_id: string | null;
  created_at: string;
};

export type EntityMention = {
  id: string;
  project_id: string;
  document_id: string;
  entity_id: string | null;
  mention_text: string;
  normalized_text: string;
  start_offset: number;
  end_offset: number;
  resolver_state: "resolved" | "ambiguous" | "unresolved" | "ignored";
  confidence: number;
  candidate_ids: string[];
  revision_no: number;
  resolution_note: string | null;
  created_at: string;
};

export type EntityRelation = {
  id: string;
  project_id: string;
  source_entity_id: string;
  target_entity_id: string;
  relation_type: string;
  label: string;
  canon_state: string;
  source_type: string;
  attributes: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type ReferenceResolution = {
  text: string;
  normalized_text: string;
  resolver_state: "resolved" | "ambiguous" | "unresolved";
  confidence: number;
  candidate_ids: string[];
  candidates: BibleEntity[];
};

export async function listEntityAliases(projectId: string): Promise<EntityAlias[]> {
  return expectJson(await fetch(`${API_BASE}/api/v1/projects/${projectId}/aliases`, { cache: "no-store" }));
}

export async function addEntityAlias(
  projectId: string,
  entityId: string,
  payload: { alias: string; alias_type?: string; language_id?: string | null },
): Promise<EntityAlias> {
  return expectJson(
    await fetch(`${API_BASE}/api/v1/projects/${projectId}/bible/${entityId}/aliases`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  );
}

export async function resolveEntityReference(projectId: string, value: string): Promise<ReferenceResolution> {
  const params = new URLSearchParams({ text: value });
  return expectJson(
    await fetch(`${API_BASE}/api/v1/projects/${projectId}/entity-intelligence/resolve?${params.toString()}`, {
      cache: "no-store",
    }),
  );
}

export async function refreshEntityMentions(
  projectId: string,
  documentId: string,
  includeCandidates = true,
): Promise<EntityMention[]> {
  return expectJson(
    await fetch(`${API_BASE}/api/v1/projects/${projectId}/manuscripts/${documentId}/mentions/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ include_candidates: includeCandidates }),
    }),
  );
}

export async function listEntityMentions(projectId: string, documentId: string): Promise<EntityMention[]> {
  return expectJson(
    await fetch(`${API_BASE}/api/v1/projects/${projectId}/manuscripts/${documentId}/mentions`, { cache: "no-store" }),
  );
}

export async function resolveEntityMention(
  projectId: string,
  mentionId: string,
  entityId: string,
  note = "author resolved",
): Promise<EntityMention> {
  return expectJson(
    await fetch(`${API_BASE}/api/v1/projects/${projectId}/mentions/${mentionId}/resolve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ entity_id: entityId, note }),
    }),
  );
}

export async function ignoreEntityMention(
  projectId: string,
  mentionId: string,
  note = "author ignored",
): Promise<EntityMention> {
  return expectJson(
    await fetch(`${API_BASE}/api/v1/projects/${projectId}/mentions/${mentionId}/ignore`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ note }),
    }),
  );
}

export async function createEntityFromMention(
  projectId: string,
  mentionId: string,
  entityType: string,
  summary = "",
): Promise<BibleEntity> {
  return expectJson(
    await fetch(`${API_BASE}/api/v1/projects/${projectId}/mentions/${mentionId}/create-entity`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ entity_type: entityType, summary }),
    }),
  );
}

export async function listEntityRelations(projectId: string): Promise<EntityRelation[]> {
  return expectJson(await fetch(`${API_BASE}/api/v1/projects/${projectId}/relations`, { cache: "no-store" }));
}

export async function createEntityRelation(
  projectId: string,
  payload: {
    source_entity_id: string;
    target_entity_id: string;
    relation_type: string;
    label?: string;
    canon_state?: string;
    source_type?: string;
    attributes?: Record<string, unknown>;
  },
): Promise<EntityRelation> {
  return expectJson(
    await fetch(`${API_BASE}/api/v1/projects/${projectId}/relations`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  );
}
