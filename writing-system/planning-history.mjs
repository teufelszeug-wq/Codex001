import fs from 'node:fs';
import {inside,read,hash,openSeries,fingerprint} from './engine.mjs';
// Read only. Incomplete operations are evidence for manual review, never replayed here.
export function planningHistory(root){
  const {config}=openSeries(root),base=fingerprint(root);
  const result={base,briefs:[],operations:[],issues:[],truncated:false};
  for(const kind of ['briefs','operations']){
    const dir=inside(root,'system/'+kind);
    if(!fs.existsSync(dir))continue;
    const names=fs.readdirSync(dir).filter(n=>n.endsWith('.json')).sort();
    if(names.length>200)result.truncated=true;
    for(const name of names.slice(0,200)){
      try{
        const id=name.slice(0,-5);if(!/^[a-f0-9-]{36}$/.test(id))throw Error();
        const record=read(inside(root,'system/'+kind+'/'+name));
        if(record.id!==id)throw Error();
        if(kind==='briefs'){
          if(record.payload?.series_id!==config.series_id||record.status!=='proposal'||record.digest!==hash(JSON.stringify(record.payload)))throw Error();
          if(!['quick','guided','full'].includes(record.payload.mode)||!record.payload.answers||!Array.isArray(record.payload.genres))throw Error();
          result.briefs.push({...record,stale:record.payload.base!==base});
        }else{
          if(record.series_id!==config.series_id||!['started','completed'].includes(record.status))throw Error();
          result.operations.push({id,status:record.status,started_at:record.started_at,completed_at:record.completed_at,result_id:record.status==='completed'&&typeof record.result?.id==='string'?record.result.id:null});
        }
      }catch{result.issues.push({kind,file:name,message:'記録を検証できません。個別の照合が必要です。'});}
    }
  }
  return result;
}
