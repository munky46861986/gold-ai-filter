# GOLD MASTER v48.7 LAB — SHADOW ONLY (draft)

**Do not merge or deploy until the review and a live smoke test are complete.**
The current broker/MT4 production code remains v48.6.

## Changes

- Adds standalone \`shadow_lab_v487.py\`; no broker calls or Telegram trade commands.
- B diagnostic: per-webhook **primary rejection reason**, not a count of unique candidate trades. Includes missing forecast, out-of-zone, missing M1 confirmation, low score, and M1 direction mismatch.
- D diagnostic: records M1 prerequisites, opposing forecast requirement, 11-price momentum pattern, and structural stop distance.
- Virtual exit comparison for each **newly observed** existing SHADOW candidate:
  - \`TP3\`: target +3 points, original SL.
  - \`TP6_BE3\`: target +6, virtual SL to entry after +3.
  - \`TP9_BE3\`: target +9, virtual SL to entry after +3.
- Logs exposure/risk-distance bucket, forecast state, and recent bar volatility at observation.
- When both stop and target or a BE activation and return to entry occur inside the same bar, labels \`AMBIGUOUS\` instead of inventing a fill ordering.
- If high/low are missing, uses close-only observations and labels their source.
- Does not retroactively backfill old SHADOW signals after a restart.

## Server endpoints after deployment

- \`GET /v487/lab?day=YYYY-MM-DD\`: research summary and virtual trade rows.
- \`GET /v487/diagnostics?day=YYYY-MM-DD\`: B/D rejection counters and risk slices.

## Guardrails

No changes to \`process_forecast_campaign\`, \`process_live_director\`, broker reconciliation, stop/target levels, recovery, lots, risk guard, MT4 execution, or Telegram trade alerts. All new hooks are isolated with \`try/except\`.

Environment variable \`V487_LAB_ENABLED=FALSE\` can disable this lab without disabling v48.6 trading. The optional \`V487_LAB_STATE_FILE\` defaults to \`v487_lab_state.json\`.

State is a local JSON file: **Render Free ephemeral storage may erase it on restart/deploy.** Persist elsewhere or export results regularly if validation requires longitudinal data.

## How to test (locally / in CI)

\`\`\`bash
python -m py_compile app.py shadow_lab_v487.py
python -m unittest -v test_shadow_lab_v487
\`\`\`

The unit tests cover TP3, break-even activation, simultaneous SL/TP ambiguity, close-only fallback, historical backfill prevention, B/D diagnostics, and state reload.

## Deployment policy

1. Review the branch diff against \`main\`, validate syntax and isolated tests.
2. Run an opt-in smoke test with simulated webhooks on a **separate staging service** before changing Render.
3. Merge only if no broker regression is observed; monitor the two v48.7 endpoints with DEMO orders unchanged.
4. Do **not** treat nominal point totals as broker profitability. Include spread/slippage and intrabar uncertainty in any final evaluation.
