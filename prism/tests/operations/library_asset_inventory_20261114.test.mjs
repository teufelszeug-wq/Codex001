import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
const root = new URL('../../data/recovery/', import.meta.url);
const read = name => JSON.parse(readFileSync(new URL(name,root),'utf8'));
test('20261114 assets are disjoint from prior inventories',()=>{
 const old=[...read('library_asset_inventory_20261112.json').assets,...read('library_asset_inventory_20261113.json').assets];
 const latest=read('library_asset_inventory_20261114.json');
 const prior=new Set(old.map(x=>x.library_file_id));
 assert.equal(latest.assets.length,2);
 assert.equal(latest.assets.filter(x=>prior.has(x.library_file_id)).length,0);
 assert.equal(new Set(latest.assets.map(x=>x.library_file_id)).size,2);
});
test('unretrieved ZIP is only a lead, not an imported asset',()=>{
 const latest=read('library_asset_inventory_20261114.json');
 assert.equal(latest.unverified_source_leads.length,1);
 assert.match(latest.unverified_source_leads[0].status,/NOT_RETRIEVED/);
 assert.equal(latest.summary.originals_migrated,0);
});
test('no post-hoc asset promoted to pre-off forecast',()=>{
 const latest=read('library_asset_inventory_20261114.json');
 assert.equal(latest.policy.promote_to_live_forecasts,false);
 assert.equal(latest.summary.live_preoff_forecasts_certified,0);
 for(const a of latest.assets){
   assert.equal(a.saved_at,null);
   assert.ok(!/LIVE_PREOFF/.test(a.evidence_class));
   assert.match(a.status,/NOT_IMPORTED/);
 }
});
