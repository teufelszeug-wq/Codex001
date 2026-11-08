"""PRISM strict PRE forecast gate and paper ROI accounting (stdlib)."""
from datetime import datetime, timedelta
import hashlib
import json

def timestamp(value):
    t = datetime.fromisoformat(value)
    if t.utcoffset() is None:
        raise ValueError("timezone required")
    return t

def digest(data):
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def validate_forecast(forecast, trusted_receipt=None, proof_bundle=None, *, verifier_context=None):
    if not isinstance(forecast, dict):
        return {"complete": False, "errors": ["INVALID_FORECAST"],
                "race_id": None, "agent_count": 0, "sha256": None}
    errors = []
    try:
        lock = timestamp(forecast["saved_at"])
        if lock >= timestamp(forecast["scheduled_off"]):
            errors.append("NOT_PRE_RACE")
    except (KeyError, ValueError, TypeError):
        errors.append("INVALID_TIME")
        lock = None
    if not forecast.get("race_id") or not forecast.get("input_hash") or not forecast.get("forecast_version"):
        errors.append("MISSING_FORECAST_IDENTITY")
    if not forecast.get("source_as_of"):
        errors.append("SOURCE_AS_OF_MISSING")
    else:
        try:
            source_time = timestamp(forecast["source_as_of"])
            if lock and source_time > lock:
                errors.append("SOURCE_AFTER_SAVE")
            if source_time >= timestamp(forecast["scheduled_off"]):
                errors.append("SOURCE_NOT_PRE_RACE")
        except (ValueError, TypeError, KeyError):
            errors.append("INVALID_SOURCE_AS_OF")
    if "input_snapshot" not in forecast:
        errors.append("INPUT_SNAPSHOT_MISSING")
    else:
        if not isinstance(forecast["input_snapshot"], (dict, list)):
            errors.append("INVALID_INPUT_SNAPSHOT")
        elif forecast.get("input_hash") != digest(forecast["input_snapshot"]):
            errors.append("INPUT_HASH_MISMATCH")
    # Provenance is an external envelope. Requiring a TSA token or storage
    # address *inside* the signed forecast would create a circular dependency.
    # Legacy fields, if present, are not trusted as evidence.
    # Reverify cryptographic proof at the acceptance boundary. A forged receipt
    # dictionary, including a forged verified_by field, is not sufficient.
    if not isinstance(proof_bundle, dict):
        errors.append("CRYPTOGRAPHIC_PROOF_BUNDLE_MISSING")
    else:
        try:
            from prism_ops.pre_provenance_verifier import verify_rfc3161_receipt
            # Never accept readback bytes or a storage address asserted by the
            # forecast producer. Re-fetch a pinned WORM version from S3.
            from prism_ops.trusted_s3_readback import verified_s3_readback
            from datetime import timedelta
            if not isinstance(verifier_context, dict):
                raise ValueError("TRUSTED_VERIFIER_CONTEXT_REQUIRED")
            if any(k in proof_bundle for k in ("trusted_s3_client", "trusted_tsa_ca_pem")):
                raise ValueError("UNTRUSTED_VERIFIER_CONFIG_IN_PROOF")
            if not all(k in verifier_context for k in ("s3_client", "bucket", "key_prefix", "tsa_ca_pem", "official_race_id", "official_scheduled_off", "official_entries")):
                raise ValueError("TRUSTED_VERIFIER_CONFIG_INCOMPLETE")
            # Official race identity and off time are verifier-owned, not
            # supplied by the prediction producer.
            if forecast.get("race_id") != verifier_context["official_race_id"]:
                raise ValueError("OFFICIAL_RACE_ID_MISMATCH")
            if timestamp(forecast["scheduled_off"]) != timestamp(verifier_context["official_scheduled_off"]):
                raise ValueError("OFFICIAL_SCHEDULED_OFF_MISMATCH")
            # The official feed is part of the verifier's trusted input.
            # Never accept a PRE if the latest official observation already
            # exposes results or reports the race cancelled.
            if verifier_context.get("official_result_exposed") is not False:
                raise ValueError("OFFICIAL_RESULT_EXPOSURE_UNVERIFIED")
            if verifier_context.get("official_race_cancelled") is not False:
                raise ValueError("OFFICIAL_RACE_STATUS_UNVERIFIED")
            try:
                observed = timestamp(verifier_context["official_as_of"])
                saved = timestamp(forecast["saved_at"])
                off = timestamp(verifier_context["official_scheduled_off"])
            except (KeyError, ValueError, TypeError) as exc:
                raise ValueError("OFFICIAL_FEED_TIME_UNVERIFIED") from exc
            if observed > saved or observed >= off:
                raise ValueError("OFFICIAL_FEED_AFTER_PRE")
            if saved - observed > timedelta(minutes=15):
                raise ValueError("OFFICIAL_FEED_STALE")
            official_entries = verifier_context["official_entries"]
            if (not isinstance(official_entries, list) or not official_entries or
                    not all(isinstance(e, dict) for e in official_entries)):
                raise ValueError("OFFICIAL_ENTRIES_UNAVAILABLE")
            def runner_identity(entries):
                return sorted((e["horse_no"], e["horse_name"]) for e in entries)
            try:
                if runner_identity(forecast["entries"]) != runner_identity(official_entries):
                    raise ValueError("OFFICIAL_ENTRIES_MISMATCH")
            except (KeyError, TypeError):
                raise ValueError("OFFICIAL_ENTRIES_MISMATCH")
            bucket = verifier_context["bucket"]
            prefix = verifier_context["key_prefix"]
            key = proof_bundle["key"]
            if (not isinstance(prefix, str) or not prefix or
                    not prefix.endswith("/") or not isinstance(key, str) or not key.startswith(prefix) or
                    ".." in key.split("/") or key.startswith("/")):
                raise ValueError("UNTRUSTED_OBJECT_KEY")
            original = proof_bundle["forecast_bytes"]
            if not isinstance(original, bytes):
                raise ValueError("FORECAST_BYTES_REQUIRED")
            immutable = verified_s3_readback(
                verifier_context["s3_client"],
                bucket=bucket,
                key=key,
                version_id=proof_bundle["version_id"],
                expected_sha256=hashlib.sha256(original).hexdigest(),
                min_retention_until=timestamp(forecast["scheduled_off"]) + timedelta(days=1))
            verified = verify_rfc3161_receipt(
                original, immutable["readback_bytes"],
                proof_bundle["tsa_response_der"], verifier_context["tsa_ca_pem"],
                immutable["immutable_location"],
                request_der=proof_bundle["tsa_request_der"])
            if "immutable_location" in proof_bundle and proof_bundle["immutable_location"] != immutable["immutable_location"]:
                raise ValueError("IMMUTABLE_LOCATION_MISMATCH")
            if trusted_receipt != verified:
                errors.append("TRUSTED_RECEIPT_NOT_DERIVED_FROM_PROOF")
            if proof_bundle["forecast_bytes"] != json.dumps(
                    forecast, ensure_ascii=False, sort_keys=True,
                    separators=(",", ":")).encode("utf-8"):
                errors.append("SIGNED_FORECAST_PAYLOAD_MISMATCH")
        except (KeyError, ValueError, TypeError, OSError) as exc:
            errors.append("CRYPTOGRAPHIC_PROOF_INVALID:" + str(exc))
    # Self-attested flags cannot establish external timestamp or readback.
    # A separate trusted verifier must provide the receipt; this module cannot mint it.
    if not isinstance(trusted_receipt, dict) or trusted_receipt.get("verified_by") != "PRISM_TRUSTED_PERSISTENCE_VERIFIER":
        errors.append("PRE_PROVENANCE_NOT_INDEPENDENTLY_VERIFIED")
    else:
        if trusted_receipt.get("race_id") != forecast.get("race_id") or trusted_receipt.get("forecast_sha256") != digest(forecast):
            errors.append("TRUSTED_RECEIPT_FORECAST_MISMATCH")
        try:
            if timestamp(trusted_receipt["trusted_saved_at"]) >= timestamp(forecast["scheduled_off"]):
                errors.append("TRUSTED_TIMESTAMP_AFTER_OFF")
        except (KeyError, ValueError, TypeError):
            errors.append("TRUSTED_TIMESTAMP_MISSING")
        if not trusted_receipt.get("immutable_location") or trusted_receipt.get("readback_verified") is not True or trusted_receipt.get("timestamp_verified") is not True:
            errors.append("TRUSTED_RECEIPT_INCOMPLETE")
    if forecast.get("results_exposed") is not False:
        errors.append("RESULT_EXPOSURE_NOT_EXCLUDED")
    runners = forecast.get("entries", [])
    if not isinstance(runners, list) or any(not isinstance(r, dict) for r in runners):
        errors.append("INVALID_ENTRIES")
        runners = []
    numbers = [r.get("horse_no") for r in runners]
    valid_numbers = [n for n in numbers if type(n) is int and n > 0]
    if len(valid_numbers) != len(numbers):
        errors.append("INVALID_HORSE_NUMBER")
    if (not runners or len(set(valid_numbers)) != len(valid_numbers) or
            len(valid_numbers) != len(numbers) or
            any(not isinstance(r.get("horse_name"), str) or
                not r["horse_name"].strip() for r in runners)):
        errors.append("INVALID_ENTRIES")
    known = set(valid_numbers)
    agents = forecast.get("agents", [])
    if not isinstance(agents, list) or any(not isinstance(a, dict) for a in agents):
        errors.append("INVALID_AGENTS")
        agents = []
    ids = [a.get("agent_id") for a in agents]
    valid_ids = [i for i in ids if isinstance(i, str) and i.strip()]
    if not agents or len(valid_ids) != len(ids) or len(valid_ids) != len(set(valid_ids)):
        errors.append("INVALID_AGENTS")
    roster = forecast.get("required_agent_ids")
    if roster is None:
        errors.append("REQUIRED_AGENT_ROSTER_MISSING")
    elif (not isinstance(roster, list) or not roster or
          any(not isinstance(x, str) or not x.strip() for x in roster) or
          len(roster) != len(set(x for x in roster if isinstance(x, str)))):
        errors.append("INVALID_REQUIRED_AGENT_ROSTER")
    elif set(valid_ids) != set(roster):
        errors.append("AGENT_COVERAGE_INCOMPLETE")
    editorial = forecast.get("editorial")
    if not isinstance(editorial, dict):
        errors.append("INVALID_EDITORIAL")
        editorial = {}
    for agent in [*agents, dict(editorial, agent_id="EDITORIAL")]:
        name = agent["agent_id"] if isinstance(agent.get("agent_id"), str) else "INVALID_AGENT"
        picks = agent.get("picks", [])
        if not isinstance(picks, list) or any(not isinstance(p, dict) for p in picks):
            errors.append(name + ":INVALID_PICKS")
            picks = []
        tickets = agent.get("tickets", [])
        if not isinstance(tickets, list) or any(not isinstance(t, dict) for t in tickets):
            errors.append(name + ":INVALID_TICKET")
            tickets = []
        if not picks or any(
                not isinstance(p.get("mark"), str) or not p["mark"] or
                p.get("horse_no") not in known or
                not isinstance(p.get("horse_name"), str) or
                p.get("horse_name") != next(
                    (r["horse_name"] for r in runners if r.get("horse_no") == p.get("horse_no")), None)
                for p in picks):
            errors.append(name + ":INVALID_PICKS")
        if not tickets and not agent.get("pass_reason"):
            errors.append(name + ":NO_TICKETS_OR_PASS")
        seen_tickets = set()
        for ticket in tickets:
            selection = ticket.get("selection")
            bet_type = ticket.get("bet_type")
            if (not isinstance(selection, list) or not selection or
                    any(type(n) is not int or n not in known for n in selection) or
                    not isinstance(bet_type, str) or not bet_type.strip()):
                errors.append(name + ":INVALID_TICKET")
                continue
            key = (bet_type, tuple(selection))
            if key in seen_tickets:
                errors.append(name + ":DUPLICATE_TICKET")
            seen_tickets.add(key)
            if type(ticket.get("stake_yen")) is not int or ticket["stake_yen"] != 100:
                errors.append(name + ":STAKE_NOT_100")
    evidence = forecast.get("evidence", [])
    if not isinstance(evidence, list) or any(not isinstance(item, dict) for item in evidence):
        errors.append("INVALID_EVIDENCE")
        evidence = []
    for item in evidence:
        if not item.get("source") or not item.get("kind") or not item.get("available_at"):
            errors.append("EVIDENCE_MISSING_PROVENANCE")
            continue
        try:
            if lock and timestamp(item["available_at"]) > lock:
                errors.append("FUTURE_EVIDENCE")
        except (TypeError, ValueError):
            errors.append("INVALID_EVIDENCE_TIME")
    return {"complete": not errors, "errors": errors, "race_id": forecast.get("race_id"),
            "agent_count": len(agents), "sha256": digest(forecast)}

