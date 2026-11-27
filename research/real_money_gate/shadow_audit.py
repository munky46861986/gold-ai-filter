#!/usr/bin/env python3
"""Offline GOLD MASTER v48.7 readiness audit. Never calls MT4, broker or network."""
import argparse
import json
from pathlib import Path


def extract_lab_reports(text):
    reports = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and value.get("version") == "48.7-LAB-ONLY":
            if not isinstance(value.get("trades"), list):
                raise ValueError("v48.7 report missing trades")
            reports.append(value)
    return reports


def dedup_opportunities(rows, tolerance_seconds=2.0):
    """Same-day/side/entry and 2-second time grouping; outcome still mode-specific."""
    groups = []
    for row in sorted(rows, key=lambda r: (r["day"], float(r["time"]))):
        found = next((g for g in groups
                      if g[0]["day"] == row["day"]
                      and g[0]["direction"] == row["direction"]
                      and abs(float(g[0]["entry"]) - float(row["entry"])) < .001
                      and abs(float(g[0]["time"]) - float(row["time"])) <= tolerance_seconds), None)
        if found is None:
            groups.append([row])
        else:
            found.append(row)
    return groups


def analyze(reports, cost_points=None):
    if cost_points is not None and cost_points < 0:
        raise ValueError("Cost cannot be negative")
    rows = []
    for report in reports:
        for trade in report["trades"]:
            track = trade.get("tracks", {}).get("TP3", {})
            if track.get("status") not in ("TP", "SL") or track.get("exit_points") is None:
                raise ValueError("Missing or unresolved TP3 track")
            rows.append(dict(trade, day=report["day"]))
    if not rows:
        raise ValueError("No lab trades")
    by_mode = {}
    daily = {}
    for target, grouping in ((by_mode, "mode"), (daily, "day")):
        for key in sorted(set(r[grouping] for r in rows)):
            subset = [r for r in rows if r[grouping] == key]
            points = [float(r["tracks"]["TP3"]["exit_points"]) for r in subset]
            wins = sum(p for p in points if p > 0)
            losses = -sum(p for p in points if p < 0)
            target[key] = {
                "signals": len(subset),
                "tp": sum(r["tracks"]["TP3"]["status"] == "TP" for r in subset),
                "sl": sum(r["tracks"]["TP3"]["status"] == "SL" for r in subset),
                "gross_points_ex_costs": round(sum(points), 3),
                "gross_profit_factor": round(wins / losses, 3) if losses else None,
                "net_points_if_assumed_cost_known": round(sum(points) - cost_points * len(subset), 3)
                    if cost_points is not None else None,
            }
    groups = dedup_opportunities(rows)
    days = sorted(set(r["day"] for r in rows))
    checks = {
        "min_200_distinct_opportunities": len(groups) >= 200,
        "min_30_session_days": len(days) >= 30,
        "untouched_out_of_sample_validation": False,
        "broker_fill_cost_reconciliation": False,
        "ordered_intrabar_execution": False,
        "verified_daily_risk_lock_and_kill_switch": False,
    }
    return {
        "version": "SHADOW_READINESS_AUDIT_V1",
        "source": "USER_SUPPLIED_V487_SHADOW_NOT_BROKER_FILLS",
        "days": days,
        "raw_signals": len(rows),
        "distinct_opportunities": len(groups),
        "overlapping_signals": len(rows) - len(groups),
        "gross_points_ex_costs": round(sum(float(r["tracks"]["TP3"]["exit_points"]) for r in rows), 3),
        "cost_points_assumption": cost_points,
        "by_mode": by_mode,
        "daily": daily,
        "ambiguous_tp6": sum(r.get("tracks", {}).get("TP6_BE3", {}).get("status") == "AMBIGUOUS" for r in rows),
        "ambiguous_tp9": sum(r.get("tracks", {}).get("TP9_BE3", {}).get("status") == "AMBIGUOUS" for r in rows),
        "gate_checks": checks,
        "real_money_ready": all(checks.values()),
        "warning": "This is only an offline screening tool: not independent evidence of profitability or executable EUR PnL.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--cost-points", type=float, default=None,
                        help="Explicit roundtrip cost; omitted means unknown")
    args = parser.parse_args()
    reports = []
    for f in args.files:
        reports.extend(extract_lab_reports(f.read_text(encoding="utf-8")))
    if not reports:
        parser.error("No v48.7 reports found")
    print(json.dumps(analyze(reports, args.cost_points), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
