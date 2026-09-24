import fs from 'node:fs';
import path from 'node:path';
import {inside,read,atomic,openSeries,fingerprint,worker,accept} from './engine.mjs';
export function councilRequests(root,id){
  if(!/^[a-f0-9-]{36}$/.test(id??''))throw Error('invalid meeting id');
  const {config}=openSeries(root),meeting=read(inside(root,'system/councils/'+id+'.json'));
  if(meeting.id!==id||meeting.series_id!==config.series_id||meeting.base!==fingerprint(root))throw Error('wrong series or stale meeting');
  const roles=['socrates','machiavelli','keynes','editor','continuity'];
  if(meeting.kind==='manuscript_review')roles.push('character');
  if(!Array.isArray(meeting.requests)||meeting.requests.length!==roles.length||new Set(meeting.requests.map(r=>r.role)).size!==roles.length||new Set(meeting.requests.map(r=>r.request_id)).size!==roles.length)throw Error('invalid meeting requests');
  for(const req of meeting.requests)if(req.series_id!==config.series_id||req.base!==meeting.base||!roles.includes(req.role)||!/^[a-f0-9-]{36}$/.test(req.request_id??''))throw Error('invalid meeting request');
  return {config,meeting};
}
export function councilReplies(root,id){
  const {meeting}=councilRequests(root,id),replies=[],pending=[];
  for(const req of meeting.requests){
    const file=inside(root,'system/inbox/'+req.request_id+'.json');
    if(!fs.existsSync(file)){pending.push(req.role);continue;}
    const r=read(file);
    if(['request_id','series_id','base','role'].some(k=>r[k]!==req[k])||r.status!=='proposal'||typeof r.output!=='string'||!r.output.trim())throw Error('invalid stored review');
    replies.push(r);
  }
  return {meeting_id:id,series_id:meeting.series_id,base:meeting.base,replies,pending,ready_for_resolution:pending.length===0};
}
export async function runCouncilReview(root,id,role){
  const {config,meeting}=councilRequests(root,id);
  if(meeting.status!=='awaiting_reviews')throw Error('meeting is not awaiting reviews');
  const req=meeting.requests.find(r=>r.role===role);if(!req)throw Error('unknown council role');
  const existing=councilReplies(root,id).replies.find(r=>r.role===role);
  if(existing)return {status:'already_received',request_id:req.request_id};
  const options=config.workers?.[role];if(!options||typeof options.command!=='string'||!Array.isArray(options.args))throw Error('worker command not configured');
  const file=inside(root,'system/worker-runs/'+req.request_id+'.json');fs.mkdirSync(path.dirname(file),{recursive:true});
  const record={series_id:config.series_id,meeting_id:id,request_id:req.request_id,role,status:'started',started_at:new Date().toISOString(),transport:'external_process'};
  let fd;try{fd=fs.openSync(file,'wx');}catch(e){if(e.code==='EEXIST')throw Error('previous worker attempt needs inspection; automatic retry refused');throw e;}
  try{fs.writeFileSync(fd,JSON.stringify(record));fs.fsyncSync(fd);}finally{fs.closeSync(fd);}
  try{
    const response=await worker(req,options);
    accept(root,req,response);
    atomic(file,{...record,status:'received',completed_at:new Date().toISOString()});
    return {status:'received',request_id:req.request_id};
  }catch(error){
    const failure_reason=error.message==='worker timeout'?'timeout':error.message==='worker returned invalid JSON'?'invalid_response':error.message.startsWith('worker failed with exit ')||error.message==='worker could not start'||error.message==='worker input failed'?'process_failed':'validation_or_storage';
    atomic(file,{...record,status:'needs_review',failure_reason,completed_at:new Date().toISOString()});
    throw Error('worker result not confirmed ('+failure_reason+'); inspect attempt before retry');
  }
}
