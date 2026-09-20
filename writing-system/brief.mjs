import crypto from 'node:crypto';
import {openSeries,fingerprint,hash,inside,atomic,read} from './engine.mjs';
import {council} from './project.mjs';
const fields={
  premise:'どんな主人公が、何を望み、何に阻まれる物語ですか？',
  reader:'どんな読者に、どんな読後感を届けたいですか？',
  appeal:'この作品で一番楽しんでほしいことは何ですか？',
  protagonist:'主人公の望み・弱さ・変化の方向は？',
  conflict:'対立する人物や制度、解決が難しい理由は？',
  world:'舞台の暮らし・制度・不思議な力の制約は？',
  style:'視点・口調・重さと笑いの配分は？',
  structure:'巻・章の役割と目標分量は？',
  language:'固有名・言語・文字・単位・通貨の方針は？',
  boundaries:'避けたい展開、他作品から持ち込まない要素は？'
};
const modes={quick:['premise','appeal'],guided:['premise','reader','appeal','protagonist','conflict','world','style'],full:Object.keys(fields)};
export function briefTemplate(root,mode='guided'){
  const {config}=openSeries(root);if(!modes[mode])throw Error('unknown planning mode');
  return {series_id:config.series_id,mode,source_ref:'',genres:[],answers:Object.fromEntries(modes[mode].map(k=>[k,''])),questions:modes[mode].map(id=>({id,question:fields[id]}))};
}
export function saveBrief(root,input){
  const {config}=openSeries(root);
  if(input.series_id!==config.series_id)throw Error('wrong series');
  if(!modes[input.mode])throw Error('unknown planning mode');
  if(typeof input.source_ref!=='string'||!input.source_ref.trim())throw Error('source reference required');
  if(!input.answers||Array.isArray(input.answers)||typeof input.answers!=='object')throw Error('answers required');
  for(const [key,value] of Object.entries(input.answers))if(!Object.hasOwn(fields,key)||typeof value!=='string')throw Error('invalid answer');
  if(!Object.values(input.answers).some(x=>x.trim()))throw Error('at least one answer required');
  if(!Array.isArray(input.genres))throw Error('genres required');
  const seen=new Set();let total=0;
  for(const g of input.genres){if(!g||typeof g.name!=='string'||!g.name.trim()||seen.has(g.name.trim())||!Number.isFinite(g.weight)||g.weight<=0||g.weight>100)throw Error('invalid genre weight');seen.add(g.name.trim());total+=g.weight;}
  if(input.genres.length&&Math.abs(total-100)>0.001)throw Error('genre weights must total 100');
  const payload={series_id:config.series_id,base:fingerprint(root),mode:input.mode,source_ref:input.source_ref,
    genres:input.genres.map(g=>({name:g.name.trim(),weight:g.weight})),answers:structuredClone(input.answers),
    unanswered:modes[input.mode].filter(k=>!input.answers[k]?.trim())};
  const record={id:crypto.randomUUID(),status:'proposal',payload,digest:hash(JSON.stringify(payload)),created_at:new Date().toISOString()};
  atomic(inside(root,'system/briefs/'+record.id+'.json'),record);return record;
}
export function briefCouncil(root,id){
  if(!/^[a-f0-9-]{36}$/.test(id))throw Error('invalid brief id');
  const record=read(inside(root,'system/briefs/'+id+'.json'));
  if(record.digest!==hash(JSON.stringify(record.payload)))throw Error('brief altered');
  const {config}=openSeries(root);
  if(record.payload.series_id!==config.series_id)throw Error('wrong series');
  if(record.payload.base!==fingerprint(root))throw Error('stale brief; review and save a new proposal');
  return council(root,'新シリーズ企画会議。以下は出典付きの未確定企画案です。未回答は補完せず質問候補にし、魅力・成立条件・代案・懸念を検討してください。本文執筆や正史化は行わないでください。\n企画ID: '+id+'\n'+JSON.stringify(record.payload,null,2));
}
