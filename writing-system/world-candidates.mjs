import fs from 'node:fs';
import {inside,read,openSeries,fingerprint,hash} from './engine.mjs';
import {worldCategories} from './world-entries.mjs';
const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
const statuses=['proposed','approved','applying','applied','rolling_back','rolled_back'];
function check(condition){if(!condition)throw Error('invalid world candidate');}
export function readWorldCandidate(root,id){
  check(typeof id==='string'&&/^[a-f0-9-]{36}$/.test(id));
  const {config}=openSeries(root),r=read(inside(root,'system/transactions/'+id+'/record.json')),p=r.payload;
  check(r.id===id&&statuses.includes(r.status)&&p?.series_id===config.series_id&&r.digest===hash(JSON.stringify(p)));
  check(p.config?.series_id===config.series_id&&p.config.state===config.state&&typeof p.base==='string'&&typeof p.reason==='string');
  check(Array.isArray(p.entries)&&p.entries.length===2&&new Set(p.entries.map(e=>e.path)).size===2);
  const w=p.entries.find(e=>e.path==='system/world.json'),s=p.entries.find(e=>e.path===config.state);check(w&&s);
  const before=JSON.parse(w.before),after=JSON.parse(w.after),bs=JSON.parse(s.before),as=JSON.parse(s.after);
  for(const v of [before,after,bs,as])check(v?.series_id===config.series_id);
  check(Array.isArray(bs.change_log)&&Array.isArray(as.change_log)&&as.change_log.length===bs.change_log.length+1);
  const decision=as.change_log.at(-1);check(decision.type==='world_entries'&&same(p.decision_ids,[decision.id])&&decision.meeting_id===p.meeting_id&&decision.reason===p.reason);
  const stateCopy=structuredClone(as);stateCopy.change_log.pop();check(same(stateCopy,bs));
  const diff=[];
  for(const category of worldCategories){
    check(Array.isArray(before[category])&&Array.isArray(after[category]));
    const maps=[before[category],after[category]].map(list=>{const m=new Map();for(const e of list){check(e&&typeof e.id==='string'&&!m.has(e.id));m.set(e.id,e);}return m;});
    for(const id of maps[0].keys())check(maps[1].has(id));
    for(const [entryId,value]of maps[1]){
      const old=maps[0].get(entryId)??null;if(same(old,value))continue;
      check(/^[a-zA-Z][a-zA-Z0-9_-]{0,79}$/.test(entryId)&&typeof value.value==='string'&&value.value.trim()&&['proposal','confirmed','rejected','unknown'].includes(value.status));
      check(Array.isArray(value.sources)&&value.sources.length&&value.sources.every(x=>typeof x==='string'&&x.trim())&&value.decision_id===decision.id);
      if(old){const retained={...value,value:old.value,status:old.status,sources:old.sources};if(Object.hasOwn(old,'decision_id'))retained.decision_id=old.decision_id;else delete retained.decision_id;check(same(retained,old));}
      diff.push({category,id:entryId,kind:old?'update':'add',before:old,after:value});
    }
  }
  check(diff.length>0&&Array.isArray(decision.entries));
  const keys=items=>items.map(x=>x.category+':'+x.id+':'+x.kind).sort();check(same(keys(diff),keys(decision.entries)));
  const top=v=>Object.fromEntries(Object.entries(v).filter(([k])=>!worldCategories.includes(k)));check(same(top(before),top(after)));
  if(r.status!=='proposed')check(r.approval?.digest===r.digest&&typeof r.approval.actor==='string'&&r.approval.actor.trim()&&typeof r.approval.source==='string'&&r.approval.source.trim());
  if(['rolling_back','rolled_back'].includes(r.status))check(typeof r.rollback?.actor==='string'&&r.rollback.actor.trim()&&typeof r.rollback.source==='string'&&r.rollback.source.trim());
  const currentMatches=side=>p.entries.every(e=>fs.readFileSync(inside(root,e.path),'utf8')===e[side]);
  return {id:r.id,status:r.status,digest:r.digest,base:p.base,stale:p.base!==fingerprint(root),reason:p.reason,meeting_id:p.meeting_id,decision_id:decision.id,diff,
    current_matches_before:currentMatches('before'),current_matches_after:currentMatches('after'),
    approval:r.approval?{actor:r.approval.actor,source:r.approval.source,at:r.approval.at}:null,
    rollback:r.rollback?{actor:r.rollback.actor,source:r.rollback.source,at:r.rollback.at}:null};
}
export function worldCandidates(root){
  openSeries(root);const folder=inside(root,'system/transactions'),records=[],issues=[];
  if(!fs.existsSync(folder))return {records,issues,truncated:false};
  const dirs=fs.readdirSync(folder,{withFileTypes:true}).filter(x=>x.isDirectory()&&/^[a-f0-9-]{36}$/.test(x.name));
  for(const item of dirs.slice(0,200)){try{records.push(readWorldCandidate(root,item.name));}catch{issues.push({id:item.name,message:'この画面では候補を検証できません。汎用候補・中断記録・破損の有無を確認してください。'});}}
  return {records,issues,truncated:dirs.length>200};
}
