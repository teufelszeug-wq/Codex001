import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { settleForecast, resultPayloadDigest } from '../../src/operations/settlement.mjs';
import { createPreRaceLedger } from '../../src/operations/forecast_history.mjs';
const when = '2026-11-09T16:10:00+09:00';
function fixture(tickets = [{type:'WIN',horse_nos:[1],stake_yen:100}]) {
  return createPreRaceLedger({race_id:'SYNTHETIC-1',race_name:'架空検証競走',off_at:'2026-11-09T15:00:00+09:00',saved_at:'2026-11-08T20:00:00+09:00',runners:[{horse_no:1,frame_no:1,horse_name:'架空馬A'},{horse_no:2,frame_no:1,horse_name:'架空馬B'},{horse_no:3,frame_no:2,horse_name:'架空馬C'}],records:[{forecaster_id:'editor',independent_execution:true,diagnoses:[1,2,3].map(horse_no=>({horse_no,reason:'架空根拠'})),tickets}]});
}
const f = fixture();
function result(overrides = {}) { return {mode:'SYNTHETIC',race_id:f.race_id,official_source:'SYNTHETIC OFFICIAL FIXTURE',published_at:'2026-11-09T16:00:00+09:00',complete_payouts:true,payouts:[{type:'WIN',horse_nos:[1],payout_per_100_yen:350}],...overrides}; }
function settle(forecast = f, overrides = {}) { return settleForecast({forecast,result:result(overrides),settled_at:when}); }
function sourced(overrides={}) {
  const r=result({mode:'OFFICIAL',status:'FINAL',official_source:'https://www.keiba.go.jp/KeibaWeb/TodayRaceInfo/RaceMark',...overrides});
  return {...r,source_snapshot:{official_url:r.official_source,captured_at:'2026-11-09T16:05:00+09:00',source_sha256:'a'.repeat(64),normalized_sha256:resultPayloadDigest(r)}};
}
test('settles 100-yen ticket and ROI without claiming execution/source authentication',()=>{const s=settle();assert.equal(s.summary[0].profit_yen,250);assert.equal(s.summary[0].roi_percent,350);assert.equal(s.mode,'SYNTHETIC');assert.equal(s.independent_execution_verified,false);assert.equal(s.source_authenticity_verified,false);});
test('rejects wrong race or absent provenance',()=>{assert.throws(()=>settle(f,{race_id:'other'}),/provenance/);assert.throws(()=>settle(f,{official_source:''}),/provenance/);});
test('does not settle before result publication or accept pre-off result timestamps',()=>{assert.throws(()=>settleForecast({forecast:f,result:result(),settled_at:'2026-11-09T15:10:00+09:00'}),/provenance/);assert.throws(()=>settle(f,{published_at:'2026-11-08T16:00:00+09:00'}),/provenance/);});
test('refund returns stake and excludes it from effective stake',()=>{const s=settle(f,{payouts:[],refunds:[{type:'WIN',horse_nos:[1]}]});assert.equal(s.summary[0].profit_yen,0);assert.equal(s.summary[0].refund_yen,100);assert.equal(s.summary[0].effective_stake_yen,0);assert.equal(s.summary[0].return_rate_percent,null);assert.equal(s.summary[0].tickets[0].outcome,'REFUNDED');});
test('unknown payouts rejected unless explicitly complete',()=>{assert.throws(()=>settle(f,{complete_payouts:false,payouts:[]}),/incomplete/);});
test('unordered quinella, wide and trio match the official canonical combination',()=>{
  for (const [type,numbers] of [['QUINELLA',[2,1]],['WIDE',[2,1]],['TRIO',[3,1,2]]]) {
    const x=fixture([{type,horse_nos:numbers,stake_yen:300}]);
    const s=settle(x,{payouts:[{type,horse_nos:[...numbers].sort(),payout_per_100_yen:500}]});
    assert.equal(s.summary[0].payout_yen,1500);
  }
});
test('exacta and trifecta preserve ordering',()=>{
  for (const [type,numbers] of [['EXACTA',[2,1]],['TRIFECTA',[3,1,2]]]) {
    const x=fixture([{type,horse_nos:numbers,stake_yen:100}]);
    assert.equal(settle(x,{payouts:[{type,horse_nos:[...numbers].sort(),payout_per_100_yen:500}]}).summary[0].payout_yen,0);
  }
});
test('frame quinella uses frame identity and permits two horses from the same frame',()=>{
  const x=fixture([{type:'FRAME',frame_nos:[1,1],stake_yen:200}]);
  assert.equal(settle(x,{payouts:[{type:'FRAME',frame_nos:[1,1],payout_per_100_yen:600}]}).summary[0].payout_yen,1200);
});
test('dead heat allows different winning combinations, but duplicate equivalent dividends fail',()=>{
  const x=fixture([{type:'QUINELLA',horse_nos:[1,2],stake_yen:100}]);
  assert.equal(settle(x,{payouts:[{type:'QUINELLA',horse_nos:[1,2],payout_per_100_yen:400},{type:'QUINELLA',horse_nos:[1,3],payout_per_100_yen:450}]}).summary[0].payout_yen,400);
  assert.throws(()=>settle(x,{payouts:[{type:'QUINELLA',horse_nos:[1,2],payout_per_100_yen:400},{type:'QUINELLA',horse_nos:[2,1],payout_per_100_yen:400}]}),/duplicate/);
});
test('conflicting payout/refund and duplicate refunds fail instead of choosing one',()=>{assert.throws(()=>settle(f,{refunds:[{type:'WIN',horse_nos:[1]}]}),/conflicting/);assert.throws(()=>settle(f,{payouts:[],refunds:[{type:'WIN',horse_nos:[1]},{type:'WIN',horse_nos:[1]}]}),/duplicate refund/);});
test('cancelled races and bet types refund all affected stakes',()=>{assert.equal(settle(f,{status:'CANCELLED',payouts:[],complete_payouts:false}).summary[0].refund_yen,100);assert.equal(settle(f,{refunded_bet_types:['WIN'],payouts:[],complete_payouts:false}).summary[0].refund_yen,100);assert.throws(()=>settle(f,{status:'CANCELLED'}),/conflicting/);});
test('rejects altered forecast hash and changed original selection',()=>{assert.throws(()=>settle({...f,content_sha256:'not-checked'}),/hash mismatch/);const changed=structuredClone(f);changed.records[0].tickets[0].stake_yen=200;assert.throws(()=>settle(changed),/hash mismatch/);});
test('real-source records require official HTTPS and snapshot payload integrity',()=>{
  const r=sourced();const s=settleForecast({forecast:f,result:r,settled_at:when});assert.equal(s.mode,'OFFICIAL_SOURCE_RECORD');
  assert.throws(()=>settleForecast({forecast:f,result:{...r,official_source:'arbitrary text'},settled_at:when}),/provenance/);
  assert.throws(()=>settleForecast({forecast:f,result:{...r,payouts:[]},settled_at:when}),/provenance/);
  assert.throws(()=>settleForecast({forecast:f,result:sourced({official_source:'https://www.jra.go.jp.evil.example/'}),settled_at:when}),/provenance/);
  assert.throws(()=>settleForecast({forecast:f,result:{...r,source_snapshot:{...r.source_snapshot,captured_at:'2026-11-09T17:00:00+09:00'}},settled_at:when}),/provenance/);
});
test('official corrections refer to earlier result and give a distinct settlement key',()=>{
  const r=sourced();const a=settleForecast({forecast:f,result:r,settled_at:when});
  const corrected=sourced({revision:2,correction_of:a.result_sha256,payouts:[{type:'WIN',horse_nos:[1],payout_per_100_yen:400}]});
  const b=settleForecast({forecast:f,result:corrected,settled_at:when});assert.notEqual(a.settlement_id,b.settlement_id);assert.equal(b.summary[0].profit_yen,300);
  assert.throws(()=>settleForecast({forecast:f,result:sourced({revision:2}),settled_at:when}),/correction/);
  assert.equal(a.settlement_id,settleForecast({forecast:f,result:r,settled_at:when}).settlement_id);
});
test('CLI accepts one JSON document and blocks incomplete official source',()=>{
  const cli=new URL('../../scripts/settle_official.mjs',import.meta.url);
  const run=spawnSync(process.execPath,[cli.pathname],{input:JSON.stringify({forecast:f,result:result(),settled_at:when}),encoding:'utf8'});assert.equal(run.status,0,run.stderr);assert.equal(JSON.parse(run.stdout).summary[0].profit_yen,250);
  const bad=spawnSync(process.execPath,[cli.pathname],{input:JSON.stringify({forecast:f,result:result({mode:'OFFICIAL'}),settled_at:when}),encoding:'utf8'});assert.equal(bad.status,1);assert.equal(JSON.parse(bad.stderr).status,'BLOCKED');
});
test('unknown publication timestamp remains unknown while snapshot observation permits settlement',()=>{
  const r=sourced({published_at:null,publication_status:'UNKNOWN_TIMESTAMP',first_observed_at:'2026-11-09T16:05:00+09:00'});
  const s=settleForecast({forecast:f,result:r,settled_at:when});
  assert.equal(s.result_published_at,null);assert.equal(s.publication_status,'UNKNOWN_TIMESTAMP');assert.equal(s.summary[0].profit_yen,250);
  const mismatched=sourced({published_at:null,publication_status:'UNKNOWN_TIMESTAMP',first_observed_at:'2026-11-09T16:01:00+09:00'});
  assert.throws(()=>settleForecast({forecast:f,result:mismatched,settled_at:when}),/observation/);
  const early=sourced({published_at:null,publication_status:'UNKNOWN_TIMESTAMP',first_observed_at:'2026-11-08T16:05:00+09:00'});
  assert.throws(()=>settleForecast({forecast:f,result:early,settled_at:when}),/provenance/);
});
test('complete boolean alone never converts missing real-source payout tables into losses',()=>{
  const incomplete=sourced({payouts:[]});
  assert.throws(()=>settleForecast({forecast:f,result:incomplete,settled_at:when}),/incomplete/);
  const wrongType=sourced({payouts:[],complete_bet_types:['PLACE']});
  assert.throws(()=>settleForecast({forecast:f,result:wrongType,settled_at:when}),/incomplete/);
  const covered=sourced({payouts:[{type:'WIN',horse_nos:[2],payout_per_100_yen:300}],complete_bet_types:['WIN']});
  assert.equal(settleForecast({forecast:f,result:covered,settled_at:when}).summary[0].tickets[0].outcome,'LOST');
});
test('unknown horse numbers and zero dividends do not become official outcomes',()=>{
  assert.throws(()=>settle(f,{payouts:[{type:'WIN',horse_nos:[99],payout_per_100_yen:300}]}),/non-runner/);
  assert.throws(()=>settle(f,{payouts:[{type:'WIN',horse_nos:[1],payout_per_100_yen:0}]}),/invalid official payout/);
});
