import fs from 'node:fs';
import path from 'node:path';
import {initialize,council,finishCouncil} from './project.mjs';
import {health,snapshot} from './health.mjs';
import {read, atomic, inside, openSeries, validate, request, accept, worker} from './engine.mjs';

const [command, rootArg, ...args] = process.argv.slice(2);
try {
  if (!rootArg) throw Error('Usage: node writing-system/cli.mjs check|status|request|run|accept <series-directory> ...');
  const root = path.resolve(rootArg);
  if(command === 'health') {
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
