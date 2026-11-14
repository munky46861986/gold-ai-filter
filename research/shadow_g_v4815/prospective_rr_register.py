"""SHADOW G v48.15 — offline, prospective MAX-plan RR register.

Reads only explicitly supplied plan details, not prices, outcomes or Telegram.
This script NEVER connects to a broker, a server, or a Telegram account.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

FREEZE_DAY = '2026-11-14'
MAX_CAPTURE_DELAY = timedelta(minutes=5)
REQUIRED_FIELDS = (
    'source', 'message_id', 'published_at', 'captured_at', 'direction',
    'zone_low', 'zone_high', 'sl', 'tp1',
)
OUTPUT_FIELDS = (*REQUIRED_FIELDS, 'rr', 'status', 'reason')


def _timestamp(raw: str):
    try:
        s = str(raw).strip()
        if s.endswith('Z'):
            s = s[:-1] + '+00:00'
        dt = datetime.fromisoformat(s)
        if dt.utcoffset() is None:
            return None
        return dt.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError):
        return None


def _number(raw):
    try:
        val = float(str(raw).strip())
        return val if math.isfinite(val) else None
    except (ValueError, TypeError):
        return None


def evaluate_plan(plan: dict) -> dict:
    """Return a decision using ONLY fields present at capture time."""
    out = {k: str(plan.get(k) or '').strip() for k in REQUIRED_FIELDS}
    out.update({'rr': '', 'status': 'NOT_EVALUABLE', 'reason': ''})
    if not all(out[f] for f in REQUIRED_FIELDS):
        out['reason'] = 'MISSING_REQUIRED_FIELD'
        return out
    posted = _timestamp(out['published_at'])
    captured = _timestamp(out['captured_at'])
    if posted is None or captured is None:
        out['reason'] = 'TIMEZONE_REQUIRED_OR_INVALID_TIME'
        return out
    if posted.astimezone(ZoneInfo('Europe/Rome')).date().isoformat() <= FREEZE_DAY:
        out['reason'] = 'NOT_PROSPECTIVE_AFTER_FREEZE'
        return out
    if captured < posted - timedelta(seconds=5):
        out['reason'] = 'CAPTURE_BEFORE_PUBLICATION'
        return out
    if captured - posted > MAX_CAPTURE_DELAY:
        out['reason'] = 'LATE_CAPTURE_UNVERIFIED_OUTCOME'
        return out
    low, high, sl, tp = [_number(out[n]) for n in ('zone_low','zone_high','sl','tp1')]
    if None in (low, high, sl, tp) or min(low, high, sl, tp) <= 0 or high < low:
        out['reason'] = 'INVALID_PRICE_OR_ZONE'
        return out
    side = out['direction'].upper()
    if side == 'BUY' and tp > high > sl:
        rr = (tp - high)/(high - sl)
    elif side == 'SELL' and sl > low > tp:
        rr = (low - tp)/(sl - low)
    else:
        out['reason'] = 'INVALID_LEVEL_ORDER_OR_DIRECTION'
        return out
    out['rr'] = f'{rr:.6f}'
    if rr + 1e-9 >= 0.5:
        out.update(status='RR_QUALIFIED_SHADOW', reason='AWAITING_BID_ASK_FIRST_TOUCH')
    else:
        out.update(status='RR_REJECTED', reason='RR_BELOW_FROZEN_0_50')
    return out


def register(rows: list[dict]) -> list[dict]:
    """Deduplicate by source+ID without letting a later revision replace original."""
    seen = set()
    results = []
    for row in rows:
        record = evaluate_plan(row)
        key = (record['source'], record['message_id'])
        if key in seen and all(key):
            record.update(status='DUPLICATE', reason='ORIGINAL_MESSAGE_ALREADY_REGISTERED')
        elif all(key):
            seen.add(key)
        results.append(record)
    return results


def run(source: Path, output: Path):
    with source.open('r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        missing = set(REQUIRED_FIELDS) - set(reader.fieldnames or [])
        if missing:
            raise ValueError('Missing CSV columns: ' + ', '.join(sorted(missing)))
        records = register(list(reader))
    output.mkdir(parents=True, exist_ok=True)
    with (output / 'rr_plan_register.csv').open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(records)
    counts = Counter(row['status'] for row in records)
    summary = {
        'model': 'SHADOW_G_v48.15_PROSPECTIVE',
        'execution': 'RESEARCH_ONLY_NO_ORDERS',
        'cutoff_day_rome': FREEZE_DAY,
        'rr_threshold': 0.5,
        'captured_within_minutes': 5,
        'total_messages': len(records),
        'status_counts': dict(counts),
        'broker_fills_verified': 0,
        'profitability_claimed': False,
    }
    (output / 'rr_plan_summary.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plans', type=Path, required=True, help='Prospectively captured, timezone-aware Max-plan CSV')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.plans, args.output), indent=2, ensure_ascii=False))
