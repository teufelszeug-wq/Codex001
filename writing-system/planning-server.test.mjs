import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import {initialize,council} from './project.mjs';
import {fingerprint} from './engine.mjs';
import {planningServer} from './planning-server.mjs';
test('new server instance returns the saved receipt without duplicate proposal',async t=>{
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'novel-restart-')),root=initialize(dir,'restart-test','restart');
  let server;
  t.after(async()=>{if(server?.listening){server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}fs.rmSync(dir,{recursive:true,force:true});});
  async function start(){server=planningServer(root);await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const url='http://127.0.0.1:'+server.address().port;return {url,init:await(await fetch(url+'/api/init')).json()};}
  let current=await start();const payload={operation_id:crypto.randomUUID(),base:current.init.base,brief:{...current.init.templates[0],source_ref:'restart test',answers:{premise:'test'}}};
  const post=()=>fetch(current.url+'/api/save',{method:'POST',headers:{'Content-Type':'application/json','X-Planning-Token':current.init.token},body:JSON.stringify(payload)});
  const first=await(await post()).json();assert.ok(first.id);
  server.closeAllConnections();await new Promise(resolve=>server.close(resolve));current=await start();
  const second=await(await post()).json();assert.equal(second.id,first.id);assert.equal(fs.readdirSync(path.join(root,'system/briefs')).length,1);
});
async function setup(t){const dir=fs.mkdtempSync(path.join(os.tmpdir(),'novel-planning-')),root=initialize(dir,'ui-test','画面試験'),server=planningServer(root);await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));t.after(async()=>{server.closeAllConnections();await new Promise(resolve=>server.close(resolve));fs.rmSync(dir,{recursive:true,force:true});});const url='http://127.0.0.1:'+server.address().port,context=await (await fetch(url+'/api/init')).json();return {root,url,context,post:async(route,data,headers={})=>fetch(url+route,{method:'POST',headers:{'Content-Type':'application/json','X-Planning-Token':context.token,...headers},body:JSON.stringify(data)})};}
test('history requires token and returns only read-only records',async t=>{const f=await setup(t);assert.equal((await fetch(f.url+'/api/history')).status,403);const response=await fetch(f.url+'/api/history',{headers:{'X-Planning-Token':f.context.token}});assert.equal(response.status,200);assert.deepEqual((await response.json()).briefs,[]);assert.ok(!fs.existsSync(path.join(f.root,'system/briefs')));});
test('HTTP council completion validates before writes, persists proposals and is idempotent',async t=>{
  const f=await setup(t),before=fingerprint(f.root),meeting=council(f.root,'test meeting');
  const payload={operation_id:crypto.randomUUID(),base:f.context.base,meeting_id:meeting.id,reviews:meeting.requests.map(r=>({role:r.role,output:'review '+r.role})),resolution:{execution_mode:'conversation_single_assistant',summary:'proposal',objections:[],pending:['unconnected AI']}};
  for(const invalid of [{...payload,reviews:payload.reviews.slice(1)},{...payload,resolution:{...payload.resolution,execution_mode:''}},{...payload,reviews:payload.reviews.map((r,i)=>i? r:{...r,output:' '})}]){
    const response=await f.post('/api/finish-council',invalid);assert.equal(response.status,400);assert.equal((await response.json()).uncertain,false);
  }
  assert.ok(!fs.existsSync(path.join(f.root,'system/operations')));assert.ok(!fs.existsSync(path.join(f.root,'system/inbox')));
  let response=await f.post('/api/finish-council',payload);assert.equal(response.status,200);assert.equal((await response.json()).status,'reviewed_proposal');
  response=await f.post('/api/finish-council',payload);assert.equal(response.status,200);
  assert.equal(fs.readdirSync(path.join(f.root,'system/inbox')).length,5);assert.equal(fs.readdirSync(path.join(f.root,'system/operations')).length,1);assert.equal(fingerprint(f.root),before);
  const history=await(await fetch(f.url+'/api/history',{headers:{'X-Planning-Token':f.context.token}})).json();assert.equal(history.councils[0].resolution.summary,'proposal');
  assert.equal((await f.post('/api/finish-council',{...payload,operation_id:crypto.randomUUID(),resolution:{...payload.resolution,summary:'overwrite'}})).status,400);
});
test('HTTP council completion rejects stale and foreign meeting records',async t=>{
  const f=await setup(t),meeting=council(f.root,'test');const payload={operation_id:crypto.randomUUID(),base:f.context.base,meeting_id:meeting.id,reviews:meeting.requests.map(r=>({role:r.role,output:'review'})),resolution:{execution_mode:'external_workers',summary:'proposal',objections:[],pending:[]}};
  const file=path.join(f.root,'system/councils',meeting.id+'.json');
  for(const changed of [{...meeting,base:'old'},{...meeting,series_id:'foreign'}]){fs.writeFileSync(file,JSON.stringify(changed));assert.equal((await f.post('/api/finish-council',payload)).status,400);}
  assert.ok(!fs.existsSync(path.join(f.root,'system/inbox')));assert.ok(!fs.existsSync(path.join(f.root,'system/operations')));
});
test('HTTP saves a proposal once and hands it to council without modifying canon',async t=>{const f=await setup(t),before=fingerprint(f.root),payload={operation_id:crypto.randomUUID(),base:f.context.base,brief:{...f.context.templates[0],source_ref:'test input',answers:{premise:'試験用の物語'}}};const a=await f.post('/api/save',payload),r=await a.json();assert.equal(a.status,200);assert.equal((await (await f.post('/api/save',payload)).json()).id,r.id);assert.equal(fs.readdirSync(path.join(f.root,'system/briefs')).length,1);const m=await f.post('/api/council',{operation_id:crypto.randomUUID(),base:f.context.base,brief_id:r.id});assert.equal(m.status,200);assert.equal((await m.json()).roles.length,5);assert.equal(fingerprint(f.root),before);assert.equal((await fetch(f.url+'/')).status,200);});
test('HTTP rejects foreign origin, missing token, wrong series and stale base',async t=>{const f=await setup(t),payload={operation_id:crypto.randomUUID(),base:f.context.base,brief:{...f.context.templates[0],source_ref:'test',answers:{premise:'x'}}};assert.equal((await f.post('/api/save',payload,{'Origin':'https://untrusted.example'})).status,403);assert.equal((await f.post('/api/save',payload,{'X-Planning-Token':''})).status,403);assert.equal((await f.post('/api/save',{...payload,base:'stale'})).status,400);assert.equal((await f.post('/api/save',{...payload,brief:{...payload.brief,series_id:'another'}})).status,400);assert.ok(!fs.existsSync(path.join(f.root,'system/briefs')));});
