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


    def test_ghij_partial_be_and_old_baseline_separate(self):
        self.tick({"close": 100}, 100, [sig()])
        self.tick({"close": 103.5}, 160, [sig()])
        self.tick({"close": 100}, 220, [sig()])
        report = self.lab.report(self.day)
        exp = report["experiments_ghij"]
        self.assertEqual(report["scenarios"]["TP3"]["nominal_net_points_ex_costs"], 3)
        self.assertEqual(exp["J_PARTIAL_BE"]["outcomes"], {"PARTIAL_BE": 1})
        self.assertEqual(exp["J_PARTIAL_BE"]["nominal_net_points_ex_costs"], 1.5)
        self.assertEqual(exp["H_RISK_FILTER"]["LE_6"]["count"], 1)
        self.assertEqual(exp["I_ANTI_CHASE"]["UNKNOWN"]["count"], 1)
        self.assertEqual(exp["G_PULLBACK"]["stats"]["count"], 0)

    def test_j_all_targets_at_equal_exposure(self):
        self.tick({"close": 100}, 100, [sig()])
        self.tick({"close": 121.5}, 160, [sig()])
        result = self.lab.report(self.day)["experiments_ghij"]["J_PARTIAL_BE"]
        self.assertEqual(result["outcomes"], {"TP_ALL": 1})
        self.assertEqual(result["nominal_net_points_ex_costs"], 9)

    def test_g_new_pullback_and_cooldown_without_baseline_change(self):
        prices = [100,101,102,103,104,105,104,103,102.5,103,103.2,104]
        def observe(stamp):
            history = [dict(time=stamp-(11-i)*60, close=p, high=p+.2, low=p-.2)
                       for i,p in enumerate(prices)]
            self.lab.observe(data={"symbol":"XAUUSD","close":104}, signals=[],
                             day=self.day, stamp=stamp, session="EUROPE",
                             forecast={"live_status":"VALID"}, bias="BUY",
                             m1={"confirmed":True,"direction":"BUY","score":8},
                             history=history)
        observe(1000)
        observe(1060)
        result = self.lab.report(self.day)
        g = result["experiments_ghij"]["G_PULLBACK"]
        self.assertEqual(result["scenarios"]["TP3"]["count"], 0)
        self.assertEqual(g["stats"]["count"], 1)
        self.assertEqual(g["reasons"]["COOLDOWN"], 1)
        self.assertEqual(g["trades"][0]["execution"] if "execution" in g["trades"][0] else result["execution"], "SHADOW_ONLY_NO_BROKER_ORDERS")
        restored = ShadowLabV487(self.lab.path, flush_every=1)
        self.assertEqual(restored.report(self.day)["experiments_ghij"]["G_PULLBACK"]["stats"]["count"], 1)

    def test_anti_chase_spike_block(self):
        history = [dict(close=100+i, high=100+i+.2, low=100+i-.2)
                   for i in range(12)]
        history[-1]["high"] += 9
        self.assertEqual(self.lab._anti_chase(history,"BUY")["status"], "BLOCK")


if __name__ == "__main__":
    unittest.main()
