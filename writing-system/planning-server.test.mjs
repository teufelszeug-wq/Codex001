import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import {initialize} from './project.mjs';
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
test('HTTP saves a proposal once and hands it to council without modifying canon',async t=>{const f=await setup(t),before=fingerprint(f.root),payload={operation_id:crypto.randomUUID(),base:f.context.base,brief:{...f.context.templates[0],source_ref:'test input',answers:{premise:'試験用の物語'}}};const a=await f.post('/api/save',payload),r=await a.json();assert.equal(a.status,200);assert.equal((await (await f.post('/api/save',payload)).json()).id,r.id);assert.equal(fs.readdirSync(path.join(f.root,'system/briefs')).length,1);const m=await f.post('/api/council',{operation_id:crypto.randomUUID(),base:f.context.base,brief_id:r.id});assert.equal(m.status,200);assert.equal((await m.json()).roles.length,5);assert.equal(fingerprint(f.root),before);assert.equal((await fetch(f.url+'/')).status,200);});
test('HTTP rejects foreign origin, missing token, wrong series and stale base',async t=>{const f=await setup(t),payload={operation_id:crypto.randomUUID(),base:f.context.base,brief:{...f.context.templates[0],source_ref:'test',answers:{premise:'x'}}};assert.equal((await f.post('/api/save',payload,{'Origin':'https://untrusted.example'})).status,403);assert.equal((await f.post('/api/save',payload,{'X-Planning-Token':''})).status,403);assert.equal((await f.post('/api/save',{...payload,base:'stale'})).status,400);assert.equal((await f.post('/api/save',{...payload,brief:{...payload.brief,series_id:'another'}})).status,400);assert.ok(!fs.existsSync(path.join(f.root,'system/briefs')));});
