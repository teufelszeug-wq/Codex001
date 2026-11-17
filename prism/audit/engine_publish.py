"""Connect a completed engine prediction lock to verified pre-race publication.

This adapter never executes the engine or verifies an external racecard source.
"""
from .engine_batch_adapter import adapt_engine_lock
from .verified_batch import publish_verified_batch

def publish_engine_lock(directory, card, lock, *, predictor_id, version, source,
                        evidence, saved_at, now=None):
    if not isinstance(lock, dict) or not isinstance(card, dict):
        raise ValueError("card and engine lock must be mappings")
    if not isinstance(evidence, list) or not evidence:
        raise ValueError("source evidence required")
    for name, value in (("predictor_id", predictor_id), ("version", version), ("source", source)):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(name + " required")
    predictions = adapt_engine_lock(card, lock)
    return publish_verified_batch(directory, card, predictions,
        predictor_id=predictor_id, version=version, source=source,
        evidence=evidence, saved_at=saved_at, now=now)
