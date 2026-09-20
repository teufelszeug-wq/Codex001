import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import {initialize} from './project.mjs';
import {briefTemplate,saveBrief} from './brief.mjs';
import {recordedOperation} from './operation-receipt.mjs';
import {planningHistory} from './planning-history.mjs';
import {fingerprint} from './engine.mjs';
function setup(t){const dir=fs.mkdtempSync(path.join(os.tmpdir(),'history-'));t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));return initialize(dir,'history-test','試験');}
test('history reads proposals and uncertain receipts without replay or canon changes',t=>{
  const root=setup(t),before=fingerprint(root),id=crypto.randomUUID();
  const brief=recordedOperation(root,id,{},()=>saveBrief(root,{...briefTemplate(root),source_ref:'test',answers:{premise:'draft'}}));
  const failed=crypto.randomUUID();assert.throws(()=>recordedOperation(root,failed,{},()=>{throw Error();}));
  const pendingPath=path.join(root,'system/operations',failed+'.json'),pending=fs.readFileSync(pendingPath,'utf8');
  const h=planningHistory(root);assert.equal(h.briefs[0].id,brief.id);assert.equal(h.briefs[0].stale,false);assert.equal(h.operations.find(x=>x.id===failed).status,'started');assert.equal(h.operations.find(x=>x.id===id).result_id,brief.id);assert.deepEqual(h.issues,[]);assert.equal(fingerprint(root),before);assert.equal(fs.readFileSync(pendingPath,'utf8'),pending);
});
test('history hides altered and foreign records and identifies stale proposals',t=>{
  const root=setup(t),make=()=>saveBrief(root,{...briefTemplate(root),source_ref:'test',answers:{premise:'secret'}}),a=make(),b=make(),c=make();
  a.payload.answers.premise='tampered';fs.writeFileSync(path.join(root,'system/briefs',a.id+'.json'),JSON.stringify(a));
  b.payload.series_id='foreign';fs.writeFileSync(path.join(root,'system/briefs',b.id+'.json'),JSON.stringify(b));
  const op=crypto.randomUUID();fs.mkdirSync(path.join(root,'system/operations'),{recursive:true});fs.writeFileSync(path.join(root,'system/operations',op+'.json'),JSON.stringify({id:op,series_id:'foreign',status:'completed',result:{id:'secret-result'}}));
  const h=planningHistory(root);assert.deepEqual(h.briefs.map(x=>x.id),[c.id]);assert.equal(h.issues.length,3);assert.equal(h.operations.length,0);assert.ok(!JSON.stringify(h).includes('secret-result'));
  c.payload.base='old';
  // A valid saved proposal can refer to an older basis.
  c.digest=crypto.createHash('sha256').update(JSON.stringify(c.payload)).digest('hex');fs.writeFileSync(path.join(root,'system/briefs',c.id+'.json'),JSON.stringify(c));assert.equal(planningHistory(root).briefs[0].stale,true);
});
