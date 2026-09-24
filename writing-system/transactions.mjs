import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {inside,read,atomic,hash,openSeries,validate,fingerprint,managedFiles} from './engine.mjs';
import {locked} from './changes.mjs';
const content=(root,p)=>{const f=inside(root,p);return fs.existsSync(f)?fs.readFileSync(f,'utf8'):null;};
const journal=(root,id)=>{if(!/^[a-f0-9-]{36}$/.test(id))throw Error('invalid transaction id');return inside(root,'system/transactions/'+id+'/record.json');};
function writeText(file,text){
  fs.mkdirSync(path.dirname(file),{recursive:true});
  const temp=file+'.'+crypto.randomUUID()+'.tmp';
  fs.writeFileSync(temp,text,{flag:'wx'});
  try{fs.renameSync(temp,file);}finally{if(fs.existsSync(temp))fs.unlinkSync(temp);}
}
function load(root,id){const r=read(journal(root,id));if(r.digest!==hash(JSON.stringify(r.payload)))throw Error('transaction payload altered');return r;}
function checkPaths(root,config,entries){
  if(!Array.isArray(entries)||!entries.length)throw Error('changes required');
  const seen=new Set();
  for(const e of entries){
    inside(root,e.path);
    if(e.path.includes('\\')||e.path.split('/').some(x=>['.','..',''].includes(x)))throw Error('noncanonical path');
    if(![config.state,'system/world.json','system/sources.json'].includes(e.path)&&!e.path.startsWith(config.manuscript_dir+'/'))throw Error('target not allowed');
    if(seen.has(e.path.toLowerCase()))throw Error('duplicate target');seen.add(e.path.toLowerCase());
    if(typeof e.after!=='string')throw Error('replacement text required; deletion is not supported');
  }
}
function checkCandidate(root,folder){
  const report=validate(folder);if(!report.passed)throw Error('candidate validation failed: '+report.errors.join('; '));
  const s=openSeries(folder);
  for(const p of ['system/world.json','system/sources.json'])if(fs.existsSync(inside(folder,p))){const data=read(inside(folder,p));if(data.series_id!==s.config.series_id)throw Error('candidate auxiliary series mismatch');}
  return report;
}
export function proposeTransaction(root,changes,{reason,meeting_id,decision_ids}={}){
  return locked(root,()=>{
    const s=openSeries(root),base=fingerprint(root);
    if(!validate(root).passed)throw Error('current state invalid');
    if(typeof reason!=='string'||!reason.trim())throw Error('reason required');
    if(!/^[a-f0-9-]{36}$/.test(meeting_id??''))throw Error('reviewed meeting required');
    const m=read(inside(root,'system/councils/'+meeting_id+'.json'));
    if(m.series_id!==s.config.series_id||m.base!==base||m.status!=='reviewed_proposal')throw Error('reviewed current meeting required');
    const entries=changes.map(e=>({path:e.path,after:e.content}));checkPaths(root,s.config,entries);
    if(!s.control.manuscript_generation_enabled&&entries.some(e=>e.path.startsWith(s.config.manuscript_dir+'/')))throw Error('manuscript changes paused');
    const stateEntry=entries.find(e=>e.path===s.config.state);
    if(!stateEntry)throw Error('state with decision history required');
    const next=JSON.parse(stateEntry.after);
    if(!Array.isArray(decision_ids)||!decision_ids.length||decision_ids.some(id=>!next.change_log?.some(d=>d.id===id)))throw Error('decision references required');
    if(!s.control.manuscript_generation_enabled&&(JSON.stringify(next.scene_log)!==JSON.stringify(s.state.scene_log)||next.current_scene!==s.state.current_scene))throw Error('scene advancement paused');
    const id=crypto.randomUUID(),folder=inside(root,'system/transactions/'+id+'/candidate');fs.mkdirSync(folder,{recursive:true});
    const baseline=managedFiles(root).map(p=>({path:p,sha256:hash(content(root,p))}));
    for(const b of baseline)writeText(inside(folder,b.path),content(root,b.path));
    for(const e of entries){e.before=content(root,e.path);writeText(inside(folder,e.path),e.after);}
    const report=checkCandidate(root,folder);
    if(fingerprint(root)!==base)throw Error('changed during staging');
    const payload={series_id:s.config.series_id,base,config:s.config,reason,meeting_id,decision_ids,baseline,entries};
    const record={id,status:'proposed',payload,digest:hash(JSON.stringify(payload)),report};atomic(journal(root,id),record);return record;
  });
}
export function approveTransaction(root,id,approval){return locked(root,()=>{
  const r=load(root,id);if(r.status!=='proposed')throw Error('not proposed');
  if(approval?.expected_digest&&approval.expected_digest!==r.digest)throw Error('reviewed candidate changed');
  if(!approval?.actor?.trim()||!approval?.source?.trim())throw Error('approval source required');
  if(fingerprint(root)!==r.payload.base)throw Error('stale transaction');
  r.approval={...approval,digest:r.digest,at:new Date().toISOString()};r.status='approved';atomic(journal(root,id),r);return r;
});}
function assertNoConflict(root,r){
  const targets=new Map(r.payload.entries.map(e=>[e.path,e]));
  const expected=new Set([...r.payload.baseline.map(b=>b.path),...targets.keys()]);
  const scan=relative=>{const folder=inside(root,relative);if(!fs.existsSync(folder))return;for(const item of fs.readdirSync(folder,{withFileTypes:true})){
    const p=relative+'/'+item.name;if(item.isSymbolicLink())throw Error('linked content during recovery');
    if(item.isDirectory())scan(p);else if(!expected.has(p))throw Error('new file during recovery: '+p);
  }};scan(r.payload.config.manuscript_dir);
  for(const p of ['system/world.json','system/sources.json'])if(content(root,p)!==null&&!expected.has(p))throw Error('new context during recovery');
  for(const b of r.payload.baseline)if(!targets.has(b.path)&&hash(content(root,b.path)??'')!==b.sha256)throw Error('unrelated file changed: '+b.path);
  for(const e of r.payload.entries){const now=content(root,e.path);if(now!==e.before&&now!==e.after)throw Error('target conflict: '+e.path);}
}
export function recoverTransaction(root,id,direction='finish',approval=null){return locked(root,()=>{
  if(!['finish','rollback'].includes(direction))throw Error('invalid recovery direction');
  const r=load(root,id),marker=inside(root,'system/transaction-active.json');
  if(approval?.expected_digest&&approval.expected_digest!==r.digest)throw Error('reviewed candidate changed');
  checkPaths(root,r.payload.config,r.payload.entries);
  if(!r.approval||r.approval.digest!==r.digest)throw Error('approval required');
  if(direction==='rollback'&&(!approval?.actor?.trim()||!approval?.source?.trim()))throw Error('rollback source required');
  if(fs.existsSync(marker)&&read(marker).id!==id)throw Error('another transaction active');
  const terminal=direction==='finish'?'applied':'rolled_back';
  if(r.status===terminal){
    assertNoConflict(root,r);
    for(const e of r.payload.entries)if(content(root,e.path)!==(direction==='finish'?e.after:e.before))throw Error('completed transaction differs');
    if(fs.existsSync(marker))fs.unlinkSync(marker);return r;
  }
  if(!['approved','applying','rolling_back','applied'].includes(r.status))throw Error('invalid transaction status');
  if(r.status==='rolling_back'&&direction==='finish')throw Error('rollback already started');
  if(r.status==='approved'&&fingerprint(root)!==r.payload.base)throw Error('stale transaction');
  assertNoConflict(root,r);
  // Every in-system reader fails closed while this marker exists.
  r.status=direction==='finish'?'applying':'rolling_back';
  if(direction==='rollback')r.rollback={...approval,at:new Date().toISOString()};
  atomic(journal(root,id),r);atomic(marker,{id,direction});
  for(const e of r.payload.entries){
    const desired=direction==='finish'?e.after:e.before,file=inside(root,e.path);
    if(content(root,e.path)===desired)continue;
    if(desired===null){if(fs.existsSync(file))fs.unlinkSync(file);}else writeText(file,desired);
  }
  // The validated bundle is now installed; preserve journal before allowing reads again.
  r.status=terminal;r.completed_at=new Date().toISOString();atomic(journal(root,id),r);fs.unlinkSync(marker);return r;
});}
