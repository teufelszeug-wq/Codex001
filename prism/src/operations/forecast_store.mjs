import { randomUUID } from 'node:crypto';
import { link, mkdir, open, readFile, unlink } from 'node:fs/promises';
import { join } from 'node:path';
import { createPreRaceLedger, appendRevision, verifyForecastRecord } from './forecast_history.mjs';

const safeId = id => {
  if (typeof id !== 'string' || !/^[a-zA-Z0-9_-]{1,120}$/.test(id)) throw new Error('unsafe race_id');
  return id;
};
async function exclusiveWrite(path, record, beforePublish) {
  const temporary = path + '.' + randomUUID() + '.tmp';
  const file = await open(temporary, 'wx', 0o600);
  try {
    try {
      await file.writeFile(JSON.stringify(record, null, 2) + '\n', 'utf8');
      await file.sync();
    } finally {
      await file.close();
    }
    beforePublish?.();
    await link(temporary, path);
  } finally {
    await unlink(temporary);
  }
}
export async function persistInitialForecast(directory, input, beforePublish) {
  const record = createPreRaceLedger(input);
  const raceDir = join(directory, safeId(record.race_id));
  await mkdir(raceDir, { recursive:true });
  const path = join(raceDir, 'v1.json');
  await exclusiveWrite(path, record, beforePublish);
  return { record, path };
}
export async function persistRevision(directory, raceId, previousVersion, input, beforePublish) {
  if (!Number.isInteger(previousVersion) || previousVersion < 1) throw new Error('invalid previousVersion');
  const raceDir = join(directory, safeId(raceId));
  const previous = JSON.parse(await readFile(join(raceDir, 'v' + previousVersion + '.json'), 'utf8'));
  verifyForecastRecord(previous, raceId, previousVersion);
  const next = appendRevision(previous, input);
  const path = join(raceDir, 'v' + next.version + '.json');
  await exclusiveWrite(path, next, beforePublish);
  return { record:next, path };
}
export async function loadForecast(directory, raceId, version = 1) {
  if (!Number.isInteger(version) || version < 1) throw new Error('invalid version');
  return JSON.parse(await readFile(join(directory, safeId(raceId), 'v' + version + '.json'), 'utf8'));
}

function roundtablePath(directory, raceId, declarations) {
  return join(directory, safeId(raceId), declarations ? 'declarations-roundtable-v1.json' : 'roundtable-v1.json');
}

export async function loadRoundtable(directory, raceId, { declarations = false } = {}) {
  return JSON.parse(await readFile(roundtablePath(directory, raceId, declarations), 'utf8'));
}

export async function persistRoundtable(directory, raceId, roundtable, beforePublish, { declarations = false } = {}) {
  await exclusiveWrite(roundtablePath(directory, raceId, declarations), roundtable, beforePublish);
}

export async function loadDeclarations(directory, raceId) {
  return JSON.parse(await readFile(join(directory, safeId(raceId), 'declarations-v1.json'), 'utf8'));
}

export async function persistDeclarations(directory, raceId, declaration, beforePublish) {
  const raceDir = join(directory, safeId(raceId));
  await mkdir(raceDir, { recursive: true });
  await exclusiveWrite(join(raceDir, 'declarations-v1.json'), declaration, beforePublish);
}
