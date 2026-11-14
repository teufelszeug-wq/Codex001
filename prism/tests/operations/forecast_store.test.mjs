import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { persistInitialForecast, persistRevision, loadForecast } from '../../src/operations/forecast_store.mjs';
const base={race_id:'SYNTHETIC-STORE',race_name:'架空競走',off_at:'2026-11-09T15:00:00+09:00',saved_at:'2026-11-09T14:00:00+09:00',runners:[{horse_no:1,horse_name:'架空馬'}],records:[{forecaster_id:'editor',independent_execution:true,diagnoses:[{horse_no:1,reason:'架空'}],tickets:[]}],source_refs:['synthetic']};
test('exclusive persistence, version chaining and no overwrites',async()=>{const dir=await mkdtemp(join(tmpdir(),'prism-'));try{const a=await persistInitialForecast(dir,base);assert.equal((await loadForecast(dir,base.race_id)).content_sha256,a.record.content_sha256);await assert.rejects(persistInitialForecast(dir,base),{code:'EEXIST'});const b=await persistRevision(dir,base.race_id,1,{saved_at:'2026-11-09T14:30:00+09:00',records:base.records});assert.equal(b.record.previous_sha256,a.record.content_sha256);assert.equal((await loadForecast(dir,base.race_id,1)).version,1);await assert.rejects(persistRevision(dir,base.race_id,1,{saved_at:'2026-11-09T14:45:00+09:00',records:base.records}),{code:'EEXIST'});}finally{await rm(dir,{recursive:true,force:true});}});
test('rejects path traversal',async()=>{const dir=await mkdtemp(join(tmpdir(),'prism-'));try{await assert.rejects(loadForecast(dir,'../../bad'),/unsafe/);}finally{await rm(dir,{recursive:true,force:true});}});
