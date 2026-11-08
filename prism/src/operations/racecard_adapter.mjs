const required = (v, label) => { if (typeof v !== 'string' || !v.trim()) throw new Error(label + ' required'); return v.trim(); };
const date = (v,label) => { if (typeof v !== 'string' || !/(Z|[+-]\d{2}:\d{2})$/.test(v) || !Number.isFinite(Date.parse(v))) throw new Error(label + ' must be offset-aware'); return v; };
/**
 * Normalizes an independently collected official racecard. This adapter does NOT
 * scrape or claim to verify an official site. Callers must provide real evidence.
 */
export function normalizeOfficialRacecard(raw) {
  if (!raw || typeof raw !== 'object') throw new Error('racecard required');
  const authority = required(raw.authority,'authority');
  if (!['JRA','NAR'].includes(authority)) throw new Error('unsupported authority');
  const race_id = required(raw.race_id,'race_id');
  const race_name = required(raw.race_name,'race_name');
  const off_at = date(raw.off_at,'off_at');
  const captured_at = date(raw.captured_at,'captured_at');
  if (Date.parse(captured_at) > Date.parse(off_at)) throw new Error('racecard captured after scheduled off');
  const official_url = required(raw.official_url,'official_url');
  if (!/^https:\/\//i.test(official_url)) throw new Error('official_url must be HTTPS');
  if (!Array.isArray(raw.runners) || !raw.runners.length) throw new Error('runner list required');
  const seen = new Set();
  const runners = raw.runners.map(r => {
    if (!Number.isInteger(r.horse_no) || r.horse_no < 1) throw new Error('invalid horse_no');
    if (seen.has(r.horse_no)) throw new Error('duplicate horse_no');
    seen.add(r.horse_no);
    const horse_name = required(r.horse_name,'horse_name');
    const status = r.status ?? 'DECLARED';
    if (!['DECLARED','SCRATCHED','EXCLUDED'].includes(status)) throw new Error('unknown runner status');
    return { horse_no:r.horse_no, horse_name, status, frame_no:r.frame_no ?? null, jockey_name:r.jockey_name ?? null };
  }).sort((a,b)=>a.horse_no-b.horse_no);
  const active_runners = runners.filter(r=>r.status==='DECLARED');
  if (!active_runners.length) throw new Error('no active runners');
  return { schema:'prism.official_racecard/v1', authority, race_id, race_name, off_at, captured_at, official_url, runners, active_runners, source_verified:false };
}
export function preOffEligibility(card, saved_at) {
  date(saved_at,'saved_at');
  return { race_id:card.race_id, eligible:Date.parse(saved_at)<Date.parse(card.off_at), active_horse_nos:card.active_runners.map(r=>r.horse_no), source_verified:card.source_verified===true };
}
