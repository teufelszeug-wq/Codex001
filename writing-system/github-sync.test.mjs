import test from 'node:test';
import assert from 'node:assert/strict';
import {githubAdapter} from './github-sync.mjs';
const config={repository:'owner/repo',branch:'main',prefix:'series/'};
const version='a'.repeat(40),id='12345678-1234-1234-1234-123456789abc';
test('GitHub reads UTF8 and sends observed blob version on update',async()=>{
  const calls=[];const a=githubAdapter(config,{token:'test-only',fetchImpl:async(url,init)=>{calls.push({url,init});return {ok:true,json:async()=>({type:'file',encoding:'base64',content:Buffer.from('日本語').toString('base64'),sha:version})};}});
  assert.deepEqual(await a.read('series/設定.md'),{content:'日本語',version});
  await a.write({target:'series/設定.md',expected_version:version,content:'改稿',operation_id:id});
  const body=JSON.parse(calls[1].init.body);assert.equal(body.sha,version);assert.equal(body.branch,'main');assert.equal(Buffer.from(body.content,'base64').toString(),'改稿');assert.equal(calls[0].init.redirect,'error');assert.ok(calls[0].init.signal);assert.equal(a.idempotent_create,false);
});
test('GitHub rejects paths outside series and protected branch',async()=>{
  let calls=0;const a=githubAdapter(config,{fetchImpl:async()=>{calls++;}});
  for(const p of ['README.md','other/a','series/../a','series/%2e%2e/a','series/a\\b','series//a'])await assert.rejects(a.read(p),/outside/);
  assert.equal(calls,0);assert.throws(()=>githubAdapter({...config,branch:'develop'}),/protected/);
});
test('GitHub does not retry a conflict or leak credentials',async()=>{
  let calls=0;const a=githubAdapter(config,{token:'secret-fixture',fetchImpl:async()=>{calls++;return {ok:false,status:409};}});
  await assert.rejects(a.write({target:'series/a',expected_version:version,content:'x',operation_id:id}),/^Error: GitHub HTTP 409$/);assert.equal(calls,1);
  const b=githubAdapter(config,{fetchImpl:async()=>{throw Error('secret-fixture');}});await assert.rejects(b.read('series/a'),/^Error: GitHub transport failed or timed out$/);
});
test('GitHub rejects creation and unsupported content',async()=>{
  const a=githubAdapter(config,{token:'test-only',fetchImpl:async()=>({ok:true,json:async()=>({type:'symlink'})})});
  await assert.rejects(a.write({target:null,content:'x',operation_id:id}),/existing/);await assert.rejects(a.read('series/a'),/unsupported/);
});
