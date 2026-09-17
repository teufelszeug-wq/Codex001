import fs from 'node:fs';
import {inside,read,atomic,hash,openSeries,validate,fingerprint} from './engine.mjs';
import crypto from 'node:crypto';
import path from 'node:path';

const encode = v => JSON.stringify(v,null,2)+'\n';
function recordPath(root,id){if(!/^[a-f0-9-]{36}$/.test(id))throw Error('invalid change id');return inside(root,'system/changes/'+id+'/record.json');}
function locked(root,fn){
  const file=inside(root,'system/change.lock');
  fs.mkdirSync(path.dirname(file),{recursive:true});
  const fd=fs.openSync(file,'wx');
  try {fs.writeSync(fd,JSON.stringify({pid:process.pid,created_at:new Date().toISOString()}));return fn();}
  finally{fs.closeSync(fd);fs.unlinkSync(file);}
}
function candidateCheck(root,state,id){
  const {config,control}=openSeries(root);
  const folder=inside(root,'system/changes/'+id+'/candidate');
  fs.mkdirSync(folder,{recursive:true});
  // This retained validation copy is also the audit artifact; no live state is replaced.
  atomic(inside(folder,'system/series.json'),config);
  atomic(inside(folder,config.control),control);
  atomic(inside(folder,config.state),state);
  const manuscript=inside(root,config.manuscript_dir);
  if(fs.existsSync(manuscript)){
    const copy=(relative)=>{for(const e of fs.readdirSync(inside(root,relative),{withFileTypes:true})){
      const p=relative+'/'+e.name;
      if(e.isSymbolicLink())throw Error('linked manuscript is not supported');
      if(e.isDirectory())copy(p);else{const dest=inside(folder,p);fs.mkdirSync(path.dirname(dest),{recursive:true});fs.copyFileSync(inside(root,p),dest);}
    }};copy(config.manuscript_dir);
  }
  return validate(folder);
}
export function proposeChange(root,next,{reason,meeting_id,decision_ids}={}){
  return locked(root,()=>{
    const s=openSeries(root),base=fingerprint(root);
    if(!validate(root).passed)throw Error('current state invalid');
    if(typeof reason!=='string'||!reason.trim())throw Error('reason required');
    if(!/^[a-f0-9-]{36}$/.test(meeting_id??''))throw Error('meeting required');
    const meeting=read(inside(root,'system/councils/'+meeting_id+'.json'));
    if(meeting.series_id!==s.config.series_id||meeting.base!==base||meeting.status!=='reviewed_proposal')throw Error('meeting must be reviewed and current');
    if(!Array.isArray(decision_ids)||!decision_ids.length||decision_ids.some(id=>!next.change_log?.some(d=>d.id===id)))throw Error('decision references required');
    if(next.series_id!==s.config.series_id)throw Error('wrong series');
    if(!s.control.manuscript_generation_enabled && (JSON.stringify(next.scene_log)!==JSON.stringify(s.state.scene_log)||next.current_scene!==s.state.current_scene))throw Error('scene advancement paused');
    const id=crypto.randomUUID(),report=candidateCheck(root,next,id);
    if(!report.passed)throw Error('candidate validation failed: '+report.errors.join('; '));
    if(fingerprint(root)!==base)throw Error('series changed during proposal');
    const before=fs.readFileSync(inside(root,s.config.state),'utf8');
    const payload={series_id:s.config.series_id,state_path:s.config.state,base,reason,meeting_id,decision_ids,before,after:encode(next)};
    const record={id,status:'proposed',payload,digest:hash(JSON.stringify(payload)),report};
    atomic(recordPath(root,id),record);return record;
  });
}
function get(root,id){const r=read(recordPath(root,id));if(r.digest!==hash(JSON.stringify(r.payload)))throw Error('change payload altered');if(r.payload.series_id!==openSeries(root).config.series_id)throw Error('wrong series');return r;}
export function approveChange(root,id,{actor,source}={}){
  return locked(root,()=>{
    const r=get(root,id);
    if(r.status!=='proposed')throw Error('change is not proposed');
    if(!actor?.trim()||!source?.trim())throw Error('approval actor and source required');
    if(fingerprint(root)!==r.payload.base)throw Error('stale proposal');
    r.approval={actor,source,digest:r.digest,at:new Date().toISOString()};r.status='approved';atomic(recordPath(root,id),r);return r;
  });
}
export function applyChange(root,id){
  return locked(root,()=>{
    const r=get(root,id),s=openSeries(root),file=inside(root,r.payload.state_path),current=fs.readFileSync(file,'utf8');
    if(r.status==='applied'){if(current!==r.payload.after)throw Error('applied state has since changed');return r;}
    if(!['approved','applying'].includes(r.status)||r.approval?.digest!==r.digest)throw Error('matching approval required');
    if(r.status==='applying'&&current===r.payload.after){r.status='applied';atomic(recordPath(root,id),r);return r;}
    if(current!==r.payload.before||fingerprint(root)!==r.payload.base)throw Error('stale proposal or recovery conflict');
    const next=JSON.parse(r.payload.after);
    if(!s.control.manuscript_generation_enabled&&(JSON.stringify(next.scene_log)!==JSON.stringify(s.state.scene_log)||next.current_scene!==s.state.current_scene))throw Error('scene advancement paused');
    if(!candidateCheck(root,next,id).passed)throw Error('candidate no longer valid');
    r.status='applying';atomic(recordPath(root,id),r);
    // Atomic replacement of the one canonical state file. The before image remains in the journal.
    atomic(file,next);
    r.status='applied';r.applied_at=new Date().toISOString();atomic(recordPath(root,id),r);return r;
  });
}
export function rollbackChange(root,id,{actor,source}={}){
  return locked(root,()=>{
    const r=get(root,id),file=inside(root,r.payload.state_path);
    if(!actor?.trim()||!source?.trim())throw Error('rollback actor and source required');
    if(!['applied','applying'].includes(r.status))throw Error('change has not been applied');
    if(fs.readFileSync(file,'utf8')!==r.payload.after)throw Error('rollback would overwrite later changes');
    // Validate restored state against the current manuscript files before replacing it.
    const before=JSON.parse(r.payload.before),checkId=crypto.randomUUID();
    if(!candidateCheck(root,before,checkId).passed)throw Error('rollback state no longer valid');
    atomic(file,before);
    r.status='rolled_back';r.rollback={actor,source,at:new Date().toISOString()};atomic(recordPath(root,id),r);return r;
  });
}
