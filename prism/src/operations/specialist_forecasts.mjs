import { randomUUID } from 'node:crypto';
import { readFile } from 'node:fs/promises';

const DAY_MS = 86_400_000;
const MARKS = ['◎', '○', '▲', '△', '☆'];
const SUPPLEMENTAL = {
  video: '映像・不利の確認記録',
  stable: '厩舎取材・陣営コメントの評価',
  pedigree: '血統の距離・馬場適性評価',
  track_bias: '当該開催の馬場バイアスと各馬の適性評価',
  weather: '予報・含水率の観測と各馬の馬場適性評価',
  workout: '追い切り・調教の評価',
  learning: '時系列検証済みの成長・改善評価',
};
const REQUIRED_EVIDENCE = new Set(['video', 'stable', 'track_bias', 'weather', 'workout', 'learning']);
export const METHODS = new Set([
  'editorial', 'reporter', 'statistics', 'ability', 'course', 'jockey', 'pace',
  'position', 'sectional', 'state', 'value', 'longshot', ...Object.keys(SUPPLEMENTAL),
]);

export async function loadForecastRoster() {
  return JSON.parse(await readFile(new URL('../../data/operations/forecast_roster.json', import.meta.url), 'utf8'));
}

function average(values) {
  return values.length ? values.reduce((a, b) => a + b, 0) / values.length : null;
}

function round(value) {
  return Number(value.toFixed(4));
}

function metric(score, reason, source) {
  return { score, reason, source };
}

function formValue(run) {
  if (!Number.isInteger(run.finish) || !Number.isInteger(run.field_size) ||
      run.finish < 1 || run.finish > run.field_size || run.field_size < 2) return null;
  return 100 * (run.field_size - run.finish) / (run.field_size - 1);
}

function averageForm(history) {
  return average(history.map(formValue).filter(Number.isFinite));
}

function withinDistance(history, distance) {
  return history.filter(run => Number.isFinite(run.distance_m) && Math.abs(run.distance_m - distance) <= 200);
}

function combine(...terms) {
  const available = terms.filter(([score]) => Number.isFinite(score));
  return available.length
    ? available.reduce((sum, [score, weight]) => sum + score * weight, 0) /
      available.reduce((sum, [, weight]) => sum + weight, 0)
    : null;
}

function horseFacts(card, horse) {
  const history = (horse.history ?? []).filter(run => run.surface === card.course.surface);
  const nearby = withinDistance(history, card.course.distance_m);
  const courseHistory = nearby.filter(run => run.venue === card.venue);
  const ratings = history.map(run => run.rating).filter(Number.isFinite);
  const officialRating = Number.isFinite(horse.official_rating) ? horse.official_rating : average(ratings);
  return {
    history, nearby, courseHistory, officialRating, ratings,
    form: averageForm(history.slice(0, 3)),
    courseForm: averageForm(courseHistory),
    distanceForm: averageForm(nearby),
    ratingScore: officialRating === null ? null : Math.max(0, Math.min(100, 2 * (officialRating - 75))),
  };
}

function fieldContext(card, method) {
  const facts = card.active_runners.map(horse => horseFacts(card, horse));
  if (method === 'pace') {
    const leaders = facts.filter(fact => fact.history.slice(0, 3).some(run => run.first_call === 1)).length;
    const paceCoverage = facts.filter(fact => fact.history.some(run => Number.isInteger(run.first_call))).length;
    return { facts, leaders, paceCoverage };
  }
  if (method !== 'value') return { facts };
  const odds = card.active_runners.map(horse => horse.win_odds);
  const scores = facts.map(fact => combine([fact.ratingScore, 7], [fact.form, 3]));
  const completeMarket = odds.every(value => Number.isFinite(value) && value > 1);
  const mass = scores.every(Number.isFinite) ? scores.map(score => Math.exp((score - 75) / 12)) : [];
  const totalMass = mass.reduce((total, value) => total + value, 0);
  return { facts, probabilities: completeMarket ? mass.map(value => value / totalMass) : [] };
}

function describe(value) {
  return value === null ? '資料なし' : value.toFixed(1);
}

