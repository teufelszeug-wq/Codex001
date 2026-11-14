import { mkdir, open, readFile, link, unlink, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { randomUUID, createHash } from 'node:crypto';

// Immutable filesystem edition store: hard-link publication never overwrites an existing edition.
export function createEditionWriter(directory) {
  return async function writeAtomic(records) {
    if (!Array.isArray(records) || !records.length) throw new Error('empty_edition');
    const first = records[0];
    const key = [first.race_id, first.version, first.record_type];
    if (key.some(v => typeof v !== 'string' || !/^[\w.-]{1,100}$/.test(v))) throw new Error('invalid_edition_key');
    const filename = key.join('__') + '.json';
    const path = join(directory, filename);
    await mkdir(directory, { recursive: true });
    const data = JSON.stringify({ schema_version: 1, records }, null, 2) + '\n';
    const digest = createHash('sha256').update(data).digest('hex');
    const temp = join(directory, '.' + randomUUID() + '.tmp');
    let handle;
    try {
      handle = await open(temp, 'wx', 0o600);
      await handle.writeFile(data);
      await handle.sync();
      await handle.close(); handle = undefined;
      await link(temp, path);
      await unlink(temp);
      const dir = await open(directory, 'r');
      try { await dir.sync(); } finally { await dir.close(); }
      return { id: filename, sha256: digest, path };
    } finally {
      if (handle) await handle.close();
      await rm(temp, { force: true });
    }
  };
}
export async function readEdition(path) {
  const raw = await readFile(path);
  const document = JSON.parse(raw.toString('utf8'));
  return { document, sha256: createHash('sha256').update(raw).digest('hex') };
}
