"""Best-effort, non-trading persistence for GOLD MASTER research labs v48/v48.6/v48.7.

Uses the same existing PostgreSQL secret as SHADOW G v48.18.
Only research state dictionaries are stored; no MT4 tokens, positions or broker actions.
A bounded, coalescing asynchronous writer keeps database I/O off the webhook path.
"""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


DDL = """CREATE TABLE IF NOT EXISTS shadow_research_snapshots (
    kind TEXT NOT NULL,
    period TEXT NOT NULL,
    payload JSONB NOT NULL,
    saved_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY(kind, period)
)"""
UPSERT = """INSERT INTO shadow_research_snapshots(kind, period, payload)
            VALUES (%s, %s, %s::jsonb)
            ON CONFLICT(kind, period) DO UPDATE
              SET payload=EXCLUDED.payload, saved_at=NOW()"""


def _dsn_from_existing_settings():
    value = os.getenv("SHADOW_V4818_DATABASE_URL", "").strip()
    if value:
        return value
    try:
        with open("/etc/secrets/shadow_v4818_db_url", encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return ""


def _today_italy():
    return datetime.now(ZoneInfo("Europe/Rome")).strftime("%Y-%m-%d")


class ResearchSnapshotStore:
    """At most one in-flight queued snapshot per lab: latest state wins."""

    def __init__(self, dsn=None, connect_timeout=3):
        self._dsn = _dsn_from_existing_settings() if dsn is None else dsn
        self._timeout = int(connect_timeout)
        self._lock = threading.Lock()
        self._pending = {}
        self._wake = threading.Event()
        self._worker = None
        self._saved = 0
        self._errors = 0
        self._last_error = None
        self._last_saved = None
        self._restored = {}

    def _connect(self):
        # Do not import psycopg2 unless PostgreSQL persistence is configured.
        import psycopg2
        conn = psycopg2.connect(
            self._dsn, connect_timeout=self._timeout,
            application_name="GOLD_MASTER_SHADOW_LABS"
        )
        conn.autocommit = False
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = '5000ms'")
            cur.execute(DDL)
        conn.commit()
        return conn

    def restore(self, kind):
        """Attempt once during application startup; never change trading logic."""
        if not self._dsn:
            return None
        conn = None
        try:
            conn = self._connect()
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT payload FROM shadow_research_snapshots "
                    "WHERE kind=%s AND period='LATEST'", (kind,)
                )
                row = cur.fetchone()
            self._restored[kind] = bool(row)
            return row[0] if row and isinstance(row[0], dict) else None
        except Exception as exc:
            self._error(exc, "RESTORE")
            return None
        finally:
            if conn is not None:
                conn.close()

    def archive(self, kind, state):
        """Non-blocking database I/O; serialization prevents mutable state races."""
        if not self._dsn or kind not in ("V48", "V487") or not isinstance(state, dict):
            return False
        try:
            payload = json.dumps(state, ensure_ascii=False, allow_nan=False,
                                 separators=(",", ":"))
        except (ValueError, TypeError) as exc:
            self._error(exc, "SERIALIZE")
            return False
        with self._lock:
            self._pending[kind] = (payload, _today_italy())
            if self._worker is None or not self._worker.is_alive():
                self._worker = threading.Thread(
                    target=self._write_loop, name="shadow-research-pg",
                    daemon=True
                )
                self._worker.start()
        self._wake.set()
        return True

    def _error(self, exc, phase):
        with self._lock:
            self._errors += 1
            self._last_error = phase + ":" + type(exc).__name__
        print("[SHADOW RESEARCH PG] " + phase + " " +
              type(exc).__name__, flush=True)

    def _write_loop(self):
        conn = None
        while True:
            self._wake.wait(timeout=60)
            self._wake.clear()
            with self._lock:
                batch = self._pending
                self._pending = {}
            if not batch:
                continue
            try:
                if conn is None or conn.closed:
                    conn = self._connect()
                with conn.cursor() as cur:
                    for kind, (payload, day) in batch.items():
                        cur.execute(UPSERT, (kind, "LATEST", payload))
                        cur.execute(UPSERT, (kind, day, payload))
                conn.commit()
                with self._lock:
                    self._saved += len(batch)
                    self._last_saved = datetime.now(timezone.utc).isoformat(
                        timespec="seconds"
                    )
            except Exception as exc:
                self._error(exc, "SAVE")
                if conn is not None:
                    try:
                        conn.rollback()
                        conn.close()
                    except Exception:
                        pass
                conn = None
                with self._lock:
                    # Never overwrite a newer state that may have arrived meanwhile.
                    for kind, value in batch.items():
                        self._pending.setdefault(kind, value)
                # Retry promptly, without blocking webhooks.
                self._wake.wait(timeout=10)
                self._wake.set()

    def status(self):
        with self._lock:
            return {
                "configured": bool(self._dsn),
                "persistence": "POSTGRES" if self._dsn else "UNCONFIGURED",
                "writer_alive": bool(self._worker and self._worker.is_alive()),
                "pending_kinds": sorted(self._pending),
                "saved_batches": self._saved,
                "errors": self._errors,
                "last_error_type": self._last_error,
                "last_saved_utc": self._last_saved,
                "restored_kinds": dict(self._restored),
                "live_trading_changed": False,
                "note": "In-process counters reset on restart. Period snapshots persist in PostgreSQL."
            }


snapshot_store = ResearchSnapshotStore()
