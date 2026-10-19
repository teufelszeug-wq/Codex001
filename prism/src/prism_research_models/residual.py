"""Regularized race-level multinomial residual model with a locked ability offset.

Only training races determine imputation, scaling and coefficients. Missingness
is explicitly represented. The caller must supply an honest pre-race baseline
and feature provenance; the mathematical model cannot establish that provenance.
"""

from datetime import date, datetime
import hashlib
import json
import math
import re


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _day(value):
    text = str(value)
    if len(text) == 8 and text.isdigit():
        text = text[:4] + "-" + text[4:6] + "-" + text[6:]
    return date.fromisoformat(text).isoformat()


def _time(value):
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timestamps require a timezone")
    return dt


def _number(value):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("features must be finite numbers or null")
    return float(value)


def _validate(row, names):
    if not isinstance(row.get("race_id"), str) or not row["race_id"]:
        raise ValueError("race_id is required")
    _day(row["date"])
    probs = row["baseline_probabilities"]
    if not isinstance(probs, dict) or len(probs) < 2:
        raise ValueError("at least two baseline runners required")
    if any(not isinstance(h, str) or not h for h in probs):
        raise ValueError("runner IDs must be nonempty strings")
    if any(_number(p) is None or p <= 0 or p > 1 for p in probs.values()):
        raise ValueError("baseline probabilities must be positive")
    if abs(sum(probs.values()) - 1.0) > 1e-8:
        raise ValueError("baseline probabilities must sum to one")
    features = row["features"]
    if set(features) != set(probs):
        raise ValueError("feature runners and baseline runners must match")
    for runner in sorted(probs):
        if not isinstance(features[runner], dict):
            raise ValueError("runner features must be an object")
        for name in names:
            _number(features[runner].get(name))
    # Unknown publication times are allowed only with an explicit unverified flag
    # in the resulting artifact. A known future publication is always rejected.
    cutoff = _time(row["cutoff"]) if row.get("cutoff") else None
    verified = bool(cutoff)
    timestamps = row.get("feature_available_at", {})
    for runner in sorted(probs):
        for name in names:
            if features[runner].get(name) is None:
                continue
            stamp = timestamps.get(runner, {}).get(name)
            if not stamp or cutoff is None:
                verified = False
            elif _time(stamp) > cutoff:
                raise ValueError("feature was unavailable at prediction cutoff")
    return verified


def _vector(values, names, scaling):
    vector = []
    for name in names:
        value = _number(values.get(name))
        scale = scaling[name]
        # All-missing training columns remain unavailable even if holdout has data.
        observed = value is not None and scale["observed_count"] > 0
        transformed = (value - scale["mean"]) / scale["std"] if observed else 0.0
        if not math.isfinite(transformed):
            raise ValueError("feature transform overflow")
        vector.extend((transformed, 0.0 if observed else 1.0))
    return vector


def _softmax(logits):
    peak = max(logits)
    vals = [math.exp(x - peak) for x in logits]
    total = sum(vals)
    return [v / total for v in vals]


