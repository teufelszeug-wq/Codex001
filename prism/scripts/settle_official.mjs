/** JSON stdin bridge. No network, clock spoofing, or file writes. */
import { settleForecast, resultPayloadDigest } from '../src/operations/settlement.mjs';
import { createPreRaceLedger } from '../src/operations/forecast_history.mjs';
try {
  let input = '';
  for await (const chunk of process.stdin) { input += chunk; if (input.length > 8_000_000) throw new Error('input too large'); }
  const args = JSON.parse(input);
  if (args.operation === 'result_digest') process.stdout.write(JSON.stringify({ normalized_sha256:resultPayloadDigest(args.result) }) + '\n');
  else if (args.operation === 'create_forecast') process.stdout.write(JSON.stringify(createPreRaceLedger(args.forecast_input)) + '\n');
  else process.stdout.write(JSON.stringify(settleForecast(args)) + '\n');
} catch (error) {
  process.stderr.write(JSON.stringify({ status:'BLOCKED', error:error.message }) + '\n');
  process.exitCode = 1;
}
