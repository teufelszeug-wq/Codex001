import { createHash } from 'node:crypto';

const EDITOR = 'PRISM-EDITOR-01';
const REPORTER = 'RIO-REPORTER-01';
const REGISTRY_SOURCE = 'https://app.notion.com/p/e4615cdcad494bf7a177c7708b5fe627';
const SURFACES = { TURF: '芝', DIRT: 'ダート', JUMP: '障害', BANEI: 'ばんえい' };
const DIRECTIONS = { LEFT: '左回り', RIGHT: '右回り', STRAIGHT: '直線' };
const TICKETS = {
  WIN: '単勝', PLACE: '複勝', QUINELLA: '馬連', EXACTA: '馬単',
  WIDE: 'ワイド', TRIO: '三連複', TRIFECTA: '三連単',
};

export function runnerKey(horse) {
  return horse?.horse_no ?? horse?.horse_id;
}

function statement(turns, speaker, text, { record, horse, reply, kind } = {}) {
  const turn = {
    turn_id: turns.length + 1, speaker_id: speaker.id, name: speaker.name, text,
    ...(record ? { execution_id: record.execution_id } : {}),
    ...(horse?.horse_no ? { horse_no: horse.horse_no } : horse ? { horse_id: horse.horse_id } : {}),
    ...(reply ? { responds_to: reply.turn_id } : {}),
    ...(kind ? { kind } : {}),
  };
  turns.push(turn);
  return turn;
}

function describeHorse(horse) {
  return horse.horse_no ? `${horse.horse_no}番${horse.horse_name}` : horse.horse_name;
}

function diagnosis(record, identity) {
  return record.diagnoses.find(row => runnerKey(row) === identity);
}

function ticketText(tickets, horses) {
  return tickets.map(ticket => {
    const names = ticket.horse_nos.map(number => describeHorse(horses.get(number)));
    return `${TICKETS[ticket.type]} ${names.join('・')} ${ticket.stake_yen}円`;
  }).join('、');
}

function selectVoice(records, horse, home, used) {
  const identity = runnerKey(horse);
  const specialists = records.filter(record => !['HONSHI', REPORTER].includes(record.forecaster_id) &&
    Number.isFinite(diagnosis(record, identity)?.score));
  const byUse = candidates => [...candidates].sort((a, b) =>
    (used.get(a.forecaster_id) ?? 0) - (used.get(b.forecaster_id) ?? 0))[0];
  return byUse(specialists.filter(record => runnerKey(record.picks[0]) === identity)) ??
    byUse(specialists.filter(record => record.picks.some(pick => runnerKey(pick) === identity))) ??
    byUse(specialists) ?? home;
}

