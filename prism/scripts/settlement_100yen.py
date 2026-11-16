"""PRISM deterministic 100-yen payout settlement. No prediction or official-data retrieval."""

def settle(bets, payouts):
    """payouts maps (bet_type, selection) to official yen per 100 yen."""
    if not isinstance(bets, list) or not isinstance(payouts, dict):
        raise ValueError('invalid inputs')
    spent = returned = 0
    rows = []
    for index, bet in enumerate(bets):
        if not isinstance(bet, dict):
            raise ValueError(f'bet[{index}] invalid')
        kind, selection, stake = bet.get('bet_type'), bet.get('selection'), bet.get('stake_yen')
        if not isinstance(kind, str) or not kind.strip() or not isinstance(selection, str) or not selection.strip():
            raise ValueError(f'bet[{index}] missing type or selection')
        if type(stake) is not int or stake < 100 or stake % 100:
            raise ValueError(f'bet[{index}] invalid stake')
        payout = payouts.get((kind, selection), 0)
        if type(payout) is not int or payout < 0:
            raise ValueError(f'bet[{index}] invalid payout')
        won = stake // 100 * payout
        spent += stake
        returned += won
        rows.append({'bet_type': kind, 'selection': selection, 'stake_yen': stake, 'return_yen': won})
    return {'stake_yen': spent, 'return_yen': returned, 'profit_yen': returned - spent, 'bets': rows}
