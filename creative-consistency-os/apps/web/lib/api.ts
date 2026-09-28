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


export type LintCatalogRule = {
  rule_id: string;
  category: string;
  default_severity: "hint" | "info" | "warning" | "error";
  description: string;
  pack?: string;
};

export type LintCatalog = {
  builtins: LintCatalogRule[];
  severities: string[];
  finding_states: string[];
  config_version: number;
};

export type LintConfig = {
  project_id: string;
  rules: {
    builtins: Record<string, { enabled?: boolean; severity?: string }>;
    custom_terms: Array<{
      id: string;
      term: string;
      severity: string;
      enabled: boolean;
      case_sensitive: boolean;
      message: string;
    }>;
  };
  config_version: number;
  updated_at: string | null;
};

export type LintFinding = {
  id: string;
  run_id: string;
  project_id: string;
  document_id: string | null;
  entity_id: string | null;
  rule_id: string;
  category: string;
  severity: "hint" | "info" | "warning" | "error";
  message: string;
  start_offset: number | null;
  end_offset: number | null;
  evidence: Record<string, unknown>;
  fingerprint: string;
  finding_state: "OPEN" | "ACKNOWLEDGED" | "IGNORED" | "RESOLVED";
  created_at: string;
};

export type LintRun = {
  id: string;
  project_id: string;
  document_id: string | null;
  scope: "document" | "project";
  document_revision: number | null;
  ruleset_version: number;
  status: string;
  summary: {
    total: number;
    by_severity: Record<string, number>;
    by_category: Record<string, number>;
  };
  created_at: string;
  findings?: LintFinding[];
};

export async function getLintCatalog(): Promise<LintCatalog> {
  return expectJson(await fetch(`${API_BASE}/api/v1/catalog/lint`, { cache: "no-store" }));
}

export async function getLintConfig(projectId: string): Promise<LintConfig> {
  return expectJson(await fetch(`${API_BASE}/api/v1/projects/${projectId}/lint-config`, { cache: "no-store" }));
}

export async function saveLintConfig(projectId: string, rules: LintConfig["rules"]): Promise<LintConfig> {
  return expectJson(
    await fetch(`${API_BASE}/api/v1/projects/${projectId}/lint-config`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rules }),
    }),
  );
}

export async function runProjectLint(projectId: string): Promise<LintRun> {
  return expectJson(
    await fetch(`${API_BASE}/api/v1/projects/${projectId}/lint/run-project`, { method: "POST" }),
  );
}

export async function runDocumentLint(projectId: string, documentId: string): Promise<LintRun> {
  return expectJson(
    await fetch(`${API_BASE}/api/v1/projects/${projectId}/manuscripts/${documentId}/lint`, { method: "POST" }),
  );
}

export async function listLintRuns(projectId: string): Promise<LintRun[]> {
  return expectJson(await fetch(`${API_BASE}/api/v1/projects/${projectId}/lint/runs`, { cache: "no-store" }));
}

export async function getLintRun(projectId: string, runId: string): Promise<LintRun> {
  return expectJson(await fetch(`${API_BASE}/api/v1/projects/${projectId}/lint/runs/${runId}`, { cache: "no-store" }));
}

export async function setLintFindingState(
  projectId: string,
  findingId: string,
  state: LintFinding["finding_state"],
): Promise<LintFinding> {
  return expectJson(
    await fetch(`${API_BASE}/api/v1/projects/${projectId}/lint/findings/${findingId}/state`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ state }),
    }),
  );
}

export type ImpactEdge = {
  id: string;
  project_id: string;
  source_type: string;
  source_id: string;
  target_type: string;
  target_id: string;
  edge_type: string;
  detail: Record<string, unknown>;
  refreshed_at: string;
};

export type ImpactPreview = {
  project_id: string;
  source: { type: string; id: string; name: string; canon_state: string };
  max_depth: number;
  affected_document_ids: string[];
  affected_timeline_event_ids: string[];
  related_entity_ids: string[];
  nodes: Array<{ type: string; id: string; depth: number; via: string; detail: Record<string, unknown> }>;
  edges: Array<ImpactEdge & { depth: number }>;
};

export type ImpactInvalidation = {
  id: string;
  project_id: string;
  source_type: string;
  source_id: string;
  change_kind: string;
  status: "PENDING" | "REVALIDATED" | "DISMISSED";
  detail: Record<string, unknown>;
  result: Record<string, unknown>;
  created_at: string;
  resolved_at: string | null;
};

export async function refreshImpactGraph(projectId: string): Promise<{ project_id: string; edge_count: number; edges: ImpactEdge[] }> {
  return expectJson(
    await fetch(`${API_BASE}/api/v1/projects/${projectId}/impact/graph/refresh`, { method: "POST" }),
  );
}

export async function listImpactEdges(projectId: string): Promise<ImpactEdge[]> {
  return expectJson(await fetch(`${API_BASE}/api/v1/projects/${projectId}/impact/edges`, { cache: "no-store" }));
}

