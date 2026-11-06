"""Fail-closed official-ticket adjudication for PRISM (integration pending)."""
def settle_ticket_outcomes(tickets, outcomes):
    """outcomes maps canonical ticket keys to {'status','payout_yen'}."""
    stake = 0
    payout = 0
    refunds = 0
    for ticket in tickets:
        if ticket.get("stake_yen") != 100:
            raise ValueError("STAKE_NOT_100")
        selection = ticket.get("selection")
        if not isinstance(selection, list) or not selection:
            raise ValueError("INVALID_SELECTION")
        key = str(ticket["bet_type"]) + ":" + "-".join(map(str, selection))
        if key not in outcomes:
            raise ValueError("UNADJUDICATED_TICKET:" + key)
        result = outcomes[key]
        status = result.get("status")
        amount = result.get("payout_yen")
        if status not in ("won", "lost", "refunded"):
            raise ValueError("INVALID_STATUS:" + key)
        if type(amount) is not int or amount < 0:
            raise ValueError("INVALID_PAYOUT:" + key)
        if (status == "lost" and amount != 0) or (status == "won" and amount == 0) or (status == "refunded" and amount != 100):
            raise ValueError("INCONSISTENT_PAYOUT:" + key)
        stake += 100
        payout += amount
        refunds += 100 if status == "refunded" else 0
    effective = stake - refunds
    return {"stake_yen": stake, "payout_yen": payout,
            "refund_yen": refunds, "effective_stake_yen": effective,
            "net_yen": payout - stake,
            "roi_pct_ex_refund": round(100 * (payout - refunds) / effective, 4) if effective else None}
