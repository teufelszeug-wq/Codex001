"""Connect a verified official racecard and an already-produced engine lock.

This does NOT run the engine, fetch official data, or assert independent AI execution.
"""
from .engine_batch_adapter import adapt_engine_lock
from .verified_batch import publish_verified_batch


def publish_engine_lock(directory, card, lock, *, predictor_id, version,
                        source, evidence, saved_at, now=None):
    """Validate the engine lock and atomically archive the full pre-race field.

    The caller must provide independently verified official racecard provenance,
    a real engine output, and evidence timestamps available before saved_at.
    """
    if not isinstance(card, dict) or not isinstance(lock, dict):
        raise ValueError("card and lock must be objects")
    if not isinstance(predictor_id, str) or not predictor_id.strip():
        raise ValueError("predictor_id required")
    if not isinstance(version, str) or not version.strip():
        raise ValueError("version required")
    if not isinstance(source, str) or not source.strip():
        raise ValueError("source required")
    predictions = adapt_engine_lock(card, lock)
    return publish_verified_batch(
        directory, card, predictions, predictor_id=predictor_id,
        version=version, source=source, evidence=evidence,
        saved_at=saved_at, now=now,
    )
