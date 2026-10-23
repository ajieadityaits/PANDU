import unittest
from pathlib import Path
import sys


SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

from pandu.config import DecisionConfig
from pandu.decision import DecisionEngine
from pandu.domain import Detection, Zone


def make_engine(**overrides):
    settings = {
        "cooldown_seconds": 6.0,
        "stability_frames": 2,
        "center_bonus": 2.0,
        "area_multiplier": 10.0,
        "confidence_multiplier": 1.0,
    }
    settings.update(overrides)
    return DecisionEngine(
        DecisionConfig(**settings),
        class_weights={"chair": 6, "car": 10},
        translations={"chair": "kursi", "car": "mobil"},
    )


class DecisionEngineTests(unittest.TestCase):
    def test_zone_boundaries(self):
        engine = make_engine()
        self.assertIs(engine.determine_zone(100, 900), Zone.LEFT)
        self.assertIs(engine.determine_zone(450, 900), Zone.CENTER)
        self.assertIs(engine.determine_zone(800, 900), Zone.RIGHT)

    def test_ignored_class_is_not_candidate(self):
        engine = make_engine()
        unknown = Detection("banana", 0.99, 100, 100, 300, 300)
        self.assertIsNone(engine.best_candidate([unknown], 900, 600))

    def test_higher_risk_vehicle_wins(self):
        engine = make_engine()
        chair = Detection("chair", 0.95, 300, 100, 650, 550)
        car = Detection("car", 0.80, 50, 100, 250, 400)
        best = engine.best_candidate([chair, car], 900, 600)
        self.assertIsNotNone(best)
        self.assertEqual(best.detection.label, "car")

    def test_stability_and_cooldown(self):
        engine = make_engine()
        chair = Detection("chair", 0.90, 350, 100, 550, 500)

        self.assertIsNone(engine.select_alert([chair], 900, 600, now=0.0))
        first = engine.select_alert([chair], 900, 600, now=0.1)
        self.assertIsNotNone(first)
        self.assertEqual(first.message, "Terdeteksi, kursi di depan.")

        self.assertIsNone(engine.select_alert([chair], 900, 600, now=2.0))
        repeated = engine.select_alert([chair], 900, 600, now=6.2)
        self.assertIsNotNone(repeated)

    def test_vehicle_uses_warning_prefix(self):
        engine = make_engine(stability_frames=1)
        car = Detection("car", 0.90, 350, 100, 550, 500)
        alert = engine.select_alert([car], 900, 600, now=0.0)
        self.assertIsNotNone(alert)
        self.assertEqual(alert.message, "Perhatian, mobil di depan.")

    def test_different_supported_object_is_announced_without_waiting_old_cooldown(self):
        engine = make_engine(stability_frames=2, cooldown_seconds=30.0)
        chair = Detection("chair", 0.90, 350, 100, 550, 500)
        car = Detection("car", 0.90, 350, 100, 550, 500)

        self.assertIsNone(engine.select_alert([chair], 900, 600, now=0.0))
        first = engine.select_alert([chair], 900, 600, now=0.1)
        self.assertIsNotNone(first)
        self.assertIsNone(engine.select_alert([car], 900, 600, now=0.2))
        second = engine.select_alert([car], 900, 600, now=0.3)

        self.assertIsNotNone(second)
        self.assertEqual(second.message, "Perhatian, mobil di depan.")


if __name__ == "__main__":
    unittest.main()
