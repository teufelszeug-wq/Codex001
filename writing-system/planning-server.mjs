import http from 'node:http';
import fs from 'node:fs';
import crypto from 'node:crypto';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {openSeries,fingerprint,read,inside,hash} from './engine.mjs';
import {worldCategories,previewWorldEntries,proposeWorldEntries} from './world-entries.mjs';
import {briefTemplate,saveBrief,briefCouncil} from './brief.mjs';
import {recordedOperation} from './operation-receipt.mjs';
import {planningHistory} from './planning-history.mjs';
import {councilSubmission} from './council-submission.mjs';
import {finishCouncil} from './project.mjs';
import {saveCouncilDraft} from './council-draft.mjs';
import {worldFields,validateWorldPlan,saveWorldPlan,worldPlans,worldPlanForCouncil,worldCouncil} from './world-plan.mjs';
export function planningServer(root){
  const {config}=openSeries(root),token=crypto.randomUUID();
  const html=fs.readFileSync(new URL('./企画入力.html',import.meta.url),'utf8');
  const server=http.createServer(async(req,res)=>{
    const origin='http://127.0.0.1:'+server.address().port;
    const reply=(status,data)=>{res.writeHead(status,{'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store'});res.end(JSON.stringify(data));};
    if(req.headers.host!==new URL(origin).host||req.headers.origin&&req.headers.origin!==origin){reply(403,{error:'この画面から操作してください。'});return;}
    if(req.method==='GET'&&req.url==='/'){res.writeHead(200,{'Content-Type':'text/html; charset=utf-8','Cache-Control':'no-store','X-Frame-Options':'DENY'});res.end(html.replace('</style>','</style><nav><a href="/world" target="_blank" rel="noopener">世界設定案を整理する ↗</a></nav>'));return;}
    if(req.method==='GET'&&req.url==='/world'){res.writeHead(200,{'Content-Type':'text/html; charset=utf-8','Cache-Control':'no-store','X-Frame-Options':'DENY'});res.end(fs.readFileSync(new URL('./世界設定.html',import.meta.url),'utf8').replace('<body>','<body><nav><a href="/world-entries" target="_blank" rel="noopener">項目ごとの変更と差分を確認する ↗</a></nav>'));return;}
    if(req.method==='GET'&&req.url==='/world-entries'){res.writeHead(200,{'Content-Type':'text/html; charset=utf-8','Cache-Control':'no-store','X-Frame-Options':'DENY'});res.end(fs.readFileSync(new URL('./世界設定の項目入力.html',import.meta.url),'utf8'));return;}
    if(req.method==='GET'&&req.url==='/api/world-entries'){
      if(req.headers['x-planning-token']!==token){reply(403,{error:'画面を開き直してください。'});return;}
      try{const world=read(inside(root,'system/world.json'));if(world.series_id!==config.series_id)throw Error();reply(200,{world,categories:worldCategories.map(id=>({id,label:worldFields[id]})),meetings:planningHistory(root).councils.filter(m=>m.status==='reviewed_proposal'&&!m.stale).map(m=>({id:m.id,agenda:m.agenda}))});}catch{reply(400,{error:'現在の設定または会議を読み込めません。'});}return;
    }
    if(req.method==='GET'&&req.url==='/api/world-plans'){
      if(req.headers['x-planning-token']!==token){reply(403,{error:'画面を開き直してください。'});return;}
      try{reply(200,{fields:worldFields,...worldPlans(root)});}catch{reply(400,{error:'作品の更新状態を確認してください。'});}return;
    }
    if(req.method==='GET'&&req.url==='/api/init'){reply(200,{token,series_id:config.series_id,title:config.title,root:path.resolve(root),base:fingerprint(root),templates:['quick','guided','full'].map(mode=>briefTemplate(root,mode))});return;}
    if(req.method==='GET'&&req.url==='/api/history'){
      if(req.headers['x-planning-token']!==token){reply(403,{error:'画面を開き直してください。'});return;}
      try{reply(200,planningHistory(root));}catch{reply(400,{error:'履歴を読み込めません。作品の更新状態を確認してください。'});}return;
    }
    if(req.method!=='POST'||!['/api/preview-world-entries','/api/propose-world-entries','/api/world-council','/api/save-world-plan','/api/save','/api/council','/api/finish-council','/api/save-council-draft'].includes(req.url)){reply(404,{error:'見つかりません。'});return;}
    if(req.headers['x-planning-token']!==token||!req.headers['content-type']?.startsWith('application/json')){reply(403,{error:'画面を開き直してください。'});return;}
    try{
      const chunks=[];let size=0;for await(const chunk of req){size+=chunk.length;if(size>100000)throw Error('入力が長すぎます。');chunks.push(chunk);}
      const input=JSON.parse(Buffer.concat(chunks).toString('utf8'));
      if(!/^[a-f0-9-]{36}$/.test(input.operation_id??''))throw Error('操作IDが不正です。');
      if(input.base!==fingerprint(root))throw Error('作品の設定が変わりました。入力を控えて画面を開き直してください。');
      if(req.url==='/api/save'&&input.brief?.series_id!==config.series_id)throw Error('作品IDが一致しません。');
      const isDraft=req.url==='/api/save-council-draft';
      if(req.url==='/api/save-world-plan')validateWorldPlan(root,input.world);
      if(req.url==='/api/world-council')worldPlanForCouncil(root,input.world_plan_id);
      if(req.url==='/api/preview-world-entries'||req.url==='/api/propose-world-entries'){
        const preview=previewWorldEntries(root,input.edit),preview_digest=hash(JSON.stringify(input.edit));
        if(req.url==='/api/preview-world-entries'){reply(200,{diff:preview.diff,preview_digest});return;}
        if(input.preview_digest!==preview_digest)throw Error('入力が変わっています。差分を確認し直してください。');
        if(typeof input.edit.reason!=='string'||!input.edit.reason.trim())throw Error('変更理由を入力してください。');
        if(!planningHistory(root).councils.some(m=>m.id===input.edit.meeting_id&&m.status==='reviewed_proposal'&&!m.stale))throw Error('現在の基準版で検討済みの会議を選んでください。');
      }
      const submission=req.url==='/api/finish-council'||isDraft?councilSubmission(root,input,{draft:isDraft}):null;
      const result=recordedOperation(root,input.operation_id,{route:req.url,input},()=>{
      let result;
      if(req.url==='/api/propose-world-entries'){const staged=proposeWorldEntries(root,input.edit);result={id:staged.transaction.id,status:staged.transaction.status,digest:staged.transaction.digest,diff:staged.diff,decision_id:staged.decision_id};}
      else if(req.url==='/api/world-council'){const meeting=worldCouncil(root,input.world_plan_id);result={id:meeting.id,status:meeting.status,execution_mode:meeting.execution_mode,world_plan_id:input.world_plan_id};}
      else if(req.url==='/api/save-world-plan'){const record=saveWorldPlan(root,input.world);result={id:record.id,status:record.status};}
      else if(req.url==='/api/save'){const record=saveBrief(root,input.brief);result={id:record.id,status:record.status,unanswered:record.payload.unanswered};}
      else if(isDraft){const record=saveCouncilDraft(root,input);result={id:record.id,status:record.status,meeting_id:input.meeting_id};}
      else if(submission){const meeting=finishCouncil(root,input.meeting_id,submission.replies,submission.resolution);result={id:meeting.id,status:meeting.status,execution_mode:meeting.execution_mode};}
      else{const meeting=briefCouncil(root,input.brief_id);result={id:meeting.id,status:meeting.status,roles:meeting.requests.map(x=>x.role)};}
      return result;
      });reply(200,result);
    }catch(e){reply(e.uncertain?409:400,{error:e.message,uncertain:!!e.uncertain});}
  });
  return server;
}
if(process.argv[1]&&import.meta.url===pathToFileURL(path.resolve(process.argv[1])).href){
  if(!process.argv[2])throw Error('作品フォルダを指定してください。');
  planningServer(path.resolve(process.argv[2])).listen(12902,'127.0.0.1',()=>console.log('http://127.0.0.1:12902'));
}
