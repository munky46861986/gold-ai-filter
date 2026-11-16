# GOLD MASTER / SHADOW G v48.17 — audit XAUUSD M1 del 16 novembre 2026

**Stato:** ricerca offline, nessun ordine, nessuna modifica a MT4/Render/GitHub `main`.
**Fonte primaria:** `XAUUSD1(1).zip` caricato dall'utente il 16 novembre; `XAUUSD1.csv` al suo interno; messaggi Telegram Max e GOLD MASTER del 16 novembre forniti dall'utente.
**Ambito:** 1.130 candele M1 del 16/11/2026 dalle 01:00 alle 19:49 in *orario dello storico MT4*. Intervallo senza minuti mancanti fra le due estremità. Quest'ultima candela potrebbe essere incompleta. Si considerano OHLC come prezzi bid, non dati tick bid/ask verificati.

## 1. Sincronizzazione degli orologi

I livelli prezzo/ora riferiti da Max e GOLD MASTER concordano meglio assumendo **orario dello storico MT4 = orario dei messaggi Telegram + 1 ora**. Verifica indipendente: i livelli TP1 comunicati da Max si toccano in queste candele con tale offset (spread SELL assunto 0,60 pt): SELL delle 11:47 → TP1 alle 14:23; SELL delle 14:38 → TP1 alle 14:57; BUY delle 15:37 → TP1 alle 15:48. La corrispondenza resta un'**inferenza**, non la certificazione del timezone da parte del broker. Per le soglie intrabar non sappiamo il secondo esatto.

## 2. Previsioni iniziali e invalidazioni

| Sessione | Forecast iniziale | Primo TP1 originale | Primo tocco invalidazione M1 | Revisione dichiarata | Scarto |
|---|---|---|---|---|---|
| EUROPE | SELL; TP1 3831,588; invalidazione 3868,982 | non toccato nel periodo verificato | 11:40 (HIGH broker 3869,27) | BUY 11:42 | 2 minuti |
| NEW YORK | BUY; TP1 3880,855; invalidazione 3858,494 | toccato 15:35 | 16:59 (LOW broker 3858,14) | SELL 17:03 | 4 minuti |

L'avviso **WEAKENING** Europa alle 09:24 precede la revisione di 138 minuti, e quello New York alle 14:41 la precede di 142 minuti. Questo NON significa ritardo di 138/142 minuti nell'invalidazione. La rottura della soglia avviene pochi minuti prima della revisione. In Europa nessuna delle candele 12:40–12:42 dello storico si è *chiusa* sopra 3868,982; il livello è stato toccato dal massimo intrabar. Per New York la prima chiusura M1 sotto 3858,494 avviene alle 17:00 Telegram-equivalenti. La routine live usa prezzi dinamici, non soltanto chiusure M1.

Per NEW YORK il target 1 iniziale è stato toccato alle 15:35, durante la fase WEAKENING. Il target 2 (3890,330) non risulta toccato nell'intervallo di confronto sino alle 17:31. Una review di sessione classificata ERRATA non autorizza a trattare tutti i singoli target come perdenti o come trade realmente eseguiti.

## 3. Controllo livelli Max — prezzi, non fill

Tutti e sei i piani hanno **RR prudenziale fino a TP1 < 0,50**. Per i SELL, RR calcolato dal bordo basso della zona; per i BUY, dal bordo alto. Quindi il filtro v48.15 *seleziona zero proposte* il 16/11.

La tabella completa `MAX_LEVEL_TOUCHES_2026-11-16.csv` riporta per ogni piano l'ora Telegram-equivalente del primo tocco teorico di TP1/TP2/TP3 e dello SL originale, dopo il primo messaggio di ingresso. Per i SELL la comparazione usa **ask teorico = bid OHLC + 0,60 punti**. Per i BUY si usa bid teorico. Gli spread effettivi, lo slippage, l'ordine intrabar dei tocchi, il prezzo effettivo di ingresso e le uscite parziali non sono ricostruiti: **non sono PnL**, né prova del successo broker di Max.

