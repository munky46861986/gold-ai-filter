"""Read-only, best-effort SHADOW G v48.18 live telemetry to Render logs or optional Postgres.

Does not import broker queue or call MetaTrader APIs. Fail-open on ALL errors.
Defaults to logs-only mode, no extra Render env vars required.
Optional PostgreSQL writes use SHADOW_V4818_DATABASE_URL or the Render secret file
/etc/secrets/shadow_v4818_db_url; SHADOW_V4818_ENABLED=false disables telemetry.
PostgreSQL writes are asynchronous; logs-only mode records allowlisted data.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from queue import Queue, Full, Empty
import threading
import time
import uuid

from research.shadow_g_v4818.decision_adapter_v4818 import from_director_context
from research.shadow_g_v4818.shadow_g_v4818_recorder import normalize


DDL = '''CREATE TABLE IF NOT EXISTS shadow_g_v4818_events (
    event_id TEXT PRIMARY KEY,
    event_ts TIMESTAMPTZ NOT NULL,
    event_kind TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)'''
INSERT = '''INSERT INTO shadow_g_v4818_events(event_id, event_ts, event_kind, payload)
            VALUES (%s,%s,%s,CAST(%s AS JSONB))
            ON CONFLICT (event_id) DO NOTHING'''


def env_enabled(value):
    return str(value or '').strip().lower() in ('1', 'true', 'yes', 'on')


def _ts():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


class ShadowV4818Live:
    """Bounded queue, isolated writer; no synchronous DB I/O in producer thread."""

    def __init__(self, *, enabled=None, dsn=None, queue_max=4000, write_timeout=5):
        self.enabled = env_enabled(os.getenv('SHADOW_V4818_ENABLED', 'true')) if enabled is None else bool(enabled)
        # Prefer existing env configuration; a Render Secret File avoids consuming another env slot.
        # Never log either connection string or file contents.
        if dsn is not None:
            self._dsn = dsn or ''
        else:
            self._dsn = os.getenv('SHADOW_V4818_DATABASE_URL', '').strip()
            if not self._dsn:
                try:
                    with open('/etc/secrets/shadow_v4818_db_url', encoding='utf-8') as secret:
                        self._dsn = secret.read().strip()
                except OSError:
                    self._dsn = ''
        self._queue = Queue(maxsize=queue_max)
        self._write_timeout = int(write_timeout)
        self._thread = None
        self._lock = threading.Lock()
        self._samples = {}
        self._metrics = {'accepted': 0, 'saved': 0, 'duplicates': 0,
                         'dropped': 0, 'errors': 0, 'logged': 0, 'last_saved_utc': None,
                         'last_queued_utc': None, 'last_error_type': None}

    @property
    def ready(self):
        return self.enabled

    def status(self):
        with self._lock:
            metrics = dict(self._metrics)
        return {
            'version': '48.18-live',
            'enabled': self.enabled,
            'database_configured': bool(self._dsn),
            'writer_alive': bool(self._thread and self._thread.is_alive()),
            'queue_pending': self._queue.qsize(),
            'metrics_since_process_start': metrics,
            'persistence': 'POSTGRES' if self._dsn else 'RENDER_LOGS_LIMITED_RETENTION',
            'live_trading_changed': False,
            'warning': ('No durable archive until Postgres URL is configured; Render logs expire.' if not self._dsn else 'Counters reset on process restart; use PostgreSQL for historical totals.')
        }

    def _start(self):
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._thread = threading.Thread(target=self._writer, name='shadow4818-pg', daemon=True)
            self._thread.start()

    def _metric(self, key, value=None):
        with self._lock:
            if value is None:
                self._metrics[key] = self._metrics.get(key, 0) + 1
            else:
                self._metrics[key] = value

    def push(self, raw):
        """Never raises into trading code; prevents storing unrecognized fields/secrets."""
        if not self.ready:
            return False
        try:
            event = normalize(raw)
            if not self._dsn:
                # Temporary diagnostic fallback; no tokens, accounts or unknown fields.
                print('SHADOW_V4818_RECORD '+json.dumps(event,sort_keys=True,separators=(',',':')), flush=True)
                self._metric('accepted')
                self._metric('logged')
                self._metric('last_queued_utc',event['timestamp'])
                return True
            self._queue.put_nowait(event)
            self._metric('accepted')
            self._metric('last_queued_utc', event['timestamp'])
            self._start()
            return True
        except Full:
            self._metric('dropped')
            return False
        except Exception:
            self._metric('errors')
            self._metric('last_error_type', 'VALIDATION')
            return False

    def _writer(self):
        conn = None
        while True:
            try:
                event = self._queue.get(timeout=60)
            except Empty:
                continue
            try:
                if conn is None or conn.closed:
                    # Imports occur ONLY in the writer thread, never in the live decision path.
                    import psycopg2
                    conn = psycopg2.connect(self._dsn, connect_timeout=self._write_timeout,
                                            application_name='SHADOW_G_V4818')
                    conn.autocommit = True
                    with conn.cursor() as cur:
                        cur.execute("SET statement_timeout = '2500ms'")
                        cur.execute(DDL)
                with conn.cursor() as cur:
                    cur.execute(INSERT, (event['event_id'], event['timestamp'],
                                         event['event_kind'], json.dumps(event, sort_keys=True)))
                    changed = cur.rowcount
                self._metric('saved' if changed else 'duplicates')
                self._metric('last_saved_utc', _ts())
            except Exception as exc:
                self._metric('errors')
                self._metric('last_error_type', type(exc).__name__)
                try:
                    if conn:
                        conn.close()
                except Exception:
                    pass
                conn = None
                # Do not discard the failed event; retry after a bounded delay.
                # The queue is bounded: overlong outages are visible in dropped count.
                time.sleep(5)
                try:
                    self._queue.put_nowait(event)
                except Full:
                    self._metric('dropped')
            finally:
                self._queue.task_done()

    def _sample(self, *, symbol, session, forecast_status, candidate, price, triggered, significant, reason, action):
        """At most one ordinary observation per minute per side/status; never hide triggers."""
        if triggered:
            return True
        now = int(time.time() // 60)
        key = (symbol, session, forecast_status, candidate, now)
        with self._lock:
            if key in self._samples:
                return False
            if len(self._samples) > 500:
                self._samples = {k:v for k,v in self._samples.items() if k[-1] >= now-3}
            self._samples[key] = True
        return significant

    def capture_director(self, *, symbol, session, price, forecast=None,
                         fast_thesis=None, m1=None, campaign_result=None,
                         director_result=None, trade=None):
        if not self.ready:
            return False
        try:
            m1 = m1 or {}
            forecast = forecast or {}
            fast_thesis = fast_thesis or {}
            campaign_result = campaign_result or {}
            director_result = director_result or {}
            trade = trade or {}
            direction = (trade.get('direction') if campaign_result.get('triggered') else m1.get('direction')) or 'UNKNOWN'
            triggered = bool(campaign_result.get('triggered'))
            significant = bool(m1.get('confirmed') and str(direction).upper() in ('BUY','SELL'))
            significant |= bool(campaign_result.get('risk_blocked') or
                                campaign_result.get('entry_quality_blocked') or
                                campaign_result.get('ghost_prevented'))
            significant |= str(forecast.get('live_status') or '').upper() in ('WEAKENING','INVALIDATED','REASSESSING')
            if not significant and not triggered:
                return False
            if not self._sample(symbol=symbol, session=session,
                                forecast_status=str(forecast.get('live_status') or 'UNKNOWN'),
                                candidate=direction, price=price,
                                triggered=triggered, significant=significant,
                                reason=campaign_result.get('reason'),
                                action=director_result.get('action')):
                return False
            # Thesis from previous sessions is NOT a valid confirmation for this session.
            if str(fast_thesis.get('stable_session') or '').upper() != str(session).upper():
                fast_thesis = {'stable_preferred': 'UNKNOWN', 'candidate_count': None}
            event = from_director_context(
                event_id='D4818:'+uuid.uuid4().hex, timestamp=_ts(),
                symbol=symbol,session=session or 'UNKNOWN',price=price,
                forecast=forecast,fast_thesis=fast_thesis,m1=m1,
                campaign_result=campaign_result,director_result=director_result,
                candidate_direction=direction,trade=trade)
            return self.push(event)
        except Exception:
            self._metric('errors')
            self._metric('last_error_type', 'CAPTURE_DECISION')
            return False

    def capture_broker_event(self, row):
        """Broker event is explicitly unverified until reconciled with actual MT4 day history."""
        if not self.ready or not isinstance(row, dict):
            return False
        try:
            state=str(row.get('event') or '').upper()
            if state not in ('OPENED','CLOSED'):
                return False
            trade_id=str(row.get('trade_id') or '')
            if not trade_id:
                return False
            payload={
                'event_id':'B4818:'+uuid.uuid4().hex,
                'timestamp':_ts(), 'event_kind':'BROKER_EVENT',
                'source':'MT4_BRIDGE_EVENT',
                'symbol':'XAUUSD','session':'UNKNOWN','trade_ref':trade_id,
                'broker_state':state,
                'broker_pnl_eur':row.get('pnl') if state=='CLOSED' else None,
            }
            return self.push(payload)
        except Exception:
            self._metric('errors')
            self._metric('last_error_type', 'CAPTURE_BROKER')
            return False


observer = ShadowV4818Live()