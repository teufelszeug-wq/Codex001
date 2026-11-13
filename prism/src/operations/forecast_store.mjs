import { randomUUID } from 'node:crypto';
import { link, mkdir, open, readFile, unlink } from 'node:fs/promises';
import { join } from 'node:path';
import { createPreRaceLedger, appendRevision } from './forecast_history.mjs';

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
  if (previous.race_id !== raceId || previous.version !== previousVersion) throw new Error('history version mismatch');
  const next = appendRevision(previous, input);
  const path = join(raceDir, 'v' + next.version + '.json');
  await exclusiveWrite(path, next, beforePublish);
  return { record:next, path };
}
export async function loadForecast(directory, raceId, version = 1) {
  if (!Number.isInteger(version) || version < 1) throw new Error('invalid version');
  return JSON.parse(await readFile(join(directory, safeId(raceId), 'v' + version + '.json'), 'utf8'));
}
