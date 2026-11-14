import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
const manifest = JSON.parse(await readFile(new URL('../../data/recovery/notion_preoff_candidate_manifest_20261109.json', import.meta.url),'utf8'));
test('recovered records have unique identity, source and timestamps',()=>{
  const keys=new Set();
  for(const r of manifest.records){
    assert.match(r.source,/^https:\/\/app\.notion\.com\/p\//);
    assert.ok(Number.isFinite(Date.parse(r.saved_at)));
    assert.ok(r.source_id && r.race_id && r.forecaster_id && r.version);
    const key=[r.race_id,r.forecaster_id,r.version].join('|');
    assert.ok(!keys.has(key));keys.add(key);
  }
  assert.equal(keys.size,manifest.summary.unique_races);
});
test('uncertified candidates cannot be promoted into live performance or ticket returns',()=>{
  for(const r of manifest.records){
    assert.equal(r.not_live_certified,true);
    assert.match(r.evidence_class,/NOT_ATTESTED/);
    assert.deepEqual(r.tickets,[]);
  }
  assert.equal(manifest.summary.fully_attested_live_snapshots,0);
  assert.equal(manifest.summary.settled_tickets,0);
});
