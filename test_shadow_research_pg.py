"""Isolated tests for durable research snapshots, without PostgreSQL or MT4."""
import json
import tempfile
import unittest
from pathlib import Path

from shadow_research_pg import ResearchSnapshotStore
from shadow_lab_v487 import ShadowLabV487, VERSION


class FakeCursor:
    def __init__(self, db):
        self.db = db
        self.fetched = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=None):
        if "SELECT payload" in sql:
            self.fetched = (self.db.rows.get((params[0], "LATEST")),)
        elif "INSERT INTO shadow_research_snapshots" in sql:
            kind, period, payload = params
            self.db.rows[(kind, period)] = json.loads(payload)
        else:
            self.db.calls.append(sql)

    def fetchone(self):
        return self.fetched if self.fetched and self.fetched[0] is not None else None


class FakeConnection:
    closed = False

    def __init__(self, db):
        self.db = db

    def cursor(self):
        return FakeCursor(self.db)

    def commit(self):
        self.db.commits += 1

    def rollback(self):
        pass

    def close(self):
        self.closed = True


class FakeDb:
    def __init__(self):
        self.rows = {}
        self.calls = []
        self.commits = 0

    def connect(self):
        return FakeConnection(self)


class TestResearchPersistence(unittest.TestCase):
    def test_not_configured_is_nonblocking(self):
        store = ResearchSnapshotStore(dsn="")
        self.assertIsNone(store.restore("V487"))
        self.assertFalse(store.archive("V487", {"version": VERSION}))
        self.assertFalse(store.status()["configured"])

    def test_restore_latest_db_snapshot(self):
        db = FakeDb()
        db.rows[("V487", "LATEST")] = {
            "version": VERSION, "days": {"2026-11-23": {"updates": 300}},
            "trades": {"sample": {"mode": "B_FORECAST_M1"}}
        }
        store = ResearchSnapshotStore(dsn="dummy")
        store._connect = db.connect
        restored = store.restore("V487")
        self.assertEqual(restored["days"]["2026-11-23"]["updates"], 300)
        self.assertTrue(store.status()["restored_kinds"]["V487"])

    def test_snapshot_sql_saves_latest_and_daily_rows(self):
        db = FakeDb()
        store = ResearchSnapshotStore(dsn="dummy")
        store._connect = db.connect
        store.archive("V48", {"version": "48.3-shadow-research-only",
                              "signals": [{"day": "2026-11-23"}], "last": {}})
        import time
        deadline = time.monotonic() + 2
        while store.status()["saved_batches"] < 1 and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertEqual(store.status()["saved_batches"], 1)
        self.assertIn(("V48", "LATEST"), db.rows)
        self.assertEqual(db.rows[("V48", "LATEST")]["signals"][0]["day"],
                         "2026-11-23")
        self.assertEqual(len(db.rows), 2)

    def test_lab_restores_and_archives_after_flush(self):
        restored = {"version": VERSION,
                    "days": {"2026-11-23": {"B": {}, "D": {}, "samples": [], "updates": 1}},
                    "trades": {"prior": {"mode": "B_FORECAST_M1"}}}
        seen = []
        with tempfile.TemporaryDirectory() as tmp:
            lab = ShadowLabV487(
                path=str(Path(tmp) / "v487.json"),
                flush_every=1,
                restore_callback=lambda kind: restored if kind == "V487" else None,
                archive_callback=lambda kind, state: seen.append(
                    (kind, state["version"]))
            )
            self.assertIn("prior", lab.state["trades"])
            lab._mark()
            self.assertEqual(seen, [("V487", VERSION)])
            self.assertTrue((Path(tmp) / "v487.json").is_file())

    def test_invalid_restored_payload_does_not_replace_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            lab = ShadowLabV487(
                path=str(Path(tmp) / "v487.json"),
                restore_callback=lambda kind: {"version": VERSION, "days": "BAD"}
            )
            self.assertIsInstance(lab.state["days"], dict)
            self.assertEqual(lab.state["trades"], {})


if __name__ == "__main__":
    unittest.main()
