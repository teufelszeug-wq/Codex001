import crypto from 'node:crypto';
import {openSeries,fingerprint,inside,atomic,hash} from './engine.mjs';
import {councilSubmission} from './council-submission.mjs';
export function saveCouncilDraft(root,input){
  const checked=councilSubmission(root,input,{draft:true});
  const payload={series_id:openSeries(root).config.series_id,base:fingerprint(root),meeting_id:input.meeting_id,
    reviews:checked.replies.map(({role,output})=>({role,output})),resolution:checked.resolution};
  const record={id:crypto.randomUUID(),status:'draft',created_at:new Date().toISOString(),payload,digest:hash(JSON.stringify(payload))};
  // Every save is a new snapshot; no prior draft is overwritten.
  atomic(inside(root,'system/council-drafts/'+record.id+'.json'),record);return record;
}
