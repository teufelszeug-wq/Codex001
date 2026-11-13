import { createHash } from 'node:crypto';
import { normalizeOfficialRacecard } from './racecard_adapter.mjs';
import { loadForecast, persistInitialForecast, persistRevision } from './forecast_store.mjs';
import { METHODS, forecastSpecialist, loadForecastRoster, validateSupplementalEvidence } from './specialist_forecasts.mjs';

const iso = /^\d{4}-\d{2}-\d{2}T.*(?:Z|[+-]\d{2}:\d{2})$/;
const hash = value => createHash('sha256').update(JSON.stringify(value)).digest('hex');
const ticketName = { WIN: '単勝' };
const HISTORY_FIELDS = [
  'date', 'venue', 'race_name', 'surface', 'distance_m', 'going', 'finish', 'field_size',
  'jockey_name', 'carried_weight', 'rating', 'last_3f', 'first_call', 'fourth_corner',
];

function jstDay(timestamp) {
  return new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Tokyo', dateStyle: 'short' }).format(new Date(timestamp));
}

function verifyRacecard(raw) {
  const normalized = normalizeOfficialRacecard(raw);
  const url = new URL(normalized.official_url);
  const jra = raw.authority === 'JRA' && ['www.jra.go.jp', 'jra.go.jp'].includes(url.hostname) &&
    url.pathname === '/JRADB/accessD.html' && raw.source_verification === 'JRA_RACECARD_IDENTITY_MATCH';
  const nar = raw.authority === 'NAR' && url.hostname === 'www.keiba.go.jp' &&
    url.pathname === '/KeibaWeb/TodayRaceInfo/DebaTable' && raw.source_verification === 'NAR_RACECARD_IDENTITY_MATCH';
  if (raw.schema !== 'prism.official_racecard/v1' || raw.source_verified !== true ||
      !(jra || nar) || url.username || url.password || url.port ||
      !/^[a-f0-9]{64}$/.test(raw.source_sha256) || !iso.test(raw.off_at) || !iso.test(raw.captured_at) ||
      !raw.race_id.startsWith(raw.race_date?.replaceAll('-', '') + '-' + raw.authority + '-') ||
      raw.race_date !== jstDay(raw.off_at) ||
      !['TURF', 'DIRT', 'JUMP', 'BANEI'].includes(raw.course?.surface) ||
      !Number.isInteger(raw.course.distance_m) || raw.course.distance_m < 100 || raw.course.distance_m > 10000 ||
      typeof raw.venue !== 'string' || !raw.venue.trim()) {
    throw new Error('verified official forecast racecard required');
  }
  const facts = new Map(raw.runners.map(horse => [horse.horse_no, horse]));
  const active = normalized.active_runners.map(horse => {
    const source = facts.get(horse.horse_no);
    const history = (source.history ?? []).map(run => {
      if (!/^\d{4}-\d{2}-\d{2}$/.test(run.date) || run.date >= raw.race_date) {
        throw new Error('prior start is not before the target race date');
      }
      return Object.fromEntries(HISTORY_FIELDS.map(key => [key, run[key] ?? null]));
    }).sort((a, b) => b.date.localeCompare(a.date));
    if (!Number.isInteger(horse.frame_no) || horse.frame_no < 1 || horse.frame_no > 8) {
      throw new Error('official frame number required');
    }
    return {
      ...horse, history, horse_id: source.horse_id ?? null, carried_weight: source.carried_weight ?? null,
      official_rating: source.official_rating ?? null, win_odds: source.win_odds ?? null,
      pedigree: { sire: source.pedigree?.sire ?? null, damsire: source.pedigree?.damsire ?? null },
    };
  });
  return {
    ...normalized, active_runners: active, source_verified: true, source_sha256: raw.source_sha256,
    race_date: raw.race_date, venue: raw.venue, race_no: raw.race_no,
    course: { surface: raw.course.surface, distance_m: raw.course.distance_m, direction: raw.course.direction ?? null },
  };
}

function validateRoster(roster) {
  if (roster.facilitator?.id !== 'PRISM-EDITOR-01' || !Array.isArray(roster.forecasters)) {
    throw new Error('forecast roster and facilitator required');
  }
  const ids = new Set(roster.forecasters.map(agent => agent.id));
  const methods = new Set(roster.forecasters.map(agent => agent.method));
  if (ids.size !== METHODS.size || methods.size !== METHODS.size || roster.forecasters.length !== METHODS.size ||
      ids.has(roster.facilitator.id) || !ids.has('HONSHI') || !ids.has('RIO-REPORTER-01') ||
      !roster.forecasters.every(agent => METHODS.has(agent.method) && agent.id && agent.name && agent.specialty)) {
    throw new Error('incomplete forecast roster');
  }
}

