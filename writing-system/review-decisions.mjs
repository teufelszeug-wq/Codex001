import fs from 'node:fs';
import path from 'node:path';
import {inside,read,openSeries,fingerprint,hash} from './engine.mjs';
const uuid=/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/;
const text=x=>typeof x==='string'&&x.trim().length>0;
function meeting(root,id){
  const {config}=openSeries(root);
  if(!uuid.test(id))throw Error('invalid meeting id');
  const m=read(inside(root,'system/councils/'+id+'.json')),s=m.manuscript;
  if(m.id!==id||m.series_id!==config.series_id||m.kind!=='manuscript_review'||m.status!=='reviewed_proposal')throw Error('reviewed manuscript meeting required');
  if(!s||s.series_id!==m.series_id||s.base!==m.base||typeof s.text!=='string'||hash(s.text)!==s.sha256)throw Error('invalid manuscript snapshot');
  return m;
}
function normalize(m,input){
  if(input.series_id!==m.series_id||input.base!==m.base||input.manuscript_sha256!==m.manuscript.sha256)throw Error('review basis mismatch');
  if(!uuid.test(input.operation_id)||!Array.isArray(input.issues)||!input.issues.length||input.issues.length>200)throw Error('operation and issues required');
  const ids=new Set();
  const issues=input.issues.map(i=>{
    if(!text(i.id)||ids.has(i.id))throw Error('unique issue id required');ids.add(i.id);
    if(!text(i.comment)||!text(i.reason)||!text(i.actor)||!text(i.source)||!['accept','reject','defer'].includes(i.decision))throw Error('decision and evidence required');
    const a=i.anchor;
    if(!a||!Number.isInteger(a.start)||!Number.isInteger(a.end)||a.start<0||a.end<=a.start||a.end>m.manuscript.text.length||m.manuscript.text.slice(a.start,a.end)!==a.quote)throw Error('exact snapshot anchor required');
    if(i.role!=='user'&&!m.requests.some(q=>q.role===i.role))throw Error('unknown reviewer');
    return {id:i.id,role:i.role,anchor:{start:a.start,end:a.end,quote:a.quote},comment:i.comment,decision:i.decision,reason:i.reason,actor:i.actor,source:i.source};
  });
  return {schema_version:1,operation_id:input.operation_id,meeting_id:m.id,series_id:m.series_id,base:m.base,manuscript_sha256:m.manuscript.sha256,issues};
}
export function readReviewDecisions(root,meetingId,operationId){
  const m=meeting(root,meetingId);
  if(!uuid.test(operationId))throw Error('invalid operation id');
  const r=read(inside(root,'system/review-decisions/'+operationId+'.json'));
  const p=normalize(m,r);
  if(r.operation_id!==operationId||r.meeting_id!==m.id||r.schema_version!==1||r.digest!==hash(JSON.stringify(p)))throw Error('decision record mismatch');
  return {...r,stale:fingerprint(root)!==m.base};
}
export function saveReviewDecisions(root,input){
  const m=meeting(root,input.meeting_id),p=normalize(m,input);
  if(fingerprint(root)!==m.base)throw Error('stale review decisions');
  const file=inside(root,'system/review-decisions/'+p.operation_id+'.json');
  const digest=hash(JSON.stringify(p));
  if(fs.existsSync(file)){
    const old=readReviewDecisions(root,m.id,p.operation_id);
    if(old.digest!==digest)throw Error('operation already saved differently');
    return old;
  }
  fs.mkdirSync(path.dirname(file),{recursive:true});
  // Exclusive append-only record: partial writes remain inspectable, never auto-overwritten.
  const fd=fs.openSync(file,'wx');
  try{fs.writeFileSync(fd,JSON.stringify({...p,digest,created_at:new Date().toISOString()},null,2)+'\n');fs.fsyncSync(fd);}finally{fs.closeSync(fd);}
  return readReviewDecisions(root,m.id,p.operation_id);
}

export function reviewDecisionHistory(root,meetingId){
  const m=meeting(root,meetingId),base=fingerprint(root);
  const directory=inside(root,'system/review-decisions'),records=[],issues=[];
  if(!fs.existsSync(directory))return {meeting_id:m.id,base,stale:base!==m.base,records,issues};
  const entries=fs.readdirSync(directory,{withFileTypes:true}).sort((a,b)=>a.name.localeCompare(b.name));
  for(const entry of entries){
    // Do not expose unverified comments or raw exception details in history.
    if(!entry.name.endsWith('.json'))continue;
    const id=entry.name.slice(0,-5);
    if(!uuid.test(id)||!entry.isFile()||entry.isSymbolicLink()){
      issues.push({operation_id:null,status:'invalid_record'});continue;
    }
    try{
      const raw=read(inside(root,'system/review-decisions/'+entry.name));
      if(raw.meeting_id!==m.id){
        // Validate other meetings too before silently excluding their records.
        readReviewDecisions(root,raw.meeting_id,id);continue;
      }
      records.push(readReviewDecisions(root,m.id,id));
    }catch{issues.push({operation_id:id,status:'invalid_record'});}
  }
  if(fingerprint(root)!==base)throw Error('changed during decision history read');
  return {meeting_id:m.id,base,stale:base!==m.base,records,issues};
}