export function buildRoundtable({ initial, comparison, roster, now }) {
  const openedAt = now();
  const editor = roster.facilitator;
  const reporter = roster.forecasters.find(person => person.id === REPORTER);
  const people = new Map(roster.forecasters.map(person => [person.id, person]));
  const records = new Map(initial.records.map(record => [record.forecaster_id, record]));
  const paper = records.get('HONSHI');
  const course = comparison.topics.find(topic => topic.id === 'COURSE').course;
  const unframed = initial.schema === 'prism.forecast_declarations/v1';
  const field = [...initial.runners];
  if (!unframed) field.sort((a, b) => a.horse_no - b.horse_no);
  const horses = new Map(field.map(horse => [runnerKey(horse), horse]));
  const topics = comparison.topics.map(topic => ({ id: topic.id, title: topic.title, turns: [] }));
  const [all, shape, info, cases, bets] = topics.map(topic => topic.turns);
  const speak = (turns, record, text, extra = {}) =>
    statement(turns, people.get(record.forecaster_id), text, { ...extra, record });

  const locality = [SURFACES[course.surface], `${course.distance_m}m`, DIRECTIONS[course.direction]].filter(Boolean).join('・');
  const order = unframed ? '出馬表の掲載順に見ていきましょう。' : '枠順の内から見ていきましょう。';
  statement(all, editor, `${initial.race_name}は${locality}、${field.length}頭です。${order}`);
  const questions = [
    name => `${name}は、今回の条件でどこを評価しましたか？`,
    name => `${name}の過去走から、どんな点が気になりますか？`,
    name => `${name}を印の候補に入れる根拠はありますか？`,
    name => `${name}の評価を決めた材料を聞かせてください。`,
  ];
  const voiceUses = new Map();
  for (const [index, horse] of field.entries()) {
    const identity = runnerKey(horse);
    const voice = selectVoice(initial.records, horse, paper, voiceUses);
    voiceUses.set(voice.forecaster_id, (voiceUses.get(voice.forecaster_id) ?? 0) + 1);
    const judgement = diagnosis(voice, identity);
    const label = horse.frame_no ? `${horse.frame_no}枠${describeHorse(horse)}` : describeHorse(horse);
    const question = statement(all, reporter, questions[index % questions.length](label), { horse });
    const reply = speak(all, voice, judgement.reason, { horse, reply: question });
    const overall = diagnosis(paper, identity);
    if (voice !== paper && judgement.score !== null && !overall.mark &&
        voice.picks.some(pick => runnerKey(pick) === identity)) {
      speak(all, paper, `本紙の一次印では無印です。${overall.reason}`, { horse, reply });
    }
  }

  statement(shape, editor, course.surface === 'BANEI'
    ? 'ばんえいは直線の障害と馬場水分を見ます。水分が多いと馬場は軽くなりやすいので、水分の発表が判断材料になります。'
    : '続いてコースと展開です。同じ距離の実績と、今回の馬場の傾向は分けて見ましょう。');
  if (comparison.track_condition) {
    statement(shape, reporter, course.surface === 'BANEI'
      ? `出馬表の馬場水分は${comparison.track_condition}％です。この数字を判断材料に入れましょう。`
      : `取得時点の公式馬場は${comparison.track_condition}です。`);
  }
  for (const finding of comparison.topics.find(topic => topic.id === 'COURSE').findings) {
    const record = records.get(finding.forecaster_id);
    const horse = horses.get(runnerKey(finding.top_pick));
    const question = statement(shape, reporter, `${record.specialty}から見ると、今回はどうでしょうか？`, { horse });
    speak(shape, record, horse ? `${describeHorse(horse)}を上位に見ました。${finding.reason}` : finding.reason,
      { horse, reply: question });
  }

  statement(info, editor, '近走の数字だけでは分からない材料も確認します。状態、調教、騎手や陣営の情報を聞きましょう。');
  for (const finding of comparison.topics.find(topic => topic.id === 'INFORMATION').findings) {
    const record = records.get(finding.forecaster_id);
    const horse = horses.get(runnerKey(finding.top_pick));
    speak(info, record, horse ? `${describeHorse(horse)}を評価しました。${finding.reason}` : finding.reason, { horse });
  }
  const informationQuestion = statement(info, reporter, '見送りの担当がいる点は、馬を低く評価したと受け取っていいですか？');
  statement(info, editor, '資料不足と評価の低さは別です。確認できた根拠を使い、未取得の資料は判断の保留として扱います。',
    { reply: informationQuestion });

  statement(cases, editor, '本命の根拠を比べましょう。別の馬を推す意見からも、各候補の弱点を確かめます。');
  const nominations = comparison.topics.find(topic => topic.id === 'CASE').nominations;
  const advocates = new Map(nominations.map(row => [runnerKey(row), initial.records.find(record =>
    record.forecaster_id !== REPORTER && runnerKey(record.picks[0]) === runnerKey(row))]));
  const presentations = new Map();
  for (const record of initial.records.filter(row => row.forecaster_id !== REPORTER && row.picks.length)) {
    const identity = runnerKey(record.picks[0]);
    const horse = horses.get(identity);
    const presentation = speak(cases, record, `私の◎は${describeHorse(horse)}です。${diagnosis(record, identity).reason}`, { horse });
    if (advocates.get(identity) === record) presentations.set(identity, presentation);
  }
  if (!presentations.size) {
    const question = statement(cases, reporter, '本命候補がまとまらなかった理由を教えてください。');
    statement(cases, editor, '比較に使える材料が限られています。各担当の見送り理由を確認しましょう。', { reply: question });
  }
  for (const [identity, presentation] of presentations) {
    const record = advocates.get(identity);
    const horse = horses.get(identity);
    const rival = [...advocates.values()].find(other => other && runnerKey(other.picks[0]) !== identity);
    const rivalKey = runnerKey(rival?.picks[0]);
    const rivalHorse = horses.get(rivalKey);
    const rivalAssessment = rival && diagnosis(rival, identity);
    const condition = diagnosis(record, identity).reason;
    const rivalReason = rival && diagnosis(rival, rivalKey).reason;
    const challenge = Number.isFinite(rivalAssessment?.score)
      ? `${describeHorse(horse)}について、私が見たのは次の点です。${rivalAssessment.reason} ${describeHorse(rivalHorse)}にも根拠があります。${rivalReason}`
      : rival && `私の担当では${describeHorse(horse)}の比較材料が足りません。評価できた${describeHorse(rivalHorse)}を推します。${rivalReason}`;
    const reply = rival
      ? speak(cases, rival, challenge, { horse: rivalHorse, reply: presentation, kind: 'REBUTTAL' })
      : statement(cases, reporter, `${describeHorse(horse)}を評価したうえで、どこを確認したいですか？`, { horse, reply: presentation });
    speak(cases, record, rival
      ? `評価の軸が違いますね。今回、私が${describeHorse(horse)}を残す材料はここです。${condition}`
      : `現在の根拠は${condition} 当日の状態や馬場に変化があれば見直します。`, { horse, reply, kind: 'RESPONSE' });
  }

  statement(bets, editor, unframed
    ? '候補を馬名で確認します。仮想買い目は枠順と馬番の公表後に決めましょう。'
    : '一次段階の買い目を確認します。一点100円の仮想買い目です。');
  for (const record of initial.records.filter(row => row.forecaster_id !== REPORTER)) {
    const horse = horses.get(runnerKey(record.picks[0]));
    const decision = record.tickets.length ? ticketText(record.tickets, horses) + '。'
      : unframed && horse ? `候補は${describeHorse(horse)}です。${record.skip_reason}` : `見送ります。${record.skip_reason}`;
    speak(bets, record, decision, { horse });
  }
  const rio = records.get(REPORTER);
  const rioKey = runnerKey(rio.picks[0]);
  const rioHorse = horses.get(rioKey);
  if (rioHorse) {
    speak(bets, rio, `私の一次予想は◎${describeHorse(rioHorse)}です。${diagnosis(rio, rioKey).reason} ${rio.tickets.length ? ticketText(rio.tickets, horses) + '。' : rio.skip_reason}`, { horse: rioHorse });
  } else {
    speak(bets, rio, `私の一次予想は見送りです。${rio.skip_reason}`);
  }
  statement(bets, editor, '意見が分かれた馬も候補に残し、各担当に最終判断を戻します。');
  return {
    schema: 'prism.roundtable/v1', race_id: initial.race_id, initial_sha256: initial.content_sha256,
    mode: 'local_evidence_dialogue', facilitator_id: EDITOR, opened_at: openedAt, recorded_at: now(),
    character_registry: {
      version: createHash('sha256').update(JSON.stringify(roster)).digest('hex'),
      source: REGISTRY_SOURCE,
      participants: [editor, ...roster.forecasters].map(person => ({
        speaker_id: person.id, name: person.name, specialty: person.specialty ?? '編集統括・進行',
        profile_status: person.profile_status ?? null,
      })),
    },
    topics,
  };
}

