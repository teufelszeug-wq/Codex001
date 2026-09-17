import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {initialize} from './project.mjs';
import {health,snapshot} from './health.mjs';
import {inside,read,atomic,request,accept} from './engine.mjs';
function fixture(t){const w=fs.mkdtempSync(path.join(os.tmpdir(),'novel-health-'));t.after(()=>fs.rmSync(w,{recursive:true,force:true}));return initialize(w,'sample-series','sample');}
test('health distinguishes records from live capability',t=>{const r=health(fixture(t));assert.equal(r.records.images,0);assert.equal(r.capabilities.external_workers.live_connection_verified,false);assert.equal(r.capabilities.map_event_simulation,'not_implemented');});
test('world change invalidates outstanding review',t=>{const root=fixture(t),req=request(root,'editor','review');const f=inside(root,'system/world.json'),w=read(f);w.countries.push({id:'test',status:'proposal'});atomic(f,w);assert.throws(()=>accept(root,req,{...req,output:'old world review'}),/stale/);});
test('editor receives emotion and style memory',t=>{const root=fixture(t),p=inside(root,'state.json'),s=read(p);s.literary_signature_log.push({id:'rule',rule:'test style'});atomic(p,s);assert.equal(request(root,'editor','review').context.literary_signature_log[0].rule,'test style');});
test('export is reproducible and contains world without claiming remote sync',t=>{const root=fixture(t),a=snapshot(root),b=snapshot(root);assert.equal(a.file,b.file);assert.equal(a.remote_sync,false);assert.ok(read(a.file).entries.some(e=>e.path==='system/world.json'));});
