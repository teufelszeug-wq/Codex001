import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import {initialize} from './project.mjs';
import {recordedOperation} from './operation-receipt.mjs';
function setup(t){const w=fs.mkdtempSync(path.join(os.tmpdir(),'novel-receipt-'));t.after(()=>fs.rmSync(w,{recursive:true,force:true}));return initialize(w,'receipt-test','test');}
test('receipt on disk returns completed result without repeating effect',t=>{const root=setup(t),id=crypto.randomUUID();let calls=0;assert.deepEqual(recordedOperation(root,id,{a:1},()=>{calls++;return {id:'saved'};}),{id:'saved'});assert.deepEqual(recordedOperation(root,id,{a:1},()=>{throw Error('must not run');}),{id:'saved'});assert.equal(calls,1);assert.throws(()=>recordedOperation(root,id,{a:2},()=>{}),/内容/);});
test('failure after side effect remains uncertain and is never replayed',t=>{const root=setup(t),id=crypto.randomUUID();let calls=0;assert.throws(()=>recordedOperation(root,id,{},()=>{calls++;throw Error('after write');}),e=>e.uncertain);assert.throws(()=>recordedOperation(root,id,{},()=>{calls++;}),e=>e.uncertain);assert.equal(calls,1);});