export function validateRoundtable(roundtable, initial, roster) {
  if (roundtable?.schema !== 'prism.roundtable/v1' || roundtable.race_id !== initial.race_id ||
      roundtable.initial_sha256 !== initial.content_sha256 || roundtable.facilitator_id !== roster.facilitator.id ||
      roundtable.mode !== 'local_evidence_dialogue' ||
      !(Date.parse(initial.saved_at) <= Date.parse(roundtable.opened_at)) ||
      !(Date.parse(roundtable.opened_at) <= Date.parse(roundtable.recorded_at)) ||
      !(Date.parse(roundtable.recorded_at) < Date.parse(initial.off_at)) ||
      roundtable.topics?.map(topic => topic.id).join(',') !== 'DIAGNOSIS,COURSE,INFORMATION,CASE,BETS') {
    throw new Error('roundtable identity, time, or five-topic coverage mismatch');
  }
  const people = new Map([[roster.facilitator.id, roster.facilitator],
    ...initial.records.map(record => [record.forecaster_id, { name: record.display_name }])]);
  const forecastIds = new Map(initial.records.map(record => [record.forecaster_id, record.execution_id]));
  const identities = new Set(initial.runners.map(runnerKey));
  const diagnosed = new Set();
  const betVoices = new Set();
  const offsetTime = value => typeof value === 'string' && /(?:Z|[+-]\d{2}:\d{2})$/.test(value) && Number.isFinite(Date.parse(value));
  if (![roundtable.opened_at, roundtable.recorded_at].every(offsetTime)) {
    throw new Error('roundtable requires timezone-aware timestamps');
  }
  for (const topic of roundtable.topics) {
    if (topic.turns?.[0]?.speaker_id !== EDITOR || topic.turns.length < 3) {
      throw new Error(`roundtable topic has no facilitated exchange: ${topic.id}`);
    }
    const prior = new Map();
    for (const turn of topic.turns) {
      const person = people.get(turn.speaker_id);
      const response = turn.responds_to === undefined ? null : prior.get(turn.responds_to);
      const subject = runnerKey(turn);
      if (!person || person.name !== turn.name || typeof turn.text !== 'string' || !turn.text.trim() ||
          turn.turn_id !== prior.size + 1 ||
          (turn.execution_id !== undefined && forecastIds.get(turn.speaker_id) !== turn.execution_id) ||
          (subject !== undefined && !identities.has(subject)) ||
          (turn.responds_to !== undefined && (!response || response.speaker_id === turn.speaker_id))) {
        throw new Error(`invalid roundtable turn: ${topic.id}/${turn.turn_id}`);
      }
      if (topic.id === 'DIAGNOSIS' && response?.speaker_id === REPORTER && turn.execution_id &&
          subject !== undefined && runnerKey(response) === subject) diagnosed.add(subject);
      if (topic.id === 'BETS' && turn.execution_id) betVoices.add(turn.speaker_id);
      if ((turn.kind === 'REBUTTAL' && (topic.id !== 'CASE' || !response || !turn.execution_id ||
          !subject || !runnerKey(response) || subject === runnerKey(response))) ||
          (turn.kind === 'RESPONSE' && (topic.id !== 'CASE' || !response || !turn.execution_id))) {
        throw new Error('roundtable rebuttal or reply does not match its subject');
      }
      prior.set(turn.turn_id, turn);
    }
  }
  if (diagnosed.size !== identities.size || betVoices.size !== initial.records.length) {
    throw new Error('roundtable lacks full-field diagnosis or forecaster ticket coverage');
  }
  return roundtable;
}

