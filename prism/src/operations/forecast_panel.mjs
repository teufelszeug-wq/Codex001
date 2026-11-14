import { createHash } from 'node:crypto';
import { verifyForecastRecord } from './forecast_history.mjs';
import { normalizeOfficialRacecard } from './racecard_adapter.mjs';
import { loadDeclarations, loadForecast, loadRoundtable, persistDeclarations, persistInitialForecast,
  persistRevision, persistRoundtable } from './forecast_store.mjs';
import { buildRoundtable, compareFinalForecasts, runnerKey, validateRoundtable } from './roundtable.mjs';
import { METHODS, forecastSpecialist, loadForecastRoster, restoreSupplementalEvidence,
  validateSupplementalEvidence } from './specialist_forecasts.mjs';

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
  const declarations = raw.entry_stage === 'DECLARATIONS';
  const inputRunners = declarations ? raw.runners.map((horse, index) => ({ ...horse, horse_no: index + 1 })) : raw.runners;
  const normalized = normalizeOfficialRacecard({ ...raw, runners: inputRunners });
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
  if (declarations && (!jra || !raw.runners.every(horse => horse.horse_no === null && horse.frame_no === null &&
      /^\d{10}$/.test(horse.horse_id)) || new Set(raw.runners.map(horse => horse.horse_id)).size !== raw.runners.length)) {
    throw new Error('unframed declarations require distinct official horse IDs and empty frame/horse numbers');
  }
  const facts = new Map(inputRunners.map(horse => [horse.horse_no, horse]));
  const active = normalized.active_runners.map(horse => {
    const source = facts.get(horse.horse_no);
    const history = (source.history ?? []).map(run => {
      if (!/^\d{4}-\d{2}-\d{2}$/.test(run.date) || run.date >= raw.race_date) {
        throw new Error('prior start is not before the target race date');
      }
      return Object.fromEntries(HISTORY_FIELDS.map(key => [key, run[key] ?? null]));
    }).sort((a, b) => b.date.localeCompare(a.date));
    if (!declarations && (!Number.isInteger(horse.frame_no) || horse.frame_no < 1 || horse.frame_no > 8)) {
      throw new Error('official frame number required');
    }
    return {
      ...horse, history, horse_id: source.horse_id ?? null, carried_weight: source.carried_weight ?? null,
      official_rating: source.official_rating ?? null, win_odds: source.win_odds ?? null,
      ...(Number.isInteger(source.body_weight) ? { body_weight: source.body_weight } : {}),
      pedigree: { sire: source.pedigree?.sire ?? null, damsire: source.pedigree?.damsire ?? null },
    };
  });
  return {
    ...normalized, active_runners: active, source_verified: true, source_sha256: raw.source_sha256,
    race_date: raw.race_date, venue: raw.venue, race_no: raw.race_no,
    course: { surface: raw.course.surface, distance_m: raw.course.distance_m, direction: raw.course.direction ?? null },
    ...(declarations ? { entry_stage: 'DECLARATIONS' } : {}),
    ...(typeof raw.track_condition === 'string' ? { track_condition: raw.track_condition } : {}),
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

export function verifyDeclarations(record, raceId) {
  const { content_sha256: contentHash, ...payload } = record;
  if (payload.schema !== 'prism.forecast_declarations/v1' || payload.race_id !== raceId ||
      hash(payload) !== contentHash) {
    throw new Error('stored declarations identity or content hash mismatch');
  }
  return record;
}

function declarationRecord({ card, records, savedAt, inputHash, modelIdentity }) {
  const horses = new Map(card.active_runners.map(horse => [horse.horse_no, horse]));
  function identity({ horse_no, ...row }) {
    return { ...row, horse_id: horses.get(horse_no).horse_id, horse_no: null };
  }
  const payload = {
    schema: 'prism.forecast_declarations/v1', race_id: card.race_id, race_name: card.race_name,
    off_at: card.off_at, saved_at: savedAt, source_refs: [card.official_url], source_sha256: card.source_sha256,
    captured_at: card.captured_at, input_sha256: inputHash, model_backend: modelIdentity, course: card.course,
    runners: card.active_runners.map(({ horse_no, history, ...horse }) => ({ ...horse, horse_no: null })),
    records: records.map(record => ({
      ...record, diagnoses: record.diagnoses.map(identity), picks: record.picks.map(identity), tickets: [],
      stake_yen: 0, skip_reason: record.skip_reason ?? '枠順・馬番の公表後に買い目を確定します。',
    })),
  };
  return { ...payload, content_sha256: hash(payload) };
}

function latestVersion(initial, final, roundtable) {
  if (final.previous_sha256 !== initial.content_sha256 || final.metadata?.phase !== 'FINAL' ||
      final.metadata.input_sha256 !== initial.metadata.input_sha256) {
    throw new Error('existing final version does not match the preliminary forecast');
  }
  if (final.metadata.roundtable_sha256 &&
      (!roundtable || hash(roundtable) !== final.metadata.roundtable_sha256 ||
       Date.parse(roundtable.recorded_at) > Date.parse(final.saved_at))) {
    throw new Error('stored roundtable does not match the final forecast');
  }
  return { initial, final, roundtable };
}

function topicRows(records, methods) {
  return records.filter(record => methods.includes(record.execution.method)).map(record => {
    const top = record.picks[0];
    const diagnosis = record.diagnoses.find(row => runnerKey(row) === runnerKey(top));
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
    const identity = runnerKey(top);
    if (top) supported.set(identity, (supported.get(identity) ?? 0) + 1);
  }
  const disagreement = [...supported].sort((a, b) => b[1] - a[1]).map(([identity, count]) => {
    const horse = initial.runners.find(horse => runnerKey(horse) === identity);
    return { horse_no: horse.horse_no, horse_name: horse.horse_name, count,
      ...(horse.horse_no === null ? { horse_id: horse.horse_id } : {}) };
  });
  return {
    type: 'structured_forecast_review',
    facilitator: roster.facilitator,
    initial_sha256: initial.content_sha256,
    ...(card.track_condition ? { track_condition: card.track_condition } : {}),
    topics: [
      {
        id: 'DIAGNOSIS', title: '全頭診断',
        findings: records.find(record => record.forecaster_id === 'HONSHI').diagnoses.map(row =>
          ({ horse_no: row.horse_no, horse_name: row.horse_name, mark: row.mark, reason: row.reason,
            ...(row.horse_no === null ? { horse_id: row.horse_id } : {}) })),
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
          counterpoints: records.filter(other => other.picks.length && runnerKey(other.picks[0]) !== runnerKey(record.picks[0]))
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

async function readIfPresent(load) {
  try {
    return await load();
  } catch (error) {
    if (error.code !== 'ENOENT') throw error;
    return null;
  }
}

async function readVersion(directory, raceId, version) {
  const record = await readIfPresent(() => loadForecast(directory, raceId, version));
  return record ? verifyForecastRecord(record, raceId, version) : null;
}

export async function runForecastPanel({
  rawRacecard, directory, evidence = [], model, modelIdentity = 'local_rules', updateFrom,
  now = () => new Date().toISOString(),
}) {
  const card = verifyRacecard(rawRacecard);
  const declarations = card.entry_stage === 'DECLARATIONS';
  if (!Array.isArray(evidence)) throw new Error('supplemental evidence must be an array');
  if (declarations && (evidence.length || model || updateFrom !== undefined)) {
    throw new Error('unframed declarations use local scoring from the official card; use numbered inputs for evidence and model calls');
  }
  if (Boolean(model) === (modelIdentity === 'local_rules')) throw new Error('model and model identity must agree');
  const roster = await loadForecastRoster();
  validateRoster(roster);
  const inputHash = hash({ card, evidence, roster, modelIdentity });
  const runnerList = card.active_runners.map(({ horse_no, horse_name, frame_no, jockey_name, horse_id }) =>
    ({ horse_no, horse_name, frame_no, jockey_name, ...(horse_id ? { horse_id } : {}) }));
  const checkClock = () => {
    const timestamp = now();
    if (!iso.test(timestamp) || !Number.isFinite(Date.parse(timestamp)) ||
        Date.parse(timestamp) < Date.parse(card.captured_at) ||
        Date.parse(timestamp) >= Date.parse(card.off_at)) {
      throw new Error('forecast clock is outside the pre-race window');
    }
    return timestamp;
  };
  const run = async (phase, review, initial, facts = evidence) => {
    const results = await Promise.allSettled(roster.forecasters.map(async agent => ({
      forecaster_id: agent.id,
      ...await forecastSpecialist({
        agent, card, evidence: facts, now: checkClock, phase, review, model,
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

  const loadEarly = async () => {
    const saved = await readIfPresent(() => loadDeclarations(directory, card.race_id));
    return saved && verifyDeclarations(saved, card.race_id);
  };
  if (declarations) {
    const readEarlyDiscussion = async saved => {
      const dialogue = await readIfPresent(() => loadRoundtable(directory, card.race_id, { declarations: true }));
      return dialogue && validateRoundtable(dialogue, saved, roster);
    };
    let saved = await loadEarly();
    if (!saved) {
      if (await readVersion(directory, card.race_id, 1)) throw new Error('numbered forecast is already saved');
      checkClock();
      const records = await run('DECLARATIONS');
      saved = declarationRecord({ card, records, savedAt: checkClock(), inputHash, modelIdentity });
      try {
        await persistDeclarations(directory, card.race_id, saved, checkClock);
      } catch (error) {
        if (error.code !== 'EEXIST') throw error;
        saved = await loadEarly();
      }
    }
    if (saved.input_sha256 !== inputHash) throw new Error('declaration forecast already saved with different inputs');
    let discussion = await readEarlyDiscussion(saved);
    if (!discussion) {
      discussion = validateRoundtable(buildRoundtable({
        initial: saved, comparison: comparePreliminary(card, roster, saved), roster, now: checkClock,
      }), saved, roster);
      try {
        await persistRoundtable(directory, card.race_id, discussion, checkClock, { declarations: true });
      } catch (error) {
        if (error.code !== 'EEXIST') throw error;
        discussion = await readEarlyDiscussion(saved);
      }
    }
    return { declarations: saved, roundtable: discussion };
  }

  if (updateFrom !== undefined) {
    return updateForecast({
      card, directory, evidence, modelIdentity, inputHash, checkClock, run, runnerList, updateFrom,
    });
  }

  let initial = await readVersion(directory, card.race_id, 1);
  validateSupplementalEvidence(evidence, card, initial?.saved_at ?? checkClock());
  if (!initial) {
    const early = await loadEarly();
    if (early && Date.parse(early.saved_at) > Date.parse(card.captured_at)) {
      throw new Error('numbered card predates the saved declarations forecast');
    }
    const earlyDialogue = early && await readIfPresent(() => loadRoundtable(directory, card.race_id, { declarations: true }));
    if (earlyDialogue) validateRoundtable(earlyDialogue, early, roster);
    const records = await run('PRELIMINARY');
    const input = {
      race_id: card.race_id, race_name: card.race_name, off_at: card.off_at, runners: runnerList,
      records, saved_at: checkClock(),
      source_refs: [...new Set([card.official_url, ...evidence.map(row => row.source_url)])],
      metadata: {
        phase: 'PRELIMINARY', input_sha256: inputHash, source_sha256: card.source_sha256,
        captured_at: card.captured_at, source_verification: rawRacecard.source_verification,
        model_backend: modelIdentity, entry_status: card.runners,
        ...(early ? { declarations_sha256: early.content_sha256 } : {}),
        ...(earlyDialogue ? { declarations_roundtable_sha256: hash(earlyDialogue) } : {}),
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
  const readRoundtable = async () => {
    const saved = await readIfPresent(() => loadRoundtable(directory, card.race_id));
    return saved && validateRoundtable(saved, initial, roster);
  };
  let roundtable = await readRoundtable();
  const existing = await readVersion(directory, card.race_id, 2);
  if (existing) return latestVersion(initial, existing, roundtable);

  checkClock();
  const review = comparePreliminary(card, roster, initial);
  if (!roundtable) {
    roundtable = validateRoundtable(buildRoundtable({
      initial, comparison: review, roster, now: checkClock,
    }), initial, roster);
    try {
      await persistRoundtable(directory, card.race_id, roundtable, checkClock);
    } catch (error) {
      if (error.code !== 'EEXIST') throw error;
      roundtable = await readRoundtable();
    }
  }
  if (Date.parse(checkClock()) < Date.parse(roundtable.recorded_at)) {
    throw new Error('roundtable timestamp is later than final forecast execution');
  }
  const records = await run('FINAL', { ...review, roundtable }, initial);
  let savedAt = checkClock();
  if (Date.parse(savedAt) <= Date.parse(initial.saved_at)) {
    await new Promise(resolve => setTimeout(resolve, 2));
    savedAt = checkClock();
  }
  const metadata = {
    phase: 'FINAL', input_sha256: inputHash, model_backend: modelIdentity,
    publication_window: jstDay(savedAt) < card.race_date ? 'PRE_DAY' : 'RACE_DAY_PRE',
    review: { ...review, reviewed_at: roundtable.recorded_at },
    roundtable_sha256: hash(roundtable),
    post_roundtable: compareFinalForecasts(initial, records),
    captured_at: card.captured_at, source_sha256: card.source_sha256, supplemental_evidence: evidence,
    win_odds: fieldValues(card, 'win_odds'), body_weights: fieldValues(card, 'body_weight'),
    track_condition: card.track_condition ?? null,
  };
  try {
    const { record: final } = await persistRevision(directory, card.race_id, 1,
      { records, saved_at: savedAt, metadata }, checkClock);
    return latestVersion(initial, final, roundtable);
  } catch (error) {
    if (error.code !== 'EEXIST') throw error;
    const final = await readVersion(directory, card.race_id, 2);
    return latestVersion(initial, final, roundtable);
  }
}

function latestRaceEdition(edition, roundtable) {
  if (edition.metadata.roundtable_sha256 &&
      (!roundtable || hash(roundtable) !== edition.metadata.roundtable_sha256)) {
    throw new Error('latest forecast does not match the saved roundtable');
  }
}

function fieldValues(card, field) {
  return Object.fromEntries(card.active_runners.map(horse => [horse.horse_no, horse[field] ?? null]));
}

function changedValues(runners, before, after) {
  if (!before) return null;
  return runners.flatMap(({ horse_no }) => before[horse_no] === after[horse_no] ? []
    : [{ horse_no, from: before[horse_no] ?? null, to: after[horse_no] }]);
}

async function updateForecast({ card, directory, evidence, modelIdentity, inputHash, checkClock,
  run, runnerList, updateFrom }) {
  if (!Number.isInteger(updateFrom) || updateFrom < 2) throw new Error('update requires a final forecast version');
  const previous = await readVersion(directory, card.race_id, updateFrom);
  if (!previous || !['FINAL', 'UPDATE'].includes(previous.metadata?.phase)) throw new Error('final forecast version required');
  const original = await readVersion(directory, card.race_id, 2);
  if (!original || original.metadata?.phase !== 'FINAL') throw new Error('original final forecast required');
  if (updateFrom > 2 && previous.metadata.original_final_sha256 !== original.content_sha256) {
    throw new Error('forecast update does not match the original final forecast');
  }
  let roundtable = null;
  if (original.metadata.roundtable_sha256) {
    roundtable = await loadRoundtable(directory, card.race_id);
    latestRaceEdition(original, roundtable);
  }
  const existing = await readVersion(directory, card.race_id, updateFrom + 1);
  if (existing) {
    if (existing.previous_sha256 !== previous.content_sha256 || existing.metadata?.input_sha256 !== inputHash) {
      throw new Error('this forecast revision already exists with different inputs');
    }
    return { final: existing, roundtable };
  }
  const capturedAt = Date.parse(card.captured_at);
  if (previous.metadata.model_backend !== modelIdentity ||
      capturedAt <= Date.parse(previous.metadata.captured_at ?? previous.saved_at) ||
      capturedAt < Date.parse(previous.saved_at) ||
      capturedAt >= Date.parse(previous.off_at) ||
      jstDay(card.captured_at) !== card.race_date) {
    throw new Error('same forecasting backend and a new race-day capture are required');
  }
  const previousNumbers = new Map(previous.runners.map(horse => [horse.horse_no, horse]));
  const newNumbers = new Map(card.runners.map(horse => [horse.horse_no, horse]));
  const active = new Set(runnerList.map(horse => horse.horse_no));
  const activeRows = new Map(card.active_runners.map(horse => [horse.horse_no, horse]));
  if (previous.race_name !== card.race_name || [...previousNumbers].some(([number, horse]) => {
    const incoming = newNumbers.get(number);
    return !incoming || incoming.horse_name !== horse.horse_name || incoming.frame_no !== horse.frame_no ||
      (horse.horse_id && active.has(number) && activeRows.get(number).horse_id !== horse.horse_id);
  }) || runnerList.some(horse => !previousNumbers.has(horse.horse_no))) {
    throw new Error('race-day update changed the identity of the numbered field');
  }
  const previousEvidence = previous.metadata.supplemental_evidence ??
    restoreSupplementalEvidence(await readVersion(directory, card.race_id, 1));
  const mergedEvidence = new Map(previousEvidence.filter(row => active.has(row.horse_no))
    .map(row => [`${row.method}:${row.horse_no}`, row]));
  validateSupplementalEvidence(evidence, card, checkClock());
  for (const row of evidence) {
    const key = `${row.method}:${row.horse_no}`;
    const old = mergedEvidence.get(key);
    if (old && Date.parse(row.available_at) < Date.parse(old.available_at)) {
      throw new Error(`older evidence cannot replace ${key}`);
    }
    mergedEvidence.set(key, row);
  }
  const facts = [...mergedEvidence.values()];
  validateSupplementalEvidence(facts, card, checkClock());
  const records = await run('UPDATE', null, previous, facts);
  const winOdds = fieldValues(card, 'win_odds');
  const bodyWeights = fieldValues(card, 'body_weight');
  const trackCondition = card.track_condition ?? null;
  const metadata = {
    ...previous.metadata, phase: 'UPDATE', publication_window: 'RACE_DAY_PRE', input_sha256: inputHash,
    captured_at: card.captured_at, source_sha256: card.source_sha256,
    original_final_sha256: original.content_sha256, supplemental_evidence: facts, entry_status: card.runners,
    win_odds: winOdds, body_weights: bodyWeights, track_condition: trackCondition,
    changes: {
      scratched: [...previousNumbers].flatMap(([number]) => !active.has(number) ? [number] : []),
      jockey: runnerList.filter(horse => horse.jockey_name !== previousNumbers.get(horse.horse_no).jockey_name)
        .map(horse => ({ horse_no: horse.horse_no, from: previousNumbers.get(horse.horse_no).jockey_name, to: horse.jockey_name })),
      added_evidence: evidence.length,
      odds: changedValues(runnerList, previous.metadata.win_odds, winOdds),
      body_weight: changedValues(runnerList, previous.metadata.body_weights, bodyWeights),
      track_condition: (previous.metadata.track_condition ?? null) === trackCondition ? null
        : { from: previous.metadata.track_condition ?? null, to: trackCondition },
      picks: records.map(record => {
        const old = previous.records.find(row => row.forecaster_id === record.forecaster_id);
        return { forecaster_id: record.forecaster_id, from: old.picks[0] ?? null, to: record.picks[0] ?? null };
      }).filter(change => hash(change.from) !== hash(change.to)),
    },
  };
  const savedAt = checkClock();
  const input = {
    records, saved_at: savedAt, off_at: card.off_at, runners: runnerList, metadata,
    source_refs: [...new Set([...previous.source_refs, card.official_url, ...facts.map(row => row.source_url)])],
  };
  try {
    const { record } = await persistRevision(directory, card.race_id, updateFrom, input, checkClock);
    return { final: record, roundtable };
  } catch (error) {
    if (error.code !== 'EEXIST') throw error;
    const saved = await readVersion(directory, card.race_id, updateFrom + 1);
    if (saved.previous_sha256 !== previous.content_sha256 || saved.metadata.input_sha256 !== inputHash) throw error;
    return { final: saved, roundtable };
  }
}
