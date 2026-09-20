import fs from 'node:fs';
import path from 'node:path';
import {initialize,council,finishCouncil} from './project.mjs';
import {health,snapshot} from './health.mjs';
import {proposeChange,approveChange,applyChange,rollbackChange} from './changes.mjs';
import {proposeTransaction,approveTransaction,recoverTransaction} from './transactions.mjs';
import {prepareSync,syncStatus,sendSync,reconcileSync} from './sync.mjs';
import {githubAdapter} from './github-sync.mjs';
import {briefTemplate,saveBrief,briefCouncil} from './brief.mjs';
import {read, atomic, inside, openSeries, validate, request, accept, worker} from './engine.mjs';

const [command, rootArg, ...args] = process.argv.slice(2);
try {
  if (!rootArg) throw Error('Usage: node writing-system/cli.mjs check|status|request|run|accept <series-directory> ...');
  const root = path.resolve(rootArg);
  if(command === 'brief-template') {
    console.log(JSON.stringify(briefTemplate(root,args[0]),null,2));
  } else if(command === 'save-brief') {
    console.log(JSON.stringify(saveBrief(root,read(inside(root,args[0]))),null,2));
  } else if(command === 'brief-council') {
    console.log(JSON.stringify(briefCouncil(root,args[0]),null,2));
  } else if(command === 'send-github' || command === 'reconcile-github' || command === 'read-github') {
    const {config}=openSeries(root);
    const adapter=githubAdapter(config.destinations.github,{token:process.env.WRITING_GITHUB_TOKEN??''});
    const result=command==='read-github'?await adapter.read(args[0]):await (command==='send-github'?sendSync:reconcileSync)(root,args[0],adapter);
    console.log(JSON.stringify(result,null,2));
  } else if(command === 'prepare-sync') {
    console.log(JSON.stringify(await prepareSync(root,read(inside(root,args[0]))),null,2));
  } else if(command === 'sync-status') {
    console.log(JSON.stringify(syncStatus(root,args[0]),null,2));
  } else if(command === 'propose-bundle') {
    const input=read(inside(root,args[0]));console.log(JSON.stringify(proposeTransaction(root,input.changes,input.metadata),null,2));
  } else if(command === 'approve-bundle') {
    console.log(JSON.stringify(approveTransaction(root,args[0],read(inside(root,args[1]))),null,2));
  } else if(command === 'apply-bundle' || command === 'recover-bundle') {
    const direction=command==='apply-bundle'?'finish':args[1];
    const approval=direction==='rollback'?read(inside(root,args[2])):null;
    console.log(JSON.stringify(recoverTransaction(root,args[0],direction,approval),null,2));
  } else if(command === 'propose-change') {
    const input=read(inside(root,args[0]));console.log(JSON.stringify(proposeChange(root,input.state,input.metadata),null,2));
  } else if(command === 'approve-change' || command === 'rollback-change') {
    const approval=read(inside(root,args[1]));
    console.log(JSON.stringify((command==='approve-change'?approveChange:rollbackChange)(root,args[0],approval),null,2));
  } else if(command === 'apply-change') {
    console.log(JSON.stringify(applyChange(root,args[0]),null,2));
  } else if(command === 'health') {
    const report=health(root);atomic(inside(root,'system/health.json'),report);console.log(JSON.stringify(report,null,2));
    if(!report.validation.passed)process.exitCode=1;
  } else if(command === 'export') {
    console.log(JSON.stringify(snapshot(root),null,2));
  } else if (command === 'init') {
    console.log(initialize(root,args[0],args.slice(1).join(' ')));
  } else if(command === 'council') {
    console.log(JSON.stringify(council(root,args.join(' ')),null,2));
  } else if(command === 'finish-council') {
    const result=read(inside(root,args[1]));
    console.log(JSON.stringify(finishCouncil(root,args[0],result.replies,result.resolution),null,2));
  } else if (command === 'check') {
    const report = validate(root);
    atomic(inside(root, 'system/validation.json'), {...report, checked_at:new Date().toISOString()});
    console.log(JSON.stringify(report,null,2));
    if (!report.passed) process.exitCode = 1;
  } else if (command === 'status') {
    const {config, control, state} = openSeries(root);
    console.log(JSON.stringify({series:config.series_id, control, current_scene:state.current_scene, validation:validate(root)},null,2));
  } else if (command === 'request' || command === 'run') {
    const req = request(root, args[0], args.slice(1).join(' '));
    atomic(inside(root, 'system/requests/' + req.request_id + '.json'), req);
    if (command === 'request') console.log(JSON.stringify(req,null,2));
    else {
      const {config} = openSeries(root);
      const result = await worker(req, config.workers?.[req.role]);
      console.log(accept(root, req, result));
    }
  } else if (command === 'accept') {
    console.log(accept(root, read(inside(root,args[0])), read(inside(root,args[1]))));
  } else throw Error('Unknown command');
} catch (e) { console.error(e.message); process.exitCode = 1; }
