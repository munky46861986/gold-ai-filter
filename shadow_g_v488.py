"""SHADOW G v48.8: isolated, causally evaluated XAUUSD research engine.

No network, broker, Telegram, GitHub or MT4 integration. Input is a strictly
ordered stream of *completed* M1 mid-price bars (UTC close timestamps).
All thresholds are provisional hypotheses inspired by publicly described
structure, liquidity, retest and multi-target management, not fitted results.
"""
from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite
from zoneinfo import ZoneInfo

ITALY = ZoneInfo("Europe/Rome")
TARGETS = (3.0, 6.0, 9.0, 15.0, 25.0)
TERMINAL = {"TP", "SL", "BE", "AMBIGUOUS", "DATA_GAP", "EXPIRED", "SKIPPED"}


def _num(v):
    if isinstance(v, bool):
        raise ValueError("boolean is not a price")
    n = float(v)
    if not isfinite(n):
        raise ValueError("not finite")
    return n


def normalize_bar(row):
    if row.get("complete") is not True:
        raise ValueError("requires complete=true and a CLOSED M1 candle")
    end = int(_num(row["end_ts"]))
    if end <= 0 or end % 60:
        raise ValueError("end_ts must be exact UTC M1 close epoch seconds")
    o, h, l, c = (_num(row[k]) for k in ("open", "high", "low", "close"))
    spread = _num(row.get("spread_points", 0.30))
    if min(o, h, l, c) <= 0 or not (l <= min(o, c) <= max(o, c) <= h):
        raise ValueError("invalid OHLC")
    if spread < 0 or spread > 6:
        raise ValueError("spread must be 0..6 mid-price points")
    return {"end_ts": end, "open": o, "high": h, "low": l, "close": c,
            "spread_points": spread, "complete": True}


def aggregate(m1, minutes):
    """Resample only fully represented, contiguous M1 bars; ignore partials."""
    size = minutes * 60
    groups = {}
    for b in m1:
        key = (b["end_ts"] - 1) // size * size + size
        groups.setdefault(key, []).append(b)
    out = []
    for k, rows in sorted(groups.items()):
        if len(rows) != minutes or [r["end_ts"] for r in rows] != list(range(k-size+60, k+1, 60)):
            continue
        out.append({"end_ts": k, "open": rows[0]["open"],
                    "high": max(r["high"] for r in rows),
                    "low": min(r["low"] for r in rows), "close": rows[-1]["close"]})
    return out


@dataclass(frozen=True)
class Candidate:
    mode: str
    side: str
    stop: float
    structural_level: float
    reason: str


def candidates(m5, m15):
    """Return independent structural hypotheses using only completed bars."""
    if len(m5) < 12 or len(m15) < 13:
        return []
    last5, last15 = m5[-1], m15[-1]
    t = last5["end_ts"]
    out = []

    # G1: failure above/below an 8xM15 swing + confirmation of M5 microshift.
    prev = m15[-9:-1]
    hi, lo = max(b["high"] for b in prev), min(b["low"] for b in prev)
    if 0 <= t - last15["end_ts"] <= 15*60:
        prior_m5_low = min(b["low"] for b in m5[-5:-1])
        prior_m5_high = max(b["high"] for b in m5[-5:-1])
        if last15["high"] >= hi+0.5 and last15["close"] <= hi-0.25 and last5["close"] < prior_m5_low-0.15:
            out.append(Candidate("G1_FAILURE_SHIFT", "SELL", last15["high"]+0.75, hi,
                                 "M15 sweep upper liquidity and M5 confirmed bearish shift"))
        if last15["low"] <= lo-0.5 and last15["close"] >= lo+0.25 and last5["close"] > prior_m5_high+0.15:
            out.append(Candidate("G1_FAILURE_SHIFT", "BUY", last15["low"]-0.75, lo,
                                 "M15 sweep lower liquidity and M5 confirmed bullish shift"))

    # G2: confirmed M15 structure break, then a later M5 retest of broken level.
    for j in range(max(8, len(m15)-4), len(m15)):
        bos = m15[j]
        if not bos["end_ts"] < t <= bos["end_ts"]+60*60:
            continue
        old = m15[j-8:j]
        old_hi, old_lo = max(b["high"] for b in old), min(b["low"] for b in old)
        if bos["close"] > old_hi+0.5 and last5["low"] <= old_hi+1.25 and last5["close"] > old_hi+0.2 and last5["close"] > last5["open"]:
            out.append(Candidate("G2_BOS_RETEST", "BUY", min(b["low"] for b in m5[-4:])-0.75,
                                 old_hi, "M15 bullish BOS, later M5 level retest and bullish close"))
            break
        if bos["close"] < old_lo-0.5 and last5["high"] >= old_lo-1.25 and last5["close"] < old_lo-0.2 and last5["close"] < last5["open"]:
            out.append(Candidate("G2_BOS_RETEST", "SELL", max(b["high"] for b in m5[-4:])+0.75,
                                 old_lo, "M15 bearish BOS, later M5 level retest and bearish close"))
            break

    # G3: trend on completed M15, then modest M5 consolidation breakout.
    slope = last15["close"]-m15[-4]["close"]
    prev4 = m5[-5:-1]
    box_hi = max(b["high"] for b in prev4)
    box_lo = min(b["low"] for b in prev4)
    if box_hi - box_lo <= 6.0:
        if slope >= 4 and 0.25 <= last5["close"] - box_hi <= 2.0:
            out.append(Candidate("G3_CONTINUATION", "BUY", box_lo-0.75, box_hi,
                                 "M15 upward drift, bounded M5 consolidation break"))
        if slope <= -4 and 0.25 <= box_lo - last5["close"] <= 2.0:
            out.append(Candidate("G3_CONTINUATION", "SELL", box_hi+0.75, box_lo,
                                 "M15 downward drift, bounded M5 consolidation break"))
    return out


