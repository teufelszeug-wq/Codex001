import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {spawn} from 'node:child_process';

export const hash = value => crypto.createHash('sha256').update(value).digest('hex');
export const read = file => JSON.parse(fs.readFileSync(file, 'utf8').replace(/^\uFEFF/, ''));
export function inside(root, relative) {
  if (typeof relative !== 'string' || !relative || path.isAbsolute(relative) || relative.includes(':')) throw Error('invalid relative path');
  const base = fs.realpathSync(root), target = path.resolve(base, relative);
  if (!target.startsWith(base + path.sep)) throw Error('path outside series');
  let existing = target;
  while (!fs.existsSync(existing)) existing = path.dirname(existing);
  const real = fs.realpathSync(existing);
  if (real !== base && !real.startsWith(base + path.sep)) throw Error('linked path outside series');
  return target;
}
export function atomic(file, value) {
  fs.mkdirSync(path.dirname(file), {recursive: true});
  const temp = file + '.' + crypto.randomUUID() + '.tmp';
  fs.writeFileSync(temp, JSON.stringify(value, null, 2) + '\n', {flag: 'wx'});
  try { fs.renameSync(temp, file); } finally { if (fs.existsSync(temp)) fs.unlinkSync(temp); }
}
export function openSeries(root) {
  root = fs.realpathSync(root);
  const config = read(inside(root, 'system/series.json'));
  if (config.schema_version !== 1 || !/^[a-z][a-z0-9-]*$/.test(config.series_id)) throw Error('invalid series config');
  const control = read(inside(root, config.control));
  const state = read(inside(root, config.state));
  if (state.series_id !== config.series_id || control.project !== config.series_id) throw Error('series identity mismatch');
  return {root, config, control, state};
}
function files(root, relative) {
  const dir = inside(root, relative);
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir, {withFileTypes: true}).flatMap(e => {
    const name = relative + '/' + e.name;
    inside(root, name);
    if (e.isSymbolicLink()) throw Error('links are not accepted in managed content');
    return e.isDirectory() ? files(root, name) : [name];
  });
}
export function validate(root) {
  const errors = [], warnings = [], counts = [];
  let s;
  try { s = openSeries(root); } catch (e) { return {passed: false, errors: [e.message], warnings, counts}; }
  const {state, config, control} = s;
  const unique = (items, label) => {
    if (!Array.isArray(items)) { errors.push(label + ': array required'); return new Map(); }
    const map = new Map();
    for (const item of items) {
      if (!item.id || map.has(item.id)) errors.push(label + ': missing/duplicate id ' + item.id);
      map.set(item.id, item);
    }
    return map;
  };
  const cards = unique(state.cards, 'cards'), scenes = unique(state.scene_log, 'scenes'), decisions = unique(state.change_log, 'decisions');
  if (state.current_scene && !scenes.has(state.current_scene)) errors.push('current_scene missing');
  if (control.phase === 'system_build' && control.manuscript_generation_enabled !== false) errors.push('system_build must pause manuscripts');
  const ref = (id, type, label) => { if (id && (!cards.has(id) || (type && cards.get(id).type !== type))) errors.push(label + ': invalid reference ' + id); };
  for (const c of cards.values()) {
    if (!c.status || !(c.source || c.sources?.length)) errors.push(c.id + ': status/source required');
    ref(c.location, 'location', c.id); ref(c.holder, 'character', c.id);
    for (const id of c.possessions ?? []) {
      ref(id, 'evidence', c.id);
      if (cards.get(id)?.holder !== c.id) errors.push(c.id + ': possession/holder mismatch ' + id);
    }
    for (const knowledge of c.knows ?? []) if ((c.does_not_know ?? []).includes(knowledge)) errors.push(c.id + ': contradictory knowledge');
    if (c.first_scene && !scenes.has(c.first_scene)) errors.push(c.id + ': first_scene missing');
  }
  const registered = new Set();
  for (const scene of scenes.values()) {
    if (!scene.status || !scene.source) errors.push(scene.id + ': status/source required');
    if (!scene.path) continue;
    try {
      if (!scene.path.startsWith(config.manuscript_dir + '/')) throw Error('manuscript path outside configured directory');
      if (registered.has(scene.path.toLowerCase())) errors.push('duplicate manuscript path');
      registered.add(scene.path.toLowerCase());
      const content = fs.readFileSync(inside(root, scene.path), 'utf8');
      const body = content.split(/\r?\n/).filter(l => !l.startsWith('#')).join('\n');
      for (const term of config.blocked_terms ?? []) if (body.includes(term)) errors.push(scene.id + ': blocked term ' + term);
      counts.push({scene: scene.id, characters: body.replace(/\s/g, '').length, sha256: hash(content)});
      ref(scene.location, 'location', scene.id);
      for (const id of scene.participants ?? []) ref(id, 'character', scene.id);
      for (const id of scene.decision_ids ?? []) if (!decisions.has(id)) errors.push(scene.id + ': missing decision ' + id);
      if (!scene.decision_ids?.length) warnings.push(scene.id + ': explicit decision links absent');
    } catch (e) { errors.push(scene.id + ': ' + e.message); }
  }
  try {
    for (const file of files(root, config.manuscript_dir)) if (file.endsWith('.md') && !registered.has(file.toLowerCase())) errors.push('unregistered manuscript: ' + file);
  } catch (e) { errors.push(e.message); }
  for (const item of state.emotional_trajectory ?? []) if (!scenes.has(item.scene)) errors.push('emotion scene missing: ' + item.scene);
  return {passed: errors.length === 0, series_id: config.series_id, errors, warnings, counts,
    limitation: 'Structural checks only; psychological, temporal and causal truth still requires editorial review.'};
}
export function fingerprint(root) {
  const {config} = openSeries(root);
  const contextFiles = config.context_files ?? [];
  const optional = ['system/world.json','system/sources.json'].filter(name=>fs.existsSync(inside(root,name)));
  const names = [...new Set(['system/series.json', config.state, config.control, ...optional, ...contextFiles, ...files(root, config.manuscript_dir)])].sort();
  return hash(JSON.stringify(names.map(name => [name, hash(fs.readFileSync(inside(root, name)))])));
}
export function request(root, role, task) {
  const s = openSeries(root), report = validate(root);
  if (!report.passed) throw Error('validation failed: ' + report.errors.join('; '));
  if (!s.config.roles.includes(role)) throw Error('unknown role');
  if (role === 'character' && !s.state.cards.some(c=>c.id===s.config.pov_character)) throw Error('POV character not configured');
  if (role === 'writer' && !s.control.manuscript_generation_enabled) throw Error('manuscript generation paused');
  const views = s.state.cards.map(c => {
    if (role !== 'character') return c;
    // Character requests receive only their own explicit knowledge, never the author cards.
    return c.id === s.config.pov_character ? {id:c.id, name:c.name, knows:c.knows ?? []} : null;
  }).filter(Boolean);
  return {protocol: 1, request_id: crypto.randomUUID(), series_id: s.config.series_id, role, task,
    base: fingerprint(root), paused: !s.control.manuscript_generation_enabled,
    rules: ['Return proposal only; do not promote canon.', 'Unknown sources stay unknown.', 'Use only this series context.'],
    context: role === 'character' ? {current_scene:s.state.current_scene,cards:views} : {
      current_scene:s.state.current_scene,cards:views,
      chronicle:s.state.scene_log,emotional_trajectory:s.state.emotional_trajectory ?? [],
      literary_signature_log:s.state.literary_signature_log ?? [],decisions:s.state.change_log,
      next:s.state.next,
      references:(s.config.context_files ?? []).map(name=>({path:name,text:fs.readFileSync(inside(root,name),'utf8')})),
      world:fs.existsSync(inside(root,'system/world.json'))?read(inside(root,'system/world.json')):null
    },
    response_contract: {request_id:'same id', series_id:'same series', base:'same base', role:'same role', output:'non-empty text'}};
}
export function accept(root, req, result) {
  openSeries(root);
  for (const k of ['request_id','series_id','base','role']) if (result[k] !== req[k]) throw Error('response mismatch: ' + k);
  if (fingerprint(root) !== req.base) throw Error('stale response: series changed');
  const s = openSeries(root);
  if (req.series_id !== s.config.series_id || !s.config.roles.includes(req.role)) throw Error('wrong series/role');
  if (req.role === 'writer' && !s.control.manuscript_generation_enabled) throw Error('manuscript generation paused');
  if (typeof result.output !== 'string' || !result.output.trim()) throw Error('empty output');
  if (!/^[a-f0-9-]{36}$/.test(req.request_id)) throw Error('invalid request id');
  const file = inside(root, 'system/inbox/' + req.request_id + '.json');
  const record = {...result, status:'proposal', accepted_at:new Date().toISOString()};
  if (fs.existsSync(file)) {
    const old = read(file);
    if (old.output !== result.output || old.base !== result.base) throw Error('request id already used');
    return file;
  }
  atomic(file, record);
  return file;
}
export function worker(req, config) {
  if (!config || typeof config.command !== 'string' || !Array.isArray(config.args)) throw Error('worker command not configured');
  return new Promise((resolve, reject) => {
    const p = spawn(config.command, config.args, {shell:false, windowsHide:true, stdio:['pipe','pipe','pipe']});
    let out = '', size = 0, done = false;
    p.stdout.setEncoding('utf8');
    const finish = (err, result) => { if(done) return; done=true; clearTimeout(timer); if(err) {p.kill(); reject(err);} else resolve(result); };
    const timer = setTimeout(() => finish(Error('worker timeout')), config.timeout_ms ?? 60000);
    p.on('error', () => finish(Error('worker could not start')));
    p.stdin.on('error', () => finish(Error('worker input failed')));
    p.stdout.on('data', chunk => {size+=chunk.length; if(size>2_000_000) finish(Error('worker output too large')); else out+=chunk.toString();});
    p.stderr.on('data', () => {}); // Never persist API secrets or provider error bodies.
    p.on('close', code => {
      if (code !== 0) return finish(Error('worker failed with exit ' + code));
      try { finish(null, JSON.parse(out)); } catch { finish(Error('worker returned invalid JSON')); }
    });
    p.stdin.end(JSON.stringify(req));
  });
}
