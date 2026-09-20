import http from 'node:http';
import fs from 'node:fs';
import crypto from 'node:crypto';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {openSeries,fingerprint} from './engine.mjs';
import {briefTemplate,saveBrief,briefCouncil} from './brief.mjs';
export function planningServer(root){
  const {config}=openSeries(root),token=crypto.randomUUID(),receipts=new Map();
  const html=fs.readFileSync(new URL('./企画入力.html',import.meta.url),'utf8');
  const server=http.createServer(async(req,res)=>{
    const origin='http://127.0.0.1:'+server.address().port;
    const reply=(status,data)=>{res.writeHead(status,{'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store'});res.end(JSON.stringify(data));};
    if(req.headers.host!==new URL(origin).host||req.headers.origin&&req.headers.origin!==origin){reply(403,{error:'この画面から操作してください。'});return;}
    if(req.method==='GET'&&req.url==='/'){res.writeHead(200,{'Content-Type':'text/html; charset=utf-8','Cache-Control':'no-store','X-Frame-Options':'DENY'});res.end(html);return;}
    if(req.method==='GET'&&req.url==='/api/init'){reply(200,{token,series_id:config.series_id,title:config.title,root:path.resolve(root),base:fingerprint(root),templates:['quick','guided','full'].map(mode=>briefTemplate(root,mode))});return;}
    if(req.method!=='POST'||!['/api/save','/api/council'].includes(req.url)){reply(404,{error:'見つかりません。'});return;}
    if(req.headers['x-planning-token']!==token||!req.headers['content-type']?.startsWith('application/json')){reply(403,{error:'画面を開き直してください。'});return;}
    try{
      const chunks=[];let size=0;for await(const chunk of req){size+=chunk.length;if(size>100000)throw Error('入力が長すぎます。');chunks.push(chunk);}
      const input=JSON.parse(Buffer.concat(chunks).toString('utf8'));
      if(!/^[a-f0-9-]{36}$/.test(input.operation_id??''))throw Error('操作IDが不正です。');
      const key=input.operation_id,payload=JSON.stringify({route:req.url,input});
      if(receipts.has(key)){const previous=receipts.get(key);if(previous.payload!==payload)throw Error('同じ操作IDの内容が変わっています。');reply(200,previous.result);return;}
      if(receipts.size>=1000)throw Error('保存記録が上限です。サーバーを再起動してください。');
      if(input.base!==fingerprint(root))throw Error('作品の設定が変わりました。入力を控えて画面を開き直してください。');
      let result;
      if(req.url==='/api/save'){const record=saveBrief(root,input.brief);result={id:record.id,status:record.status,unanswered:record.payload.unanswered};}
      else{const meeting=briefCouncil(root,input.brief_id);result={id:meeting.id,status:meeting.status,roles:meeting.requests.map(x=>x.role)};}
      receipts.set(key,{payload,result});reply(200,result);
    }catch(e){reply(400,{error:e.message});}
  });
  return server;
}
if(process.argv[1]&&import.meta.url===pathToFileURL(path.resolve(process.argv[1])).href){
  if(!process.argv[2])throw Error('作品フォルダを指定してください。');
  planningServer(path.resolve(process.argv[2])).listen(12902,'127.0.0.1',()=>console.log('http://127.0.0.1:12902'));
}