class ShadowG:
    def __init__(self, *, spread_fallback=0.30, slippage_points=0.10,
                 max_gap_points=2.0, min_risk=2.0, max_risk=15.0,
                 spike_guard=True, max_signals_day=20, cooldown_seconds=1800):
        if slippage_points < 0 or spread_fallback < 0:
            raise ValueError("spread and slippage must be nonnegative")
        self.bars = deque(maxlen=1800)
        self.trades = []
        self.last_end = None
        self.last_trigger = {}
        self.settings = dict(spread_fallback=spread_fallback,
                             slippage_points=slippage_points,
                             max_gap_points=max_gap_points, min_risk=min_risk,
                             max_risk=max_risk, spike_guard=spike_guard,
                             max_signals_day=max_signals_day,
                             cooldown_seconds=cooldown_seconds)
        self.diagnostics = Counter()

    @staticmethod
    def _day(end):
        return datetime.fromtimestamp(end, timezone.utc).astimezone(ITALY).strftime("%Y-%m-%d")

    @staticmethod
    def _session(end):
        local = datetime.fromtimestamp(end, timezone.utc).astimezone(ITALY)
        return local.weekday() < 5 and 8 <= local.hour < 18

    def _spike(self):
        r = list(self.bars)[-12:]
        if len(r) < 12:
            return True
        return max(b["high"] - b["low"] for b in r) >= 8.0 or max(abs(a["close"]-b["close"]) for a,b in zip(r, r[1:])) >= 6.0

    def _advance(self, b):
        """Only *future* closed M1 bars can fill or resolve an existing candidate."""
        for trade in self.trades:
            if trade["decision_ts"] >= b["end_ts"]:
                continue
            sign = 1 if trade["side"] == "BUY" else -1
            half = b["spread_points"] / 2
            if trade["state"] == "PENDING":
                if b["end_ts"] - trade["decision_ts"] > 120:
                    trade["state"] = "EXPIRED"
                    self.diagnostics["expired_pending"] += 1
                    continue
                # Execute at NEXT M1 OPEN, not at decision candle's CLOSE.
                fill = b["open"] + sign*(half + self.settings["slippage_points"])
                if abs(fill - trade["reference_close"]) > self.settings["max_gap_points"]:
                    trade["state"] = "SKIPPED"
                    trade["skip_reason"] = "GAP_ENTRY"
                    continue
                risk = (fill - trade["sl"]) * sign
                if not self.settings["min_risk"] <= risk <= self.settings["max_risk"]:
                    trade["state"] = "SKIPPED"
                    trade["skip_reason"] = "RISK_AFTER_FILL"
                    continue
                trade["entry"] = round(fill, 5)
                trade["risk_points"] = round(risk, 5)
                trade["fill_ts"] = b["end_ts"]
                trade["state"] = "OPEN"
                trade["tracks"] = {f"TP{int(target)}": {"status": "OPEN", "be": False, "points": None}
                                   for target in TARGETS}
            if trade["state"] != "OPEN":
                continue
            entry = trade["entry"]
            # Exit a BUY on BID, a SELL on ASK; price data are MID OHLC.
            favorable = (b["high"]-half-entry) if sign == 1 else (entry-(b["low"]+half))
            adverse = (entry-(b["low"]-half)) if sign == 1 else ((b["high"]+half)-entry)
            for target in TARGETS:
                k, track = f"TP{int(target)}", trade["tracks"][f"TP{int(target)}"]
                if track["status"] != "OPEN":
                    continue
                stop_dist = 0.0 if track["be"] else trade["risk_points"]
                risk_hit = adverse >= stop_dist - 1e-9
                take_hit = favorable >= target - 1e-9
                # BE is tested after TP2, independently for longer-target policies.
                new_be = target > 6 and not track["be"] and favorable >= 6.0
                be_crossed = adverse >= 0
                if (risk_hit and take_hit) or (new_be and be_crossed):
                    track.update(status="AMBIGUOUS", points=None)
                elif risk_hit:
                    track.update(status="BE" if track["be"] else "SL",
                                 points=0.0 if track["be"] else -trade["risk_points"])
                elif take_hit:
                    track.update(status="TP", points=target)
                elif new_be:
                    track["be"] = True
            if all(track["status"] != "OPEN" for track in trade["tracks"].values()):
                trade["state"] = "RESOLVED"

    def push(self, row):
        """Return new virtual candidate (if any). No trading side effects."""
        row = dict(row)
        row.setdefault("spread_points", self.settings["spread_fallback"])
        b = normalize_bar(row)
        if self.last_end is not None:
            if b["end_ts"] <= self.last_end:
                raise ValueError("duplicate or out-of-order M1 close")
            if b["end_ts"] != self.last_end + 60:
                for trade in self.trades:
                    if trade["state"] in ("PENDING", "OPEN"):
                        trade["state"] = "DATA_GAP"
                        for tr in trade.get("tracks", {}).values():
                            if tr["status"] == "OPEN":
                                tr["status"] = "DATA_GAP"
                self.bars.clear()
                self.diagnostics["data_gaps"] += 1
        self.last_end = b["end_ts"]
        self._advance(b)
        self.bars.append(b)
        if b["end_ts"] % 300 or not self._session(b["end_ts"]):
            return None
        if self.settings["spike_guard"] and self._spike():
            self.diagnostics["spike_skipped"] += 1
            return None
        m5, m15 = aggregate(self.bars, 5), aggregate(self.bars, 15)
        if not m5 or m5[-1]["end_ts"] != b["end_ts"] or not m15:
            return None
        if self._day(b["end_ts"]) != self._day(b["end_ts"]-60):
            return None
        todays = sum(t["day"] == self._day(b["end_ts"]) for t in self.trades)
        if todays >= self.settings["max_signals_day"]:
            self.diagnostics["day_limit"] += 1
            return None
        for cand in candidates(m5, m15):
            sign = 1 if cand.side == "BUY" else -1
            risk = sign*(b["close"]-cand.stop)
            if not self.settings["min_risk"] <= risk <= self.settings["max_risk"]:
                self.diagnostics["structural_risk_rejected"] += 1
                continue
            key = (cand.mode, cand.side)
            if b["end_ts"] - self.last_trigger.get(key, 0) < self.settings["cooldown_seconds"]:
                self.diagnostics["cooldown"] += 1
                continue
            # One chosen candidate per time block; avoid counting one move 2-3 times.
            if any(t["decision_ts"] == b["end_ts"] and t["side"] == cand.side for t in self.trades):
                return None
            trade = {"id": f"G:{b['end_ts']}:{cand.mode}:{cand.side}",
                     "version": "48.8-RESEARCH-ONLY", "execution": "SHADOW_ONLY_NO_BROKER",
                     "day": self._day(b["end_ts"]), "decision_ts": b["end_ts"],
                     "mode": cand.mode, "side": cand.side, "symbol": "XAUUSD",
                     "reference_close": b["close"], "structural_level": cand.structural_level,
                     "sl": round(cand.stop, 5), "reason": cand.reason,
                     "state": "PENDING", "entry": None, "fill_ts": None,
                     "risk_points": None, "tracks": {}}
            self.trades.append(trade)
            self.last_trigger[key] = b["end_ts"]
            self.diagnostics["signals"] += 1
            return trade
        return None

    def report(self, day=None, *, include_trades=False):
        rows = [t for t in self.trades if day is None or t["day"] == day]
        scenario = {}
        for target in TARGETS:
            name = f"TP{int(target)}"
            paired = [(t, t["tracks"][name]) for t in rows if name in t["tracks"]]
            statuses = Counter(track["status"] for _, track in paired)
            done = [track["points"] for _, track in paired
                    if track["status"] in ("TP", "SL", "BE")]
            # The nominal baseline excludes intrabar first-touch uncertainty.
            # Stress it by treating each AMBIGUOUS outcome as a full initial SL.
            # DATA_GAP remains unknown and must be evaluated separately.
            ambiguous_sl_penalty = sum(float(t.get("risk_points") or 0.0)
                                       for t, track in paired
                                       if track["status"] == "AMBIGUOUS")
            scenario[name] = {"statuses": dict(statuses),
                              "resolved_unambiguous": len(done),
                              "sum_nominal_points_ex_commission": round(sum(done), 3),
                              "ambiguous_not_counted": statuses["AMBIGUOUS"],
                              "stress_nominal_if_ambiguous_sl": round(sum(done) - ambiguous_sl_penalty, 3),
                              "unknown_data_gap_count": statuses["DATA_GAP"]}
        result = {"version": "48.8-RESEARCH-ONLY", "execution": "SHADOW_ONLY_NO_BROKER",
                  "day": day, "signal_count": len(rows),
                  "modes": dict(Counter(t["mode"] for t in rows)),
                  "pending": sum(t["state"] == "PENDING" for t in rows),
                  "diagnostics": dict(self.diagnostics), "scenarios": scenario,
                  "limitations": "M1 mid OHLC with assumed next-bar fills, spread/slippage model; ambiguous same-bar ordering excluded; historical prices required; no broker PnL"}
        if include_trades:
            result["trades"] = rows
        return result