function positionScore(history, key) {
  const runs = history.filter(run => Number.isInteger(run[key]) && run[key] >= 1 && run[key] <= run.field_size && run.field_size > 1);
  return average(runs.map(run => 100 * (run.field_size - run[key]) / (run.field_size - 1)));
}

function bloodlineForm(card, horse) {
  const sire = horse.pedigree.sire;
  const relatives = card.active_runners.filter(other => other.horse_no !== horse.horse_no && sire && other.pedigree.sire === sire);
  const samples = relatives.flatMap(other => withinDistance(
    other.history.filter(run => run.surface === card.course.surface), card.course.distance_m));
  return { sire, count: samples.length, score: samples.length >= 2 ? averageForm(samples) : null };
}

function evaluate({ method, card, horse, fact, field, index, evidence }) {
  const { history, nearby, courseHistory, officialRating, ratings, form, courseForm, distanceForm, ratingScore } = fact;
  const raceSource = card.official_url;
  if (Object.hasOwn(SUPPLEMENTAL, method)) {
    const item = evidence.find(row => row.method === method && row.horse_no === horse.horse_no);
    if (item) return metric(item.score, item.reason, item.source_url);
    if (REQUIRED_EVIDENCE.has(method)) return metric(null, `${SUPPLEMENTAL[method]}が未取得。`, null);
  }
  switch (method) {
    case 'editorial':
      return metric(combine([ratingScore, 5], [form, 3], [distanceForm, 2]),
        `公式評価${describe(officialRating)}、近3走の着順指数${describe(form)}、近い距離の指数${describe(distanceForm)}を総合。`, raceSource);
    case 'reporter': {
      const last = history[0];
      const recent = last ? formValue(last) : null;
      return metric(combine([recent, 3], [distanceForm, 3], [form, 2], [ratingScore, 2]),
        `同馬場の前走${last?.finish ? `${last.finish}着／${last.field_size}頭` : '資料なし'}。今回の距離に近い過去走は${nearby.length}件。`, raceSource);
    }
    case 'statistics':
      return metric(combine([average(ratings.map(rating => 2 * (rating - 75))), 4], [form, 1]),
        `同馬場の過去走レーティング${ratings.length}件、平均${describe(average(ratings))}。着順指数${describe(form)}。`, raceSource);
    case 'ability':
      return metric(ratingScore ?? form, `公式レーティング${describe(officialRating)}、同馬場の着順指数${describe(form)}。今回の馬体は未評価。`, raceSource);
    case 'pedigree': {
      const family = bloodlineForm(card, horse);
      return metric(family.score, `父${family.sire ?? '未確認'}。同父の別出走馬による同馬場・近距離の過去走${family.count}件を比較。`, raceSource);
    }
    case 'course':
      return metric(combine([courseForm, 4], [distanceForm, 2]),
        `${card.venue}・近い距離での実走${courseHistory.length}件。同馬場で距離差200m以内は${nearby.length}件。`, raceSource);
    case 'jockey': {
      const sameJockey = history.filter(run => run.jockey_name && run.jockey_name.replace(/\s/g, '') ===
        horse.jockey_name?.replace(/\s/g, ''));
      return metric(averageForm(sameJockey),
        `${horse.jockey_name ?? '騎手未確認'}との掲載済み同馬場実績${sameJockey.length}件。指数${describe(averageForm(sameJockey))}。`, raceSource);
    }
    case 'pace': {
      const position = positionScore(history.slice(0, 3), 'first_call');
      const enough = field.paceCoverage >= Math.ceil(card.active_runners.length * 0.6);
      const busy = field.leaders >= 3;
      const score = enough && position !== null && form !== null
        ? 0.65 * form + 0.35 * (busy ? 100 - position : position) : null;
      return metric(score, enough
        ? `先頭通過歴のある馬が${field.leaders}頭。序盤位置指数${describe(position)}と着順指数から展開を評価。`
        : '通過順位の取得頭数が少なく、想定ペースを確定できない。', raceSource);
    }
    case 'position': {
      const score = positionScore(history, 'first_call');
      return metric(score, `同馬場での最初のコーナー位置指数${describe(score)}。発馬そのものの計測値は未取得。`, raceSource);
    }
    case 'sectional': {
      const times = nearby.map(run => run.last_3f).filter(Number.isFinite);
      return metric(times.length ? -average(times) : null,
        `同馬場・距離差200m以内の上がり3Fを${times.length}件比較。平均${describe(average(times))}${times.length ? '秒' : ''}。`, raceSource);
    }
    case 'state': {
      const days = history[0]
        ? (Date.parse(card.race_date) - Date.parse(history[0].date)) / DAY_MS
        : null;
      const latest = history[0] ? formValue(history[0]) : null;
      const score = Number.isFinite(days) && latest !== null
        ? combine([latest, 2], [Math.max(0, 100 - Math.abs(days - 35)), 1]) : null;
      return metric(score, `同馬場の直近実戦から${describe(days)}日、着順指数${describe(latest)}。調整過程は未取得。`, raceSource);
    }
    case 'value': {
      const probability = field.probabilities[index];
      const value = Number.isFinite(probability) ? probability * horse.win_odds : null;
      return metric(value, value === null ? '全頭の単勝オッズまたはモデル入力が不足。'
        : `単勝${horse.win_odds}倍、未校正の推定勝率${(100 * probability).toFixed(1)}%、試算した払戻倍率${value.toFixed(2)}。`, raceSource);
    }
    case 'longshot': {
      const odds = horse.win_odds;
      const score = odds >= 10 ? combine([distanceForm, 4], [form, 3], [ratingScore, 3]) : null;
      return metric(score, Number.isFinite(odds)
        ? `単勝${odds}倍。10倍以上を対象に、同馬場の近走・距離実績を比較。`
        : '単勝オッズ未取得につき、穴馬条件を照合できない。', raceSource);
    }
    default:
      throw new Error(`unknown forecasting method: ${method}`);
  }
}

