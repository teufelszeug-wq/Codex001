import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, rm, readdir } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createEditionWriter, readEdition } from './atomic_edition_store.mjs';
const record = {race_id:'20261115_JRA_TOKYO_11', version:'previous_day_v1', record_type:'pre_race', horse_name:'テスト馬', predictor_id:'editor', saved_at:'2026-11-14T18:00:00+09:00'};
async function fixture(fn) {const dir=await mkdtemp(join(tmpdir(),'prism-edition-'));try{await fn(dir)}finally{await rm(dir,{recursive:true,force:true})}}
test('persist and read back with matching sha256',async()=>fixture(async dir=>{const receipt=await createEditionWriter(dir)([record]);const saved=await readEdition(receipt.path);assert.deepEqual(saved.document.records,[record]);assert.equal(saved.sha256,receipt.sha256)}));
test('immutable edition refuses overwrite',async()=>fixture(async dir=>{const writer=createEditionWriter(dir);await writer([record]);await assert.rejects(writer([{...record,horse_name:'改ざん'}]),{code:'EEXIST'});const files=await readdir(dir);assert.equal(files.length,1)}));
test('concurrent writes only one succeeds',async()=>fixture(async dir=>{const writer=createEditionWriter(dir);const results=await Promise.allSettled([writer([record]),writer([record])]);assert.equal(results.filter(x=>x.status==='fulfilled').length,1);assert.equal(results.filter(x=>x.status==='rejected').length,1)}));
test('invalid edition key rejected',async()=>fixture(async dir=>{await assert.rejects(createEditionWriter(dir)([{...record,race_id:'../bad'}]),/invalid_edition_key/)}));
test('empty edition rejected',async()=>fixture(async dir=>{await assert.rejects(createEditionWriter(dir)([]),/empty_edition/)}));
