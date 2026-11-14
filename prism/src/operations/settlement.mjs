const fail = message => { throw new Error(message); };
const validDate = value => typeof value === 'string' && /(Z|[+-]\d{2}:\d{2})$/.test(value) && Number.isFinite(Date.parse(value));
const unordered = new Set(['QUINELLA', 'WIDE', 'TRIO']);
const ticketKey = (type, horses) => type + ':' + JSON.stringify(unordered.has(type) ? [...horses].sort((a,b) => a-b) : horses);
export function settleForecast({ forecast, result, settled_at }) {
  if (!forecast || forecast.schema !== 'prism.forecast_history/v1') fail('forecast history required');
  if (!validDate(settled_at) || Date.parse(settled_at) < Date.parse(forecast.off_at)) fail('settlement must occur after off');
  if (!result || result.race_id !== forecast.race_id || !result.official_source || !validDate(result.published_at) || Date.parse(result.published_at) > Date.parse(settled_at)) fail('official result provenance required');
  if (!Array.isArray(result.payouts)) fail('official payouts array required');
  const byTicket = new Map();
  for (const p of result.payouts) {
    if (!Number.isInteger(p.payout_per_100_yen) || p.payout_per_100_yen < 0 || !Array.isArray(p.horse_nos)) fail('invalid official payout');
    const key = ticketKey(p.type, p.horse_nos);
    if (byTicket.has(key)) fail('duplicate payout'); byTicket.set(key,p.payout_per_100_yen);
  }
  const refunds = result.refunds || [];
  if (!Array.isArray(refunds)) fail('invalid refunds');
  if ((result.refunded_horse_nos !== undefined && !Array.isArray(result.refunded_horse_nos)) ||
      (result.complete_payout_types !== undefined && !Array.isArray(result.complete_payout_types))) {
    fail('invalid official payout coverage');
  }
  const refundedHorses = new Set(result.refunded_horse_nos ?? []);
  const completeTypes = new Set(result.complete_payout_types ?? []);
  const summary = [];
  for (const record of forecast.records) {
    let stake_yen = 0, payout_yen = 0;
    const tickets = [];
    for (const ticket of record.tickets) {
      const stake = ticket.stake_yen;
      if (!Number.isInteger(stake) || stake < 100 || stake % 100) fail('invalid stake');
      const key = ticketKey(ticket.type, ticket.horse_nos);
      const refunded = ticket.horse_nos.some(number => refundedHorses.has(number)) ||
        refunds.some(refund => ticketKey(refund.type, refund.horse_nos) === key);
      if (!refunded && !byTicket.has(key) && result.complete_payouts !== true && !completeTypes.has(ticket.type)) {
        fail('incomplete official payout coverage');
      }
      const paid = refunded ? stake : (byTicket.get(key) || 0) * stake / 100;
      stake_yen += stake; payout_yen += paid;
      tickets.push({ ...ticket, refunded, payout_yen: paid });
    }
    summary.push({ forecaster_id: record.forecaster_id, stake_yen, payout_yen, profit_yen:payout_yen-stake_yen, roi_percent:stake_yen ? payout_yen / stake_yen * 100 : null, tickets });
  }
  return { schema:'prism.official_settlement/v1', race_id:forecast.race_id, forecast_sha256:forecast.content_sha256, official_source:result.official_source, result_published_at:result.published_at, settled_at, summary };
}
