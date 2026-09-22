import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import vm from 'node:vm';
import {initialize} from './project.mjs';
import {fingerprint,read,hash} from './engine.mjs';
import {saveWorldPlan,worldPlans} from './world-plan.mjs';
import {planningServer} from './planning-server.mjs';
function fixture(t){const w=fs.mkdtempSync(path.join(os.tmpdir(),'world-plan-')),root=initialize(w,'world-a','World');t.after(()=>fs.rmSync(w,{recursive:true,force:true}));return {w,root,input:{series_id:'world-a',base:fingerprint(root),source_ref:'test fixture only',notes:{countries:'test proposal'}}};}
test('world proposals preserve canon and keep old snapshots',t=>{const f=fixture(t),before=fingerprint(f.root),a=saveWorldPlan(f.root,f.input),b=saveWorldPlan(f.root,{...f.input,notes:{languages:'second test'}});assert.notEqual(a.id,b.id);assert.equal(worldPlans(f.root).records.length,2);assert.equal(fingerprint(f.root),before);assert.equal(read(path.join(f.root,'system/control.json')).manuscript_generation_enabled,false);assert.deepEqual(a.payload.notes,{countries:'test proposal'});});
test('reject foreign, stale, empty, unsupported and unreferenced proposals',t=>{const f=fixture(t);for(const change of [{series_id:'world-b'},{base:'old'},{notes:{}},{notes:{unknown:'x'}},{source_ref:''},{notes:{countries:5}}])assert.throws(()=>saveWorldPlan(f.root,{...f.input,...change}));assert.ok(!fs.existsSync(path.join(f.root,'system/world-plans')));});
test('history hides tampered and foreign records, labels old base',t=>{const f=fixture(t),a=saveWorldPlan(f.root,f.input);const file=path.join(f.root,'system/world-plans',a.id+'.json');a.payload.notes.countries='tampered';fs.writeFileSync(file,JSON.stringify(a));assert.equal(worldPlans(f.root).issues.length,1);a.digest=hash(JSON.stringify(a.payload));a.payload.series_id='world-b';a.digest=hash(JSON.stringify(a.payload));fs.writeFileSync(file,JSON.stringify(a));assert.equal(worldPlans(f.root).records.length,0);a.payload.series_id='world-a';a.payload.base='previous';a.digest=hash(JSON.stringify(a.payload));fs.writeFileSync(file,JSON.stringify(a));assert.equal(worldPlans(f.root).records[0].stale,true);});
test('world HTTP validates before receipts, persists once and requires token',async t=>{
  const f=fixture(t),server=planningServer(f.root);await new Promise(r=>server.listen(0,'127.0.0.1',r));t.after(async()=>{server.closeAllConnections();await new Promise(r=>server.close(r));});const url='http://127.0.0.1:'+server.address().port,context=await(await fetch(url+'/api/init')).json();
  const post=world=>fetch(url+'/api/save-world-plan',{method:'POST',headers:{'Content-Type':'application/json','X-Planning-Token':context.token},body:JSON.stringify({operation_id:op,base:context.base,world})});const op=crypto.randomUUID();
  assert.equal((await post({...f.input,source_ref:''})).status,400);assert.ok(!fs.existsSync(path.join(f.root,'system/operations')));
  const first=await(await post(f.input)).json(),second=await(await post(f.input)).json();assert.equal(first.id,second.id);assert.equal(worldPlans(f.root).records.length,1);assert.equal((await fetch(url+'/api/world-plans')).status,403);
  const history=await(await fetch(url+'/api/world-plans',{headers:{'X-Planning-Token':context.token}})).json();assert.equal(history.records[0].id,first.id);assert.equal(fingerprint(f.root),f.input.base);
  assert.match(await(await fetch(url)).text(),/href="\/world"/);const html=await(await fetch(url+'/world')).text();assert.match(html,/世界設定案/);new vm.Script(html.match(/<script>([\s\S]*?)<\/script>/)[1]);
});
