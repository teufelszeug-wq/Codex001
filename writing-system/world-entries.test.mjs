import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import vm from 'node:vm';
import {planningServer} from './planning-server.mjs';
import {initialize,council,finishCouncil} from './project.mjs';
import {fingerprint,read} from './engine.mjs';
import {previewWorldEntries,proposeWorldEntries} from './world-entries.mjs';
import {approveTransaction,recoverTransaction} from './transactions.mjs';
function fixture(t){const w=fs.mkdtempSync(path.join(os.tmpdir(),'world-entries-')),root=initialize(w,'entry-test','Test only');t.after(()=>fs.rmSync(w,{recursive:true,force:true}));const m=council(root,'test world entries');finishCouncil(root,m.id,m.requests.map(r=>({...r,output:'test-only review'})),{execution_mode:'conversation_single_assistant',summary:'test proposal',objections:[],pending:[]});return {root,input:{series_id:'entry-test',base:fingerprint(root),meeting_id:m.id,reason:'test-only change',entries:[{category:'countries',id:'test-region',value:'test setting',status:'confirmed',sources:['test fixture']}]}};}
test('world entry preview is read-only and explicit, stage requires separate approval, rollback restores files',t=>{
 const f=fixture(t),before=fingerprint(f.root),preview=previewWorldEntries(f.root,f.input);assert.equal(preview.diff[0].kind,'add');assert.equal(fingerprint(f.root),before);
 const result=proposeWorldEntries(f.root,f.input);assert.equal(result.transaction.status,'proposed');assert.equal(fingerprint(f.root),before);assert.throws(()=>recoverTransaction(f.root,result.transaction.id));
 approveTransaction(f.root,result.transaction.id,{actor:'test',source:'test approval'});recoverTransaction(f.root,result.transaction.id);
 const world=read(path.join(f.root,'system/world.json')),state=read(path.join(f.root,'state.json'));assert.equal(world.countries[0].decision_id,result.decision_id);assert.equal(state.change_log.at(-1).id,result.decision_id);assert.equal(read(path.join(f.root,'system/control.json')).manuscript_generation_enabled,false);
 recoverTransaction(f.root,result.transaction.id,'rollback',{actor:'test',source:'test rollback'});assert.equal(fingerprint(f.root),before);
});
test('world entry edits reject missing evidence, duplicate IDs, unsupported category and stale identity',t=>{const f=fixture(t);for(const edit of [{sources:[]},{id:'../outside'},{status:'approved'},{category:'earth_terms'}])assert.throws(()=>previewWorldEntries(f.root,{...f.input,entries:[{...f.input.entries[0],...edit}]}));assert.throws(()=>previewWorldEntries(f.root,{...f.input,entries:[...f.input.entries,...f.input.entries]}));assert.throws(()=>previewWorldEntries(f.root,{...f.input,series_id:'other'}));assert.throws(()=>previewWorldEntries(f.root,{...f.input,base:'old'}));assert.throws(()=>proposeWorldEntries(f.root,{...f.input,meeting_id:'missing'}));});
test('updating one entry preserves other entries and detects no-op',t=>{const f=fixture(t),file=path.join(f.root,'system/world.json'),world=read(file);world.countries=[{id:'test-region',value:'old',status:'proposal',sources:['older'],extra:'retain'},{id:'other-region',value:'untouched',status:'unknown',sources:['other']}];fs.writeFileSync(file,JSON.stringify(world));const input={...f.input,base:fingerprint(f.root)},p=previewWorldEntries(f.root,input);assert.equal(p.diff[0].kind,'update');assert.equal(p.world.countries[0].extra,'retain');assert.deepEqual(p.world.countries[1],world.countries[1]);assert.throws(()=>previewWorldEntries(f.root,{...input,entries:[{category:'countries',...world.countries[0]}]}),/no world changes/);});
test('CLI previews and stages explicit world entries without applying them',t=>{const f=fixture(t),file=path.join(f.root,'system/entry-input.json');fs.writeFileSync(file,JSON.stringify(f.input));const cli=fileURLToPath(new URL('./cli.mjs',import.meta.url)),run=command=>JSON.parse(execFileSync(process.execPath,[cli,command,f.root,'system/entry-input.json'],{encoding:'utf8',windowsHide:true,timeout:60000}));assert.equal(run('preview-world-entries').diff.length,1);assert.equal(run('propose-world-entries').transaction.status,'proposed');assert.equal(fingerprint(f.root),f.input.base);});
test('HTTP world entry preview is read-only; stage is checked, replayable and never applies canon',async t=>{
 const f=fixture(t),server=planningServer(f.root);await new Promise(r=>server.listen(0,'127.0.0.1',r));t.after(async()=>{server.closeAllConnections();await new Promise(r=>server.close(r));});const url='http://127.0.0.1:'+server.address().port,context=await(await fetch(url+'/api/init')).json();
 const post=(route,data)=>fetch(url+route,{method:'POST',headers:{'Content-Type':'application/json','X-Planning-Token':context.token},body:JSON.stringify({operation_id:crypto.randomUUID(),base:context.base,...data})});
 assert.equal((await fetch(url+'/api/world-entries')).status,403);const data=await(await fetch(url+'/api/world-entries',{headers:{'X-Planning-Token':context.token}})).json();assert.equal(data.categories.length,8);assert.ok(data.meetings.some(m=>m.id===f.input.meeting_id));
 const preview=await(await post('/api/preview-world-entries',{edit:f.input})).json();assert.equal(preview.diff[0].kind,'add');assert.ok(!fs.existsSync(path.join(f.root,'system/operations')));assert.equal(fingerprint(f.root),f.input.base);
 assert.equal((await post('/api/propose-world-entries',{edit:f.input,preview_digest:'wrong'})).status,400);const missing={...f.input,meeting_id:''};const p=await(await post('/api/preview-world-entries',{edit:missing})).json();assert.equal((await post('/api/propose-world-entries',{edit:missing,preview_digest:p.preview_digest})).status,400);assert.ok(!fs.existsSync(path.join(f.root,'system/operations')));
 const operation_id=crypto.randomUUID(),payload={operation_id,edit:f.input,preview_digest:preview.preview_digest},first=await post('/api/propose-world-entries',payload);assert.equal(first.status,200);const result=await first.json();assert.equal((await(await post('/api/propose-world-entries',payload)).json()).id,result.id);assert.equal(result.status,'proposed');assert.equal(fs.readdirSync(path.join(f.root,'system/transactions')).length,1);assert.equal(fingerprint(f.root),f.input.base);
 assert.match(await(await fetch(url+'/world')).text(),/href="\/world-entries"/);const html=await(await fetch(url+'/world-entries')).text();new vm.Script(html.match(/<script>([\s\S]*?)<\/script>/)[1]);
});