export function compareFinalForecasts(initial, finalRecords) {
  return finalRecords.map(record => {
    const prior = initial.records.find(row => row.forecaster_id === record.forecaster_id);
    return {
      forecaster_id: record.forecaster_id, name: record.display_name,
      initial_execution_id: prior.execution_id, final_execution_id: record.execution_id,
      initial_pick: prior.picks[0] ?? null, final_pick: record.picks[0] ?? null,
      changed: JSON.stringify(prior.picks) !== JSON.stringify(record.picks) ||
        JSON.stringify(prior.tickets) !== JSON.stringify(record.tickets),
      reason: record.review_reason ?? record.skip_reason,
    };
  });
}

export function formatRoundtable(roundtable, raceName = roundtable.race_id) {
  const lines = [`# 座談会｜${raceName}`, '',
    '担当別の一次予想をもとに、質問・反論・回答を組み立てた自動編集版です。', ''];
  for (const topic of roundtable.topics) {
    lines.push(`## ${topic.title}`, '');
    for (const turn of topic.turns) lines.push(`**${turn.name}**「${turn.text}」`, '');
  }
  return lines.join('\n') + '\n';
}

export function formatForecastChanges(changes) {
  const horse = pick => pick ? `${pick.mark}${describeHorse(pick)}` : '見送り';
  const lines = ['## 座談会後の最終判断', '', '| 担当 | 一次 | 最終 | 判断の理由 |', '|---|---|---|---|'];
  for (const row of changes) {
    const reason = (row.reason ?? '担当の評価を維持。').replaceAll('|', '｜').replaceAll('\n', ' ');
    lines.push(`| ${row.name} | ${horse(row.initial_pick)} | ${horse(row.final_pick)} | ${reason} |`);
  }
  return lines.join('\n') + '\n';
}
