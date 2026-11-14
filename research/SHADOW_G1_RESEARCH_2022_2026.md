# GOLD MASTER — Nuova ricerca SHADOW G1 v48.9 (14 novembre 2026)

**Stato:** ricerca OFFLINE e SHADOW ONLY; nessuna modifica a `main`, al conto DEMO, a MT4, all'EA o a Render.

## Dati verificati

- Fonte: archivio originale `XAUUSD1.zip`, già conservato nella Libreria `/GOLD_MASTER/Storici/XAUUSD1_storico_M1_2004_2026.zip`.
- Archivio completo: 7.074.474 righe di prezzi M1, 2004–13 novembre 2026.
- Replay di segnali SHADOW G1/G2/G3 effettuato su **1.687.076 candele M1** dal 2022 al 13 novembre 2026; agosto 2026 assente.
- Studio degli indicatori ex ante su tutti i **1.289 segnali G1** registrati in questi 5 anni.
- Modello di entrata: SHADOW G v48.8, ingresso alla candela M1 successiva, stop strutturale, risultati solo virtuali. Lo spread è *assunto*, non quello storico del broker UltimaMarkets: 0,30 oppure 0,60 punti, con 0,10 punti di slippage. Non include commissioni, swap, conversione EUR, leva o portafoglio di posizioni sovrapposte.
- I prezzi vengono interpretati come bid e trasformati in mid con metà spread, orario CSV interpretato come Europe/Rome **da verificare**. Nessuna candela M1 può provare l'ordine intrabar di TP e SL; `AMBIGUOUS` rimane distinto e lo stress tratta gli ambigui come SL. `DATA_GAP` resta non verificato.

## 1. G1 invariato — target fisso di 6 punti

| Anno | Proposte G1 | Saldo punti, spread 0,30 | Saldo punti, spread 0,60 | TP / operazioni risolte, spread 0,30 |
|---|---:|---:|---:|---:|
| 2022 | 228 | -108,59 | -153,30 | 84 / 202 = 41,6% |
| 2023 | 202 | -10,47 | -81,13 | 79 / 179 = 44,1% |
| 2024 | 276 | -230,47 | -311,75 | 110 / 260 = 42,3% |
| 2025 | 344 | **+278,68** | **+157,41** | 206 / 334 = 61,7% |
| 2026 | 239 | -255,56 | -338,14 | 131 / 234 = 56,0% |
| **Totale** | **1.289** | **-326,41** | **-726,91** | |

Il 2025 è **unico anno positivo** per questo scenario. Nel 2026 il 56,0% di TP non è sufficiente perché lo stop medio delle perdite è circa 10,11 punti, contro 7,48 nel 2025. Il tasso teorico di pareggio con target +6 e stop medio delle SL è ~62,8% nel 2026, ma il tasso osservato è ~56,0%.

Sono saldi nominali dei segnali risolti, non il P&L effettivo di un portafoglio o di un conto.

## 2. Regime della volatilità — filtro ex ante (esplorativo)

Indicatori costruiti **solo dalle M1 già chiuse prima della decisione**:
- `vol60` = media del movimento assoluto tra due close sulle ultime 60 M1 (minimo 48 coppie valide).
- `vol240` = stesso indicatore sulle ultime 240 M1 (minimo 200 coppie valide).
- `ACCELERATING` quando `vol60 / vol240 > 1,15`; il resto è normale o quieto.
- L'analisi include tutti i segnali con un regime assegnabile; 1.289/1.289 hanno il rapporto calcolabile.

G1 solo quando ACCELERATING, TP+6:
| Anno | Proposte filtrate | Punti, spread 0,30 | Punti, spread 0,60 |
|---|---:|---:|---:|
| 2022 | 143 | -55,57 | -71,47 |
| 2023 | 138 | +27,08 | -20,48 |
| 2024 | 176 | -104,40 | -175,78 |
| 2025 | 139 | +150,91 | +96,03 |
| 2026 | 56 (55 con spread 0,60) | +2,55 | -6,15 |
| **Totale** | **652** | **+20,57** | **-177,85** |

