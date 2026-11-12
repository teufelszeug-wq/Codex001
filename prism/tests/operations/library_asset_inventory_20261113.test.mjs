import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
const root=new URL('../../data/recovery/',import.meta.url);
const read=async name=>JSON.parse(await readFile(new URL(name,root),'utf8'));
test('new library inventory is disjoint from prior inventory and does not promote reviews',async()=>{
 const old=await read('library_asset_inventory_20261112.json');
 const current=await read('library_asset_inventory_20261113.json');
 const ids=new Set(old.assets.map(a=>a.library_file_id));
 assert.equal(current.assets.length,3);
 assert.equal(new Set(current.assets.map(a=>a.library_file_id)).size,3);
 for(const a of current.assets){
   assert.ok(!ids.has(a.library_file_id),'duplicate across inventory dates');
   assert.equal(a.saved_at,null);
   assert.equal(a.race_id,null);
   assert.match(a.status,/NOT_IMPORTED$/);
   assert.notEqual(a.evidence_class,'LIVE_PRE_OFF');
 }
 assert.equal(current.summary.originals_migrated,0);
 assert.equal(current.summary.live_preoff_forecasts_certified,0);
});
