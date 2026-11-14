# GOLD MASTER — SHADOW G v48.9, ricerca sequenziale M15→M5→retest

**Data ricerca:** 14 novembre 2026. **Stato:** offline / SHADOW ONLY, non collegato al conto, a Render, a MT4 o ai comandi di trading.

## Fonte e procedura

Archivio utente `XAUUSD1.zip`, 7.074.474 righe MT4, di cui **3.088.561 M1** dal 2018 al novembre 2026. Sono stati esaminati direttamente **1.687.076 M1 nel 2022–2026** e **1.401.485 M1 nel 2018–2021**. Agosto 2026 manca. Le sole candele M5/M15 con tutte le rispettive M1 vengono aggregate; gli intervalli con dati mancanti non vengono interpolati.

### Due ipotesi nuove (parametri fissati prima di verificare 2018–2021)

- **SEQ:** una M15 completa supera il massimo/minimo delle otto M15 precedenti di almeno 0,5 punti e chiude dentro il livello di almeno 0,25. Successivamente, entro 15 minuti, una M5 completa rompe con il proprio close il minimo/massimo delle quattro M5 precedenti, con margine 0,15 punti e corpo almeno il 45% del range. Ingresso soltanto all'apertura M1 dopo la conferma.
- **SEQ_RETEST:** richiede anche che una successiva M5 (entro 15 minuti dalla conferma) ritesti e respinga il livello microstrutturale rotto; corpo almeno il 35% del range, close nuovamente oltre il livello. Ingresso all'apertura della M1 successiva al retest.

Per entrambe: stop oltre estremo sweep M15 di 0,75 punti, distanza di rischio 2–15, target fisso **+6 punti XAUUSD**, sessioni 08:00–18:00 del calendario assunto italiano, massimo 20 segnali al giorno, cooldown 30 minuti sullo stesso verso, filtro spike su 12 M1, gap d'ingresso non oltre 2 punti. Le regole non sono state riottimizzate sui risultati. Nelle chiusure BUY si usa il bid; nelle chiusure SELL si simula l'ask con spread fisso; slippage avverso di 0,10. L'interpretazione del timezone broker e dello spread è **ipotesi da verificare**.

## Risultati 2022–2026 (periodo esplorato nello sviluppo)

| Variante | Proposte spread 0,30 | Nominale spread 0,30 | Proposte spread 0,60 | Nominale spread 0,60 |
|---|---:|---:|---:|---:|
| G1 originale v48.8 (fonte: rapporto precedente) | 1.289 | −326,41 | circa 1.289 | −726,91 |
| G1 SEQ | 1.214 | **−430,95** | 1.212 | **−755,32** |
| G1 SEQ_RETEST | 374 | **−66,21** | 372 | **−164,42** |

G1 SEQ_RETEST fa perdere meno punti nominali in questo insieme, **ma produce molti meno ingressi**, pertanto la sola differenza del saldo non dimostra una migliore qualità dei singoli trade.

## Controllo separato 2018–2021

| Anno | SEQ_RETEST, spread 0,30 | SEQ_RETEST, spread 0,60 |
|---|---:|---:|
| 2018 | −21,78 | −24,48 |
| 2019 | +44,91 | +29,70 |
| 2020 | +28,76 | −6,21 |
| 2021 | −44,17 | −55,42 |
| **Totale** | **+7,72** | **−56,41** |

Il 2018–2021 non è stato usato per scegliere le soglie della variante, ma è **un controllo retrospettivo su un periodo precedente**, non una validazione prospettica o un walk-forward temporale convenzionale. Anche qui basta aumentare lo spread ipotizzato da 0,30 a 0,60 per far diventare negativo il risultato complessivo.

## Sommario sui 9 anni disponibili 2018–2026 (agosto 2026 mancante)

| Motore | Proposte con spread 0,30 | Saldo punti con spread 0,30 | Proposte con spread 0,60 | Saldo punti con spread 0,60 |
|---|---:|---:|---:|---:|
| G1 SEQ | 1.828 | −454,78 | 1.826 | −943,11 |
| **G1 SEQ_RETEST** | **590** | **−58,49** | **588** | **−220,83** |

Con spread 0,60 per G1 SEQ_RETEST, 248 TP, 282 SL e **58 casi DATA_GAP** non risolti. Il saldo nominale dei 530 esiti risolti è −220,83 punti, **non** una P&L di portafoglio: operazioni sovrapposte, lotti, swap, commissioni, capitalizzazione, margini e conversione EUR non modellati. Un'eventuale uscita prima della chiusura di mercato o un time-stop potrebbero cambiare i risultati, ma richiedono un test separato fissato a priori.

Nel solo 2026 SEQ_RETEST sembra promettente (+31,70 con spread 0,60), **ma sono appena 40 proposte**, e nei precedenti anni lo stesso modello è negativo: non promuoverlo in live.

## Verifiche tecniche

Sei test unitari superati: M15 completa necessaria; falso breakout con 8 M15 precedenti; retest solo dopo la conferma; barra con TP e SL simultanei marcata AMBIGUOUS; evento futuro non altera lo SL passato; un buco nei minuti non può creare un TP fittizio. Il test rimane una simulazione su OHLC minuto, non su tick bid/ask storici.

## Decisione operativa

1. **Non** promuovere né SEQ né SEQ_RETEST a ordini DEMO/reali. Nessuna modifica a `main`, Render, EA o VPS.
2. Conserveremo G1 SEQ_RETEST come ipotesi di lavoro, ma la prova storica non dimostra redditività.
3. La fase successiva utile è acquisire dati indipendenti e verificare spread, timezone e sequenza dei tocchi via tick, definire time-stop e limiti di posizioni sovrapposte *prima* del successivo test.
4. Qualsiasi ulteriore filtro scelto osservando questi risultati necessita di prova su date future o dati non usati nella selezione.

**Riproduzione:** `python -m unittest discover -s . -p 'test_*.py' -v`; `python g1_sequential_replay.py --zip XAUUSD1.zip --out risultati --years 2022 2023 2024 2025 2026` e poi `--years 2018 2019 2020 2021`.