export async function previewEntityImpact(projectId: string, entityId: string, maxDepth = 4): Promise<ImpactPreview> {
  const params = new URLSearchParams({ max_depth: String(maxDepth), refresh: "true" });
  return expectJson(
    await fetch(`${API_BASE}/api/v1/projects/${projectId}/impact/entities/${entityId}?${params.toString()}`, { cache: "no-store" }),
  );
}

export async function listImpactInvalidations(projectId: string, statusFilter?: string): Promise<ImpactInvalidation[]> {
  const params = new URLSearchParams();
  if (statusFilter) params.set("status_filter", statusFilter);
  const suffix = params.size ? `?${params.toString()}` : "";
  return expectJson(
    await fetch(`${API_BASE}/api/v1/projects/${projectId}/impact/invalidations${suffix}`, { cache: "no-store" }),
  );
}

export async function revalidateImpact(projectId: string, invalidationId: string, maxDepth = 4): Promise<ImpactInvalidation> {
  return expectJson(
    await fetch(`${API_BASE}/api/v1/projects/${projectId}/impact/invalidations/${invalidationId}/revalidate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ max_depth: maxDepth }),
    }),
  );
}

export async function dismissImpact(projectId: string, invalidationId: string, reason: string): Promise<ImpactInvalidation> {
  return expectJson(
    await fetch(`${API_BASE}/api/v1/projects/${projectId}/impact/invalidations/${invalidationId}/dismiss`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason }),
    }),
  );
}


export type IsekaiCategory = {
  key: string;
  label: string;
  description: string;
};

export type IsekaiCatalogTerm = {
  term: string;
  category: string;
  concept_key: string;
  generic_replacement: string;
};

export type IsekaiCatalog = {
  categories: IsekaiCategory[];
  earth_terms: IsekaiCatalogTerm[];
  strictness: string[];
  attribute_contracts: Record<string, unknown>;
  pack_version: number;
};

export type IsekaiCustomTerm = {
  id: string;
  term: string;
  category: string;
  concept_key: string;
  generic_replacement: string;
  severity: string | null;
  enabled: boolean;
};

export type IsekaiReplacement = {
  earth_term: string;
  world_term: string;
  source_place_entity_id: string | null;
  notes: string;
};

export type IsekaiTravelRoute = {
  id: string;
  from_entity_id: string;
  to_entity_id: string;
  mode: string;
  min_hours: number;
  max_hours: number;
  bidirectional: boolean;
  notes: string;
};

export type IsekaiPackConfig = {
  project_id: string;
  enabled: boolean;
  strictness: string;
  enabled_categories: Record<string, boolean>;
  allow_terms: string[];
  custom_terms: IsekaiCustomTerm[];
  replacements: IsekaiReplacement[];
  require_world_mapping: boolean;
  travel_routes: IsekaiTravelRoute[];
  magic_policy: {
    enabled: boolean;
    require_cost: boolean;
    allowed_cost_types: string[];
    costless_tiers: string[];
  };
  economy_policy: {
    enabled: boolean;
    currencies: string[];
    price_bands: Array<{
      id: string;
      category: string;
      currency: string;
      min_price: number;
      max_price: number;
      notes: string;
    }>;
  };
  healing_policy: {
    enabled: boolean;
    resurrection_allowed: boolean;
    limb_regrowth_allowed: boolean;
  };
  status: "draft" | "configured";
  pack_version: number;
  updated_at: string | null;
};

export type IsekaiPackWrite = Omit<IsekaiPackConfig, "project_id" | "pack_version" | "updated_at">;

export type IsekaiReplacementPreview = {
  term: string;
  matched: boolean;
  allowed: boolean;
  category: string | null;
  concept_key: string | null;
  generic_replacement: string | null;
  world_replacement: string | null;
  source_place_entity_id: string | null;
  notes?: string;
  needs_author_decision: boolean;
};

export async function getIsekaiCatalog(): Promise<IsekaiCatalog> {
  return expectJson(await fetch(`${API_BASE}/api/v1/catalog/isekai`, { cache: "no-store" }));
}

export async function getIsekaiPack(projectId: string): Promise<IsekaiPackConfig> {
  return expectJson(await fetch(`${API_BASE}/api/v1/projects/${projectId}/isekai`, { cache: "no-store" }));
}

export async function saveIsekaiPack(projectId: string, payload: IsekaiPackWrite): Promise<IsekaiPackConfig> {
  return expectJson(
    await fetch(`${API_BASE}/api/v1/projects/${projectId}/isekai`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  );
}

export async function previewIsekaiReplacement(
  projectId: string,
  term: string,
): Promise<IsekaiReplacementPreview> {
  return expectJson(
    await fetch(`${API_BASE}/api/v1/projects/${projectId}/isekai/replacement-preview`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ term }),
    }),
  );
}
