import assert from 'node:assert/strict';
import {ArtifactCache,runPipeline,sha256} from '../../src/foundation/pipeline.mjs';
const fixture={race_id:'TEST|20261007|X|1',authority:'TEST',runners:[{horse_no:2},{horse_no:1}]};
const cache=new ArtifactCache();
const a=runPipeline({raceScope:fixture.race_id,input:fixture,cache});
const b=runPipeline({raceScope:fixture.race_id,input:fixture,cache});
assert.equal(a.final_hash,b.final_hash);
assert.equal(a.ledger.filter(x=>x.decision==='RUN').length,4);
assert.equal(b.ledger.filter(x=>x.decision==='SKIP_CACHE_HIT').length,4);
assert.deepEqual(b.artifact.horse_nos,[1,2]);
const changed={...fixture,runners:[...fixture.runners,{horse_no:3}]};
const c=runPipeline({raceScope:fixture.race_id,input:changed,cache});
assert.notEqual(c.final_hash,a.final_hash);
assert.equal(c.ledger.filter(x=>x.decision==='RUN').length,4);
assert.equal(sha256({b:2,a:1}),sha256({a:1,b:2}));
console.log(JSON.stringify({assertions:7,status:'PASS',first:a.ledger,second:b.ledger,changed:c.ledger,hash:a.final_hash},null,2));

