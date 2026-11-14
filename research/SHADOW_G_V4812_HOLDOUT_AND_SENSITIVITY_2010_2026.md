# GOLD MASTER — SHADOW G v48.12: controllo indipendente 2010–2013 e robustezza 2010–2026

**Data:** 14 novembre 2026 · **Ambiente:** soltanto ricerca offline. Nessuna modifica al ramo `main`, Render, EA MT4, token o ordini.

## Obiettivo

Verificare il filtro F2 già congelato nella v48.11 sui dati precedentemente non utilizzati **2010–2013**, poi riassumere e stressare il comportamento su **2010–2026**. Non è stata modificata alcuna regola di ingresso, di stop o di uscita in base agli esiti di questi nuovi anni.

## Fonte

`XAUUSD1.zip`, storico XAUUSD MT4 consegnato dall'utente e salvato in Libreria in `GOLD_MASTER/Storici/XAUUSD1_storico_M1_2004_2026.zip`. I nuovi replay v48.12 includono **1.318.323** M1 del 2010–2013 (316.648 del 2010, 1.001.675 del 2011–2013), oltre alle vecchie prove v48.11 2014–2026. Si mantengono le ipotesi del motore v48.9: candele M1 complete, M5/M15 ricostruite a fine barra; ingresso alla M1 successiva; BUY/SELL teorici su OHLC trattati come bid, spread fisso ipotizzato 0,30/0,60 punti XAUUSD e slippage 0,10. Target 6 punti, stop strutturale; gap di dati non attribuiti a vittoria.

F2 è lo stesso filtro del 14 novembre nella v48.11: **coda di rifiuto della M5 di retest ≥30% del range** e **chiusura ≥15% del range oltre il livello di microstruttura**. Le feature sono calcolate esclusivamente su M1 antecedenti all'istante d'ingresso. Gli anni 2010–2013 non erano stati usati per scegliere tali soglie, ma rimane un test storico retrospettivo, **non** un test live prospettico.

## Nuovo controllo 2010–2013

Con spread simulato di 0,60 punti:

| Regola | Segnali | TP | SL | Non risolti | Saldo dei risolti | Scenario non risolti=SL |
|---|---:|---:|---:|---:|---:|---:|
| G1 Seq + Retest | 196 | 54 | 104 | 38 | −266,10 | −483,02 |
| G1 Seq + Retest + F2 | 40 | 11 | 23 | 6 | **−64,40** | **−100,17** |

Con spread ipotizzato 0,30, F2 mantiene **−45,22 punti** nei soli esiti conosciuti e **−73,35** con non risolti=SL.

## Totale complessivo 2010–2026

Sono **907** proposte della baseline e **235** con F2 allo spread 0,60. Lo stesso periodo contiene **909** proposte con spread 0,30, a causa delle diverse regole di ammissione dipendenti dallo spread.

| Spread | Regola | Segnali | TP | SL | Non risolti | Nominale noto | Non risolti=SL |
|---|---|---:|---:|---:|---:|---:|---:|
| 0,30 | BASE | 909 | 342 | 437 | 130 | −397,31 | −1.187,85 |
| 0,30 | F2 | 235 | 99 | 112 | 24 | **−18,71** | −161,04 |
| 0,60 | BASE | 907 | 324 | 452 | 131 | −642,09 | −1.469,27 |
| 0,60 | F2 | 235 | 91 | 117 | 27 | **−114,20** | **−280,12** |

Il filtro riduce molto le entrate e anche la perdita nominale assoluta, ma **non elimina la perdita media per operazione**. F2 con spread 0,60 ha **−0,549** punti per trade risolto e **−0,137R** medi (R = PnL nominale / rischio iniziale). Sono dati simulati senza commissioni e senza ricostruzione del portafoglio.

### Sensibilità di soglia

Sono state valutate, **per verificare fragilità, non per scegliere retroattivamente un vincitore**, le 9 combinazioni date da coda M5 ≥0,25/0,30/0,35 del range e chiusura oltre livello ≥0,10/0,15/0,20 del range. **Tutte e nove danno saldi nominali negativi con spread 0,60** nei trade risolti: dal migliore −41,48 al peggiore −182,66 punti. Anche tutti gli stress con gap=SL sono negativi. Le soglie v48.11 originali (0,30 e 0,15) restano congelate.

### Incertezza statistica descrittiva

Bootstrap esplorativo per **giornate di trading**, 5.000 riscampionamenti con seme 4812, limitato agli esiti TP/SL conosciuti:

- F2, spread 0,60: **208 operazioni risolte in 201 giornate**; media −0,1369R per operazione; intervallo percentilico 95% circa **[−0,2699R; −0,0030R]**.
- F2, spread 0,30: 211 operazioni risolte; media −0,0569R; intervallo circa [−0,1902R; +0,0827R].

Questi non sono intervalli di affidabilità del futuro: ignorano risultati mancanti, dispersione dei costi, cambiamenti di regime, selezione multipla delle strategie e incertezza sul modello di esecuzione. Non dimostrano un vantaggio reale.

## Qualità e limiti

1. **Fuso orario MT4 non certificato**; ore operative 08–18 interpretate nel clock originale dello storico.
2. **Spread storico bid/ask non disponibile**; 0,30/0,60 sono scenari ipotetici, non costi certificati UltimaMarkets.
3. Un'operazione `DATA_GAP` non equivale a break-even né necessariamente a SL; lo scenario `non risolti=SL` è solo uno stress illustrativo.
4. Lo storico 2026 non include agosto; non interpolare i mesi mancanti.
5. I trade possono sovrapporsi, e i punti nominali non sono profitti in EUR con size/risk guard; mancano commissioni, swap, slippage effettivo, equity curve broker.
6. Le soglie sono state scelte su dati storici prima del 2010–13, e ripetere prove sugli stessi anni aumenta il rischio di adattamento ai dati.
7. Non è dimostrato che questa logica riproduca il metodo operativo di Max. Le sue comunicazioni Telegram non forniscono da sole fill bid/ask indipendenti.

## Decisione di ricerca

**Non promuovere F2 o G1 al conto DEMO o al broker.** La v48.12 aggiunge evidenza negativa indipendente dalle precedenti ottimizzazioni e non fornisce un segnale robustamente profittevole.

Il passo successivo utile non è scegliere la migliore delle nove soglie appena esplorate: è passare a un protocollo prospettico con spread/tick bid/ask reali, orari broker confermati, gestione delle posizioni sovrapposte e confronto strutturato con le entrate del trader Max. Le ipotesi future v48.13 andranno *pre-registrate* e testate su anni non utilizzati in alcun modo per definirle, con segmenti di mercato rilevanti. Finché questo non accade, nessuna esecuzione automatica.

## Riproduzione

Il pacchetto v48.12 contiene `holdout_f2_validation.py`, `robustness_grid.py`, `bootstrap_f2.py`, `test_v4812.py`, CSV dei 2010–13 e delle prove di robustezza, con un riferimento alla baseline congelata v48.9 e alla funzione per le feature della v48.11. Richiede il grande archivio ZIP originale per il replay completo.

Test automatici verificati: **5/5 nuovi test v48.12**, oltre ai **7/7 test v48.11** eseguiti nuovamente. Sono test tecnici, non validazione di redditività.