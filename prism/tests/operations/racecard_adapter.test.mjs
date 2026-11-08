import test from 'node:test';
import assert from 'node:assert/strict';
import { normalizeOfficialRacecard, preOffEligibility } from '../../src/operations/racecard_adapter.mjs';
const raw={authority:'JRA',race_id:'SYNTHETIC-JRA-1',race_name:'架空競走',off_at:'2026-11-09T15:00:00+09:00',captured_at:'2026-11-09T13:00:00+09:00',official_url:'https://www.jra.go.jp/',runners:[{horse_no:2,horse_name:'架空馬B',status:'SCRATCHED'},{horse_no:1,horse_name:'架空馬A'}]};
test('sorts official-style racecard and excludes scratched from active field',()=>{const c=normalizeOfficialRacecard(raw);assert.deepEqual(c.runners.map(r=>r.horse_no),[1,2]);assert.deepEqual(c.active_runners.map(r=>r.horse_no),[1]);assert.equal(c.source_verified,false);});
test('rejects duplicate runners and missing evidence',()=>{assert.throws(()=>normalizeOfficialRacecard({...raw,runners:[raw.runners[0],raw.runners[0]]}),/duplicate/);assert.throws(()=>normalizeOfficialRacecard({...raw,official_url:'http://bad.test'}),/HTTPS/);});
test('rejects stale post-off capture',()=>assert.throws(()=>normalizeOfficialRacecard({...raw,captured_at:'2026-11-09T15:00:01+09:00'}),/after/));
test('evaluates deadline without pretending independent verification',()=>{const c=normalizeOfficialRacecard(raw);assert.equal(preOffEligibility(c,'2026-11-09T14:59:59+09:00').eligible,true);assert.equal(preOffEligibility(c,'2026-11-09T15:00:00+09:00').eligible,false);});
