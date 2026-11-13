import { createHash } from 'node:crypto';

const date = (v, field) => {
  if (typeof v !== 'string' || !/(Z|[+-]\d{2}:\d{2})$/.test(v) || !Number.isFinite(Date.parse(v))) throw new Error(field + ': offset-aware timestamp required');
  return Date.parse(v);
};
const fail = message => { throw new Error(message); };
const hash = value => createHash('sha256').update(JSON.stringify(value)).digest('hex');
const requireText = (value, field) => typeof value === 'string' && value.trim() ? value : fail(field + ': required');
const requireTicket = ticket => {
  if (!ticket || !['WIN', 'PLACE', 'QUINELLA', 'EXACTA', 'TRIO', 'TRIFECTA', 'WIDE'].includes(ticket.type)) fail('unsupported ticket');
  if (!Array.isArray(ticket.horse_nos) || !ticket.horse_nos.length || !ticket.horse_nos.every(n => Number.isInteger(n) && n > 0) || new Set(ticket.horse_nos).size !== ticket.horse_nos.length) fail('invalid ticket horse numbers');
  const legs = { WIN: 1, PLACE: 1, QUINELLA: 2, EXACTA: 2, WIDE: 2, TRIO: 3, TRIFECTA: 3 };
  if (ticket.horse_nos.length !== legs[ticket.type]) fail('ticket leg count');
  if (!Number.isInteger(ticket.stake_yen) || ticket.stake_yen < 100 || ticket.stake_yen % 100) fail('stake must be positive 100-yen units');
};
export function createPreRaceLedger({ race_id, race_name, off_at, runners, records, saved_at, source_refs = [], metadata }) {
  requireText(race_id, 'race_id'); requireText(race_name, 'race_name');
  const off = date(off_at, 'off_at'), saved = date(saved_at, 'saved_at');
  if (saved >= off) fail('forecast must be saved before off');
  if (!Array.isArray(runners) || !runners.length || !runners.every(r => Number.isInteger(r.horse_no) && r.horse_no > 0 && typeof r.horse_name === 'string' && r.horse_name.trim())) fail('full official runner list required');
  const horseNos = runners.map(r => r.horse_no);
  if (new Set(horseNos).size !== horseNos.length) fail('duplicate runners');
  if (!Array.isArray(records) || !records.length) fail('forecast records required');
  const authors = new Set();
  for (const rec of records) {
    requireText(rec.forecaster_id, 'forecaster_id');
    if (authors.has(rec.forecaster_id)) fail('duplicate forecaster'); authors.add(rec.forecaster_id);
    if (!Array.isArray(rec.diagnoses) || rec.diagnoses.length !== runners.length || new Set(rec.diagnoses.map(d => d.horse_no)).size !== runners.length || !rec.diagnoses.every(d => horseNos.includes(d.horse_no) && typeof d.reason === 'string' && d.reason.trim())) fail('all-runner diagnosis required for every forecaster');
    if (!Array.isArray(rec.tickets)) fail('tickets array required; [] means pass');
    for (const t of rec.tickets) { requireTicket(t); if (!t.horse_nos.every(n => horseNos.includes(n))) fail('ticket refers to non-runner'); }
    if (rec.independent_execution !== true) fail('independent execution must be explicitly evidenced');
  }
  if (!Array.isArray(source_refs) || !source_refs.every(x => typeof x === 'string' && x.trim())) fail('source refs invalid');
  const payload = { schema: 'prism.forecast_history/v1', race_id, race_name, off_at, runners, records, saved_at, source_refs, version: 1, status: 'PRE_UNATTESTED' };
  if (metadata !== undefined) payload.metadata = metadata;
  return { ...payload, content_sha256: hash(payload) };
}
export function appendRevision(previous, { records, saved_at, metadata }) {
  if (!previous || previous.schema !== 'prism.forecast_history/v1') fail('previous record required');
  if (date(saved_at, 'saved_at') <= date(previous.saved_at, 'previous saved_at')) fail('revision must have later saved_at');
  const next = createPreRaceLedger({ race_id: previous.race_id, race_name: previous.race_name, off_at: previous.off_at, runners: previous.runners, records, saved_at, source_refs: previous.source_refs, metadata });
  const { content_sha256: _, ...payload } = next;
  payload.version = previous.version + 1;
  payload.previous_sha256 = previous.content_sha256;
  return { ...payload, content_sha256: hash(payload) };
}
export function assessCoverage(ledger, requiredForecasters = []) {
  const observed = new Set(ledger?.records?.map(r => r.forecaster_id) || []);
  const missing = requiredForecasters.filter(id => !observed.has(id));
  return { race_id: ledger?.race_id ?? null, saved_before_off: !!ledger && date(ledger.saved_at, 'saved_at') < date(ledger.off_at, 'off_at'), complete_forecasters: missing.length === 0, missing_forecasters: missing, forecast_count: observed.size };
}
