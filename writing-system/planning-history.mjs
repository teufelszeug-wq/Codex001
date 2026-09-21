import fs from 'node:fs';
import {inside,read,hash,openSeries,fingerprint} from './engine.mjs';
// Read only. Incomplete operations are evidence for manual review, never replayed here.
export function planningHistory(root){
  const {config}=openSeries(root),base=fingerprint(root);
  const result={base,briefs:[],operations:[],councils:[],drafts:[],issues:[],truncated:false};
  for(const kind of ['briefs','operations','councils','council-drafts']){
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
        }else if(kind==='council-drafts'){
          if(record.status!=='draft'||record.payload?.series_id!==config.series_id||record.digest!==hash(JSON.stringify(record.payload))||!/^[a-f0-9-]{36}$/.test(record.payload.meeting_id??'')||!Array.isArray(record.payload.reviews)||record.payload.reviews.length!==5)throw Error();
          const roles=['socrates','machiavelli','keynes','editor','continuity'];
          if(new Set(record.payload.reviews.map(r=>r.role)).size!==5||record.payload.reviews.some(r=>!roles.includes(r.role)||typeof r.output!=='string'))throw Error();
          const r=record.payload.resolution;if(!r||!['','conversation_single_assistant','external_workers'].includes(r.execution_mode)||typeof r.summary!=='string'||!Array.isArray(r.objections)||!Array.isArray(r.pending)||[...r.objections,...r.pending].some(x=>typeof x!=='string'))throw Error();
          result.drafts.push({...record,stale:record.payload.base!==base});
        }else if(kind==='councils'){
          if(record.series_id!==config.series_id||!['awaiting_reviews','reviewed_proposal'].includes(record.status)||typeof record.agenda!=='string'||!Array.isArray(record.requests)||record.requests.length!==5)throw Error();
          const roles=['socrates','machiavelli','keynes','editor','continuity'];
          const ids=new Set();
          for(const req of record.requests){
            if(req.series_id!==config.series_id||req.base!==record.base||!roles.includes(req.role)||ids.has(req.request_id)||!req.request_id)throw Error();
            ids.add(req.request_id);
          }
          if(new Set(record.requests.map(r=>r.role)).size!==5)throw Error();
          let replies=[];
          if(record.status==='reviewed_proposal'){
            if(!['conversation_single_assistant','external_workers'].includes(record.execution_mode)||record.resolution?.execution_mode!==record.execution_mode||typeof record.resolution?.summary!=='string'||!Array.isArray(record.resolution.objections)||!Array.isArray(record.resolution.pending)||!Array.isArray(record.replies)||record.replies.length!==5)throw Error();
            if(record.result_digest!==JSON.stringify({replies:record.replies,resolution:record.resolution}))throw Error();
            const seen=new Set();
            for(const reply of record.replies){const req=record.requests.find(r=>r.request_id===reply.request_id);if(!req||seen.has(reply.request_id)||['series_id','base','role'].some(k=>req[k]!==reply[k])||typeof reply.output!=='string'||!reply.output.trim())throw Error();seen.add(reply.request_id);}
            replies=record.replies;
          }else if(record.execution_mode!=='requests_only')throw Error();
          result.councils.push({id,status:record.status,agenda:record.agenda,stale:record.base!==base,execution_mode:record.execution_mode,reviews:record.requests.map(req=>({role:req.role,output:replies.find(r=>r.request_id===req.request_id)?.output??null})),resolution:record.status==='reviewed_proposal'?record.resolution:null});
        }else{
          if(record.series_id!==config.series_id||!['started','completed'].includes(record.status))throw Error();
          result.operations.push({id,status:record.status,started_at:record.started_at,completed_at:record.completed_at,result_id:record.status==='completed'&&typeof record.result?.id==='string'?record.result.id:null});
        }
      }catch{result.issues.push({kind,file:name,message:'記録を検証できません。個別の照合が必要です。'});}
    }
  }
  return result;
}