export function validateSupplementalEvidence(rows, card, asOf) {
  if (!Array.isArray(rows)) throw new Error('supplemental evidence must be an array');
  const horses = new Set(card.active_runners.map(horse => horse.horse_no));
  const keys = new Set();
  for (const row of rows) {
    const key = `${row.method}:${row.horse_no}`;
    if (!Object.hasOwn(SUPPLEMENTAL, row.method) || !horses.has(row.horse_no) || keys.has(key) ||
        !Number.isFinite(row.score) || row.score < 0 || row.score > 100 ||
        typeof row.reason !== 'string' || !row.reason.trim() ||
        typeof row.source_url !== 'string' || new URL(row.source_url).protocol !== 'https:' ||
        typeof row.available_at !== 'string' || !/(Z|[+-]\d{2}:\d{2})$/.test(row.available_at) ||
        !Number.isFinite(Date.parse(row.available_at)) ||
        Date.parse(row.available_at) > Date.parse(asOf)) {
      throw new Error(`invalid or unavailable supplemental evidence: ${key}`);
    }
    keys.add(key);
  }
}

export function restoreSupplementalEvidence(initial) {
  if (!initial) throw new Error('initial forecast required to recover prior evidence');
  const entries = new Map();
  for (const record of initial.records) {
    if (!Object.hasOwn(SUPPLEMENTAL, record.execution.method)) continue;
    for (const row of record.diagnoses) {
      if (!row.source_ref || row.source_ref === initial.source_refs[0] ||
          !initial.source_refs.includes(row.source_ref) || !Number.isFinite(row.score)) continue;
      entries.set(`${record.execution.method}:${row.horse_no}`, {
        method: record.execution.method, horse_no: row.horse_no, score: row.score,
        reason: row.reason, source_url: row.source_ref, available_at: initial.saved_at,
      });
    }
  }
  return [...entries.values()];
}

