import fs from 'node:fs';
import crypto from 'node:crypto';
import {inside,read,atomic,openSeries,fingerprint,hash,request} from './engine.mjs';
import {fileURLToPath} from 'node:url';

export function manuscriptForReview(root,{series_id,scene_id,base}={}) {
  const s=openSeries(root),current=fingerprint(root);
  if(series_id!==s.config.series_id)throw Error('wrong series');
  if(base!==current)throw Error('stale manuscript review');
  const matches=s.state.scene_log.filter(x=>x.id===scene_id);
  if(matches.length!==1)throw Error('registered scene required');
  const scene=matches[0];
  if(typeof scene.path!=='string'||!scene.path.startsWith(s.config.manuscript_dir+'/'))throw Error('registered manuscript required');
  const text=fs.readFileSync(inside(root,scene.path),'utf8');
  if(!text.trim())throw Error('empty manuscript');
  if(fingerprint(root)!==current)throw Error('changed during read');
  return {series_id,base:current,scene_id,path:scene.path,status:scene.status,source:scene.source,sha256:hash(text),text};
}

export function manuscriptCouncil(root,input) {
  const source=manuscriptForReview(root,input),s=openSeries(root);
  if(input.manuscript_sha256!==source.sha256)throw Error('reviewed manuscript changed');
  if(typeof input.agenda!=='string'||!input.agenda.trim())throw Error('agenda required');
  if(!['conversation','generated_then_review','hybrid'].includes(input.workflow))throw Error('workflow required');
  const character=s.state.cards.find(c=>c.id===s.config.pov_character&&c.type==='character');
  if(!character)throw Error('POV character required');
  const roles=read(fileURLToPath(new URL('./council.json',import.meta.url))).roles;
  const requests=roles.map(p=>{
    const req=request(root,p.id,'既存本文の検討。改稿本文の生成や正本への反映は行わず、指摘・根拠・改善案を返す。\n議題（参照資料）：'+input.agenda);
    return {...req,perspective:p.id==='editor'?{...p,name:'作家視点の編集レビュー'}:p,context:{...req.context,manuscript:source}};
  });
  // Author agenda and full manuscript can contain future events or unrevealed truth.
  // The character sees only the existing explicit knowledge view, never these inputs.
  const pov=request(root,'character','現在の明示された知識の範囲で、人物としての感情・動機・判断を検討してください。未提示の本文内容や未来を推測せず、判断できない点は保留してください。');
  requests.push({...pov,perspective:{id:'character',name:character.name??character.id,focus:['現在の知識','感情と動機'],limitation:'本文と作者議題は未共有。本文の逐語評価ではない'}});
  if(requests.some(r=>r.base!==source.base)||fingerprint(root)!==source.base)throw Error('changed during review preparation');
  const meeting={schema_version:1,id:crypto.randomUUID(),series_id:source.series_id,base:source.base,kind:'manuscript_review',workflow:input.workflow,agenda:input.agenda,status:'awaiting_reviews',execution_mode:'requests_only',manuscript:source,requests};
  for(const req of requests)atomic(inside(root,'system/requests/'+req.request_id+'.json'),req);
  atomic(inside(root,'system/councils/'+meeting.id+'.json'),meeting);
  return meeting;
}
