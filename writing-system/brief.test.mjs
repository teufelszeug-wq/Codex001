import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {initialize} from './project.mjs';
import {fingerprint,inside,read,atomic} from './engine.mjs';
import {briefTemplate,saveBrief,briefCouncil} from './brief.mjs';
function setup(t){const dir=fs.mkdtempSync(path.join(os.tmpdir(),'novel-brief-'));t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));return initialize(dir,'brief-test','企画試験');}
function input(root){return {...briefTemplate(root,'quick'),source_ref:'test:user-request',answers:{premise:'試験用の企画'}};}
test('three modes provide increasing questions with no invented answers',t=>{const root=setup(t),a=['quick','guided','full'].map(m=>briefTemplate(root,m));assert.ok(a[0].questions.length<a[1].questions.length&&a[1].questions.length<a[2].questions.length);assert.ok(a.every(x=>Object.values(x.answers).every(v=>v==='')));});
test('proposal reaches all council perspectives without changing canon or pause',t=>{const root=setup(t),before=fingerprint(root),r=saveBrief(root,input(root)),m=briefCouncil(root,r.id);assert.equal(fingerprint(root),before);assert.deepEqual(r.payload.unanswered,['appeal']);assert.ok(['socrates','machiavelli','keynes'].every(role=>m.requests.some(x=>x.role===role)));assert.ok(m.requests.every(x=>x.paused&&x.task.includes('試験用の企画')));});
test('wrong series, unsupported fields and invalid blend rejected',t=>{const root=setup(t),i=input(root);assert.throws(()=>saveBrief(root,{...i,series_id:'other'}),/wrong series/);assert.throws(()=>saveBrief(root,{...i,answers:{alien:'x'}}),/invalid answer/);assert.throws(()=>saveBrief(root,{...i,genres:[{name:'幻想',weight:60}]}),/total 100/);assert.throws(()=>saveBrief(root,{...i,source_ref:''}),/source reference/);});
test('changed source state or altered proposal cannot enter council',t=>{const root=setup(t),r=saveBrief(root,input(root)),file=inside(root,'state.json'),s=read(file);s.next='変更';atomic(file,s);assert.throws(()=>briefCouncil(root,r.id),/stale/);const fresh=saveBrief(root,input(root)),p=inside(root,'system/briefs/'+fresh.id+'.json');fresh.payload.answers.premise='改変';atomic(p,fresh);assert.throws(()=>briefCouncil(root,fresh.id),/altered/);});