def fit_model(train_rows, feature_names, *, training_cutoff, l2=0.1,
              learning_rate=0.1, epochs=200):
    """Fit equal-race-weight cross entropy with a fixed baseline logit offset.

    Dead heats use equal winner-label mass. The fit cutoff is mandatory; known
    unavailable outcomes are rejected. Missing outcome times remain disclosed.
    """
    rows = list(train_rows)
    names = list(feature_names)
    if not rows or any(not isinstance(n, str) for n in names) or len(set(names)) != len(names):
        raise ValueError("nonempty unique training races and unique features required")
    if any(not isinstance(n, str) or not n or re.search(
            r"(^|_)(winner|result|payout|finish|rank|outcome|profit|label)(_|$)", n, re.I) for n in names):
        raise ValueError("declared features cannot contain outcome fields")
    if (not isinstance(epochs, int) or isinstance(epochs, bool) or epochs < 1
            or not math.isfinite(l2) or l2 < 0
            or not math.isfinite(learning_rate) or learning_rate <= 0):
        raise ValueError("invalid optimizer configuration")
    cutoff = _time(training_cutoff)
    rows.sort(key=lambda r: (_day(r["date"]), r["race_id"]))
    ids = [r["race_id"] for r in rows]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate training race")
    feature_times_verified = True
    outcome_times_verified = True
    for row in rows:
        feature_times_verified &= _validate(row, names)
        if _day(row["date"]) > cutoff.date().isoformat():
            raise ValueError("training race after training cutoff")
        if row.get("cutoff") and _time(row["cutoff"]) > cutoff:
            raise ValueError("training race prediction cutoff is after training cutoff")
        stamp = row.get("outcome_available_at")
        if stamp:
            if _time(stamp) > cutoff:
                raise ValueError("training outcome unavailable at training cutoff")
            if row.get("cutoff") and _time(stamp) < _time(row["cutoff"]):
                raise ValueError("outcome cannot precede prediction cutoff")
        else:
            outcome_times_verified = False
        winners = row.get("winner_ids", [])
        if (not winners or len(winners) != len(set(winners))
                or not set(winners).issubset(row["baseline_probabilities"])):
            raise ValueError("valid unique winner_ids required for training")
    scaling = {}
    for name in names:
        observed = [_number(r["features"][h].get(name)) for r in rows
                    for h in sorted(r["features"]) if r["features"][h].get(name) is not None]
        mean = sum(observed) / len(observed) if observed else 0.0
        variance = sum((x - mean) ** 2 for x in observed) / len(observed) if observed else 0.0
        scaling[name] = {"mean": mean, "std": math.sqrt(variance) if variance > 1e-12 else 1.0,
                         "observed_count": len(observed)}
    batches = []
    for row in rows:
        runners = sorted(row["baseline_probabilities"])
        x = [_vector(row["features"][h], names, scaling) for h in runners]
        offset = [math.log(row["baseline_probabilities"][h]) for h in runners]
        y = [1.0 / len(row["winner_ids"]) if h in row["winner_ids"] else 0.0 for h in runners]
        batches.append((x, offset, y))
    coefficients = [0.0] * (2 * len(names))

    def loss_gradient():
        loss, gradient = 0.0, [0.0] * len(coefficients)
        for x, offset, y in batches:
            logits = [b + sum(a * w for a, w in zip(v, coefficients)) for v, b in zip(x, offset)]
            p = _softmax(logits)
            peak = max(logits)
            logz = peak + math.log(sum(math.exp(z - peak) for z in logits))
            loss += sum(t * (logz - z) for t, z in zip(y, logits))
            for v, q, t in zip(x, p, y):
                for j, a in enumerate(v):
                    gradient[j] += a * (q - t)
        size = len(batches)
        loss = loss / size + 0.5 * l2 * sum(w * w for w in coefficients)
        gradient = [g / size + l2 * w for g, w in zip(gradient, coefficients)]
        return loss, gradient

    initial_loss, _ = loss_gradient()
    for _ in range(epochs):
        _, gradient = loss_gradient()
        coefficients = [w - learning_rate * g for w, g in zip(coefficients, gradient)]
        if any(not math.isfinite(w) for w in coefficients):
            raise ValueError("optimizer diverged")
    final_loss, _ = loss_gradient()
    model = {"schema": "prism.research.residual/v1", "feature_names": names,
             "encoded_features": [part for n in names for part in (n, n + ":missing")],
             "scaling": scaling, "coefficients": coefficients,
             "train_race_ids": ids, "train_min_date": _day(rows[0]["date"]),
             "train_max_date": _day(rows[-1]["date"]), "training_cutoff": cutoff.isoformat(),
             "train_input_hash": _hash(rows), "optimizer": {"name": "full_batch_gradient_descent",
             "epochs": epochs, "learning_rate": learning_rate, "l2": l2},
             "training_loss": {"initial": initial_loss, "final": final_loss},
             "feature_times_verified": feature_times_verified,
             "outcome_times_verified": outcome_times_verified,
             "source_authenticity_verified": False,
             "performance_validated": False}
    model["model_hash"] = _hash(model)
    return model


def predict_model(model, row):
    """Predict only later, unseen races; target labels are never consulted."""
    expected = _hash({k: v for k, v in model.items() if k != "model_hash"})
    if model.get("schema") != "prism.research.residual/v1" or model.get("model_hash") != expected:
        raise ValueError("model artifact hash mismatch")
    names = model["feature_names"]
    times_verified = _validate(row, names)
    if row["race_id"] in model["train_race_ids"] or _day(row["date"]) <= model["train_max_date"]:
        raise ValueError("prediction requires an unseen race on a later day")
    if row.get("cutoff") and _time(row["cutoff"]) <= _time(model["training_cutoff"]):
        raise ValueError("model was not fitted before prediction cutoff")
    # Dates without cutoff times still must be later than the fit cutoff's local day.
    if _day(row["date"]) <= _time(model["training_cutoff"]).date().isoformat():
        raise ValueError("prediction day must follow the training cutoff day")
    ids = sorted(row["baseline_probabilities"])
    vectors = [_vector(row["features"][h], names, model["scaling"]) for h in ids]
    coefficients = model["coefficients"]
    if all(w == 0 for w in coefficients):
        probabilities = {h: row["baseline_probabilities"][h] for h in ids}
    else:
        logits = [math.log(row["baseline_probabilities"][h]) + sum(v * w for v, w in zip(x, coefficients))
                  for h, x in zip(ids, vectors)]
        probabilities = dict(zip(ids, _softmax(logits)))
    prediction_input = {"race_id": row["race_id"], "date": _day(row["date"]),
                        "baseline_probabilities": row["baseline_probabilities"],
                        "features": {h: {n: row["features"][h].get(n) for n in names} for h in ids},
                        "cutoff": row.get("cutoff"), "feature_available_at": row.get("feature_available_at")}
    return {"race_id": row["race_id"], "probabilities": probabilities,
            "model_hash": model["model_hash"], "input_hash": _hash(prediction_input),
            "missing_rates": {n: sum(row["features"][h].get(n) is None for h in ids) / len(ids) for n in names},
            "feature_times_verified": times_verified,
            "source_authenticity_verified": False, "performance_validated": False}
