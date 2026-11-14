"""Read-only offline replay for SHADOW G v48.8. It NEVER connects to MT4.

Run: python replay_shadow_g_v488.py --m1 xauusd_m1.csv --output ./research_results
Requires UTC M1 candle CLOSE timestamps and truthful spread points, with
columns end_ts,open,high,low,close,spread_points. Each row is a completed bar.
"""
import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from shadow_g_v488 import ShadowG


def _parse_timestamp(raw):
    try:
        ts = float(raw)
        if ts > 1000000000 and ts.is_integer():
            return int(ts)
    except ValueError:
        pass
    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("Timestamp requires UTC offset (no naive datetimes)")
    return int(dt.astimezone(timezone.utc).timestamp())


def replay(path, *, guard=True):
    engine = ShadowG(spike_guard=guard)
    with Path(path).open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        required = {"end_ts", "open", "high", "low", "close", "spread_points"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError("M1 CSV requires columns: " + ", ".join(sorted(required)))
        n=0
        for line, row in enumerate(reader, 2):
            try:
                engine.push({
                    "end_ts": _parse_timestamp(row["end_ts"]),
                    "open": row["open"], "high": row["high"],
                    "low": row["low"], "close": row["close"],
                    "spread_points": row["spread_points"], "complete": True
                })
                n += 1
            except Exception as exc:
                raise ValueError(f"Invalid candle line {line}: {exc}") from exc
    return engine, n


def main():
    parser=argparse.ArgumentParser(description="SHADOW G offline M1 simulation, no broker orders")
    parser.add_argument("--m1", type=Path, required=True, help="broker M1 candle OHLC data with UTC close time")
    parser.add_argument("--output", type=Path, required=True, help="local research directory")
    parser.add_argument("--no-spike-guard", action="store_true", help="test a separate hypothetical scenario")
    args=parser.parse_args()
    engine, n = replay(args.m1, guard=not args.no_spike_guard)
    args.output.mkdir(parents=True, exist_ok=True)
    report = engine.report(include_trades=False)
    report["m1_candles_processed"] = n
    report["hypothetical_spike_guard_enabled"] = not args.no_spike_guard
    (args.output / "shadow_g_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False),encoding="utf-8")
    with (args.output / "shadow_g_signals.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["decision_ts_utc", "day_rome", "strategy", "side", "reference_close", "stop", "next_open_entry", "state", "TP3", "TP6", "TP9", "TP15", "TP25"])
        for t in engine.trades:
            w.writerow([datetime.fromtimestamp(t["decision_ts"], timezone.utc).isoformat(),
                        t["day"], t["mode"], t["side"], t["reference_close"],
                        t["sl"], t["entry"], t["state"],
                        *[t["tracks"].get(f"TP{int(x)}",{}).get("status", "NOT_FILLED") for x in (3,6,9,15,25)]])
    print(f"Processed {n} complete M1 candles, {len(engine.trades)} virtual hypotheses. No broker orders.")
    print("Results:", args.output)

if __name__ == "__main__":
    main()
