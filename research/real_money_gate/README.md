# GOLD MASTER — from SHADOW research toward a real-money decision

This is an OFFLINE, read-only audit. It does not import app.py or communicate
with Render, MT4, broker, trading accounts or Telegram. Nothing in this
folder can generate or transmit an order.

## Baseline evidence (19–20 Nov 2026)

The two exported v48.7 lab reports show 32 simulated TP3 signals but
only **26 distinct entry opportunities** after grouping the same price,
side and timestamp across modes. This grouping is a heuristic; it is
not verified broker trade matching.

Mode / signals / TP / SL / gross nominal points before costs:

- A_FORECAST_ANTICIPATORY: 4 / 4 / 0 / +12
- B_FORECAST_M1: 3 / 3 / 0 / +9
- RANGE_M1_SCOUT: 9 / 5 / 4 / -9
- TREND_CONTINUATION: 16 / 4 / 12 / -33.72
- Combined raw signals: 32 / 16 / 16 / -21.72

Do not treat duplicate signals as independently executed trades. None
of the reported points is verified EUR PnL; stop/target ordering is
imperfect and execution costs are absent. Small-sample success for A/B
does not justify real-money trading. A TP3 against a 12-point SL needs
more than an 80% win rate just to overcome risk before costs.

## Reproducible usage

Run the script using text / Markdown exports that contain v48.7 JSON
objects on individual lines:

    python research/real_money_gate/shadow_audit.py day19.md day20.txt

Optional explicit round-trip cost assumption (in XAUUSD price points):

    python research/real_money_gate/shadow_audit.py day19.md day20.txt --cost-points 0.4

This number is an example of CLI usage, NOT an assumption about the
broker. Omit the flag unless real fill data supports it.

Unit tests:

    cd research/real_money_gate
    python -m unittest -v test_shadow_audit.py

## Experiments to pre-register

1. Baseline original TREND_CONTINUATION versus a variant with structural
   retest; compare both on the same events. Do not retune using outcomes
   of the day being scored.
2. RANGE_M1_SCOUT with and without breakout/retest, including RANGE NY
   with thesis+M1 aligned. Audit early SELL signals that stop out on
   rebound even if the session later falls.
3. TP3, TP6/BE3 and TP9/BE3 with time-ordered bid/ask data. Keep all
   same-bar stop/target or BE ordering cases AMBIGUOUS until resolved.
4. Persist raw inputs, signals, broker fill tickets, actual entry/exit,
   SL/TP updates, spread, commissions, slippage, account currency and
   any rejected orders, independently of ephemeral Render storage.
5. Walk-forward / untouched out-of-sample periods including both quiet
   and high-volatility Asia, Europe and New York sessions; report
   expectancy, max drawdown, loss streaks, and profit factor after costs.
6. Verify MT4 demo risk controls and a kill switch, including broker
   reconnection, duplicate prevention and a daily account-equity lock.

## Research thresholds (not guarantees)

As an initial screen, demand at least 200 distinct opportunities over
30 trading days plus separate untouched out-of-sample evidence. These
are necessary research checks, not sufficient conditions or predictions
of profit. Require independent broker reconciliation and robust positive
net expectancy before proposing a micro-live trial.

An eventual micro-live pilot should only follow explicit approval,
with broker-calibrated limits such as 0.25% of equity per position,
1% daily drawdown cap, no lot size escalation after losses, no martingale,
and a verified emergency disable. If the broker's minimum lot size or
SL distance cannot meet these limits, the real-money pilot must not run.

NEVER automatically promote SHADOW outcomes to live broker execution.
