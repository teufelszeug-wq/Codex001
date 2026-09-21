import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import {initialize,council,finishCouncil} from './project.mjs';
import {briefTemplate,saveBrief} from './brief.mjs';
import {recordedOperation} from './operation-receipt.mjs';
import {planningHistory} from './planning-history.mjs';
import {fingerprint,accept} from './engine.mjs';
function setup(t){const dir=fs.mkdtempSync(path.join(os.tmpdir(),'history-'));t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));return initialize(dir,'history-test','試験');}
test('history shows partial collected answers without claiming completed council or live workers',t=>{
  const root=setup(t),meeting=council(root,'partial reviews'),before=fingerprint(root),req=meeting.requests[0],waiting=meeting.requests[1];
  accept(root,req,{request_id:req.request_id,series_id:req.series_id,base:req.base,role:req.role,output:'collected opinion'});
  const runs=path.join(root,'system/worker-runs');fs.mkdirSync(runs,{recursive:true});fs.writeFileSync(path.join(runs,waiting.request_id+'.json'),JSON.stringify({series_id:meeting.series_id,meeting_id:meeting.id,request_id:waiting.request_id,role:waiting.role,status:'started'}));
  const h=planningHistory(root),m=h.councils[0];assert.equal(m.collected_count,1);assert.equal(m.status,'awaiting_reviews');assert.equal(m.resolution,null);assert.equal(m.reviews[0].source,'inbox');assert.equal(m.reviews[0].output,'collected opinion');assert.equal(m.reviews[1].attempt_status,'started');assert.equal(m.reviews[1].output,null);assert.equal(fingerprint(root),before);
  const file=path.join(root,'system/inbox',req.request_id+'.json'),r=JSON.parse(fs.readFileSync(file,'utf8'));r.series_id='foreign';fs.writeFileSync(file,JSON.stringify(r));const checked=planningHistory(root);assert.equal(checked.councils.length,0);assert.ok(checked.issues.some(x=>x.kind==='councils'));assert.ok(!JSON.stringify(checked).includes('collected opinion'));
});
test('council history distinguishes requests from completed role reviews and stays read-only',t=>{
  const root=setup(t),before=fingerprint(root),meeting=council(root,'会議履歴の試験');
  let h=planningHistory(root);assert.equal(h.councils[0].execution_mode,'requests_only');assert.ok(h.councils[0].reviews.every(r=>r.output===null));assert.equal(h.councils[0].resolution,null);
  const replies=meeting.requests.map(r=>({request_id:r.request_id,series_id:r.series_id,base:r.base,role:r.role,output:'試験の回答 '+r.role}));
  finishCouncil(root,meeting.id,replies,{execution_mode:'conversation_single_assistant',summary:'試験の提案',objections:['未検証あり'],pending:['実接続']});
  const file=path.join(root,'system/councils',meeting.id+'.json'),saved=fs.readFileSync(file,'utf8');
  h=planningHistory(root);assert.equal(h.councils[0].status,'reviewed_proposal');assert.equal(h.councils[0].reviews.length,5);assert.ok(h.councils[0].reviews.every(r=>r.output));assert.equal(h.councils[0].resolution.pending[0],'実接続');assert.equal(fingerprint(root),before);assert.equal(fs.readFileSync(file,'utf8'),saved);
});
test('foreign, duplicate and altered council records are hidden as issues',t=>{
  const root=setup(t),a=council(root,'foreign private agenda'),b=council(root,'duplicate'),c=council(root,'altered');
  a.series_id='another';b.requests[1]=b.requests[0];
  for(const m of [a,b])fs.writeFileSync(path.join(root,'system/councils',m.id+'.json'),JSON.stringify(m));
  const replies=c.requests.map(r=>({request_id:r.request_id,series_id:r.series_id,base:r.base,role:r.role,output:'test'}));
  const completed=finishCouncil(root,c.id,replies,{execution_mode:'external_workers',summary:'test',objections:[],pending:[]});completed.replies[0].output='altered';fs.writeFileSync(path.join(root,'system/councils',c.id+'.json'),JSON.stringify(completed));
  const h=planningHistory(root);assert.equal(h.councils.length,0);assert.equal(h.issues.length,3);assert.ok(!JSON.stringify(h).includes('foreign private agenda'));
});
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
