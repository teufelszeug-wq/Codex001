import {inside,read,openSeries,fingerprint} from './engine.mjs';
// Validate before the operation journal is created: ordinary input errors are retryable.
export function councilSubmission(root,input){
  if(!/^[a-f0-9-]{36}$/.test(input.meeting_id??''))throw Error('会議IDが不正です。');
  const meeting=read(inside(root,'system/councils/'+input.meeting_id+'.json'));
  const {config}=openSeries(root),base=fingerprint(root);
  if(meeting.id!==input.meeting_id||meeting.series_id!==config.series_id||meeting.base!==base)throw Error('会議の作品または基準版が一致しません。');
  const roles=['socrates','machiavelli','keynes','editor','continuity'];
  if(!['awaiting_reviews','reviewed_proposal'].includes(meeting.status)||!Array.isArray(meeting.requests)||meeting.requests.length!==5||new Set(meeting.requests.map(r=>r.role)).size!==5||new Set(meeting.requests.map(r=>r.request_id)).size!==5)throw Error('会議記録を確認してください。');
  for(const req of meeting.requests)if(!roles.includes(req.role)||req.series_id!==config.series_id||req.base!==base||!/^[a-f0-9-]{36}$/.test(req.request_id??''))throw Error('会議依頼が不整合です。');
  if(!Array.isArray(input.reviews)||input.reviews.length!==5||new Set(input.reviews.map(r=>r?.role)).size!==5)throw Error('5担当すべての回答を入力してください。');
  const replies=meeting.requests.map(req=>{
    const review=input.reviews.find(r=>r?.role===req.role);
    if(typeof review?.output!=='string'||!review.output.trim())throw Error('5担当すべての回答を入力してください。');
    return {request_id:req.request_id,series_id:req.series_id,base:req.base,role:req.role,output:review.output};
  });
  const r=input.resolution;
  if(!r||!['conversation_single_assistant','external_workers'].includes(r.execution_mode)||typeof r.summary!=='string'||!r.summary.trim()||!Array.isArray(r.objections)||!Array.isArray(r.pending)||[...r.objections,...r.pending].some(x=>typeof x!=='string'||!x.trim()))throw Error('実行方式・結論・異論・保留の入力を確認してください。');
  const resolution={execution_mode:r.execution_mode,summary:r.summary,objections:r.objections,pending:r.pending};
  if(meeting.status==='reviewed_proposal'&&meeting.result_digest!==JSON.stringify({replies,resolution}))throw Error('保存済みの会議を別の内容で上書きできません。');
  return {replies,resolution};
}
