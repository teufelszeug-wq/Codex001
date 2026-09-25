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
          if(record.status!=='draft'||record.payload?.series_id!==config.series_id||record.digest!==hash(JSON.stringify(record.payload))||!/^[a-f0-9-]{36}$/.test(record.payload.meeting_id??'')||!Array.isArray(record.payload.reviews)||![5,6].includes(record.payload.reviews.length))throw Error();
          const parent=read(inside(root,'system/councils/'+record.payload.meeting_id+'.json'));
          if(parent.id!==record.payload.meeting_id||parent.series_id!==config.series_id||parent.base!==record.payload.base)throw Error();
          const roles=['socrates','machiavelli','keynes','editor','continuity'];
          if(parent.kind==='manuscript_review')roles.push('character');
          if(record.payload.reviews.length!==roles.length)throw Error();
          if(new Set(record.payload.reviews.map(r=>r.role)).size!==roles.length||record.payload.reviews.some(r=>!roles.includes(r.role)||typeof r.output!=='string'))throw Error();
          const r=record.payload.resolution;if(!r||!['','conversation_single_assistant','external_workers'].includes(r.execution_mode)||typeof r.summary!=='string'||!Array.isArray(r.objections)||!Array.isArray(r.pending)||[...r.objections,...r.pending].some(x=>typeof x!=='string'))throw Error();
          result.drafts.push({...record,stale:record.payload.base!==base});
        }else if(kind==='councils'){
          if(record.series_id!==config.series_id||!['awaiting_reviews','reviewed_proposal'].includes(record.status)||typeof record.agenda!=='string'||!Array.isArray(record.requests))throw Error();
          const roles=['socrates','machiavelli','keynes','editor','continuity'];
          if(record.kind==='manuscript_review')roles.push('character');
          if(record.requests.length!==roles.length)throw Error();
          let manuscript=null;
          if(record.kind==='manuscript_review'){
            const m=record.manuscript;
            if(!m||m.series_id!==config.series_id||m.base!==record.base||typeof m.text!=='string'||m.sha256!==hash(m.text)||typeof m.scene_id!=='string'||typeof m.path!=='string'||!m.path.startsWith(config.manuscript_dir+'/'))throw Error();
            inside(root,m.path);
            manuscript={scene_id:m.scene_id,path:m.path,status:m.status,source:m.source,sha256:m.sha256,text:m.text};
          }
          const ids=new Set();
          for(const req of record.requests){
            if(req.series_id!==config.series_id||req.base!==record.base||!roles.includes(req.role)||ids.has(req.request_id)||!/^[a-f0-9-]{36}$/.test(req.request_id??''))throw Error();
            ids.add(req.request_id);
          }
          if(new Set(record.requests.map(r=>r.role)).size!==roles.length)throw Error();
          let replies=[];
          if(record.status==='reviewed_proposal'){
            if(!['conversation_single_assistant','external_workers'].includes(record.execution_mode)||record.resolution?.execution_mode!==record.execution_mode||typeof record.resolution?.summary!=='string'||!Array.isArray(record.resolution.objections)||!Array.isArray(record.resolution.pending)||!Array.isArray(record.replies)||record.replies.length!==roles.length)throw Error();
            if(record.result_digest!==JSON.stringify({replies:record.replies,resolution:record.resolution}))throw Error();
            const seen=new Set();
            for(const reply of record.replies){const req=record.requests.find(r=>r.request_id===reply.request_id);if(!req||seen.has(reply.request_id)||['series_id','base','role'].some(k=>req[k]!==reply[k])||typeof reply.output!=='string'||!reply.output.trim())throw Error();seen.add(reply.request_id);}
            replies=record.replies;
          }else{
            if(record.execution_mode!=='requests_only')throw Error();
            for(const req of record.requests){const file=inside(root,'system/inbox/'+req.request_id+'.json');if(!fs.existsSync(file))continue;const reply=read(file);if(['request_id','series_id','base','role'].some(k=>reply[k]!==req[k])||reply.status!=='proposal'||typeof reply.output!=='string'||!reply.output.trim())throw Error();replies.push(reply);}
          }
          const reviews=record.requests.map(req=>{
            const output=replies.find(r=>r.request_id===req.request_id)?.output??null;
            let attempt_status=null;
            const file=inside(root,'system/worker-runs/'+req.request_id+'.json');
            if(record.status==='awaiting_reviews'&&fs.existsSync(file)){
              const attempt=read(file);if(attempt.series_id!==config.series_id||attempt.meeting_id!==id||attempt.request_id!==req.request_id||attempt.role!==req.role||!['started','received','needs_review'].includes(attempt.status))throw Error();
              attempt_status=attempt.status;
            }
            return {role:req.role,output,source:output?(record.status==='reviewed_proposal'?'final_record':'inbox'):null,attempt_status};
          });
          result.councils.push({id,kind:record.kind??'planning',manuscript,status:record.status,agenda:record.agenda,stale:record.base!==base,execution_mode:record.execution_mode,collected_count:replies.length,reviews,resolution:record.status==='reviewed_proposal'?record.resolution:null});
        }else{
          if(record.series_id!==config.series_id||!['started','completed'].includes(record.status))throw Error();
          result.operations.push({id,status:record.status,started_at:record.started_at,completed_at:record.completed_at,result_id:record.status==='completed'&&typeof record.result?.id==='string'?record.result.id:null});
        }
      }catch{result.issues.push({kind,file:name,message:'記録を検証できません。個別の照合が必要です。'});}
    }
  }
  return result;
}
