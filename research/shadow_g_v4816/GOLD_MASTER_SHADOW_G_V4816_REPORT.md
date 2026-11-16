# GOLD MASTER × MAX — SHADOW G v48.16: audit causale del 16 novembre 2026

**Stato:** ricerca offline, senza esecuzioni, deploy, modifiche all'EA, a Render o al ramo `main`.
**Fonti:** file utente `Testo incollato(20261116-163851).txt` (messaggi di Max e GOLD MASTER fino alle 17:31), JSON `/mt4/status` incollato dall'utente dopo il ripristino della comunicazione (ultimo heartbeat 18:33), immagini MT4 fornite, codice `app.py` della branch GitHub preesistente, report offline v48.13 e v48.14. Nessun dato tick o storico broker M1 del 16 novembre disponibile nell'archivio XAUUSD fornito: termina il 13 novembre 2026.

## 1. Risultato tecnico del 16/11: separare errore strategico da errore bridge

La mattina il bridge MT4 non aveva comunicazioni del broker valide: `BROKER_DAY_HISTORY_UNVERIFIED`, `locked=true`, conto 4270639. Dopo aver compilato URL/token/simbolo, la foto degli Esperti conferma `POLL OK`; successivo JSON delle 18:33 indica `broker_day_reconciled=true`, `pnl_source=MT4_BROKER_CLOSED_HISTORY`, `locked=false`, `balance=equity=1000 EUR`, `closed_pnl=0`, `trade_count=0`, `commands_opened=0`, `commands_completed=0`. **Questi dati dimostrano lo sblocco e zero aperture documentate dal bridge, NON dimostrano se eventuali campagne previsionali storiche avrebbero vinto.** Nessuna modifica alla scelta dell'utente `EnableTrading=true`; il cambiamento nello stato AutoTrading è esterno a questa ricerca.

## 2. Sei piani Max e calcolo ex ante delle distanze (non esiti)

Per ogni SELL il punto d'ingresso prudente è il bordo **inferiore**; per ogni BUY è il bordo **superiore**. Rischio = distanza dall'ingresso prudente allo SL; premio = distanza al TP di interesse. Non sono conteggiati spread, commissioni, slippage o fill.

| Ora | Tipo | Rischio pt | RR TP1 | RR TP2 | RR TP3 | RR teorico 50% TP1 + 50% TP3 | Primo target con RR >= 0,50 |
|---|---|---:|---:|---:|---:|---:|---|
| 08:12 | SELL 3853–56 | 14 | 0,214 | 0,429 | 0,643 | 0,429 | TP3 |
| 11:50 | SELL 3868–72 | 14 | 0,286 | 0,500 | 0,714 | 0,500 | TP2 |
| 14:38 | SELL 3868–71 | 9 | 0,333 | 0,667 | 1,000 | 0,667 | TP2 |
| 15:38 | BUY 3879–81 | 14 | 0,214 | 0,429 | 0,643 | 0,429 | TP3 |
| 16:01 | BUY 3874–77 | 13 | 0,231 | 0,538 | 0,769 | 0,500 | TP2 |
| 16:11 | BUY 3871–74 | 13 | 0,231 | 0,462 | 0,692 | 0,462 | TP3 |

**Soglia RR>=0,50 sulla regola congelata v48.15 (TP1): 0/6.** RR teorico TP2: 3/6; TP3: 6/6; 50% TP1+50% TP3: 3/6. Non utilizzare quest'ultimo insieme di confronti per scegliere a posteriori un nuovo vincitore: l'uscita più lontana viene raggiunta meno spesso, e la coppia 14:38 è descritta da Max come «stesso trade con stop loss stretto», quindi non sono sei esperimenti statisticamente indipendenti.

### Messaggi di esito: cosa è verificabile

Max **ha annunciato** il raggiungimento di TP1 per i piani delle 11:50, 14:38, 15:38, 16:01 e TP2 per gli ultimi tre; il SELL iniziale è descritto come uscito senza TP1. Per il BUY delle 16:11 alle 16:39 dichiara stop e alle 16:46 precisa che il prezzo **non** ha toccato 3861: classificare esito **contraddittorio/non determinato**, non perdita confermata. Le dichiarazioni non costituiscono esecuzioni broker né dimostrano PnL o completamento di tutti i target.

### Controprova sullo storico già studiato, NON sul 16/11

Il precedente replay v48.13 dei **905 piani gennaio–13 novembre 2026** ha trovato con spread simulato 0,60 punti, su 582 casi comparabili, **−1.012,16 punti nominali** per la gestione 50% TP1/50% TP2 con stop a BE sulla seconda metà, e **−1.069,72 punti** per TP1/TP3. Quindi promuovere TP3 soltanto perché nei sei piani odierni supera il rapporto geometrico 0,50 sarebbe scorretto. Lo stesso replay non riproduce esecuzioni reali di Max.

## 3. Due forecast GOLD MASTER iniziali errati — cronologia, non backtest

