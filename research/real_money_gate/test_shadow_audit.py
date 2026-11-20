import unittest
from shadow_audit import analyze, dedup_opportunities, extract_lab_reports


def trade(mode, ts, points):
    return {
        "day": "2026-11-20", "mode": mode,
        "time": ts, "entry": 3569.18, "direction": "SELL",
        "tracks": {"TP3": {"status": "TP" if points > 0 else "SL",
                            "exit_points": points}}
    }


class ShadowAuditTests(unittest.TestCase):
    def test_simultaneous_modes_are_one_opportunity(self):
        a = trade("TREND_CONTINUATION", 1000.0, -4.775)
        b = trade("RANGE_M1_SCOUT", 1000.001, -6.0)
        self.assertEqual(len(dedup_opportunities([a, b])), 1)
        result = analyze([{"day": "2026-11-20", "trades": [a, b]}])
        self.assertEqual(result["raw_signals"], 2)
        self.assertEqual(result["distinct_opportunities"], 1)
        self.assertFalse(result["real_money_ready"])

    def test_no_silent_cost_assumption(self):
        row = trade("A_FORECAST_ANTICIPATORY", 1000, 3.0)
        report = [{"day": "2026-11-20", "trades": [row]}]
        self.assertIsNone(analyze(report)["by_mode"]["A_FORECAST_ANTICIPATORY"]["net_points_if_assumed_cost_known"])
        self.assertEqual(analyze(report, .4)["by_mode"]["A_FORECAST_ANTICIPATORY"]["net_points_if_assumed_cost_known"], 2.6)

    def test_pasted_json(self):
        payload = '{"version":"48.7-LAB-ONLY","day":"2026-11-20","trades":[]}'
        self.assertEqual(len(extract_lab_reports(payload)), 1)


if __name__ == "__main__":
    unittest.main()
