# GOLD MASTER — SHADOW G v48.10: durata, retest e uscite proporzionate al rischio

**Ricerca completata:** 14 novembre 2026. **Ambito:** solo offline / SHADOW, non integrato con Render, MT4 né ordini. Nessun risultato costituisce una promessa di rendimento.

## 1. Fonte e riproducibilità

- Fonte originale fornita dall'utente: `XAUUSD1.zip`, storico broker/MT4 XAUUSD M1. Archivio completo 2004–novembre 2026; per questo audit sono stati riletti **3.088.561 minuti** del 2018–novembre 2026, con **agosto 2026 assente**.
- Ingressi: **esattamente quelli accettati** da `G1_SEQ_RETEST` di SHADOW G v48.9, senza riottimizzare, selezionare a posteriori o aggiungere segnali. Sono 590 proposte con spread ipotizzato di 0,30 e 588 con spread 0,60, per un totale di 1.178 righe di riferimento.
- Regole originarie: sweep M15 di 8 barre, shift M5, retest M5 successivo, stop strutturale, target fisso +6 punti XAUUSD. Filtro orario 08–18 secondo l'ipotesi di timezone precedente.
- Lo storico è di prezzi OHLC M1 *bid* assunti, senza dati tick bid/ask né spread variabile; è stato simulato uno spread costante di 0,30 o 0,60 punti e slippage sfavorevole di 0,10 già incorporato nell'entry storica.
- Il replay della configurazione originaria, eseguito da un secondo simulatore, ha riprodotto **tutti i 1.178 esiti** di riferimento. Per preservare i valori floating-point al momento della lettura CSV è indispensabile `float_precision='round_trip'`: altrimenti un valore al limite del target viene erroneamente classificato come TP.
- **22 test unitari superati**, inclusi controllo anticipo del prezzo futuro, barra simultanea TP/SL (ambigua), interruzioni di dati e costo spread lato SELL.

## 2. Time-stop — fissare la durata massima

Una nuova regola chiude al prezzo di chiusura bid della M1 completata dopo 30/60/120/240 minuti dall'entry, se TP o SL non sono già stati raggiunti; il SELL paga l'ask simulato. Se manca una M1 prima del termine senza un TP/SL noto, l'esito rimane `DATA_GAP`, non si inventa un prezzo d'uscita.

| Durata massima | Spread 0,30: saldo | Spread 0,60: saldo | Senza esito a spread 0,60 |
|---|---:|---:|---:|
| 30 minuti | −289,37 | −451,00 | 1 |
| 60 minuti | −304,26 | −451,51 | 2 |
| 120 minuti | −198,40 | −333,46 | 2 |
| 240 minuti | −122,42 | −285,82 | 3 |
| **Senza time-stop (riferimento)** | **−58,49** | **−220,83** | **58** |

**Decisione:** il time-stop 30–240 minuti risolve molti trade prima di interruzioni dei dati, ma peggiora il saldo nominale nello storico. Non inserirlo nel bot. Il confronto non è monetario né una curva equity.

## 3. Target proporzionati allo stop: medesimi ingressi

Un secondo replay ha provato TP pari al 75%, 100% o 150% del rischio iniziale, sempre con SL strutturale identico. `R` indica la distanza fra entry e SL; non significa un lotto maggiore. Non è stato usato breakeven dinamico.

| Uscita | Spread 0,30 | Spread 0,60 | DATA_GAP a spread 0,60 |
|---|---:|---:|---:|
| TP fisso +6 punti | −58,49 | −220,83 | 58 |
| TP 0,75R | +3,08 (−1,00 stress ambigua=SL) | −128,45 | 48 |
| TP 1R | +20,10 | −178,44 | 65 |
| TP 1,5R | −45,90 | −225,99 | 93 |

Con costi più bassi due varianti diventano marginalmente positive, ma **nessuna** resiste allo spread ipotizzato di 0,60, ancora prima di commissioni, swap, lotti e riempimenti reali. Cambiando target cambiano anche i casi senza esito, quindi confrontare solo i saldi nominali esclude una quota non trascurabile di trade.

## 4. Controllo di possibili falsi miglioramenti degli ingressi

Le caratteristiche disponibili **prima dell'entry** sono state esaminate senza usarle per selezionare un filtro operativo:

- I 53 segnali con **rischio iniziale ≥11 punti** danno +80,99 punti nominali con spread 0,60; ma **+80,54 punti provengono dal solo 2026**, dove i segnali sono 23. Nel 2025 lo stesso sottogruppo perde −6,49: il risultato positivo totale non è una regola robusta.
- I 62 segnali delle **17:00** sembrano produrre +67,34 punti, ma **28 di 62** hanno `DATA_GAP`: questo può distorcere il confronto, perché molte perdite/vittorie successive non sono conosciute.
- Il ritardo del retest (5/10/15 minuti), il corpo della candela di conferma e l'ora non mostrano un vantaggio stabile anno per anno. Queste caratteristiche sono ipotesi per ulteriori controlli, **non** filtri da installare.

## 5. Limiti e conclusione

- Anni e soglie di ingresso erano già stati osservati in ricerca precedente. I nuovi studi delle uscite sono **esplorativi**, non un test fuori campione prospettico.
- Lo spread reale storico, la timezone effettiva del broker, l'ordine intrabar dei tocchi, commissioni, esecuzioni reali, sovrapposizione delle operazioni e conversione PnL in EUR sono ancora da misurare.
- `DATA_GAP` resta **unknown**, non è né una perdita né una vittoria; non deve essere messo a zero per costruire un'aspettativa di guadagno.
- **Nessuna configurazione ha dimostrato redditività robusta.** Nessuna modifica a `main`, Render, EA MT4 o protezioni del DEMO.

**Passo tecnico successivo:** acquisire spread bid/ask e timestamp affidabili sullo stesso broker e costruire una nuova ipotesi sulla *qualità del falso breakout* (profondità dello sweep rispetto all'ATR pre-ingresso e distanza del retest), con parametri fissati *prima* della verifica prospettica. Evitare ottimizzazione per anno, fascia oraria o dimensione stop osservando gli esiti già conosciuti.

## Riproduzione

Servono `XAUUSD1.zip`, `GOLD_MASTER_SHADOW_G_V489_RICERCA_2018_2026.zip`, Python con `numpy` e `pandas`, e i file inclusi nel pacchetto ZIP v48.10:

```bash
python -m unittest discover -p 'test_*.py' -v
python time_stop_audit.py --source-zip /path/XAUUSD1.zip --previous-results /path/GOLD_MASTER_SHADOW_G_V489_RICERCA_2018_2026.zip --out ./results
python adaptive_target_audit.py --source-zip /path/XAUUSD1.zip --previous-results /path/GOLD_MASTER_SHADOW_G_V489_RICERCA_2018_2026.zip --out ./results
```

Sono disponibili i CSV aggregati e ogni trade simulato, incluso lo stato originale e l'esito per ciascuna variante.