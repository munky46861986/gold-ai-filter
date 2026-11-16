# GOLD MASTER — SHADOW G v48.18: registratore decisioni

**Data:** 16 novembre 2026. **Ambiente:** script offline / solo ramo di ricerca. Nessun deploy, nessuna modifica MT4, Render o GitHub `main`. Nessun accesso al broker.

## Risultato tecnico consegnato

- `shadow_g_v4818_recorder.py`: ingestione di snapshot JSONL in SQLite, report CSV/JSON; timestamp ISO con timezone; registro immutabile con duplicati idempotenti e conflitti rifiutati.
- `decision_adapter_v4818.py`: adattatore puro dalla struttura del Director; conserva solo un insieme controllato di campi. La Thesis stabile deriva esclusivamente da `_thesis_fast_state()` e non dal `preferred` generico.
- `test_shadow_g_v4818.py`: **17 test automatici superati**, comprese protezioni per credenziali, date senza timezone, NaN, duplicazioni, eventi broker, tre politiche A/B/C e livelli non disponibili.
- `example_synthetic_events.jsonl`: **solo tre eventi sintetici**, non sono messaggi del bot o transazioni verificate.
- `synthetic_report/decision_audit.csv` e `summary.json`: output dimostrativo con 3 decisioni, 1 campagna simulata e 2 rifiuti. B blocca la sola campagna simulata in WEAKENING, C non la blocca. Zero ordini broker e zero risultati di trading verificati.

## Come leggere A/B/C

| Politica | Significato | Cosa misura oggi |
|---|---|---|
| A | Campagne che il codice Director segnala come `triggered=True` | Decisione teorica, non fill |
| B | Veto su A se mappa `WEAKENING` e direzione invariata | Quante campagne A avrebbe scartato |
| C | Veto su A se Thesis FAST 2/2 opposta alla direzione proposta | Eventuali veto aggiuntivi (probabile ridondanza in STANDARD) |

La mancata creazione di una campagna da A non viene reinterpretata come un'operazione vincente o perdente. I campi `entry`, `sl`, `tp1`, `tp2` sono `null` se non forniti. I motivi di rifiuto sono soltanto quelli comunicati dal processo che produce l'evento.

## Cosa NON è stato fatto

- **Non è stato collegato al servizio Render.** Non sta acquisendo automaticamente gli eventi live.
- Non è stato modificato il programma `app.py` né eseguito alcun deploy nel ramo operativo.
- Non sono state cambiate soglie o criteri della strategia e non è stato aperto alcun ordine.
- Non è stato eseguito un backtest economico A/B/C; richiede reali snapshot storiche dell'engine e prezzi bid/ask successivi, non deducibili dai soli messaggi Telegram.
- Non è dimostrato che uno dei gate sia profittevole.

## Passaggio necessario prima di una valutazione LIVE

Collegare in modo **esplicito e separato** il produttore di snapshot alle decisioni GOLD MASTER, inclusi i ritorni anticipati/guardrail, con telemetria di sola lettura; scegliere archiviazione persistente, con condizioni di disattivazione, eventi idempotenti, costi e verifica del clock; testare su DEMO senza cambiare il percorso degli ordini. Una eventuale promozione a `main`/deploy è fuori dallo scopo della v48.18 e deve essere autorizzata e verificata separatamente.
