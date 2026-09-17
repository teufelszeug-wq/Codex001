import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {inside,atomic,read,validate,request,accept,fingerprint} from './engine.mjs';
const here=path.dirname(fileURLToPath(import.meta.url));
export function initialize(workspace,id,title) {
  if(!/^[a-z][a-z0-9-]*$/.test(id)||['sources','writing-system','amelia'].includes(id)) throw Error('invalid or reserved series id');
  if(typeof title!=='string'||!title.trim()) throw Error('title required');
  const target=inside(workspace,id);
  if(fs.existsSync(target)) throw Error('series already exists');
  // mkdir without recursive prevents concurrent creation from overwriting another project.
  fs.mkdirSync(target);
  for(const dir of ['system','manuscript','meetings','sources','images']) fs.mkdirSync(path.join(target,dir));
  atomic(path.join(target,'system/series.json'),{schema_version:1,series_id:id,title,state:'state.json',control:'system/control.json',manuscript_dir:'manuscript',pov_character:null,roles:['coordinator','writer','editor','continuity','world','emotion','character','proofreader','visual','socrates','machiavelli','keynes'],workers:{},blocked_terms:[],destinations:{}});
  atomic(path.join(target,'system/control.json'),{project:id,phase:'planning',manuscript_generation_enabled:false,deployment_mode:'conversation_and_external_worker',reason:'企画と設定を先に整理する'});
  atomic(path.join(target,'state.json'),{series_id:id,schema_version:'2.0',current_scene:null,cards:[],scene_log:[],change_log:[],emotional_trajectory:[],literary_signature_log:[],image_assets:[],next:'企画会議：読者、ジャンル、作品の魅力を決める'});
  const world=read(path.join(here,'templates/world.json'));world.series_id=id;world.status='proposal';
  atomic(path.join(target,'system/world.json'),world);
  atomic(path.join(target,'system/sources.json'),{series_id:id,sources:[],note:'未取得資料を読了扱いにしない'});
  fs.writeFileSync(path.join(target,'README.md'),`# ${title}\n\n作品ID: ${id}\n企画準備中。本文・確定設定はまだありません。共通システムは writing-system/。\n`);
  fs.writeFileSync(path.join(target,'AGENTS.md'),'# 作品別運用\n\nsystem/control.jsonを最初に確認。本文停止中は追加しない。他作品の設定を混ぜない。会議はwriting-system/council.jsonを参照。提案の確定には承認根拠を残す。\n');
  if(!validate(target).passed) throw Error('new series validation failed; inspect incomplete directory');
  return target;
}
export function council(root,agenda) {
  if(!agenda?.trim()) throw Error('agenda required');
  const roles=read(path.join(here,'council.json')).roles;
  const requests=roles.map(r=>({...request(root,r.id,agenda),perspective:r}));
  const meeting={schema_version:1,id:crypto.randomUUID(),series_id:requests[0].series_id,base:requests[0].base,agenda,status:'awaiting_reviews',execution_mode:'requests_only',requests};
  atomic(inside(root,'system/councils/'+meeting.id+'.json'),meeting);
  for(const req of requests) atomic(inside(root,'system/requests/'+req.request_id+'.json'),req);
  return meeting;
}
export function finishCouncil(root,id,replies,resolution) {
  if(!/^[a-f0-9-]{36}$/.test(id)) throw Error('invalid meeting id');
  const file=inside(root,'system/councils/'+id+'.json'),meeting=read(file);
  if(meeting.base!==fingerprint(root)) throw Error('stale meeting');
  if(!Array.isArray(replies)||replies.length!==meeting.requests.length) throw Error('all perspectives required');
  if(!resolution||!['conversation_single_assistant','external_workers'].includes(resolution.execution_mode)||!resolution.summary?.trim()||!Array.isArray(resolution.objections)||!Array.isArray(resolution.pending)) throw Error('resolution, objections and pending required');
  const ids=new Set(replies.map(r=>r.request_id));
  if(ids.size!==meeting.requests.length) throw Error('duplicate review');
  // Validate every response before any inbox writes.
  for(const req of meeting.requests){
    const reply=replies.find(r=>r.request_id===req.request_id);
    if(!reply||['series_id','base','role'].some(k=>reply[k]!==req[k])||typeof reply.output!=='string'||!reply.output.trim()) throw Error('review mismatch');
  }
  const digest=JSON.stringify({replies,resolution});
  if(meeting.status==='reviewed_proposal') {
    if(meeting.result_digest!==digest) throw Error('meeting already completed differently');
    return meeting;
  }
  for(const req of meeting.requests) accept(root,req,replies.find(r=>r.request_id===req.request_id));
  const completed={...meeting,status:'reviewed_proposal',execution_mode:resolution.execution_mode,replies,resolution,result_digest:digest,completed_at:new Date().toISOString()};
  atomic(file,completed);
  return completed;
}
