"""Smoke tests for v48.7 Flask routes without live webhook or broker calls."""
import tempfile
import unittest
from pathlib import Path

import app
from shadow_lab_v487 import ShadowLabV487


class V487AppSmokeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.prior_lab = app.V487_LAB
        app.V487_LAB = ShadowLabV487(
            path=str(Path(self.temp.name) / "lab.json"), flush_every=1
        )
        self.client = app.app.test_client()
        self.day = "2026-11-11"

    def tearDown(self):
        app.V487_LAB = self.prior_lab
        self.temp.cleanup()

    def test_empty_report_endpoints(self):
        for route in (
            "/v487/lab?day=2026-11-11",
            "/v487/diagnostics?day=2026-11-11",
        ):
            response = self.client.get(route)
            self.assertEqual(response.status_code, 200)
            body = response.get_json()
            self.assertEqual(body["version"], "48.7-LAB-ONLY")
            self.assertTrue(body["enabled"])
            self.assertEqual(body["execution"], "SHADOW_ONLY_NO_BROKER_ORDERS")

    def test_synthetic_observation_visible_through_flask(self):
        rows = [
            {"close": 99.0, "high": 99.3, "low": 98.7}
            for _ in range(11)
        ]
        event = {"symbol": "XAUUSD", "close": 100.0, "high": 100.2, "low": 99.8}
        self.signal = {
            "time": 100.0, "day": self.day, "symbol": "XAUUSD",
            "mode": "TREND_CONTINUATION", "direction": "BUY",
            "entry": 100.0, "sl": 96.0, "tp1": 103.0,
            "score": 8, "execution": "SHADOW_ONLY",
        }
        app.V487_LAB.observe(
            data=event, signals=[self.signal], day=self.day, stamp=100.0,
            session="EUROPE", forecast={
                "live_status": "VALID",
                "preferred_zone_low": 98.0,
                "preferred_zone_high": 102.0,
            },
            bias="BUY", m1={
                "confirmed": True, "direction": "BUY", "score": 8
            }, history=rows
        )
        payload = self.client.get("/v487/lab?day=" + self.day).get_json()
        self.assertEqual(len(payload["trades"]), 1)
        self.assertEqual(payload["diagnostics"]["updates"], 1)
        self.assertEqual(payload["diagnostics"]["B"]["B_ELIGIBLE_PRE_DEDUP"], 1)
        self.assertEqual(payload["scenarios"]["TP3"]["count"], 1)
        payload2 = self.client.get(
            "/v487/diagnostics?day=" + self.day
        ).get_json()
        self.assertEqual(payload2["diagnostics"]["updates"], 1)


if __name__ == "__main__":
    unittest.main()