function verifyStoredVersion(record, raceId, version) {
  const { content_sha256: contentHash, ...payload } = record;
  if (payload.race_id !== raceId || payload.version !== version || hash(payload) !== contentHash) {
    throw new Error('stored forecast identity or content hash mismatch');
  }
  return record;
}

function latestVersion(initial, final) {
  if (final.previous_sha256 !== initial.content_sha256 || final.metadata?.phase !== 'FINAL' ||
      final.metadata.input_sha256 !== initial.metadata.input_sha256) {
    throw new Error('existing final version does not match the preliminary forecast');
  }
  return { initial, final };
}

function topicRows(records, methods) {
  return records.filter(record => methods.includes(record.execution.method)).map(record => {
    const top = record.picks[0];
    const diagnosis = record.diagnoses.find(row => row.horse_no === top?.horse_no);
    return {
      forecaster_id: record.forecaster_id, execution_id: record.execution_id,
      top_pick: top ?? null, reason: diagnosis?.reason ?? record.skip_reason,
    };
  });
}

function comparePreliminary(card, roster, initial) {
  const records = initial.records;
  const supported = new Map();
  for (const record of records) {
    const top = record.picks[0];
    if (top) supported.set(top.horse_no, (supported.get(top.horse_no) ?? 0) + 1);
  }
  const disagreement = [...supported].sort((a, b) => b[1] - a[1]).map(([number, count]) => ({
    horse_no: number, horse_name: card.active_runners.find(horse => horse.horse_no === number).horse_name, count,
  }));
  return {
    type: 'structured_forecast_review',
    facilitator: roster.facilitator,
    initial_sha256: initial.content_sha256,
    topics: [
      {
        id: 'DIAGNOSIS', title: '全頭診断',
        findings: records.find(record => record.forecaster_id === 'HONSHI').diagnoses.map(row =>
          ({ horse_no: row.horse_no, horse_name: row.horse_name, mark: row.mark, reason: row.reason })),
      },
      {
        id: 'COURSE', title: 'コース・馬場・展開', course: card.course,
        findings: topicRows(records, ['course', 'pace', 'position', 'track_bias', 'weather']),
      },
      {
        id: 'INFORMATION', title: '情報・状態・取材',
        findings: topicRows(records, ['video', 'stable', 'pedigree', 'jockey', 'ability', 'sectional', 'workout', 'state', 'learning']),
      },
      {
        id: 'CASE', title: '本命の比較と反証', nominations: disagreement,
        findings: records.filter(record => record.picks.length).map(record => ({
          forecaster_id: record.forecaster_id, execution_id: record.execution_id, pick: record.picks[0],
          counterpoints: records.filter(other => other.picks.length && other.picks[0].horse_no !== record.picks[0].horse_no)
            .map(other => ({ forecaster_id: other.forecaster_id, pick: other.picks[0] })),
        })),
      },
      {
        id: 'BETS', title: '100円買い目と見送り',
        findings: records.map(record => ({
          forecaster_id: record.forecaster_id, tickets: record.tickets.map(ticket => ({
            ...ticket, label: ticketName[ticket.type],
          })), skip_reason: record.skip_reason,
        })),
      },
    ],
  };
}

function checkRecords(records, card, roster, initial = null) {
  if (records.length !== roster.forecasters.length) throw new Error('forecast roster coverage mismatch');
  const executions = new Set(initial?.records.map(record => record.execution_id));
  const responses = new Set(initial?.records.map(record => record.execution.response_id).filter(Boolean));
  for (const record of records) {
    const run = record.execution;
    if (executions.has(record.execution_id) || !record.execution_id ||
        !iso.test(run.started_at) || !iso.test(run.finished_at) ||
        Date.parse(run.started_at) < Date.parse(card.captured_at) ||
        Date.parse(run.finished_at) < Date.parse(run.started_at) ||
        Date.parse(run.finished_at) >= Date.parse(card.off_at) ||
        (initial && Date.parse(run.started_at) < Date.parse(initial.saved_at)) ||
        (!record.tickets.length && !record.skip_reason) ||
        record.tickets.some(ticket => ticket.stake_yen !== 100)) {
      throw new Error(`invalid specialist execution or output: ${record.forecaster_id}`);
    }
    executions.add(record.execution_id);
    if (run.response_id) {
      if (responses.has(run.response_id)) throw new Error('duplicate model response ID');
      responses.add(run.response_id);
    }
  }
}

