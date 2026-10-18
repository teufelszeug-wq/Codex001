"""Engineering acceptance, synthetic inputs only. Does not close Phase D."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'tests/engine'))
from fixture import raw_fixture,seal,calibration_fixture,market_fixture,observations_fixture
from prism_engine.adapters import normalize
from run_core_engine import run,write_immutable
from prism_engine import predict,post_market
from prism_engine.contracts import digest
from prism_engine.engine import MODULES
from prism_engine.market import hit

def main(out):
    suite=unittest.defaultTestLoader.discover(str(ROOT/'tests/engine'),pattern='test_*.py');log=io.StringIO()
    result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
    observations=observations_fixture();raw,normalization=normalize(observations);calibration=calibration_fixture();when='2026-01-01T09:55:00+09:00'
    lock=predict(raw,when,calibration=calibration);market=market_fixture(lock)
    proposal=post_market(lock,market)
    finish=('h1','h2','h3','h4','h5','h6')
    synthetic_result={'race_id':lock['race_id'],'prediction_hash':lock['lock_hash'],
                      'available_at':'2026-01-01T10:05:00+09:00','refund_keys':[],
                      'complete_bet_types':sorted({c['bet_type'] for c in proposal['candidate_values']}),
                      'payouts':[{'bet_type':t['bet_type'],'legs':t['legs'],'payout_per_100_yen':350}
                                 for t in proposal['plan']['tickets'] if hit(t['bet_type'],t['legs'],finish,lock['frames'],2)]}
    with tempfile.TemporaryDirectory() as tmp:
        a=run(observations,market,when,Path(tmp)/'a',calibration=calibration,result=synthetic_result)
        b=run(observations,market,when,Path(tmp)/'b',calibration=calibration,result=synthetic_result)
        assert (Path(tmp)/'a/bundle.json').read_bytes()==(Path(tmp)/'b/bundle.json').read_bytes()
        run(observations,market,when,Path(tmp)/'a',calibration=calibration,result=synthetic_result)
    coverage={m:any(h['availability'].get(m)=='AVAILABLE' for h in lock['features']['horses'].values()) for m in MODULES}
    assert all(coverage.values()),coverage
    source_hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                   for folder in ('src/prism_engine','scripts','tests/engine') for p in sorted((ROOT/folder).rglob('*.py'))}
    report={'status':'PASS' if result.wasSuccessful() else 'FAIL','acceptance_scope':'PHASE_B_EXPERIMENTAL_ENGINEERING',
            'synthetic_only':True,'tests_run':result.testsRun,'test_failures':len(result.failures),'test_errors':len(result.errors),
            'component_connection_checks':coverage,'prediction_hash':lock['lock_hash'],'bundle_hash':digest(a),
            'determinism':'two independent byte-identical bundles; idempotent replay',
            'ticket_types':sorted({c['bet_type'] for c in a['market_values']['candidate_values']}),
            'budget_yen':500,'selected_stake_yen':a['market_values']['plan']['stake_yen'],
            'rank_model':lock['rank_model'],'source_sha256':source_hashes,
            'phase_b_domain_checks':{'base_ability':'past-rank normalizer + decay + explicit prior',
                'course_surface_class':'distance/direction/venue/class/load adjustments',
                'state_recency_rotation':'readiness/rotation with observation times',
                'pace':'five scenario win/joint probabilities',
                'bias_tbi_ssi':'signed inputs + fixed barrier width + route separation',
                'workout_condition':'structured time/body observations to experimental scores',
                'jockey':'wins/rides smoothed score and sample shrinkage',
                'specialist_nvalue':'evidence dedup + independent deterministic recheck + post-lock review',
                'monte_carlo_probability':'exact joint mixture + seeded top3 sampling',
                'calibration':'temperature-fit interface + disjoint/time/hash gates',
                'market_value_bet':'8 ticket types + conservative EV + bounded exact portfolio search'},
            'end_to_end_settlement_included':True,
            'performance_validated':False,'production_ready':False,'phase_d_complete':False,
            'normalization':normalization,
            'note':'Structured observation extraction verified on synthetic data; source authenticity, learned models, real-race performance and temporal certification are not established.'}
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    write_immutable(out/'PHASE_B_ACCEPTANCE_20261018.json',report)
    write_immutable(out/'PHASE_B_SYNTHETIC_BUNDLE_20261018.json',a)
    print(log.getvalue(),file=sys.stderr);print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0 if result.wasSuccessful() else 1

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True);args=parser.parse_args();sys.exit(main(args.out))
