import copy
import unittest

from prism_research_models import fit_model, predict_model


def row(race, day, *, winner="h1", signal=1.0):
    return {"race_id": race, "date": day,
            "baseline_probabilities": {"h1": 0.4, "h2": 0.6},
            "features": {"h1": {"jockey_signal": signal},
                         "h2": {"jockey_signal": -signal}},
            "winner_ids": [winner]}


def fit(rows=None, names=None, **kw):
    return fit_model(rows or [row("train1", "20260101"), row("train2", "2026-01-02")],
                     ["jockey_signal"] if names is None else names,
                     training_cutoff="2026-01-15T23:59:59+09:00", **kw)


class ResidualModelTests(unittest.TestCase):
    def test_learns_and_is_deterministic(self):
        model = fit()
        self.assertEqual(model, fit())
        self.assertGreater(model["coefficients"][0], 0)
        self.assertLess(model["training_loss"]["final"], model["training_loss"]["initial"])
        pred = predict_model(model, row("test", "20260116"))
        self.assertGreater(pred["probabilities"]["h1"], 0.4)
        self.assertAlmostEqual(sum(pred["probabilities"].values()), 1)
        self.assertFalse(pred["source_authenticity_verified"])

    def test_row_and_runner_order_do_not_change_fitted_artifact(self):
        rows = [row("a", "20260101"), row("b", "20260102")]
        expected = fit(rows)
        rows.reverse()
        for raw in rows:
            raw["features"] = dict(reversed(list(raw["features"].items())))
            raw["baseline_probabilities"] = dict(reversed(list(raw["baseline_probabilities"].items())))
        self.assertEqual(expected, fit(rows))

    def test_missingness_has_a_trainable_coefficient(self):
        rows = [row("a", "20260101"), row("b", "20260102")]
        for raw in rows:
            raw["features"]["h1"]["jockey_signal"] = None
            raw["features"]["h2"]["jockey_signal"] = 0
        model = fit(rows)
        self.assertGreater(model["coefficients"][1], 0)
        target = copy.deepcopy(rows[0])
        target.update(race_id="test", date="20260116")
        del target["winner_ids"]
        self.assertGreater(predict_model(model, target)["probabilities"]["h1"], 0.4)

    def test_zero_extra_features_exactly_preserves_baseline(self):
        pred = predict_model(fit(names=[]), row("test", "20260116"))
        self.assertEqual(pred["probabilities"], {"h1": 0.4, "h2": 0.6})

    def test_outcome_and_unused_fields_do_not_change_prediction(self):
        model = fit()
        raw = row("test", "20260116")
        expected = predict_model(model, raw)
        raw["winner_ids"] = ["h2"]
        raw["outcome_available_at"] = "2026-01-16T15:00:00+09:00"
        raw["features"]["h1"]["not_selected"] = 99999
        self.assertEqual(expected, predict_model(model, raw))

    def test_train_only_scaling_and_holdout_is_read_only(self):
        model = fit()
        before = copy.deepcopy(model)
        raw = row("test", "20260116", signal=9999)
        predict_model(model, raw)
        self.assertEqual(model, before)
        self.assertEqual(model["scaling"]["jockey_signal"]["mean"], 0)
        self.assertEqual(model["scaling"]["jockey_signal"]["std"], 1)

    def test_missing_features_and_all_missing_training(self):
        rows = [row("a", "20260101"), row("b", "20260102")]
        rows[0]["features"]["h1"]["jockey_signal"] = None
        model = fit(rows)
        raw = row("test", "20260116")
        raw["features"]["h2"] = {}
        pred = predict_model(model, raw)
        self.assertEqual(pred["missing_rates"], {"jockey_signal": 0.5})
        model = fit(names=["unknown"])
        self.assertEqual(model["scaling"]["unknown"]["observed_count"], 0)
        self.assertEqual(predict_model(model, raw)["missing_rates"], {"unknown": 1.0})

    def test_duplicate_and_overlap_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            fit([row("a", "20260101"), row("a", "20260102")])
        model = fit()
        for race, day in (("train1", "20260116"), ("new", "20260102"), ("new", "20260115")):
            with self.assertRaises(ValueError):
                predict_model(model, row(race, day))

    def test_training_cutoff_and_available_outcome_guard(self):
        with self.assertRaisesRegex(ValueError, "after training cutoff"):
            fit([row("a", "20260116")])
        raw = row("a", "20260101")
        raw["outcome_available_at"] = "2026-01-16T00:00:00+09:00"
        with self.assertRaisesRegex(ValueError, "outcome unavailable"):
            fit([raw])

    def test_feature_timestamp_guard_and_verification_disclosure(self):
        raw = row("test", "20260116")
        raw["cutoff"] = "2026-01-16T10:00:00+09:00"
        raw["feature_available_at"] = {h: {"jockey_signal": "2026-01-15T00:00:00+09:00"}
                                       for h in ("h1", "h2")}
        self.assertTrue(predict_model(fit(), raw)["feature_times_verified"])
        raw["feature_available_at"]["h1"]["jockey_signal"] = "2026-01-16T11:00:00+09:00"
        with self.assertRaisesRegex(ValueError, "unavailable"):
            predict_model(fit(), raw)

    def test_prediction_cannot_precede_model_fit(self):
        raw = row("test", "20260116")
        raw["cutoff"] = "2026-01-15T10:00:00+09:00"
        with self.assertRaisesRegex(ValueError, "before prediction cutoff"):
            predict_model(fit(), raw)

    def test_invalid_inputs_and_outcome_feature_rejected(self):
        for value in (float("nan"), float("inf"), True, "1"):
            raw = row("a", "20260101", signal=1)
            raw["features"]["h1"]["jockey_signal"] = value
            with self.assertRaises(ValueError):
                fit([raw])
        for name in ("winner_id", "finish_rank", "result", "profit"):
            with self.assertRaisesRegex(ValueError, "outcome fields"):
                fit(names=[name])
        raw = row("a", "20260101")
        raw["winner_ids"] = ["unknown"]
        with self.assertRaisesRegex(ValueError, "winner_ids"):
            fit([raw])
        raw = row("a", "20260101")
        raw["baseline_probabilities"]["h1"] = 0
        with self.assertRaisesRegex(ValueError, "positive"):
            fit([raw])

    def test_dead_heat_and_artifact_integrity(self):
        raw = row("a", "20260101")
        raw["winner_ids"] = ["h1", "h2"]
        model = fit([raw])
        pred = predict_model(model, row("test", "20260116"))
        self.assertGreater(pred["probabilities"]["h1"], 0.4)
        model["coefficients"][0] += 0.01
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            predict_model(model, row("test", "20260116"))


if __name__ == "__main__":
    unittest.main()
