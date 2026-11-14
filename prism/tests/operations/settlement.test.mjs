import test from 'node:test';
import assert from 'node:assert/strict';
import { settleForecast } from '../../src/operations/settlement.mjs';
const f={schema:'prism.forecast_history/v1',race_id:'SYNTHETIC-1',off_at:'2026-11-09T15:00:00+09:00',content_sha256:'fixture',records:[{forecaster_id:'editor',tickets:[{type:'WIN',horse_nos:[1],stake_yen:100}]}]};
const result={race_id:f.race_id,official_source:'SYNTHETIC OFFICIAL FIXTURE',published_at:'2026-11-09T16:00:00+09:00',complete_payouts:true,payouts:[{type:'WIN',horse_nos:[1],payout_per_100_yen:350}]};
test('settles 100-yen ticket and ROI',()=>{const s=settleForecast({forecast:f,result,settled_at:'2026-11-09T16:10:00+09:00'});assert.equal(s.summary[0].profit_yen,250);assert.equal(s.summary[0].roi_percent,350);});
test('rejects wrong race or absent provenance',()=>{assert.throws(()=>settleForecast({forecast:f,result:{...result,race_id:'other'},settled_at:'2026-11-09T16:10:00+09:00'}),/provenance/);});
test('does not settle before published result',()=>{assert.throws(()=>settleForecast({forecast:f,result,settled_at:'2026-11-09T15:10:00+09:00'}),/provenance/);});
test('refund returns stake',()=>{const s=settleForecast({forecast:f,result:{...result,refunds:[{type:'WIN',horse_nos:[1]}]},settled_at:'2026-11-09T16:10:00+09:00'});assert.equal(s.summary[0].profit_yen,0);});
test('unknown payouts rejected unless complete',()=>{assert.throws(()=>settleForecast({forecast:f,result:{...result,complete_payouts:false,payouts:[]},settled_at:'2026-11-09T16:10:00+09:00'}),/incomplete/);});

test('official payout coverage is per type and unordered combinations normalize', () => {
  const forecast = { ...f, records: [{ forecaster_id: 'editor', tickets: [
    { type: 'QUINELLA', horse_nos: [3, 1], stake_yen: 100 },
    { type: 'QUINELLA', horse_nos: [1, 2], stake_yen: 100 },
  ] }] };
  const official = { ...result, complete_payouts: false, complete_payout_types: ['QUINELLA'], payouts: [
    { type: 'QUINELLA', horse_nos: [1, 3], payout_per_100_yen: 420 },
  ] };
  const s = settleForecast({ forecast, result: official, settled_at: '2026-11-09T16:10:00+09:00' });
  assert.deepEqual(s.summary[0].tickets.map(row => row.payout_yen), [420, 0]);
  assert.throws(() => settleForecast({ forecast, result: { ...official, complete_payout_types: [] },
    settled_at: '2026-11-09T16:10:00+09:00' }), /incomplete/);
});

test('official scratch returns every affected ticket including an unavailable pool', () => {
  const forecast = { ...f, records: [{ forecaster_id: 'editor', tickets: [
    { type: 'TRIO', horse_nos: [2, 1, 3], stake_yen: 100 },
  ] }] };
  const official = { ...result, complete_payouts: false, payouts: [], refunded_horse_nos: [1] };
  const s = settleForecast({ forecast, result: official, settled_at: '2026-11-09T16:10:00+09:00' });
  assert.equal(s.summary[0].tickets[0].refunded, true);
  assert.equal(s.summary[0].payout_yen, 100);
});
