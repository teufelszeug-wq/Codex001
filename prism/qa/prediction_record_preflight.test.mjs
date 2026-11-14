import test from 'node:test';
import assert from 'node:assert/strict';
import { validatePredictionRecord } from './prediction_record_preflight.mjs';
const base = {race_id:'JRA-20261114-TEST-11',horse_name:'テスト馬',predictor_id:'editorial',source:'fixture',saved_at:'2026-11-13T18:00:00+09:00',scheduled_start_at:'2026-11-14T15:00:00+09:00',version:'eve-v1',record_type:'pre_race',result_known:false};
test('valid pre-race fixture',()=>assert.equal(validatePredictionRecord(base).valid,true));
test('reject post-start save',()=>assert.ok(validatePredictionRecord({...base,saved_at:base.scheduled_start_at}).errors.includes('not_pre_race')));
test('reject malformed timestamp',()=>assert.ok(validatePredictionRecord({...base,saved_at:'yesterday'}).errors.includes('invalid_datetime:saved_at')));
test('reject missing provenance',()=>assert.ok(validatePredictionRecord({...base,source:''}).errors.includes('missing:source')));
test('reject result leakage',()=>assert.ok(validatePredictionRecord({...base,result_known:true}).errors.includes('result_leak')));

test('allow retrospective save after start without mislabeling as pre-race',()=>{const result=validatePredictionRecord({...base,record_type:'retrospective',saved_at:'2026-11-14T18:00:00+09:00',result_known:true});assert.equal(result.valid,true);});
test('reject pre-race record saved after start even when result unknown',()=>assert.ok(validatePredictionRecord({...base,saved_at:'2026-11-14T18:00:00+09:00'}).errors.includes('not_pre_race')));
