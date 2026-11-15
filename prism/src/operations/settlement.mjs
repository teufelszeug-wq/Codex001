import { createHash } from 'node:crypto';
import { normalizeTicket, ticketKey, verifyForecastLedger } from './forecast_history.mjs';

const fail = message => { throw new Error(message); };
const validDate = value => typeof value === 'string' && /(Z|[+-]\d{2}:\d{2})$/.test(value) && Number.isFinite(Date.parse(value));
const SHA256 = /^[a-f0-9]{64}$/;
const stable = value => Array.isArray(value) ? value.map(stable) : value && typeof value === 'object' ? Object.fromEntries(Object.keys(value).sort().map(k=>[k,stable(value[k])])) : value;
const digest = value => createHash('sha256').update(JSON.stringify(stable(value))).digest('hex');
const RESULT_FIELDS = ['race_id','published_at','payouts','refunds','complete_payouts','status','refunded_bet_types','revision','correction_of','publication_status','first_observed_at','complete_bet_types'];
export function resultPayloadDigest(result) {
  return digest(Object.fromEntries(RESULT_FIELDS.filter(k=>Object.hasOwn(result,k)).map(k=>[k,result[k]])));
}
function officialURL(value) {
  try {
    const u = new URL(value);
    return u.protocol === 'https:' && !u.username && !u.password && !u.port && ['jra.go.jp','www.jra.go.jp','keiba.go.jp','www.keiba.go.jp','sp.keiba.go.jp'].includes(u.hostname);
  } catch { return false; }
}
function checkProvenance(result, forecast, settled_at) {
  if (!result || result.race_id !== forecast.race_id || !result.official_source) fail('official result provenance required');
  const observedOnly = result.published_at === null && result.publication_status === 'UNKNOWN_TIMESTAMP';
  const resultTime = observedOnly ? result.first_observed_at : result.published_at;
  if (!validDate(resultTime) || Date.parse(resultTime) < Date.parse(forecast.off_at) || Date.parse(resultTime) > Date.parse(settled_at)) fail('official result provenance required');
  if (result.mode === 'SYNTHETIC') return;
  if (result.mode !== undefined && result.mode !== 'OFFICIAL') fail('unsupported result mode');
  const s = result.source_snapshot;
  if (!officialURL(result.official_source) || !s || s.official_url !== result.official_source || !validDate(s.captured_at) || Date.parse(s.captured_at) < Date.parse(resultTime) || Date.parse(s.captured_at) > Date.parse(settled_at) || !SHA256.test(s.source_sha256) || s.normalized_sha256 !== resultPayloadDigest(result)) fail('official result snapshot provenance required');
  if (observedOnly && result.first_observed_at !== s.captured_at) fail('official result observation must match snapshot capture');
  if (result.revision !== undefined && (!Number.isInteger(result.revision) || result.revision < 1)) fail('invalid official correction revision');
  if (result.revision > 1 && !SHA256.test(result.correction_of || '')) fail('official correction must reference previous result hash');
}
function checkRunnerNumbers(ticket, forecast) {
  const normalized = normalizeTicket(ticket, {requireStake:false});
  const field = normalized.type === 'FRAME' ? 'frame_nos' : 'horse_nos';
  const allowed = new Set(forecast.runners.map(r=>r[normalized.type === 'FRAME' ? 'frame_no' : 'horse_no']));
  if (!normalized[field].every(n=>allowed.has(n))) fail('official ticket refers to non-runner or unknown frame');
  return normalized;
}
/** Computes a versioned settlement; source provenance is not external attestation. */
export function settleForecast({ forecast, result, settled_at }) {
  verifyForecastLedger(forecast);
  if (!validDate(settled_at) || Date.parse(settled_at) < Date.parse(forecast.off_at)) fail('settlement must occur after off');
  checkProvenance(result, forecast, settled_at);
  if (!Array.isArray(result.payouts)) fail('official payouts array required');
  if ((result.mode !== 'SYNTHETIC' || result.status !== undefined) && !['FINAL','CANCELLED'].includes(result.status)) fail('official result not final');
  const byTicket = new Map();
  for (const p of result.payouts) {
    const ticket = checkRunnerNumbers(p, forecast);
    if (!Number.isInteger(p.payout_per_100_yen) || p.payout_per_100_yen <= 0) fail('invalid official payout');
    const key = ticketKey(ticket);
    if (byTicket.has(key)) fail('duplicate payout'); byTicket.set(key, p.payout_per_100_yen);
  }
  const refunds = result.refunds || [];
  if (!Array.isArray(refunds)) fail('invalid refunds');
  const refundedKeys = new Set();
  for (const refund of refunds) {
    const key = ticketKey(checkRunnerNumbers(refund, forecast));
    if (refundedKeys.has(key)) fail('duplicate refund');
    if (byTicket.has(key)) fail('conflicting payout and refund');
    refundedKeys.add(key);
  }
  const refundedTypes = new Set();
  if (result.refunded_bet_types !== undefined && !Array.isArray(result.refunded_bet_types)) fail('invalid refunded bet types');
  for (const type of result.refunded_bet_types || []) {
    const normalized = type === 'FRAME_QUINELLA' ? 'FRAME' : type;
    if (!['WIN','PLACE','QUINELLA','EXACTA','WIDE','TRIO','TRIFECTA','FRAME'].includes(normalized) || refundedTypes.has(normalized)) fail('invalid refunded bet types');
    refundedTypes.add(normalized);
  }
  for (const key of byTicket.keys()) if (result.status === 'CANCELLED' || refundedTypes.has(key.split(':')[0])) fail('conflicting cancelled race/type and payout');
  const completeTypes = new Set();
  if (result.complete_bet_types !== undefined && !Array.isArray(result.complete_bet_types)) fail('invalid complete bet types');
  for (const type of result.complete_bet_types || []) {
    const normalized = type === 'FRAME_QUINELLA' ? 'FRAME' : type;
    if (!['WIN','PLACE','QUINELLA','EXACTA','WIDE','TRIO','TRIFECTA','FRAME'].includes(normalized) || completeTypes.has(normalized)) fail('invalid complete bet types');
    completeTypes.add(normalized);
  }
  const summary = [];
  for (const record of forecast.records) {
    let stake_yen = 0, payout_yen = 0, refund_yen = 0, dividend_yen = 0;
    const tickets = [];
    for (const t of record.tickets) {
      const ticket = normalizeTicket(t), stake = ticket.stake_yen, key = ticketKey(ticket);
      const refunded = result.status === 'CANCELLED' || refundedTypes.has(ticket.type) || refundedKeys.has(key);
      if (!refunded && !byTicket.has(key) && !(result.complete_payouts === true && (result.mode === 'SYNTHETIC' || completeTypes.has(ticket.type)))) fail('incomplete official payout coverage');
      const paid = refunded ? stake : (byTicket.get(key) || 0) * stake / 100;
      stake_yen += stake; payout_yen += paid;
      if (refunded) refund_yen += paid; else dividend_yen += paid;
      tickets.push({ ...ticket, refunded, outcome:refunded ? 'REFUNDED' : paid > 0 ? 'WON' : 'LOST', payout_yen:paid });
    }
    const effective_stake_yen = stake_yen - refund_yen;
    summary.push({ forecaster_id:record.forecaster_id, stake_yen, effective_stake_yen, dividend_yen, refund_yen, payout_yen, profit_yen:payout_yen-stake_yen, roi_percent:stake_yen ? payout_yen/stake_yen*100 : null, return_rate_percent:effective_stake_yen ? dividend_yen/effective_stake_yen*100 : null, tickets });
  }
  const result_sha256 = resultPayloadDigest(result);
  return { schema:'prism.official_settlement/v1', settlement_id:digest({ forecast_sha256:forecast.content_sha256, result_sha256 }), race_id:forecast.race_id, forecast_sha256:forecast.content_sha256, result_sha256, official_source:result.official_source, source_snapshot:result.source_snapshot || null, result_published_at:result.published_at, result_first_observed_at:result.first_observed_at || null, publication_status:result.publication_status || 'DECLARED_TIMESTAMP', settled_at, mode:result.mode === 'SYNTHETIC' ? 'SYNTHETIC' : 'OFFICIAL_SOURCE_RECORD', source_authenticity_verified:false, independent_execution_verified:false, summary };
}
