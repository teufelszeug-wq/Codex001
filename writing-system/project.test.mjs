import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {initialize,council,finishCouncil} from './project.mjs';
import {validate,request,read,inside} from './engine.mjs';
function fixture(t){const root=fs.mkdtempSync(path.join(os.tmpdir(),'novel-test-'));t.after(()=>fs.rmSync(root,{recursive:true,force:true}));return root;}
test('new series are empty, separated and paused',t=>{const w=fixture(t),a=initialize(w,'novel-a','A'),b=initialize(w,'novel-b','B');assert.equal(validate(a).passed,true);assert.equal(validate(b).passed,true);assert.equal(read(inside(a,'state.json')).cards.length,0);assert.throws(()=>initialize(w,'novel-a','overwrite'));assert.throws(()=>initialize(w,'../escape','bad'));assert.throws(()=>request(a,'writer','test'),/paused/);assert.throws(()=>request(a,'character','test'),/POV/);});
test('council includes three intellects; all reviews required; retry is safe',t=>{const a=initialize(fixture(t),'novel-a','A'),m=council(a,'system review');assert.deepEqual(m.requests.slice(0,3).map(r=>r.role),['socrates','machiavelli','keynes']);const replies=m.requests.map(r=>({...r,output:'test review'})),resolution={execution_mode:'conversation_single_assistant',summary:'test proposal',objections:[],pending:[]};assert.throws(()=>finishCouncil(a,m.id,replies.slice(1),resolution));assert.equal(finishCouncil(a,m.id,replies,resolution).status,'reviewed_proposal');assert.equal(finishCouncil(a,m.id,replies,resolution).status,'reviewed_proposal');assert.throws(()=>finishCouncil(a,m.id,replies,{...resolution,summary:'different'}));assert.equal(read(inside(a,'system/control.json')).manuscript_generation_enabled,false);});
test('meeting cannot be transferred between series',t=>{const w=fixture(t),a=initialize(w,'novel-a','A'),b=initialize(w,'novel-b','B'),m=council(a,'test');assert.throws(()=>finishCouncil(b,m.id,[],{}));});
