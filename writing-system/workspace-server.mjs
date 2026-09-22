import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {pathToFileURL} from 'node:url';
import {inside,openSeries} from './engine.mjs';
import {initialize} from './project.mjs';
import {planningServer} from './planning-server.mjs';
const validId=id=>typeof id==='string'&&/^[a-z][a-z0-9-]*$/.test(id)&&!['sources','writing-system'].includes(id);
export function workspaceServer(workspace){
  workspace=fs.realpathSync(workspace);
  const token=crypto.randomUUID(),sessions=new Map();
  const html=fs.readFileSync(new URL('./作品一覧.html',import.meta.url),'utf8');
  function seriesRoot(id){
    if(!validId(id))throw Error('作品IDが不正です。');
    const root=inside(workspace,id);
    if(fs.lstatSync(root).isSymbolicLink())throw Error('リンクされた作品は開けません。');
    if(openSeries(root).config.series_id!==id)throw Error('作品IDと保存先が一致しません。');
    return root;
  }
  function inventory(){
    const series=[],issues=[];
    for(const entry of fs.readdirSync(workspace,{withFileTypes:true})){
      if(!entry.isDirectory()||!validId(entry.name))continue;
      const candidate=inside(workspace,entry.name);
      if(!fs.existsSync(path.join(candidate,'system/series.json')))continue;
      try{const root=seriesRoot(entry.name),{config}=openSeries(root);series.push({id:config.series_id,title:config.title,root});}
      catch{issues.push(entry.name);}
    }
    return {workspace,series,issues};
  }
  const server=http.createServer(async(req,res)=>{
    const origin='http://127.0.0.1:'+server.address().port;
    const reply=(status,data)=>{res.writeHead(status,{'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store'});res.end(JSON.stringify(data));};
    if(req.headers.host!==new URL(origin).host||req.headers.origin&&req.headers.origin!==origin){reply(403,{error:'作品一覧の画面から操作してください。'});return;}
    if(req.method==='GET'&&req.url==='/'){res.writeHead(200,{'Content-Type':'text/html; charset=utf-8','Cache-Control':'no-store','X-Frame-Options':'DENY'});res.end(html);return;}
    try{
      if(req.method==='GET'&&req.url==='/api/init'){reply(200,{token,...inventory()});return;}
      if(req.method!=='POST'||!['/api/create','/api/open'].includes(req.url)){reply(404,{error:'見つかりません。'});return;}
      if(req.headers['x-workspace-token']!==token||!req.headers['content-type']?.startsWith('application/json')){reply(403,{error:'作品一覧を開き直してください。'});return;}
      let size=0;const chunks=[];
      for await(const chunk of req){size+=chunk.length;if(size>10000)throw Error('入力が長すぎます。');chunks.push(chunk);}
      const input=JSON.parse(Buffer.concat(chunks).toString('utf8'));
      if(!validId(input.id))throw Error('作品IDは半角英小文字で始まる英小文字・数字・ハイフンにしてください。');
      if(req.url==='/api/create'){
        if(input.id==='amelia'||typeof input.title!=='string'||!input.title.trim()||input.title.length>200)throw Error('作品IDまたはタイトルを確認してください。');
        if(fs.existsSync(inside(workspace,input.id)))throw Error('同じ保存先が存在します。一覧を更新して確認してください。');
        try{const root=initialize(workspace,input.id,input.title.trim());reply(201,{id:input.id,root});}
        catch{reply(409,{error:'作成結果を確認できません。保存先を確認してください。同じIDでは上書きしません。',uncertain:true});}return;
      }
      const root=seriesRoot(input.id);
      if(!sessions.has(input.id)){
        const pending=new Promise((resolve,reject)=>{const child=planningServer(root);child.once('error',reject);child.listen(0,'127.0.0.1',()=>resolve(child));});
        sessions.set(input.id,pending);
        pending.catch(()=>sessions.delete(input.id));
      }
      const child=await sessions.get(input.id);
      reply(200,{url:'http://127.0.0.1:'+child.address().port,id:input.id});
    }catch{reply(400,{error:'操作できませんでした。作品ID・タイトル・保存先と作品の更新状態を確認してください。'});}
  });
  server.closePlanning=async()=>{for(const pending of sessions.values()){try{const child=await pending;await new Promise(resolve=>child.close(resolve));}catch{}}sessions.clear();};
  return server;
}
if(process.argv[1]&&import.meta.url===pathToFileURL(path.resolve(process.argv[1])).href){
  const server=workspaceServer(path.resolve(process.argv[2]||'.'));
  server.listen(12903,'127.0.0.1',()=>console.log('http://127.0.0.1:12903'));
  for(const signal of ['SIGINT','SIGTERM'])process.on(signal,async()=>{await server.closePlanning();server.close();});
}
