import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {atomic, read, inside, validate, request, accept, worker} from './engine.mjs';
const here = path.dirname(fileURLToPath(import.meta.url));
function fixture(t) {
  const base = fs.mkdtempSync(path.join(os.tmpdir(), 'writing-system-test-'));
  const root = path.join(base,'amelia');
  fs.cpSync(path.join(here,'../amelia'),root,{recursive:true,filter:p=>!p.includes('archive')&&!p.includes('delivery')});
  t.after(()=>fs.rmSync(base,{recursive:true,force:true}));
  return root;
}
function edit(root,file,fn) {const p=inside(root,file),v=read(p);fn(v);atomic(p,v);}
test('existing manuscript validates without alteration',t=>{const root=fixture(t);assert.equal(validate(root).passed,true);assert.equal(validate(root).counts.length,2);});
test('path traversal and absolute targets rejected',t=>{const root=fixture(t);assert.throws(()=>inside(root,'../outside'));assert.throws(()=>inside(root,'C:/outside'));});
test('cross-series state rejected',t=>{const root=fixture(t);edit(root,'state.json',s=>s.series_id='other');assert.equal(validate(root).passed,false);});
test('unknown current scene rejected',t=>{const root=fixture(t);edit(root,'state.json',s=>s.current_scene='absent');assert.equal(validate(root).passed,false);});
test('duplicate card detected',t=>{const root=fixture(t);edit(root,'state.json',s=>s.cards.push(s.cards[0]));assert.equal(validate(root).passed,false);});
test('unregistered manuscript detected',t=>{const root=fixture(t);fs.writeFileSync(inside(root,'manuscript/test.md'),'test fixture');assert.equal(validate(root).passed,false);});
test('wrong evidence holder detected',t=>{const root=fixture(t);edit(root,'state.json',s=>s.cards.find(c=>c.id==='E05').holder='P07');assert.equal(validate(root).passed,false);});
test('paused writer rejected but editor allowed',t=>{const root=fixture(t);assert.throws(()=>request(root,'writer','test'),/paused/);assert.equal(request(root,'editor','test').role,'editor');});
test('character view excludes author secrets',t=>{const root=fixture(t),r=request(root,'character','test');assert.equal(r.context.cards.length,1);assert.equal(r.context.cards[0].id,'P01');assert.equal(JSON.stringify(r).includes('author_only'),false);assert.equal(JSON.stringify(r).includes('偽警告'),false);});
test('cross-series worker response rejected',t=>{const root=fixture(t),r=request(root,'editor','test');assert.throws(()=>accept(root,r,{...r,series_id:'other',output:'review'}));});
test('stale response rejected',t=>{const root=fixture(t),r=request(root,'editor','test');edit(root,'state.json',s=>s.next='test fixture change');assert.throws(()=>accept(root,r,{...r,output:'review'}),/stale/);});
test('proposal replay is idempotent; different output conflicts',t=>{const root=fixture(t),r=request(root,'editor','test'),a={...r,output:'review'};const p=accept(root,r,a);assert.equal(accept(root,r,a),p);assert.equal(read(p).status,'proposal');assert.throws(()=>accept(root,r,{...a,output:'changed'}));});
test('worker transport supports separate process',async t=>{const root=fixture(t),r=request(root,'editor','test');const result=await worker(r,{command:process.execPath,args:['-e',"let s='';process.stdin.on('data',c=>s+=c);process.stdin.on('end',()=>console.log(JSON.stringify({...JSON.parse(s),output:'transport test only'})))"]});assert.equal(result.request_id,r.request_id);assert.ok(accept(root,r,result));});
test('worker timeout handled',async()=>{await assert.rejects(worker({}, {command:process.execPath,args:['-e','setInterval(()=>{},1000)'],timeout_ms:100}),/timeout/);});
test('worker invalid output handled',async()=>{await assert.rejects(worker({}, {command:process.execPath,args:['-e',"process.stdin.resume();process.stdin.on('end',()=>console.log('bad json'))"]}),/invalid JSON/);});
test('worker failure handled',async()=>{await assert.rejects(worker({}, {command:process.execPath,args:['-e','process.exit(2)']}));});