async function readVersion(directory, raceId, version) {
  try {
    return verifyStoredVersion(await loadForecast(directory, raceId, version), raceId, version);
  } catch (error) {
    if (error.code !== 'ENOENT') throw error;
    return null;
  }
}

export async function runForecastPanel({
  rawRacecard, directory, evidence = [], model, modelIdentity = 'local_rules',
  now = () => new Date().toISOString(),
}) {
  const card = verifyRacecard(rawRacecard);
  if (Boolean(model) === (modelIdentity === 'local_rules')) throw new Error('model and model identity must agree');
  const roster = await loadForecastRoster();
  validateRoster(roster);
  const inputHash = hash({ card, evidence, roster, modelIdentity });
  const runnerList = card.active_runners.map(({ horse_no, horse_name, frame_no, jockey_name }) =>
    ({ horse_no, horse_name, frame_no, jockey_name }));
  const checkClock = () => {
    const timestamp = now();
    if (!iso.test(timestamp) || !Number.isFinite(Date.parse(timestamp)) ||
        Date.parse(timestamp) < Date.parse(card.captured_at) ||
        Date.parse(timestamp) >= Date.parse(card.off_at)) {
      throw new Error('forecast clock is outside the pre-race window');
    }
    return timestamp;
  };
  const run = async (phase, review, initial) => {
    const results = await Promise.allSettled(roster.forecasters.map(async agent => ({
      forecaster_id: agent.id,
      ...await forecastSpecialist({
        agent, card, evidence, now: checkClock, phase, review, model,
        initial: initial?.records.find(record => record.forecaster_id === agent.id) ?? null,
      }),
    })));
    const errors = results.flatMap((result, index) => result.status === 'rejected'
      ? [`${roster.forecasters[index].id}: ${result.reason.message}`] : []);
    if (errors.length) throw new Error(errors.join('\n'));
    const records = results.map(result => result.value);
    checkRecords(records, card, roster, initial);
    return records;
  };

  let initial = await readVersion(directory, card.race_id, 1);
  validateSupplementalEvidence(evidence, card, initial?.saved_at ?? checkClock());
  if (!initial) {
    const records = await run('PRELIMINARY');
    const input = {
      race_id: card.race_id, race_name: card.race_name, off_at: card.off_at, runners: runnerList,
      records, saved_at: checkClock(),
      source_refs: [...new Set([card.official_url, ...evidence.map(row => row.source_url)])],
      metadata: {
        phase: 'PRELIMINARY', input_sha256: inputHash, source_sha256: card.source_sha256,
        captured_at: card.captured_at, source_verification: rawRacecard.source_verification,
        model_backend: modelIdentity, entry_status: card.runners,
      },
    };
    try {
      ({ record: initial } = await persistInitialForecast(directory, input, checkClock));
    } catch (error) {
      if (error.code !== 'EEXIST') throw error;
      initial = await readVersion(directory, card.race_id, 1);
    }
  }
  if (initial.metadata?.phase !== 'PRELIMINARY' || initial.metadata.input_sha256 !== inputHash) {
    throw new Error('initial forecast already exists with different inputs; use the original card and model to resume');
  }
  const existing = await readVersion(directory, card.race_id, 2);
  if (existing) return latestVersion(initial, existing);

  checkClock();
  const review = comparePreliminary(card, roster, initial);
  const reviewedAt = checkClock();
  const records = await run('FINAL', review, initial);
  let savedAt = checkClock();
  if (Date.parse(savedAt) <= Date.parse(initial.saved_at)) {
    await new Promise(resolve => setTimeout(resolve, 2));
    savedAt = checkClock();
  }
  const metadata = {
    phase: 'FINAL', input_sha256: inputHash, model_backend: modelIdentity,
    publication_window: jstDay(savedAt) < card.race_date ? 'PRE_DAY' : 'RACE_DAY_PRE',
    review: { ...review, reviewed_at: reviewedAt },
  };
  try {
    const { record: final } = await persistRevision(directory, card.race_id, 1,
      { records, saved_at: savedAt, metadata }, checkClock);
    return { initial, final };
  } catch (error) {
    if (error.code !== 'EEXIST') throw error;
    const final = await readVersion(directory, card.race_id, 2);
    return latestVersion(initial, final);
  }
}
