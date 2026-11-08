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


def settle_with_trusted_official_result(forecast, official_result, *,
                                        trusted_result_context,
                                        trusted_receipt=None, proof_bundle=None,
                                        verifier_context=None):
    """Require a verifier-owned official result before paper settlement.

    The result adapter must independently authenticate the final official feed.
    No result-supplied flag or source URL alone can grant authenticity.
    """
    from prism_ops.forecast_completion_gate import settle_forecast, timestamp

    if not isinstance(official_result, dict) or not isinstance(trusted_result_context, dict):
        raise ValueError("TRUSTED_OFFICIAL_RESULT_REQUIRED")
    if trusted_result_context.get("verified_by") != "PRISM_TRUSTED_OFFICIAL_RESULT_VERIFIER":
        raise ValueError("TRUSTED_OFFICIAL_RESULT_REQUIRED")
    if trusted_result_context.get("official_final") is not True:
        raise ValueError("OFFICIAL_RESULT_NOT_FINAL")
    if (not isinstance(forecast, dict) or
            trusted_result_context.get("race_id") != forecast.get("race_id") or
            official_result.get("race_id") != forecast.get("race_id")):
        raise ValueError("OFFICIAL_RESULT_RACE_MISMATCH")
    source = trusted_result_context.get("official_source")
    if not isinstance(source, str) or not source or source != official_result.get("official_source"):
        raise ValueError("OFFICIAL_RESULT_SOURCE_MISMATCH")
    try:
        off = timestamp(forecast["scheduled_off"])
        published = timestamp(trusted_result_context["official_published_at"])
        observed = timestamp(trusted_result_context["official_observed_at"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("OFFICIAL_RESULT_TIME_UNVERIFIED") from exc
    if not off < published <= observed:
        raise ValueError("OFFICIAL_RESULT_TIME_UNVERIFIED")
    # Compare a canonical hash of the independently fetched final result.
    # Caller-supplied URLs, flags or ticket_outcomes cannot substitute for it.
    from prism_ops.forecast_completion_gate import digest
    if trusted_result_context.get("official_result_sha256") != digest(official_result):
        raise ValueError("OFFICIAL_RESULT_HASH_MISMATCH")
    return settle_forecast(forecast, official_result, trusted_receipt,
                           proof_bundle, verifier_context=verifier_context)
