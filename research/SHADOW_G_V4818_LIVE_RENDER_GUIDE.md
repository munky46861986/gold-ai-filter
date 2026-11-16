# SHADOW G v48.18 — Passive Render Observer
**Research-only.** This feature does not call MT4, queue trades, modify Forecast, change entry filters, or adjust risk settings.
The only touch points in `app.py` are AFTER `process_live_director` and AFTER broker-event state saving. They catch all observer exceptions.

## Environment
- `SHADOW_V4818_ENABLED=false` by default.
- Set `SHADOW_V4818_ENABLED=true` to record qualifying Director observations (up to one per minute per symbol/session/direction/forecast state) and all created campaigns; the broker state is logged separately on OPENED/CLOSED.
- `SHADOW_V4818_DATABASE_URL=postgresql://...` is **optional** for startup; when present it uses asynchronous idempotent PostgreSQL INSERTs. Never put this URL in logs, GitHub, or chat.
- Without a DATABASE_URL, observations appear in Render's private service logs prefixed `SHADOW_V4818_RECORD`; **this is TEMPORARY, NOT A DURABLE ARCHIVE**.
- The free PostgreSQL instance `shadow-g-v4818` created 16 Nov 2026 expires **16 Dec 2026**. Export data or migrate before that date. No paid subscription was chosen.
- `GET /shadow/v4818/status` gives only safe counters and a persistence mode; no tokens/account numbers are exposed.
- If DB inaccessible, queue is bounded; drops and errors reported by /shadow/v4818/status. Nothing fails closed into trading.
- Price snapshots are current, not independently verified MT4 quotes. Broker PnL events remain UNVERIFIED until reconciled with broker history.

## Do NOT
- Promote research sample RR>=0.50 to order logic.
- Interpret CAMPAIGN_CREATED as a broker fill.
- Interpret TEMPORARY_RENDER_LOGS as persistent.
- Add any missing broker credential through this feature.
- Enable trading just to produce SHADOW telemetry.

## Testing
```sh
python -m py_compile app.py shadow_g_v4818_live.py
python -m unittest -q test_shadow_v4818_live research.shadow_g_v4818.test_shadow_g_v4818
```
Expected: 30 tests. Imported module has no network call until the first event and only if enabled.
