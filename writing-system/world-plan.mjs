import fs from 'node:fs';
import crypto from 'node:crypto';
import {openSeries,fingerprint,inside,atomic,read,hash} from './engine.mjs';
export const worldFields={countries:'国・地域',languages:'言語・命名',writing_systems:'文字体系',units:'単位・暦',currencies:'通貨・取引',religions:'宗教・信仰',magic_rules:'魔法・科学的仮定と制約',institutions:'制度・暮らし',earth_terms:'地球由来語の扱い'};
export function validateWorldPlan(root,input){
  const {config}=openSeries(root);
  if(!input||input.series_id!==config.series_id)throw Error('作品IDが一致しません。');
  if(input.base!==fingerprint(root))throw Error('作品の基準版が変わりました。再確認してください。');
  if(typeof input.source_ref!=='string'||!input.source_ref.trim()||input.source_ref.length>4000)throw Error('出典を入力してください。');
  if(!input.notes||Array.isArray(input.notes)||typeof input.notes!=='object')throw Error('設定案を入力してください。');
  for(const [key,value]of Object.entries(input.notes))if(!Object.hasOwn(worldFields,key)||typeof value!=='string'||value.length>10000)throw Error('設定項目が不正です。');
  if(!Object.values(input.notes).some(x=>x.trim()))throw Error('少なくとも一項目を入力してください。');
  return {series_id:config.series_id,base:input.base,source_ref:input.source_ref,notes:structuredClone(input.notes)};
}
export function saveWorldPlan(root,input){
  const payload=validateWorldPlan(root,input),record={id:crypto.randomUUID(),status:'proposal',payload,digest:hash(JSON.stringify(payload)),created_at:new Date().toISOString()};
  atomic(inside(root,'system/world-plans/'+record.id+'.json'),record);return record;
}
export function worldPlans(root){
  const {config}=openSeries(root),base=fingerprint(root),dir=inside(root,'system/world-plans'),records=[],issues=[];
  if(!fs.existsSync(dir))return {records,issues,truncated:false};
  const files=fs.readdirSync(dir).filter(x=>/^[a-f0-9-]{36}\.json$/.test(x));
  for(const name of files.slice(0,200)){
    try{
      const r=read(inside(root,'system/world-plans/'+name));
      if(r.id+'.json'!==name||r.status!=='proposal'||r.payload?.series_id!==config.series_id||typeof r.payload.base!=='string'||typeof r.created_at!=='string'||!Number.isFinite(Date.parse(r.created_at))||r.digest!==hash(JSON.stringify(r.payload)))throw Error('invalid record');
      // Validate the content against the current contract, without treating an old base as current.
      validateWorldPlan(root,{...r.payload,base});
      records.push({...r,stale:r.payload.base!==base});
    }catch{issues.push({file:name,message:'内容を確認できないため表示しません。'});}
  }
  records.sort((a,b)=>b.created_at.localeCompare(a.created_at));
  return {records,issues,truncated:files.length>200};
}