def settle_forecast(forecast, official_result, trusted_receipt=None, proof_bundle=None, *, verifier_context=None):
    """Strict per-agent settlement. Never infer an unlisted outcome is a loss.

    official_result.ticket_outcomes must explicitly adjudicate each ticket.
    A caller must separately verify the official result source and its timestamp.
    """
    from prism_ops.settlement_fail_closed import settle_ticket_outcomes

    gate = validate_forecast(forecast, trusted_receipt, proof_bundle, verifier_context=verifier_context)
    if not gate["complete"]:
        raise ValueError("invalid PRE forecast: " + repr(gate["errors"]))
    if official_result.get("race_id") != forecast.get("race_id"):
        raise ValueError("race mismatch")
    if not official_result.get("official_source"):
        raise ValueError("missing official source")
    outcomes = official_result.get("ticket_outcomes")
    if not isinstance(outcomes, dict):
        raise ValueError("MISSING_TICKET_OUTCOMES")
    report = {}
    for agent in [*forecast["agents"], dict(forecast["editorial"], agent_id="EDITORIAL")]:
        report[agent["agent_id"]] = settle_ticket_outcomes(agent.get("tickets", []), outcomes)
    return {"race_id": forecast["race_id"], "forecast_sha256": gate["sha256"],
            "official_source": official_result["official_source"], "by_agent": report}