Rilievi:
- SELL 08:11: stop originale teoricamente toccato alle 11:38; TP1 non raggiunto. Max comunica uscita alle 11:41.
- SELL 11:47: TP1 rilevato alle 14:23, SL originale alle 15:35. Non si conosce la gestione effettiva dopo TP1.
- SELL 14:38: TP1 alle 14:57, TP2 alle 15:24, SL originale alle 15:35. Max aveva annunciato lo spostamento dello SL alle 15:26, quindi SL originale successivo **non equivale** a perdita eseguita.
- BUY 15:37: TP1/TP2 risultano toccati alle 15:48; SL originale alle 16:23, dopo possibile presa di profitto/BE.
- BUY 16:00: TP1 alle 16:01 e TP2 alle 16:02, MA la prima intersezione OHLC della zona **dal minuto intero successivo** è solo alle 16:07. L'ordine fra reale ingresso e target non è dimostrabile su M1. Non conteggiare i target come fill di quel piano.
- BUY 16:10: il minimo dello storico fino alle 16:46 è 3861,43, sopra SL 3861; primo tocco SL alle 16:56. Le due dichiarazioni Max delle 16:39 e 16:46 sono quindi in conflitto/rettifica, non broker fills certificati.

## 4. Controllo A/B/C — cosa SI e cosa NON si può misurare

| Configurazione | Regola ipotizzata | Cosa emerge dal 16 novembre |
|---|---|---|
| A | GOLD MASTER corrente | Il bridge MT4 aveva il blocco `BROKER_DAY_HISTORY_UNVERIFIED` fino al ripristino alle 18:33; ultimo JSON ricevuto: **0 ordini eseguiti** e 0 PnL broker. Non esistono trade A della giornata da confrontare. |
| B | Sospendi nuovi ingressi nel lato iniziale dal primo WEAKENING alla REVISION | Per NY avrebbe sospeso BUY dalle 14:41 alle 17:03. Tre piani **esterni di Max** sono BUY in quella finestra (15:37, 16:00, 16:10); almeno due avevano target annunciati. Questo è un test di *rischio opportunità*, NON una stima PnL di GOLD MASTER. |
| C | Sospendi il lato iniziale solo se Session Thesis stabile è contraria | Nel codice attuale del ramo `main`, la campagna FORECAST standard **già richiede** `stable_preferred == bias` e Session Thesis stabile nella stessa sessione. Aggiungere il medesimo filtro senza cambiare altro risulterebbe ridondante per gli ingressi standard. Le pre-revision opposte sono percorso separato. |

**Nessun backtest di entrate PnL A/B/C può essere considerato completo con il solo M1:** servirebbero gli snapshot puntuali dei `m1.confirmed`, `m1.score`, Session Thesis stabile, preflight, campagne, prezzi d'ingresso/SL/TP e la sincronizzazione delle fonti di prezzo. Non inventare operazioni del bot assenti dai log.

## 5. Decisione di ricerca

- **Non promuovere B**: il 16 novembre il blocco indiscriminato di BUY in `WEAKENING` potrebbe aver cancellato opportunità favorevoli, in particolare il tocco del target NY BUY alle 15:35; servono dati su ingressi validi, non solo target raggiunti.
- **Non promuovere C come nuovo filtro**: appare già incorporato nel gate Thesis standard; serve dimostrare una vera differenza comportamentale prima di testarlo.
- **Mantenere A sul conto DEMO invariato** e preparare una telemetria SHADOW comparativa che registri *ogni intenzione di entry* prima del controllo di rischio: `ts_telegram`, `ts_broker`, `session`, `forecast_bias`, `forecast_live_status`, `thesis_stable_bias`, `m1_score`, `m1_confirmed`, `risk_gate`, `entry`, `sl`, `tp1`, `reason_A`, `reason_B`, `reason_C`. La telemetria deve **non inviare ordini** e non alterare i criteri di esecuzione. Dati futuri servono per TP/SL reali e opportunità bloccate.
- Il filtro RR≥0,50 di Max resta sperimentale, su un canale indipendente: il 16/11 ha qualificato 0/6 piani.

## Caveat

Differenza di timezone inferita; bid/ask reale non disponibile; SL modificati nel corso della giornata; prezzi di ingresso e ordine degli eventi intrabar sconosciuti; storico terminale scaricato durante la giornata; assenza del feed dei trigger TradingView completo; risultati di Max non verificati da estratto conto. Non c'è evidenza per stimare un vantaggio in EUR o per applicare la modifica al conto reale.