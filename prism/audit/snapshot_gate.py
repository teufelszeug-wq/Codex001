"""Standalone snapshot and 100-yen settlement checks; not integrated with PRISM engine."""
from datetime import datetime
from decimal import Decimal

def dt(s):
    d = datetime.fromisoformat(s.replace('Z', '+00:00'))
    if d.tzinfo is None:
        raise ValueError('timezone required')
    return d

def validate_snapshot(snapshot):
    required = ('race_id', 'horse_name', 'predictor_id', 'source', 'saved_at', 'version', 'off_at', 'kind')
    for key in required:
        if not snapshot.get(key):
            raise ValueError('missing ' + key)
    if snapshot['kind'] not in ('pre_race', 'post_race_review'):
        raise ValueError('invalid snapshot kind')
    saved, off = dt(snapshot['saved_at']), dt(snapshot['off_at'])
    if snapshot['kind'] == 'pre_race' and saved >= off:
        raise ValueError('late pre-race snapshot')
    if snapshot['kind'] == 'post_race_review' and saved < off:
        raise ValueError('premature post-race review')
    for ev in snapshot.get('evidence', []):
        available = dt(ev['available_at'])
        if available > saved:
            raise ValueError('future evidence')
        for key in ('occurred_at', 'observed_at', 'captured_at'):
            if key in ev and dt(ev[key]) > available:
                raise ValueError('backdated evidence')
    return True

def settle_100yen(stake_units, payout_per_100):
    if type(stake_units) is not int or stake_units < 0:
        raise ValueError('invalid stake units')
    p = Decimal(str(payout_per_100))
    if p < 0 or p != p.to_integral_value():
        raise ValueError('invalid payout')
    cost = 100 * stake_units
    refund = int(p) * stake_units
    return {'cost_yen': cost, 'refund_yen': refund, 'profit_yen': refund - cost}
