import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {initialize,council,finishCouncil} from './project.mjs';
import {read,inside,atomic,openSeries} from './engine.mjs';
import {proposeTransaction,approveTransaction,recoverTransaction} from './transactions.mjs';
const auth={actor:'test author',source:'test approval'};
function fixture(t){const w=fs.mkdtempSync(path.join(os.tmpdir(),'novel-bundle-'));t.after(()=>fs.rmSync(w,{recursive:true,force:true}));const root=initialize(w,'test-novel','test');const m=council(root,'test review');finishCouncil(root,m.id,m.requests.map(r=>({...r,output:'test'})),{execution_mode:'conversation_single_assistant',summary:'test',objections:[],pending:[]});const s=read(inside(root,'state.json'));s.change_log.push({id:'D-test',status:'proposal',change:'test'});const world=read(inside(root,'system/world.json'));world.countries.push({id:'C-test',status:'proposal'});return {root,changes:[{path:'state.json',content:JSON.stringify(s,null,2)+'\n'},{path:'system/world.json',content:JSON.stringify(world,null,2)+'\n'}],meta:{reason:'test',meeting_id:m.id,decision_ids:['D-test']}};}
function proposed(f){const r=proposeTransaction(f.root,f.changes,f.meta);approveTransaction(f.root,r.id,auth);return r;}
function interrupt(f,r){const p=inside(f.root,'system/transactions/'+r.id+'/record.json'),v=read(p);v.status='applying';atomic(p,v);atomic(inside(f.root,'system/transaction-active.json'),{id:r.id,direction:'finish'});fs.writeFileSync(inside(f.root,r.payload.entries[0].path),r.payload.entries[0].after);}
test('bundle requires approval and applies both files',t=>{const f=fixture(t),r=proposeTransaction(f.root,f.changes,f.meta);assert.throws(()=>recoverTransaction(f.root,r.id),/approval/);approveTransaction(f.root,r.id,auth);assert.equal(recoverTransaction(f.root,r.id).status,'applied');for(const e of r.payload.entries)assert.equal(fs.readFileSync(inside(f.root,e.path),'utf8'),e.after);assert.equal(recoverTransaction(f.root,r.id).status,'applied');});
test('interrupted bundle blocks reads then finishes',t=>{const f=fixture(t),r=proposed(f);interrupt(f,r);assert.throws(()=>openSeries(f.root),/unfinished/);assert.equal(recoverTransaction(f.root,r.id).status,'applied');assert.equal(openSeries(f.root).state.change_log.length,1);});
test('interrupted bundle restores every original byte',t=>{const f=fixture(t),r=proposed(f);interrupt(f,r);recoverTransaction(f.root,r.id,'rollback',auth);for(const e of r.payload.entries)assert.equal(fs.readFileSync(inside(f.root,e.path),'utf8'),e.before);assert.equal(openSeries(f.root).state.change_log.length,0);});
test('external conflict is preserved and blocks recovery',t=>{const f=fixture(t),r=proposed(f);interrupt(f,r);fs.writeFileSync(inside(f.root,'system/world.json'),'external edit');assert.throws(()=>recoverTransaction(f.root,r.id),/conflict/);assert.equal(fs.readFileSync(inside(f.root,'system/world.json'),'utf8'),'external edit');assert.throws(()=>openSeries(f.root),/unfinished/);});
test('new manuscript during interruption is detected',t=>{const f=fixture(t),r=proposed(f);interrupt(f,r);fs.writeFileSync(inside(f.root,'manuscript/extra.md'),'test fixture');assert.throws(()=>recoverTransaction(f.root,r.id),/new file/);});
test('paused manuscript and protected config writes rejected',t=>{const f=fixture(t);assert.throws(()=>proposeTransaction(f.root,[...f.changes,{path:'manuscript/new.md',content:'test'}],f.meta),/paused/);assert.throws(()=>proposeTransaction(f.root,[...f.changes,{path:'system/control.json',content:'{}'}],f.meta),/not allowed/);});
test('cross-series world and duplicate paths rejected before writes',t=>{const f=fixture(t);f.changes[1].content='{"series_id":"other"}';assert.throws(()=>proposeTransaction(f.root,f.changes,f.meta),/mismatch/);assert.throws(()=>proposeTransaction(f.root,[f.changes[0],f.changes[0]],f.meta),/duplicate/);assert.equal(openSeries(f.root).state.change_log.length,0);});
test('completed rollback receipt can clear interrupted marker',t=>{const f=fixture(t),r=proposed(f);recoverTransaction(f.root,r.id);recoverTransaction(f.root,r.id,'rollback',auth);atomic(inside(f.root,'system/transaction-active.json'),{id:r.id,direction:'rollback'});assert.equal(recoverTransaction(f.root,r.id,'rollback',auth).status,'rolled_back');assert.equal(openSeries(f.root).state.change_log.length,0);});
test('actual process termination leaves recoverable journal and owned lock',t=>{
  const f=fixture(t),r=proposed(f);
  const script=`import fs from 'node:fs'; import {recoverTransaction} from ${JSON.stringify(new URL('./transactions.mjs',import.meta.url).href)};
const rename=fs.renameSync;fs.renameSync=function(a,b){rename(a,b);if(b===process.argv[3])process.exit(91);};recoverTransaction(process.argv[1],process.argv[2]);`;
  const result=spawnSync(process.execPath,['--input-type=module','-e',script,f.root,r.id,inside(f.root,'state.json')],{encoding:'utf8',timeout:15000,windowsHide:true});
  assert.equal(result.status,91,result.stderr);
  assert.throws(()=>openSeries(f.root),/unfinished/);
  const lock=inside(f.root,'system/change.lock');assert.equal(read(lock).pid,result.pid);
  // This exact child has terminated; only its test-owned lock is released.
  fs.unlinkSync(lock);
  assert.equal(recoverTransaction(f.root,r.id).status,'applied');
  for(const e of r.payload.entries)assert.equal(fs.readFileSync(inside(f.root,e.path),'utf8'),e.after);
});
