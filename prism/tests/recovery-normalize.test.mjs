import test from 'node:test';
import assert from 'node:assert/strict';
import {normalizeRecovery} from '../recovery/normalize-recovery.mjs';
const base={race_id:'20261108-NAR-KOCHI-07',forecaster_id:'rio',version:'v1',source:'Library',evidence_class:'POST_RACE_RETROSPECTIVE_RECONSTRUCTION',saved_at:null,tickets:[{stake_yen:100}]};
test('deduplicates identical source/version while preserving original',()=>{const x=normalizeRecovery([{records:[base,base]}]);assert.equal(x.records.length,1);assert.equal(x.records[0].original,base)});
test('post-race cannot become live',()=>{const x=normalizeRecovery([{records:[base]}]);assert.equal(x.records[0].live_eligible,false);assert.equal(x.records[0].temporal_class,'post_race_reconstruction')});
test('declared pre-off cannot become certified live',()=>{const x=normalizeRecovery([{records:[{...base,evidence_class:'PRE_OFF_DECLARED_WORKING_NOT_ATTESTED',saved_at:'2026-11-07T12:00:00+09:00'}]}]);assert.equal(x.records[0].live_eligible,false);assert.equal(x.records[0].temporal_class,'pre_off_unverified')});
test('rejects non-100-yen tickets',()=>{const x=normalizeRecovery([{records:[{...base,tickets:[{stake_yen:150}]}]}]);assert.equal(x.conflicts[0].reason,'invalid_stake')});
test('rejects missing identity',()=>{const x=normalizeRecovery([{records:[{...base,race_id:null}]}]);assert.equal(x.records.length,0);assert.equal(x.conflicts.length,1)});
