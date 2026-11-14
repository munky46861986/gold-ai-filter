# GOLD MASTER — SHADOW MAX PLANS v48.13

**Data:** 14 novembre 2026 · **Tipo:** ricerca OFFLINE, senza ordini MT4, Render, Telegram o modifiche al ramo operativo `main`.

## Perché questa ricerca

Dopo G1/G2/G3 e il filtro F2, è stato verificato il contenuto originale dei segnali di **Max Gold Operativo**, non solo i pattern genericamente "ispirati" a Max. La domanda precisa è: se un osservatore avesse seguito in modo meccanico e conservativo la zona, SL e i target pubblicati, quali livelli avrebbe effettivamente potuto raggiungere il prezzo **dopo** il messaggio? Non è un audit degli ordini realmente eseguiti da Max e non è una verifica dei suoi profitti dichiarati.

## Fonti ispezionate

- **905 schede strutturate** `MAX_segnali_strutturati.csv`, 466 BUY, 439 SELL, messaggi 7 gennaio–13 novembre 2026; ogni scheda collegata al relativo ID Telegram e all'HTML originale.
- **12 file HTML Telegram** (nomi vari `messages*.html`), verificati direttamente per controllare livelli e frasi originali.
- **273.974 M1 2026** dall'archivio MT4 dell'utente `XAUUSD1.zip`, disponibili gennaio–luglio e settembre–13 novembre; **agosto 2026 assente**. Lo storico contiene OHLC bid approssimativi, non tick bid/ask né spread storico.
- In otto piani il campo `tp_last` punta nella direzione sbagliata (per esempio BUY con ultimo TP sotto TP1); sono **esclusi dal confronto del target finale**. Nel testo originale sono presenti anche diversi valori TP incongruenti, conservati come errori di qualità, non corretti silenziosamente. I TP intermedi sono ricostruiti e ordinati solo se numericamente compatibili.

## Scoperta 1 — Offset di orario nelle fonti

Il file Telegram dichiara un timestamp con `UTC+01:00`. Lo storico MT4 non certifica il proprio timezone. L'allineamento retrospettivo prezzo–zona indica fortemente **timestamp Telegram + 1 ora = timestamp MT4**.

| Offset applicato al messaggio | Messaggi con prezzi disponibili | Prezzo dell'ultima candela M1 *chiusa* entro 5 punti dalla zona | Distanza mediana oltre la zona |
|---|---:|---:|---:|
| +0 ore | 821 | 45,19% | 5,89 punti |
| **+1 ora** | **830** | **94,22%** | **0,48 punti** |
| +2 ore | 830 | 48,31% | 5,36 punti |

Il risultato è coerente per i mesi gennaio–luglio e settembre–novembre; in ottobre il tasso entro 5 punti rimane comunque 86,8%. Lo scarto di un'ora **non è una conferma ufficiale del timezone del broker** e il suo riconoscimento sullo stesso campione introduce una scelta retrospettiva.

## Protocollo del replay

1. Usa esclusivamente la **prima candela M1 successiva** al minuto di pubblicazione (convertito con offset +1 ora), non la candela del messaggio: evita di leggere un massimo/minimo avvenuto prima della pubblicazione.
2. Un piano viene considerato *potenzialmente entrato* se il prezzo disponibile entra nella zona pubblicata nei primi 30 minuti; ingresso stimato all'open della candela o al primo bordo della zona toccato da OHLC. Non è un fill del broker.
3. Ipotesi di spread fisse **0,30 / 0,60 punti XAUUSD**, slippage avverso 0,10, BUY eseguiti lato ask e vendite lato bid. SL e TP vengono valutati sul lato di uscita corretto con spread ipotizzato. Nessuna commissione, swap o conversione EUR.
4. Orizzonte massimo **240 minuti** dall'ingresso. Se TP/SL non arrivano, l'eventuale *TIMEOUT_MARK* è un prezzo teorico di chiusura, non un risultato dichiarato da Max.
5. Quando l'OHLC non determina se SL o TP sia arrivato per primo nella stessa candela, l'esito è **AMBIGUOUS**. Gap di dati oltre due minuti interrompono la verifica. I piani senza ingresso non vengono conteggiati come operazioni perse o vinte.
6. Per le uscite progressive, simula due metà **uguali e separate**: 50% a TP1, 50% al TP2/TP3/ultimo TP con stop del secondo 50% spostato al prezzo d'ingresso dopo TP1. **Non è la gestione reale di Max**, che può usare altri lotti, scaling, uscita discrezionale e più operazioni sovrapposte.

## Risultato 2 — Il TP1 frequente non basta

