import { createHash } from 'node:crypto';

const date = (v, field) => {
  if (typeof v !== 'string' || !/(Z|[+-]\d{2}:\d{2})$/.test(v) || !Number.isFinite(Date.parse(v))) throw new Error(field + ': offset-aware timestamp required');
  return Date.parse(v);
};
const fail = message => { throw new Error(message); };
const hash = value => createHash('sha256').update(JSON.stringify(value)).digest('hex');
const requireText = (value, field) => typeof value === 'string' && value.trim() ? value : fail(field + ': required');
const LEGS = { WIN:1, PLACE:1, QUINELLA:2, EXACTA:2, TRIO:3, TRIFECTA:3, WIDE:2, FRAME:2 };
const UNORDERED = new Set(['QUINELLA', 'WIDE', 'TRIO', 'FRAME']);

/** Frame tickets always use frame_nos; frame numbers are never horse numbers. */
export function normalizeTicket(ticket, { requireStake = true } = {}) {
  if (!ticket || typeof ticket !== 'object') fail('invalid ticket');
  const type = ticket.type === 'FRAME_QUINELLA' ? 'FRAME' : ticket.type;
  if (!Object.hasOwn(LEGS,type)) fail('unsupported ticket');
  const field = type === 'FRAME' ? 'frame_nos' : 'horse_nos';
  const other = type === 'FRAME' ? 'horse_nos' : 'frame_nos';
  const numbers = ticket[field];
  if (ticket[other] !== undefined || !Array.isArray(numbers) || numbers.length !== LEGS[type] || !numbers.every(n => Number.isInteger(n) && n > 0 && (type !== 'FRAME' || n <= 8))) fail('invalid ticket leg count or numbers');
  if (type !== 'FRAME' && new Set(numbers).size !== numbers.length) fail('invalid ticket duplicate horse numbers');
  if (requireStake && (!Number.isInteger(ticket.stake_yen) || ticket.stake_yen < 100 || ticket.stake_yen % 100)) fail('stake must be positive 100-yen units');
  const normalized = { ...ticket, type, [field]:UNORDERED.has(type) ? [...numbers].sort((a,b)=>a-b) : [...numbers] };
  return normalized;
}
export function ticketKey(ticket) {
  const normalized = normalizeTicket(ticket, { requireStake:false });
  return normalized.type + ':' + JSON.stringify(normalized[normalized.type === 'FRAME' ? 'frame_nos' : 'horse_nos']);
}
export function forecastDigest(record) {
  const { content_sha256: _, ...payload } = record;
  return hash(payload);
}
export function verifyForecastLedger(record) {
  if (!record || record.schema !== 'prism.forecast_history/v1' || record.content_sha256 !== forecastDigest(record)) fail('forecast hash mismatch');
  if (!validRecordShape(record)) fail('forecast record contract invalid');
  return record;
}
function validRecordShape(record) {
  if (!Array.isArray(record.runners) || !record.runners.length || !Array.isArray(record.records) || !record.records.length) return false;
  try {
    // Re-use creation validation; do not replace the original snapshot's version/hash.
    createPreRaceLedger(record);
    return Number.isInteger(record.version) && record.version > 0;
  } catch { return false; }
}
export function createPreRaceLedger({ race_id, race_name, off_at, runners, records, saved_at, source_refs = [] }) {
  requireText(race_id, 'race_id'); requireText(race_name, 'race_name');
  const off = date(off_at, 'off_at'), saved = date(saved_at, 'saved_at');
  if (saved >= off) fail('forecast must be saved before off');
  if (!Array.isArray(runners) || !runners.length || !runners.every(r => Number.isInteger(r.horse_no) && r.horse_no > 0 && typeof r.horse_name === 'string' && r.horse_name.trim())) fail('full official runner list required');
  const horseNos = runners.map(r => r.horse_no);
  if (new Set(horseNos).size !== horseNos.length) fail('duplicate runners');
  if (!Array.isArray(records) || !records.length) fail('forecast records required');
  const authors = new Set();
  const normalizedRecords = records.map(rec => {
    requireText(rec.forecaster_id, 'forecaster_id');
    if (authors.has(rec.forecaster_id)) fail('duplicate forecaster'); authors.add(rec.forecaster_id);
    if (!Array.isArray(rec.diagnoses) || rec.diagnoses.length !== runners.length || new Set(rec.diagnoses.map(d => d.horse_no)).size !== runners.length || !rec.diagnoses.every(d => horseNos.includes(d.horse_no) && typeof d.reason === 'string' && d.reason.trim())) fail('all-runner diagnosis required for every forecaster');
    if (!Array.isArray(rec.tickets)) fail('tickets array required; [] means pass');
    const seenTickets = new Set();
    const tickets = rec.tickets.map(t => {
      const normalized = normalizeTicket(t);
      if (normalized.type === 'FRAME') {
        const counts = new Map();
        for (const r of runners) if (Number.isInteger(r.frame_no)) counts.set(r.frame_no, (counts.get(r.frame_no) || 0) + 1);
        if (!normalized.frame_nos.every(n => counts.has(n)) || normalized.frame_nos[0] === normalized.frame_nos[1] && counts.get(normalized.frame_nos[0]) < 2) fail('frame ticket refers to non-runner or unavailable frame');
      } else if (!normalized.horse_nos.every(n => horseNos.includes(n))) fail('ticket refers to non-runner');
      const key = ticketKey(normalized);
      if (seenTickets.has(key)) fail('duplicate ticket; combine 100-yen units into one stake');
      seenTickets.add(key);
      return normalized;
    });
    if (rec.independent_execution !== true && rec.mode !== 'single_model_simulation') fail('independent execution must be explicitly evidenced or marked single_model_simulation');
    return { ...rec, tickets };
  });
  if (!Array.isArray(source_refs) || !source_refs.every(x => typeof x === 'string' && x.trim())) fail('source refs invalid');
  // This compatibility ledger does not certify the caller's execution claim.
  const payload = { schema:'prism.forecast_history/v1', race_id, race_name, off_at, runners, records:normalizedRecords, saved_at, source_refs, version:1, status:'PRE_UNATTESTED', independent_execution_verified:false };
  return { ...payload, content_sha256:hash(payload) };
}
export function appendRevision(previous, { records, saved_at }) {
  verifyForecastLedger(previous);
  if (date(saved_at, 'saved_at') <= date(previous.saved_at, 'previous saved_at')) fail('revision must have later saved_at');
  const next = createPreRaceLedger({ race_id:previous.race_id, race_name:previous.race_name, off_at:previous.off_at, runners:previous.runners, records, saved_at, source_refs:previous.source_refs });
  const { content_sha256: _, ...payload } = next;
  payload.version = previous.version + 1;
  payload.previous_sha256 = previous.content_sha256;
  return { ...payload, content_sha256:hash(payload) };
}
export function assessCoverage(ledger, requiredForecasters = []) {
  const observed = new Set(ledger?.records?.map(r => r.forecaster_id) || []);
  const missing = requiredForecasters.filter(id => !observed.has(id));
  return { race_id:ledger?.race_id ?? null, saved_before_off:!!ledger && date(ledger.saved_at, 'saved_at') < date(ledger.off_at, 'off_at'), complete_forecasters:missing.length === 0, missing_forecasters:missing, forecast_count:observed.size, independent_execution_verified:false };
}
