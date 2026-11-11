"""v48.7 LAB isolated tests. Run: python -m unittest -v test_shadow_lab_v487"""
import tempfile
import unittest
from pathlib import Path
from shadow_lab_v487 import ShadowLabV487


def sig(t=100, day="2026-11-11", direction="BUY", entry=100, sl=96):
    return dict(
        time=t, day=day, direction=direction, entry=entry, sl=sl,
        symbol="XAUUSD", mode="TREND_CONTINUATION", execution="SHADOW_ONLY",
        tp1=entry+3 if direction=="BUY" else entry-3, score=8
    )


class ShadowLabV487Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.lab = ShadowLabV487(str(Path(self.temp.name)/"state.json"), flush_every=1)
        self.day = "2026-11-11"

    def tearDown(self):
        self.temp.cleanup()

    def tick(self, data, stamp, signals=None):
        self.lab.observe(
            data={"symbol": "XAUUSD", **data},
            signals=signals or [], day=self.day, stamp=stamp, diagnostics=False
        )

    def tracks(self):
        return self.lab.report(self.day)["trades"][0]["tracks"]

    def test_tp3_then_be_for_longer_targets(self):
        source = [sig()]
        self.tick({"close": 100}, 100, source)
        self.tick({"close": 103.5, "high": 104, "low": 100.5}, 160, source)
        self.assertEqual(self.tracks()["TP3"]["status"], "TP")
        self.assertTrue(self.tracks()["TP6_BE3"]["be_active"])
        self.assertEqual(self.tracks()["TP6_BE3"]["status"], "OPEN")
        self.tick({"close": 100.8, "high": 102, "low": 99.5}, 220, source)
        self.assertEqual(self.tracks()["TP6_BE3"]["status"], "BE")
        self.assertEqual(self.tracks()["TP6_BE3"]["exit_points"], 0)
        self.assertEqual(self.tracks()["TP9_BE3"]["status"], "BE")

    def test_same_bar_be_is_ambiguous(self):
        source = [sig()]
        self.tick({"close": 100}, 100, source)
        self.tick({"close": 102, "high": 104.2, "low": 99.8}, 160, source)
        self.assertEqual(self.tracks()["TP3"]["status"], "TP")
        self.assertEqual(self.tracks()["TP6_BE3"]["status"], "AMBIGUOUS")
        self.assertIsNone(self.tracks()["TP6_BE3"]["exit_points"])

    def test_same_bar_tp_and_sl_is_ambiguous(self):
        source = [sig()]
        self.tick({"close": 100}, 100, source)
        self.tick({"close": 100, "high": 104, "low": 95}, 160, source)
        self.assertEqual(self.tracks()["TP3"]["status"], "AMBIGUOUS")
        self.assertEqual(self.tracks()["TP6_BE3"]["status"], "AMBIGUOUS")

    def test_close_only_fallback(self):
        source = [sig(direction="SELL", sl=105)]
        self.tick({"close": 100}, 100, source)
        self.tick({"close": 97}, 160, source)
        self.assertEqual(self.tracks()["TP3"]["status"], "TP")
        self.assertEqual(self.tracks()["TP3"]["source"], "CLOSE_ONLY")

    def test_never_retroactively_import_old_signals(self):
        self.tick({"close": 100}, 1000, [sig(t=100)])
        self.assertEqual(self.lab.report(self.day)["trades"], [])

    def test_b_and_d_rejection_diagnostics(self):
        forecast = {
            "preferred_zone_low": 98, "preferred_zone_high": 102,
            "live_status": "VALID"
        }
        closes = [100, 99, 98, 97, 96, 95, 95, 95.5, 96, 97, 98]
        history = [dict(close=p, high=p+.4, low=p-.4) for p in closes]
        self.lab.observe(
            data={"symbol": "XAUUSD", "close": 98}, signals=[],
            day=self.day, stamp=100, session="EUROPE", forecast=forecast,
            bias="SELL", m1={"confirmed": True, "direction": "BUY", "score": 8},
            history=history
        )
        diag = self.lab.report(self.day, include_trades=False)["diagnostics"]
        self.assertEqual(diag["B"]["M1_OPPOSITE_FORECAST"], 1)
        self.assertEqual(diag["D"]["D_ELIGIBLE_PRE_COOLDOWN"], 1)
        self.lab.observe(
            data={"symbol": "XAUUSD", "close": 105}, signals=[],
            day=self.day, stamp=160, session="EUROPE", forecast=forecast,
            bias="SELL", m1={"confirmed": False, "direction": "SELL", "score": 4},
            history=history
        )
        diag = self.lab.report(self.day, include_trades=False)["diagnostics"]
        self.assertEqual(diag["B"]["OUTSIDE_PREFERRED_ZONE"], 1)

    def test_state_save_and_reload(self):
        self.tick({"close": 100}, 100, [sig()])
        reopened = ShadowLabV487(
            str(Path(self.temp.name)/"state.json"), flush_every=1
        )
        self.assertEqual(len(reopened.report(self.day)["trades"]), 1)


if __name__ == "__main__":
    unittest.main()
