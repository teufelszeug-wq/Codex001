import fs from 'node:fs';
const required=['index.html','src/main.js','src/scenes/GameScene.js','public/manifest.json','public/service-worker.js'];
for(const f of required){ if(!fs.existsSync(f)){ console.error('missing',f); process.exitCode=1; } }
if(!process.exitCode) console.log('project structure OK');
