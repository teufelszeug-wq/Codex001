import http from 'node:http';
import path from 'node:path';
import fs from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../dist');
const types={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.json':'application/json','.png':'image/png','.woff2':'font/woff2','.woff':'font/woff'};
const port=Number(process.env.PORT||8080);
http.createServer(async(req,res)=>{try{const url=new URL(req.url,'http://localhost');let route=decodeURIComponent(url.pathname);if(route.endsWith('/'))route+='index.html';const file=path.resolve(root,'.'+route);if(!file.startsWith(root+path.sep)){res.writeHead(403);res.end();return;}const bytes=await fs.readFile(file);res.writeHead(200,{'Content-Type':types[path.extname(file)]||'application/octet-stream','Cache-Control':'no-cache'});res.end(bytes);}catch{res.writeHead(404);res.end('Not found');}}).listen(port,'127.0.0.1',()=>console.log(`GDA: http://localhost:${port} (Ctrl+C to stop)`));
