# GOLD MASTER v48.5 — RESEARCH DEMO

This branch contains the complete existing app.py (~1 MB), including Forecast, Session Thesis, Live Director, Telegram, MT4 bridge and historical SHADOW modules.

## Experimental profile

- A: Forecast zone anticipation (SHADOW, TP1 CLOSE proxy).
- B: Forecast zone + confirmed M1 (SHADOW, TP1 CLOSE proxy).
- C: existing LIVE Director (broker DEMO; one 0.01-lot Forecast leg per order).
- Recovery is excluded from the research profile.
- Virtual SHADOW signals are *not* stopped after a daily loss.
- Broker cap: EUR 100 daily emergency limit and EUR 25 per new campaign, configurable downward only. The EA independently enforces its own parameters.
- No guarantee of broker executions or profitability. TradingView CLOSE proxy is not a candle intrabar backtest.
- v48.5 single-leg profile closes at TP1; TP2/runner are NOT broker-managed as three-leg A/B/C.
- This experimental code is on a separate branch, not deployed to Render.

## Installation

Do NOT deploy before compiling the matching EA `GoldBotBridge_v48_5_RESEARCH_DEMO_SINGLE_LEG.mq4` in MetaEditor and dry-running with EnableTrading=false. Check all Render environment variables, EA settings, broker symbol and account history.

Endpoints: `/v484/triple-strategy`, `/v48/shadow`, `/v483/diagnostics`, `/v48/risk`.