export async function forecastSpecialist({ agent, card, evidence, now, phase, review, initial, model }) {
  const startedAt = now();
  const field = fieldContext(card, agent.method);
  const diagnoses = card.active_runners.map((horse, index) => {
    const assessment = evaluate({ method: agent.method, card, horse, fact: field.facts[index], field, index, evidence });
    return {
      horse_no: horse.horse_no,
      horse_name: horse.horse_name,
      score: Number.isFinite(assessment.score) ? round(assessment.score) : null,
      reason: assessment.reason,
      source_ref: assessment.source,
      mark: null,
    };
  });
  let ranked = diagnoses.filter(row => row.score !== null).sort((a, b) => b.score - a.score || a.horse_no - b.horse_no);
  const standard = ranked.length >= 2 && ranked[0].score !== ranked.at(-1).score;
  const hasRanking = ['value', 'longshot'].includes(agent.method) ? ranked.length > 0 : standard;
  let skipReason = null;
  let reviewReason = review ? '五議題の比較を確認し、担当分野の採点を維持。' : null;
  let modelTrace = null;
  let modelPassed = false;
  let modelReason = null;
  if (model) {
    const decision = await model({
      agent, card, diagnoses, eligible: hasRanking ? ranked.map(row => row.horse_no) : [],
      review: review?.topics ?? null, roundtable: review?.roundtable ?? null, initial, offAt: card.off_at,
    });
    const byNumber = new Map(ranked.map(row => [row.horse_no, row]));
    if (!Array.isArray(decision.horse_nos) || decision.horse_nos.length > MARKS.length ||
        (!hasRanking && decision.horse_nos.length) ||
        new Set(decision.horse_nos).size !== decision.horse_nos.length ||
        !decision.horse_nos.every(number => byNumber.has(number)) ||
        typeof decision.reason !== 'string' || !decision.reason.trim() ||
        !decision.response_id || !decision.model) {
      throw new Error(`invalid model forecast: ${agent.id}`);
    }
    ranked = decision.horse_nos.map(number => byNumber.get(number));
    modelReason = decision.reason;
    if (ranked.length) ranked[0].reason = `${ranked[0].reason} モデル見解：${decision.reason}`;
    else {
      modelPassed = true;
      skipReason = decision.reason;
    }
    reviewReason = review ? decision.reason : null;
    modelTrace = { provider: 'openai', response_id: decision.response_id, model: decision.model };
  }
  let picks = [];
  if (hasRanking && !modelPassed) {
    picks = ranked.slice(0, MARKS.length).map((row, index) => {
      row.mark = MARKS[index];
      return { horse_no: row.horse_no, horse_name: row.horse_name, mark: row.mark };
    });
  } else if (!skipReason) {
    skipReason = Object.hasOwn(SUPPLEMENTAL, agent.method)
      ? `${SUPPLEMENTAL[agent.method]}が比較できる頭数に届かず見送り。`
      : '比較できる実測値が不足、または同点のため見送り。';
  }
  if (agent.method === 'value' && picks.length && ranked[0].score <= 1) {
    skipReason = '推定払戻倍率が1を超える単勝候補なし。';
  }
  const tickets = skipReason ? [] : [{ type: 'WIN', horse_nos: [picks[0].horse_no], stake_yen: 100 }];
  if (review && initial && !modelReason) {
    const before = initial.picks[0];
    const after = picks[0];
    const topic = review.roundtable?.topics.find(topic => topic.id === 'CASE');
    const challenge = topic?.turns.find(turn => turn.kind === 'REBUTTAL' && topic.turns.some(
      target => target.turn_id === turn.responds_to && target.horse_no === before?.horse_no));
    const compared = card.active_runners.find(horse => horse.horse_no === challenge?.horse_no);
    reviewReason = after && compared
      ? `${compared.horse_name}を推す意見を確認。担当分野の評価を優先し、${after.horse_name}を維持。`
      : skipReason ?? reviewReason;
  }
  return {
    display_name: agent.name, specialty: agent.specialty, profile_status: agent.profile_status ?? null,
    mode: 'independent_execution', independent_execution: true, execution_id: randomUUID(),
    execution: {
      method: agent.method, engine_version: 'prism-specialists/1', phase,
      started_at: startedAt, finished_at: now(), ...(modelTrace ?? { provider: 'local_rules' }),
    },
    diagnoses, picks, tickets, stake_yen: tickets.length * 100,
    skip_reason: skipReason, review_reason: reviewReason,
  };
}
