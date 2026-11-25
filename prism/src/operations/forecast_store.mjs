import { createHash, randomUUID } from 'node:crypto';
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

function declarationVersion(version) {
  if (!Number.isSafeInteger(version) || version < 1) throw new Error('invalid declaration version');
  return version;
}
function roundtablePath(directory, raceId, declarations, version = 1) {
  if (!declarations && version !== 1) throw new Error('numbered roundtable version must be 1');
  return join(directory, safeId(raceId), declarations ? `declarations-roundtable-v${declarationVersion(version)}.json` : 'roundtable-v1.json');
}

export async function loadRoundtable(directory, raceId, { declarations = false, version = 1 } = {}) {
  return JSON.parse(await readFile(roundtablePath(directory, raceId, declarations, version), 'utf8'));
}

export async function persistRoundtable(directory, raceId, roundtable, beforePublish, { declarations = false, version = 1 } = {}) {
  await exclusiveWrite(roundtablePath(directory, raceId, declarations, version), roundtable, beforePublish);
}

export async function loadDeclarations(directory, raceId, version = 1) {
  return JSON.parse(await readFile(join(directory, safeId(raceId), `declarations-v${declarationVersion(version)}.json`), 'utf8'));
}

export async function persistDeclarations(directory, raceId, declaration, beforePublish, version = 1) {
  const raceDir = join(directory, safeId(raceId));
  await mkdir(raceDir, { recursive: true });
  await exclusiveWrite(join(raceDir, `declarations-v${declarationVersion(version)}.json`), declaration, beforePublish);
}

function executionPath(directory, raceId, inputKey, forecasterId) {
  if (!/^[a-f0-9]{64}$/.test(inputKey)) throw new Error('invalid specialist input key');
  return join(directory, safeId(raceId), 'executions', inputKey, safeId(forecasterId) + '.json');
}

export async function loadSpecialistExecution(directory, raceId, inputKey, forecasterId) {
  const saved = JSON.parse(await readFile(executionPath(directory, raceId, inputKey, forecasterId), 'utf8'));
  const { content_sha256, ...payload } = saved;
  const actual = createHash('sha256').update(JSON.stringify(payload)).digest('hex');
  if (content_sha256 !== actual || payload.schema !== 'prism.specialist_execution/v1' ||
      payload.race_id !== raceId || payload.input_key !== inputKey ||
      payload.record?.forecaster_id !== forecasterId) {
    throw new Error('specialist execution identity or content hash mismatch');
  }
  return payload.record;
}

export async function persistSpecialistExecution(directory, raceId, inputKey, record, beforePublish) {
  const payload = { schema: 'prism.specialist_execution/v1', race_id: raceId, input_key: inputKey, record };
  const content_sha256 = createHash('sha256').update(JSON.stringify(payload)).digest('hex');
  const path = executionPath(directory, raceId, inputKey, record.forecaster_id);
  await mkdir(join(directory, safeId(raceId), 'executions', inputKey), { recursive: true });
  await exclusiveWrite(path, { ...payload, content_sha256 }, beforePublish);
}
