import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';

const definitions = JSON.parse(readFileSync(new URL('../../data/operations/forecaster_contracts.json', import.meta.url), 'utf8'));
const text = value => typeof value === 'string' && value.trim();
const compact = value => typeof value === 'string' ? value.replace(/\s/g, '') : '';
export const FORECAST_CONTRACT_VERSION = definitions.version;
export const FORECAST_CONTRACT_SHA256 = createHash('sha256').update(JSON.stringify(definitions)).digest('hex');

export function validateForecasterContracts(roster, contracts = definitions) {
  if (contracts.schema !== 'prism.forecaster_contracts/v1' || !text(contracts.version) ||
      !Array.isArray(contracts.forecasters) || contracts.forecasters.length !== roster.forecasters.length ||
      contracts.facilitator?.id !== roster.facilitator.id ||
      contracts.facilitator.participates_in_forecasts !== false ||
      compact(contracts.facilitator.name) !== compact(roster.facilitator.name)) {
    throw new Error('forecaster contracts do not match the roster and facilitator');
  }
  const ids = new Set();
  const methods = new Set();
  for (const contract of contracts.forecasters) {
    const agent = roster.forecasters.find(row => row.id === contract.forecaster_id);
    let source;
    try { source = new URL(contract.canonical_source); } catch { /* rejected below */ }
    if (!agent || ids.has(agent.id) || methods.has(contract.method) ||
        contract.method !== agent.method || compact(contract.display_name) !== compact(agent.name) ||
        !['objective', 'canonical_role', 'decision_rule', 'implementation_limit', 'feedback_rule'].every(key => text(contract[key])) ||
        !Array.isArray(contract.required_inputs) || !contract.required_inputs.length || !contract.required_inputs.every(text) ||
        !Array.isArray(contract.output_requirements) ||
        !['ALL_RUNNER_DIAGNOSES_WITH_SOURCES', 'RANKED_PICKS_OR_EXPLICIT_PASS',
          '100_YEN_TICKETS_OR_EXPLICIT_PASS', 'VERSIONED_FINAL_REVIEW'].every(key => contract.output_requirements.includes(key)) ||
        contract.missing_input_policy !== 'PASS_WITH_SPECIFIC_MISSING_INPUTS' ||
        !['SOURCE_CONFIRMED', 'UNCONFIRMED'].includes(contract.persona?.voice_status) ||
        (contract.persona.voice_status === 'SOURCE_CONFIRMED' ? !text(contract.persona.voice) : contract.persona.voice !== null) ||
        source?.protocol !== 'https:' || source.username || source.password) {
      throw new Error(`invalid forecaster contract: ${contract.forecaster_id}`);
    }
    ids.add(agent.id);
    methods.add(contract.method);
  }
  return contracts;
}

export function getForecasterContract(agent) {
  const contract = definitions.forecasters.find(row => row.forecaster_id === agent.id);
  if (!contract || contract.method !== agent.method || compact(contract.display_name) !== compact(agent.name)) {
    throw new Error(`unknown or mismatched forecaster contract: ${agent.id}`);
  }
  return { version: definitions.version, ...structuredClone(contract) };
}

// This describes the existing local adapter's input coverage, not forecasting
// quality, trained-model readiness, API success, or an actual prediction.
export function buildForecasterReadiness({ agent, card, diagnoses }) {
  const contract = getForecasterContract(agent);
  if (!Array.isArray(diagnoses) || !card.active_runners.length ||
      diagnoses.length !== card.active_runners.length ||
      new Set(diagnoses.map(row => row.horse_no)).size !== diagnoses.length ||
      !diagnoses.every(row => card.active_runners.some(horse => horse.horse_no === row.horse_no &&
        horse.horse_name === row.horse_name) && (row.score === null || Number.isFinite(row.score)))) {
    throw new Error('readiness requires complete matching runner assessments');
  }
  const scored = diagnoses.filter(row => row.score !== null);
  const missing = diagnoses.filter(row => row.score === null);
  const different = new Set(scored.map(row => row.score)).size > 1;
  return {
    contract_version: contract.version,
    scope: 'LOCAL_ADAPTER_INPUT_COVERAGE_NOT_QUALITY_CERTIFICATION',
    state: !scored.length ? 'MISSING_INPUT' : missing.length ? 'PARTIAL_INPUT' : 'INPUT_AVAILABLE',
    runners: diagnoses.length, assessed_runners: scored.length, missing_runners: missing.length,
    local_ranking_ready: ['value', 'longshot'].includes(agent.method) ? scored.length > 0 : different,
    missing_horses: missing.map(row => ({ horse_no: row.horse_no, horse_name: row.horse_name, reason: row.reason })),
    required_inputs: contract.required_inputs,
    implementation_limit: contract.implementation_limit,
    next_action: !scored.length ? '担当資料を収集し、出典・時点・採点根拠を入力する。'
      : missing.length ? '根拠のある馬を評価し、不足馬の資料を補う。'
      : '入力の出典と担当の実装範囲を確認し、一次予想を実行する。',
  };
}