| Replay singolo TP1 | Spread 0,30 | Spread 0,60 |
|---|---:|---:|
| Piani pubblicati | 905 | 905 |
| Ingressi stimati inclusi quelli ambigui | 730 | 722 |
| Nessuna entrata nella zona in 30 min | 100 | 108 |
| Dati insufficienti prima dell'ingresso | 75 | 75 |
| Ingressi con ordine intrabar ambiguo | 70 | 59 |
| **TP1 prima di SL** | **447** | **437** |
| **SL prima di TP1** | **207** | **221** |
| Primo obiettivo raggiunto tra i soli TP/SL | 68,3% | 66,4% |
| Saldo in punti sui soli TP1 e SL non ambigui | **−559,54** | **−781,68** |
| Punti medi sui soli TP/SL conosciuti | −0,856 | −1,188 |

Con spread 0,60, il guadagno medio dei 437 TP1 risulta **+3,90 punti**, mentre la perdita media dei 221 SL risulta **−11,25 punti**. Per coprire quel rapporto di premi e rischi servirebbe circa **74,3% di TP1** tra gli esiti chiaramente risolti (prima delle commissioni), superiore al 66,4% osservato. Quattro timeout valutati in via teorica come chiusura M1 producono +66,01 punti, riducendo a −715,67 la somma con timeout; non sono però broker fills e non cambiano la conclusione.

Un bootstrap descrittivo con 10.000 ricampionamenti delle **195 giornate** con trade TP/SL, spread 0,60, ha dato per la media per operazione un intervallo percentilico 95% di circa **[−1,79; −0,59] punti**; non fornisce garanzie predittive e non risolve le incertezze di ingresso/overlap/commissioni.

## Risultato 3 — Uscite progressive

Per i target intermedi e l'ultimo target con valori numerici coerenti, sullo **stesso sottoinsieme con esito completo** (spread 0,60):

| Esempio meccanico 50% TP1 + 50% runner | Trade confrontabili | TP1-only sugli stessi | Due uscite sulla stessa selezione | Differenza |
|---|---:|---:|---:|---:|
| Runner a TP2 con BE dopo TP1 | 582 | −1.034,91 | −1.012,16 | +22,75 |
| Runner a TP3 con BE dopo TP1 | 582 | −1.034,91 | −1.069,72 | −34,81 |
| Runner all'ultimo TP valido con BE dopo TP1 | 580 | −972,11 | −1.062,15 | −90,04 |

Sono **somme di punti nominali tra piani potenzialmente sovrapposti**, non equity, non bilancio in EUR. La lieve differenza positiva TP2 rispetto a TP1-alone **non** significa che il metodo TP2 sia positivo: entrambi sono negativi sul sottoinsieme. TP3 e ultimo TP peggiorano. Gli esiti intrabar non sequenziabili sono esclusi.

## Risultato 4 — Finestra di ingresso

Nello scenario spread 0,60, saldo sui soli TP1/SL definitivi:

| Ingresso entro | Trade TP1 | Trade SL | Saldo nominale |
|---|---:|---:|---:|
| 10 minuti | 391 | 205 | −778,48 |
| **30 minuti** | **437** | **221** | **−781,68** |
| 60 minuti | 458 | 227 | −770,38 |

Il risultato non diventa positivo ampliando o restringendo la finestra: il problema del rapporto payoff/rischio resta.

## Cosa sappiamo e cosa NON sappiamo

**Sappiamo** che gli orari Telegram vanno riallineati prima di qualsiasi confronto, che buona parte delle zone è coerente con il prezzo di mercato e che il **piano statico e meccanico** TP1/SL pubblicato non appare profittevole su questi dati con spread stimato. Questo è molto diverso dal sostenere che **Max come trader reale perda**: senza contratti, registri broker, lotti, prezzi di esecuzione, timing degli spostamenti di SL, aggiunte e chiusure parziali, non si può replicare la gestione discrezionale.

Lo storico non dispone del mese di agosto, di tick bid/ask e di spread minuto per minuto. I piani di un medesimo giorno si sovrappongono e non è stato simulato un portafoglio con capitale e limiti di rischio. Molti segnali non entrati, entrati in modo incerto o senza dati sufficienti non contribuiscono ai saldi riportati: non interpretare i risultati come un test broker completo. Le performance future non sono garantite.

## Decisione e prossimi passi

- **Nessuna promozione a MT4 o a un conto reale.** Nessuna variazione a `main`, Render, EA o AutoTrading.
- Una futura **v48.14** dovrebbe concentrarsi sul *timing e gestione dinamica* degli stop/BE e sul filtrare i piani prima dell'ingresso con caratteristiche causali del contesto, non copiare gli annunci di TP come risultati certi.
- Ricercare la conferma indipendente dell'orologio broker e dati **bid/ask tick** per evitare arbitraggi apparenti dovuti a OHLC di un minuto.
- Definire un protocollo prospettico congelato, con limiti di rischio e controllo delle contemporaneità, su dati mai usati in questa lunga fase di ricerca.

## Riproducibilità

Sono inclusi `max_plan_replay_v4813.py`, `target_ladder_audit.py`, **8 test unitari**, i CSV di allineamento, entrata e uscite. Si usano come input lo storico M1 e i segnali originali con gli HTML, che **non** sono inclusi nel piccolo pacchetto risultati per non duplicare l'archivio dell'utente.