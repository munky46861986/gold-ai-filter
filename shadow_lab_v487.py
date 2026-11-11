"""GOLD MASTER v48.7 LAB -- standalone SHADOW-only diagnostics and exit scenarios.

Never submits broker orders. All price, forecast and M1 inputs are supplied by
app.py after the existing research engines. Results are hypothetical, not fills.
"""
from __future__ import annotations

import json
import math
import os
import time
from collections import Counter

SCENARIOS = ("TP3", "TP6_BE3", "TP9_BE3")
FINAL = {"TP", "SL", "BE", "AMBIGUOUS", "EXPIRED"}
VERSION = "48.7-LAB-ONLY"


def _float(value, default=None):
    try:
        n = float(value)
        return n if math.isfinite(n) else default
    except (TypeError, ValueError, OverflowError):
        return default


def _sign(direction):
    return 1 if direction == "BUY" else -1


class ShadowLabV487:
    """Persistent where disk is durable; bounded, fail-safe research state."""

    def __init__(self, path="v487_lab_state.json", max_trades=1200, flush_every=10):
        self.path = path
        self.max_trades = max(50, int(max_trades))
        self.flush_every = max(1, int(flush_every))
        self.state = {"version": VERSION, "days": {}, "trades": {}}
        self.dirty = 0
        self._load()

    def _load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                saved = json.load(fh)
            if isinstance(saved, dict) and saved.get("version") == VERSION:
                if isinstance(saved.get("days"), dict) and isinstance(saved.get("trades"), dict):
                    self.state = saved
        except (OSError, ValueError, TypeError):
            pass

    def _flush(self, force=False):
        if not force and self.dirty < self.flush_every:
            return
        try:
            with open(self.path + ".tmp", "w", encoding="utf-8") as fh:
                json.dump(self.state, fh, ensure_ascii=False, allow_nan=False)
            os.replace(self.path + ".tmp", self.path)
            self.dirty = 0
        except (OSError, ValueError, TypeError):
            pass

    def _mark(self):
        self.dirty += 1
        self._flush()

    def _day(self, day):
        return self.state["days"].setdefault(
            day, {"B": {}, "D": {}, "samples": [], "updates": 0}
        )

    def _b_reason(self, *, session, forecast, bias, close, m1):
        if session not in ("EUROPE", "NEWYORK"):
            return "OUTSIDE_OPERATING_SESSION"
        if not isinstance(forecast, dict):
            return "FORECAST_MISSING"
        if str(forecast.get("live_status") or "VALID").upper() in (
            "ARCHIVED", "INVALIDATED", "REASSESSING"
        ):
            return "FORECAST_STATUS_BLOCKED"
        if bias not in ("BUY", "SELL"):
            return "FORECAST_SIDE_MISSING"
        if close is None or close <= 0:
            return "PRICE_MISSING"
        lo = _float(forecast.get("live_preferred_zone_low"),
                    _float(forecast.get("preferred_zone_low")))
        hi = _float(forecast.get("live_preferred_zone_high"),
                    _float(forecast.get("preferred_zone_high")))
        if lo is None or hi is None or lo <= 0 or hi < lo:
            return "PREFERRED_ZONE_INVALID"
        if not lo <= close <= hi:
            return "OUTSIDE_PREFERRED_ZONE"
        if not m1.get("confirmed"):
            return "M1_NOT_CONFIRMED"
        if (_float(m1.get("score"), 0) or 0) < 6:
            return "M1_SCORE_BELOW_6"
        if str(m1.get("direction") or "").upper() != bias:
            return "M1_OPPOSITE_FORECAST"
        return "B_ELIGIBLE_PRE_DEDUP"

    def _d_reason(self, *, session, bias, m1, history):
        if session not in ("EUROPE", "NEWYORK"):
            return "OUTSIDE_OPERATING_SESSION"
        direction = str(m1.get("direction") or "").upper()
        if direction not in ("BUY", "SELL"):
            return "M1_DIRECTION_MISSING"
        if not m1.get("confirmed"):
            return "M1_NOT_CONFIRMED"
        if (_float(m1.get("score"), 0) or 0) < 6:
            return "M1_SCORE_BELOW_6"
        if bias not in ("BUY", "SELL"):
            return "FORECAST_SIDE_MISSING"
        if bias == direction:
            return "M1_SAME_AS_FORECAST"
        if len(history) < 11:
            return "HISTORY_LT_11"
        closes = [_float(r.get("close")) for r in history[-11:]]
        if any(p is None or p <= 0 for p in closes):
            return "INVALID_CLOSE_SERIES"
        sign = _sign(direction)
        if sign * (closes[5] - closes[0]) > -3.0:
            return "PRIOR_IMPULSE_LT_3"
        if sign * (closes[-1] - closes[5]) < 2.0:
            return "REVERSAL_LT_2"
        if sign * (closes[-1] - closes[-2]) < 0.25:
            return "LAST_STEP_LT_0_25"
        ranges = [(_float(r.get("high"), 0), _float(r.get("low"), 0))
                  for r in history[-10:]]
        if any(hi is None or lo is None or hi < lo or lo <= 0
               for hi, lo in ranges):
            return "INVALID_BAR_RANGES"
        stop = (min(lo for _, lo in ranges) - 0.8 if sign == 1
                else max(hi for hi, _ in ranges) + 0.8)
        if not 3.0 <= abs(closes[-1] - stop) <= 12.0:
            return "STRUCTURAL_STOP_OUTSIDE_3_TO_12"
        return "D_ELIGIBLE_PRE_COOLDOWN"

    def _diagnose(self, *, day, session, forecast, bias, m1, history, close, stamp):
        row = self._day(day)
        b = self._b_reason(session=session, forecast=forecast, bias=bias,
                           close=close, m1=m1)
        d = self._d_reason(session=session, bias=bias, m1=m1, history=history)
        row["B"][b] = int(row["B"].get(b, 0)) + 1
        row["D"][d] = int(row["D"].get(d, 0)) + 1
        row["updates"] = int(row.get("updates", 0)) + 1
        sample = {
            "time": round(stamp, 3), "session": session, "bias": bias,
            "close": close, "m1_direction": str(m1.get("direction") or "").upper(),
            "m1_score": int(_float(m1.get("score"), 0) or 0),
            "B": b, "D": d
        }
        samples = row.setdefault("samples", [])
        if (not samples or samples[-1]["B"] != b or samples[-1]["D"] != d
                or row["updates"] % 30 == 0):
            samples.append(sample)
            row["samples"] = samples[-35:]
        self._mark()

    @staticmethod
    def _source_key(signal):
        stamp, entry = _float(signal.get("time")), _float(signal.get("entry"))
        if stamp is None or entry is None:
            return None
        return "%s|%s|%s|%s|%.3f|%.3f" % (
            signal.get("day"), signal.get("symbol"), signal.get("mode"),
            signal.get("direction"), stamp, entry
        )

    @staticmethod
    def _volatility(history):
        sample = [r for r in (history or [])[-12:] if isinstance(r, dict)]
        ranges = []
        for row in sample:
            hi, lo = _float(row.get("high")), _float(row.get("low"))
            if hi is not None and lo is not None and lo > 0 and hi >= lo:
                ranges.append(hi - lo)
        closes = [_float(r.get("close")) for r in sample]
        jumps = [abs(a-b) for a,b in zip(closes, closes[1:])
                 if a is not None and b is not None]
        return {
            "max_bar_points": round(max(ranges, default=0), 3),
            "max_close_jump_points": round(max(jumps, default=0), 3),
            "history_bars": len(sample),
            "spike_flag": bool(len(sample) >= 3 and (
                max(ranges, default=0) >= 8 or max(jumps, default=0) >= 6))
        }

    def _discover(self, signals, day, stamp, history, forecast):
        trades = self.state["trades"]
        changed = False
        for sig in signals[-150:]:
            if not isinstance(sig, dict) or sig.get("day") != day:
                continue
            if sig.get("execution") != "SHADOW_ONLY":
                continue
            t = _float(sig.get("time"))
            entry, sl = _float(sig.get("entry")), _float(sig.get("sl"))
            direction = str(sig.get("direction") or "").upper()
            if (t is None or entry is None or sl is None or
                    direction not in ("BUY", "SELL")):
                continue
            # Never retroactively use unseen candles from before this process.
            if stamp < t or stamp - t > 120 or entry <= 0 or abs(sl-entry) < .01:
                continue
            if (sl-entry) * _sign(direction) >= 0:
                continue
            key = self._source_key(sig)
            if not key or key in trades:
                continue
            risk = round(abs(entry-sl), 3)
            tracks = {
                name: {"status": "OPEN", "be_active": False,
                       "observations": 0, "exit_points": None,
                       "level": None, "source": None}
                for name in SCENARIOS
            }
            trades[key] = {
                "key": key, "day": day, "time": t, "symbol": sig.get("symbol"),
                "mode": sig.get("mode"), "direction": direction,
                "entry": entry, "sl": sl,
                "tp1_original": _float(sig.get("tp1")),
                "score": _float(sig.get("score")),
                "risk_points": risk,
                "risk_band": "LE_3_5" if risk <= 3.5 else (
                    "LE_6" if risk <= 6 else "GT_6"),
                "forecast_status_at_observation":
                    str((forecast or {}).get("live_status") or "UNKNOWN"),
                "volatility_at_observation": self._volatility(history),
                "tracks": tracks
            }
            changed = True
        if changed:
            if len(trades) > self.max_trades:
                sorted_keys = sorted(trades, key=lambda k: trades[k].get("time", 0))
                for key in sorted_keys[:len(trades)-self.max_trades]:
                    del trades[key]
            self._mark()

    @staticmethod
    def _finish(track, status, points=None, source=None, level=None):
        track["status"] = status
        track["exit_points"] = round(points, 3) if points is not None else None
        track["source"] = source
        track["level"] = round(level, 3) if level is not None else None

    def _advance(self, data, stamp):
        symbol = str(data.get("symbol") or "XAUUSD").upper()
        close = _float(data.get("close"))
        if close is None or close <= 0:
            return
        raw_hi, raw_lo = _float(data.get("high")), _float(data.get("low"))
        has_range = (raw_hi is not None and raw_lo is not None and
                     raw_lo > 0 and raw_hi >= raw_lo and raw_lo <= close <= raw_hi)
        hi, lo = (raw_hi, raw_lo) if has_range else (close, close)
        source = "BAR_HIGH_LOW_UNORDERED" if has_range else "CLOSE_ONLY"
        changed = False
        for trade in self.state["trades"].values():
            if trade.get("symbol") != symbol or stamp <= (
                    _float(trade.get("time"), 0) or 0):
                continue
            sign = _sign(trade["direction"])
            entry, original_sl = trade["entry"], trade["sl"]
            favorable = (hi-entry) if sign == 1 else (entry-lo)
            adverse = (entry-lo) if sign == 1 else (hi-entry)
            for name, track in trade["tracks"].items():
                if track["status"] in FINAL:
                    continue
                track["observations"] += 1
                changed = True
                if track["observations"] > 180:
                    self._finish(track, "EXPIRED", source=source)
                    continue
                take = 3.0 if name == "TP3" else (
                    6.0 if name == "TP6_BE3" else 9.0)
                tp = entry + sign*take
                risk_level = entry if track["be_active"] else original_sl
                risk_dist = abs(risk_level-entry)
                risk_hit = (adverse >= risk_dist if risk_dist > 0 else
                            (lo <= entry if sign == 1 else hi >= entry))
                target_hit = favorable >= take
                new_be = (name != "TP3" and not track["be_active"]
                          and favorable >= 3.0)
                be_crossed = lo <= entry if sign == 1 else hi >= entry
                ambiguous = has_range and (
                    (risk_hit and target_hit) or (new_be and be_crossed))
                if ambiguous:
                    self._finish(track, "AMBIGUOUS", source=source)
                elif risk_hit:
                    self._finish(track, "BE" if track["be_active"] else "SL",
                                 (risk_level-entry)*sign, source, risk_level)
                elif target_hit:
                    self._finish(track, "TP", take, source, tp)
                elif new_be:
                    track["be_active"] = True
        if changed:
            self._mark()

    def observe(self, *, data, signals, day, stamp=None, session="",
                forecast=None, bias="", m1=None, history=None,
                diagnostics=True):
        """Call after existing SHADOW observers; no broker methods are referenced."""
        if not isinstance(data, dict) or not isinstance(signals, list):
            return
        stamp = _float(stamp, time.time())
        m1 = m1 if isinstance(m1, dict) else {}
        history = history if isinstance(history, list) else []
        session, bias = str(session or "").upper(), str(bias or "").upper()
        # Process existing virtual entries BEFORE discovering new ones on this bar.
        self._advance(data, stamp)
        self._discover(signals, day, stamp, history, forecast)
        if diagnostics:
            self._diagnose(day=day, session=session, forecast=forecast,
                           bias=bias, m1=m1, history=history,
                           close=_float(data.get("close")), stamp=stamp)

    def report(self, day, include_trades=True):
        trades = [r for r in self.state["trades"].values() if r.get("day") == day]
        scenarios = {}
        for name in SCENARIOS:
            counts = Counter(r["tracks"][name]["status"] for r in trades)
            resolved = [
                r["tracks"][name]["exit_points"] for r in trades
                if r["tracks"][name]["exit_points"] is not None
            ]
            scenarios[name] = {
                "count": len(trades), "outcomes": dict(counts),
                "nominal_net_points_ex_costs": round(sum(resolved), 3),
                "resolved_count": len(resolved),
                "ambiguous_count": counts["AMBIGUOUS"]
            }
        slices = {}
        for field in ("risk_band", "forecast_status_at_observation"):
            slices[field] = {}
            for value in sorted(set(str(r.get(field) or "UNKNOWN") for r in trades)):
                subset = [
                    r["tracks"]["TP3"] for r in trades
                    if str(r.get(field) or "UNKNOWN") == value
                ]
                slices[field][value] = {
                    "count": len(subset),
                    "outcomes": dict(Counter(x["status"] for x in subset))
                }
        slices["spike_flag"] = {}
        for flag in ("YES", "NO"):
            subset = [
                r["tracks"]["TP3"] for r in trades
                if bool(r.get("volatility_at_observation", {}).get("spike_flag")) == (
                    flag == "YES")
            ]
            slices["spike_flag"][flag] = {
                "count": len(subset),
                "outcomes": dict(Counter(x["status"] for x in subset))
            }
        answer = {
            "version": VERSION, "day": day,
            "execution": "SHADOW_ONLY_NO_BROKER_ORDERS",
            "data_persistence": "LOCAL_FILE_EPHEMERAL_UNLESS_PERSISTENT_DISK",
            "diagnostics": self._day(day), "scenarios": scenarios,
            "risk_slices": slices,
            "warning": (
                "High/low has no first-touch ordering; simultaneous stop/target "
                "or same-bar BE is AMBIGUOUS. CLOSE_ONLY uses closes. "
                "No broker fills, spread, slippage or commissions."
            )
        }
        if include_trades:
            answer["trades"] = sorted(
                trades, key=lambda x: x.get("time", 0))[-100:]
        return answer
