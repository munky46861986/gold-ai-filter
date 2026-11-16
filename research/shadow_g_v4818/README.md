# SHADOW G v48.18 — Registratore decisioni (SOLO RICERCA)

**Stato: CODICE CREATO E TESTATO, NON DEPLOYATO.** Caricato esclusivamente nel ramo `research/shadow-g-v48-8`. Non importa il bot live, non ha rete, non invia ordini, non cambia parametri MT4/Render. Non legge Telegram. L'integrazione nel servizio reale va trattata come un'attività separata, da verificare prima della messa in servizio.

## Che cosa registra

- Tutti gli eventi **consegnati** al registratore (decisioni di campagna accettate o rifiutate). Non cattura autonomamente gli eventi che il servizio live non gli invia.
- Timestamp con timezone obbligatorio; sessione; prezzo di osservazione; direzione; Forecast iniziale, LIVE e stato; `stable_preferred` e `candidate_count` della **Thesis FAST**, M1; esito `process_forecast_campaign()` e motivo di rifiuto; azione Director; prezzo entry, SL e TP1/TP2 **solo quando disponibili**.
- Eventi separati di broker dichiarati da una fonte esterna, **non presunti dalla creazione di una campagna**. Sono indicati come *non verificati indipendentemente* finché non confrontati con la storia MT4.
- `event_id` univoco immutabile: ripetere lo stesso evento è idempotente; cambiare il contenuto mantenendo lo stesso ID genera errore.
- Chiavi sconosciute non salvate; campi che paiono segreti (token/password/API key ecc.) **rifiutati**. Non inviare nemmeno gli identificativi sensibili dell'account.

## Le tre politiche controfattuali (NESSUNA modifica LIVE)

- **A** — decisione osservata: `campaign_triggered=True` significa *campagna teorica creata*, **NON** eseguita dal broker.
- **B** — su una campagna creata da A, veto se `forecast_status=WEAKENING` e direzione proposta coincide con Forecast iniziale.
- **C** — su una campagna creata da A, veto se `_thesis_fast_state()` riporta `stable_preferred` **opposto** con almeno due conferme. La logica corrente richiede già l'allineamento della Thesis stabile per la campagna standard; questo veto potrebbe quindi essere ridondante.
- Se A aveva già rifiutato: B e C **non inventano** entrate. Se manca il dato della Thesis o della mappa: `UNKNOWN_GATE` e non un passaggio tacito.
- Non vengono attribuiti PnL, TP o SL a operazioni ipotetiche. Per misurarli servono quotazioni **successive** con corretto clock e modello bid/ask, prezzi del piano e ordini effettivamente negoziati.

## Uso offline

Richiede soltanto Python standard (senza pip). Esempio di input JSONL `example_synthetic_events.jsonl` (SOLO DATI DI TEST, NON QUOTAZIONI VERIFICATE):

```bash
python shadow_g_v4818_recorder.py ingest --db shadow_v4818.sqlite --jsonl example_synthetic_events.jsonl
python shadow_g_v4818_recorder.py report --db shadow_v4818.sqlite --out results
python -m unittest discover -s . -p 'test_*.py' -v
```

Output: `results/summary.json`, `results/decision_audit.csv`; database SQLite con transazioni, senza dipendere dall'ordine di ricezione. **Non conservare il DB su disco effimero Render** se in futuro si abilita l'acquisizione; usare prima una posizione persistente autorizzata e testare restart/doppioni. Il modulo non scrive mai su Render da solo.

## Punto di integrazione FUTURO, non attivo

In una versione dedicata del servizio, dopo `process_forecast_campaign(...)` e dopo il Director, si può estrarre **soltanto** i campi ammessi con `decision_adapter_v4818.from_director_context(...)` e inviarli alla coda del registratore (default disattivato), passando esplicitamente `fast_thesis=_thesis_fast_state(symbol)` e `trade` solo per campagne esistenti. L'integrazione dovrà gestire ogni ritorno anticipato, ogni rifiuto di rischio, autenticazione degli eventi, concorrenza, persistenza, errori senza bloccare il trading e consensi prima di un deploy. **Non modificare `main` né fare deploy senza una verifica separata.**

## Limiti dell'attuale release

- Nessuna acquisizione LIVE su Render/MT4 finché non sarà collegato un produttore di snapshot.
- Nessuna verifica end-to-end di segnali reali o risultato broker: i dati di prova sono sintetici.
- Non prova che B o C migliorino la redditività; il 16 novembre aveva zero trade broker nel bridge durante il blocco.
- Le snapshot fornite dall'esterno devono essere prodotte al momento reale della decisione, non ricostruite usando futuro (il modulo non può attestare da solo questa provenienza).