| Evento | Europa | New York |
|---|---|---|
| Forecast originale | 08:03, SELL, 78/100 | 14:33, BUY, 84/100 |
| Avviso weakening | 09:24, prezzo 3860,740 | 14:41, prezzo 3866,520 |
| Thesis nell'avviso | **EUROPE_FADE_SELL → SELL**, ancora conforme alla mappa | **NY_FADE_SELL → SELL**, opposta alla mappa BUY |
| Invalidation originale | sopra 3868,982 | sotto 3858,494 |
| Distanza fra warning e invalidazione | 8,242 punti | 8,026 punti |
| Revisione ufficiale | 11:42, BUY, prezzo 3869,125 | 17:03, SELL, prezzo 3858,005 |
| Warning → messaggio revisione | **138 minuti** | **142 minuti** |
| Review iniziale | 12:31, ERRATO | 17:31, ERRATO |
| Sessione reale secondo il bot | Open 3848,815, close 3874,315 (+25,500) | Open 3869,485, close 3859,215 (−10,270) |

Nota: la review NY contiene massimo **3888,955**, superiore al primo target BUY **3880,855**, ma inferiore al secondo **3890,330**. Dire che la *mappa iniziale* è ERRATA per l'esito direzionale della sessione non equivale a dire che nessun livello fosse mai raggiungibile; il raggiungimento di un livello, d'altra parte, non conferma fill o profitto.

I 138 e 142 minuti sono **distanze fra notifiche**, NON misure del primo attraversamento dell'invalidazione. Per questo servono eventi tick/M1 della giornata. Il cronometro è letto dai messaggi Telegram, non dal broker. La forza 78/100 e 84/100 è **score euristico**, non probabilità di successo.

## 4. Lettura tecnica del codice, verificata su `app.py`

La funzione `maybe_dynamic_forecast_update` stabilisce `WEAKENING` se il prezzo è vicino all'invalidazione rispetto al range di riferimento oppure se le Thesis contrarie lo richiedono. Soltanto l'invalidazione formale (`price >= invalidation` per SELL, `price <= invalidation` per BUY), insieme alle verifiche del nuovo lato, consente la revisione automatica.

`process_forecast_campaign` non considera **da solo** `WEAKENING` un veto: il blocco immediato di stato è `INVALIDATED`, `REASSESSING`, `ARCHIVED`. **Però** un ingresso standard richiede già che `stable_preferred` della Thesis coincida con il bias Forecast e che M1 sia confermato nello stesso lato: perciò non è lecito dire che il bot avrebbe comunque aperto un trade sbagliato dopo il warning. La PRE-REVISION ha a sua volta conferme più forti e separate.

Risultato metodologico: la «debolezza» non deve essere trasformata in un flip automatico. Un candidato da provare, senza cambiare il codice operativo, è **SHADOW-WEAKENING-GATE**: marcare ogni nuova proposta Forecast sul lato iniziale come `PAUSE_CANDIDATE` dal primo warning fino a ripresa documentata delle condizioni originali o revisione formale; contare operazioni *evitate*, trade vincenti *persi*, durata di blocco, falsi allarmi, e performance after cost sul medesimo stream. Non intervenire su gestione di posizioni già aperte o sugli altri motori.

## 5. Protocollo di ricerca seguente

1. Acquisire eventi storici completi di Forecast/Thesis/M1, inclusi warning non seguiti da inversione, e prezzi M1 dopo l'evento; **il file del 16/11 e lo storico fino al 13/11 non bastano** per un backtest quantitativo del nuovo gate.
2. Confrontare A = algoritmo attuale; B = «pausa nuovi ingressi nella direzione iniziale da weakening»; C = più stretto, pausa soltanto se si rileva anche Thesis opposta *stabile*. Tutti i gate sono **frozen** prima del successivo test, non scelti dai risultati del 16/11.
3. Usare l'istante di notifica reale e almeno la prima barra **completamente successiva** per ogni controfattuale. Niente first-touch indeterminato trasformato in vittoria, nessuna liquidazione immaginaria senza bid/ask, niente conteggi doppi per ri-entry e piani Max sovrapposti.
4. Confrontare il rapporto geometrico v48.15 su TP1 contro le uscite progressive **come esperimento separato**, tenendo ferma la soglia prospettica RR TP1 ≥0,50. Riportare tutti gli scartati.
5. Non modificare `main`, Render, VPS, EA o trading account. Non ci sono elementi per dichiarare una strategia profittevole.

## 6. Riproducibilità

File `nov16_audit.py` e `test_nov16_audit.py`: parser del documento utente, calcolo delle distanze ex ante e cronologia dei forecast; **15 test automatici superati**; CSV `max_plans_nov16.csv`, `forecast_events_nov16.csv`, JSON `audit_summary.json`. Il programma non apre ordini, non comunica con internet, non contiene token e non ricostruisce fill. Non pubblicare su GitHub il file originale del canale Telegram, né credenziali.