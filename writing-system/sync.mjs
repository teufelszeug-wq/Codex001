import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {inside,read,atomic,hash,openSeries,fingerprint,validate} from './engine.mjs';

function location(root,id){if(!/^[a-f0-9-]{36}$/.test(id))throw Error('invalid sync id');return inside(root,'system/sync/'+id+'.json');}
async function exclusive(root,fn){
  const file=inside(root,'system/sync.lock');fs.mkdirSync(path.dirname(file),{recursive:true});
  const fd=fs.openSync(file,'wx');
  try{fs.writeSync(fd,JSON.stringify({pid:process.pid,at:new Date().toISOString()}));return await fn();}
  finally{fs.closeSync(fd);fs.unlinkSync(file);}
}
function load(root,id){const r=read(location(root,id));if(r.digest!==hash(JSON.stringify(r.payload)))throw Error('sync plan altered');return r;}
function save(root,r){atomic(location(root,r.id),r);return r;}
export async function prepareSync(root,{source,destination,target=null,expected_version=null}={}){
  return exclusive(root,()=>{
    const s=openSeries(root);
    if(!validate(root).passed)throw Error('series validation failed');
    if(!(s.config.sync_files??[]).includes(source))throw Error('source is not explicitly enabled for sync');
    if(!Object.hasOwn(s.config.destinations??{},destination))throw Error('destination not configured');
    if(target!==null&&(typeof target!=='string'||!target.trim()))throw Error('invalid target');
    if(target!==null&&(typeof expected_version!=='string'||!expected_version.trim()))throw Error('existing target requires observed remote version');
    if(target===null&&expected_version!==null)throw Error('new target cannot have a previous version');
    const text=fs.readFileSync(inside(root,source),'utf8');
    const payload={series_id:s.config.series_id,base:fingerprint(root),source,destination,
      destination_config:s.config.destinations[destination],target,expected_version,content:text,sha256:hash(text)};
    return save(root,{id:crypto.randomUUID(),payload,digest:hash(JSON.stringify(payload)),status:'prepared',attempts:0});
  });
}
function identity(adapter,r){
  if(!adapter||adapter.destination!==r.payload.destination||JSON.stringify(adapter.destination_config)!==JSON.stringify(r.payload.destination_config))throw Error('adapter destination mismatch');
  if(typeof adapter.read!=='function'||typeof adapter.write!=='function')throw Error('adapter read/write required');
}
async function verify(root,r,adapter,target){
  let actual;
  try{actual=await adapter.read(target);}catch{r.status='uncertain';r.error='readback_failed';return save(root,r);}
  if(!actual||actual.content!==r.payload.content||typeof actual.version!=='string'){
    r.status='conflict';r.error='readback_mismatch';return save(root,r);
  }
  r.status='verified';r.remote={target,version:actual.version,sha256:hash(actual.content)};
  r.verified_at=new Date().toISOString();delete r.error;return save(root,r);
}
export async function sendSync(root,id,adapter){
  return exclusive(root,async()=>{
    const r=load(root,id);identity(adapter,r);
    if(r.status==='verified')return r;
    // A crash after dispatch may have created a page. Never resend without reconciliation.
    if(r.status!=='prepared')throw Error('sync requires reconciliation or a new plan');
    if(fingerprint(root)!==r.payload.base||hash(fs.readFileSync(inside(root,r.payload.source),'utf8'))!==r.payload.sha256)throw Error('local source changed');
    if(r.payload.target!==null){
      if(adapter.conditional_update!==true)throw Error('adapter must support conditional updates');
      const actual=await adapter.read(r.payload.target);
      if(!actual||actual.version!==r.payload.expected_version){r.status='conflict';r.error='remote_version_changed';return save(root,r);}
    }else if(adapter.idempotent_create!==true||typeof adapter.lookup!=='function')throw Error('new target requires idempotent create and operation lookup');
    r.status='sending';r.attempts++;save(root,r);
    let result;
    try{result=await adapter.write({operation_id:r.id,target:r.payload.target,expected_version:r.payload.expected_version,content:r.payload.content});}
    catch{r.status='uncertain';r.error='write_result_unknown';return save(root,r);}
    if(!result||typeof result.target!=='string'||!result.target){r.status='uncertain';r.error='missing_remote_target';return save(root,r);}
    if(r.payload.target!==null&&result.target!==r.payload.target){r.status='conflict';r.error='wrong_remote_target';return save(root,r);}
    r.observed_target=result.target;save(root,r);
    return verify(root,r,adapter,result.target);
  });
}
export async function reconcileSync(root,id,adapter){
  return exclusive(root,async()=>{
    const r=load(root,id);identity(adapter,r);
    if(r.status==='verified')return r;
    if(!['uncertain','sending'].includes(r.status))throw Error('operation is not uncertain');
    let target=r.observed_target??r.payload.target;
    if(target===null||target===undefined){
      if(typeof adapter.lookup!=='function')throw Error('operation lookup required');
      const found=await adapter.lookup(r.id);
      if(!Array.isArray(found)||found.length!==1){r.status='uncertain';r.error='creation_not_uniquely_located';return save(root,r);}
      target=found[0];
    }
    // This performs no write, even if lookup finds nothing or content differs.
    return verify(root,r,adapter,target);
  });
}
export function syncStatus(root,id){return load(root,id);}