Questo filtro riduce le perdite simulate di alcune situazioni ma **non regge lo spread di 0,60**, e peggiora ancora con le commissioni. È stato esaminato sul medesimo archivio: il piccolo saldo +20,57 non è una conferma fuori campione né un vantaggio economico dimostrato.

## 3. Uscite proporzionali al rischio — test effettivo su M1

Ho realizzato un secondo simulatore indipendente che applica target +0,75R, +1,00R e +1,50R alle stesse entrate e agli stessi stop strutturali G1. R è la distanza `entry → SL` per ogni operazione; non è un cambiamento del lotto. Il replay usa le candele M1 successive all'entrata senza guardare i dati futuri nella scelta dell'ingresso. Nessun BE per le politiche R; TP/SL nella stessa M1 = AMBIGUOUS, candele mancanti = DATA_GAP.

**Controllo incrociato:** usando il TP fisso +6, il nuovo simulatore replica esattamente lo stato dei trade **1282/1282 con spread 0,30 e 1277/1277 con spread 0,60** per i segnali con ingresso. Nessuna discrepanza di stato.

Saldo nominale G1 con spread 0,60:

| Anno | TP fisso +6 | TP 0,75R | TP 1R | TP 1,5R |
|---|---:|---:|---:|---:|
| 2022 | -153,30 | -217,00 | -135,26 | -148,82 |
| 2023 | -81,13 | -97,23 | -70,44 | -107,75 |
| 2024 | -311,75 | -339,01 | -324,34 | -386,08 |
| 2025 | +157,41 | +132,23 | -41,06 | -156,41 |
| 2026 | -338,14 | -368,47 | -274,75 | -463,03 |

**Conclusione:** cambiare semplicemente il TP in multipli dello stop non risolve il problema. Il TP 1R è negativo in tutti i cinque anni con questa ipotesi di spread.

## 4. Diagnosi e decisione

- Le false rotture di G1 richiedono più qualità nel *riconoscimento del contesto e del segnale*, non soltanto un TP differente.
- Il 2025 non rappresenta un vantaggio prevedibile da solo: selezionare dopo aver visto quell'anno genera forte rischio di overfitting.
- Non avviamo G1, G2 o G3 sul conto DEMO; nessuna promozione da SHADOW a ordini.
- Nel futuro SHADOW G v48.9 l'ipotesi prioritaria è verificare *conferma della falsa rottura*: prima una M15 che prende liquidità oltre un estremo, poi rientra e, solo dopo, una M5 che rompe una microstruttura nella direzione opposta. Dovrà essere definita senza anticipazioni, con timestamp e livelli osservabili *prima* dell'ingresso.
- Valutare anche l'ATR M15 ex ante, volatilità per sessione e time-stop come filtri separati, evitando ricerca di soglie col risultato migliore sul passato.
- Per una verifica indipendente, bloccare a priori le regole e usare nuove sessioni live in SHADOW (non dati 2022–2026 già visionati). Verificare bid/ask reali, timezone, tick di primo tocco e limiti di esposizione.

## File prodotti

- `SHADOW_G_REPLAY_2022_2023.py` e `SHADOW_G_REPLAY_2022_2023_SPREAD60.py`: riproduzione dello storico 2022–23.
- `SHADOW_G_G1_VOLATILITY_AUDIT_2022_2026.py`: regime calcolato da passato, aggregato per anno.
- `SHADOW_G_G1_R_MULTIPLE_REPLAY.py`: nuove uscite 0,75R, 1R, 1,5R con validazione incrociata TP+6.
- `SHADOW_G_G1_REGIME_COMPARISON_2022_2026.csv` e `SHADOW_G_G1_R_MULTIPLE_SUMMARY_2022_2026.csv`: tabelle replicabili.
- `SHADOW_G_G1_R_MULTIPLE_2022_2026.csv`: singoli esiti dei test varianti.

**Nota di metodologia:** queste osservazioni sono ricerca esplorativa retrospettiva con selezione multipla di modelli, non un certificato di profittabilità e non un backtest sui 7 milioni di minuti per le strategie.