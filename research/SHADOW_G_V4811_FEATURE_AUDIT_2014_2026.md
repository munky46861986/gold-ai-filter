# GOLD MASTER — SHADOW G v48.11: audit della falsa rottura M15 e del retest M5

**Data:** 14 novembre 2026 · **Stato:** ricerca offline; nessuna modifica a `main`, MT4, Render, broker o ordini.

## Obiettivo

Dopo i risultati negativi della v48.10, verificare se due proprietà **già osservabili prima dell'ingresso** — profondità della falsa rottura M15 e rifiuto del livello su M5 — individuino un sottogruppo di segnali G1 Sequenziale + Retest migliore. Non modificare l'uscita originaria: target +6 punti XAUUSD e stop strutturale.

## Fonte e controlli

- Archivio utente `XAUUSD1.zip`, prezzi XAUUSD M1 esportati da MT4. Una scansione selettiva ha ricostruito **263.866 candele M1** attorno agli eventi per estrarre i dati pre-ingresso.
- Baseline v48.9 congelata per gli anni **2018–2026**, più replay aggiuntivo **2014–2017** con il medesimo codice baseline: **1.394.433 candele M1** in quel periodo.
- Replay della baseline sui periodi 2014–2017 e 2018–2026: rispettivamente **123** e **588** ingressi allo spread ipotizzato di **0,60** (totale **711**); per spread 0,30 gli ingressi sono 123 e 590 (totale 713).
- Vengono ricalcolate 15 candele M15 complete antecedenti alla barra di sweep, la barra M15 di sweep e la barra M5 completa di retest. Il prezzo a partire dalla **candela di ingresso** non partecipa alle nuove feature. **7 test automatici superati**; uno di essi modifica intenzionalmente la candela d'ingresso e verifica che le feature restino inalterate.
- Per **8 eventi unici su 713** le feature non sono calcolabili perché manca almeno una candela del contesto richiesto; questi eventi **non vengono considerati idonei** ai filtri. In tabella è indicato il conteggio per scenario.

## Filtri predefiniti esplorati

| Regola | Definizione prima di osservare l'esito |
|---|---|
| BASE | G1 Sequenziale + Retest v48.9, nessun filtro aggiunto |
| F1 — sweep moderato | profondità di sweep / ATR M15 precedente compresa fra 0,15 e 0,75 |
| F2 — rifiuto | coda di rifiuto M5 almeno il 30% del range della M5 e chiusura almeno 15% del range oltre il livello microstrutturale |
| F3 — combinazione | F1 e F2 contemporaneamente |
| F4 — rientro | rientro M15 rispetto al livello estremo almeno 0,20 ATR e profondità dello sweep non oltre 0,75 ATR |

**Nota metodologica:** gli ATR sono stimati dalle 14 barre M15 completate **prima** della barra che esegue lo sweep, non dalla barra in formazione e non dalla serie futura. Le regole sono esplorative e non costituiscono segnali autorizzati.

## Risultati complessivi 2014–2026

Target fisso +6 punti; SL originale; slippage sfavorevole ipotizzato 0,10 punti; spread fisso **non storico** di 0,30 o 0,60 punti. I saldi sono **punti nominali**, con sole operazioni risolte; non includono commissioni, swap, conversione EUR o comportamento di portafoglio.

| Regola | Segnali a spread 0,60 | Nominale spread 0,30 | Nominale spread 0,60 | Gap a spread 0,60 | Stress spread 0,60: gap=SL |
|---|---:|---:|---:|---:|---:|
| BASE | 711 | −182,37 | **−375,99** | 93 | −986,25 |
| F1 | 557 | −214,18 | −366,33 | 61 | −759,93 |
| F2 | **195** | +26,51 | **−49,80** | **21** | −179,95 |
| F3 | 157 | −12,26 | −66,09 | 14 | −153,95 |
| F4 | 520 | −226,96 | −370,01 | 59 | −748,18 |

Lo stress `gap=SL` è soltanto uno **scenario ipotetico** in cui ogni operazione non risolta viene contabilizzata con la perdita iniziale: non è un limite garantito al danno effettivo in presenza di gap e slippage.

Il risultato nominale F2 a spread 0,30 diventa negativo (−87,69) nello stesso scenario di stress. **Nessun filtro è profittevole nel test conservativo a spread 0,60.**

## F2, ripartizione temporale con spread 0,60

| Periodo | Segnali F2 | Risolti | Gap | Punti nominali noti | Stress gap=SL |
|---|---:|---:|---:|---:|---:|
| 2014–2017 | 32 | 21 | 11 | −5,79 | −65,89 |
| 2018–2021 | 62 | 56 | 6 | −71,21 | −104,71 |
| 2022–2026 | 101 | 97 | 4 | +27,20 | −9,35 |
| **Totale** | **195** | **174** | **21** | **−49,80** | **−179,95** |

F2 non generalizza: ha performance negativa nel 2014–2021 e il vantaggio più recente viene meno nello stress. Le soglie v48.11 non sono state ottimizzate, ma i periodi 2018–2026 erano già stati esaminati nei progetti precedenti; il controllo 2014–2017 resta **storico retrospettivo**, non un test prospettico indipendente.

## Rischi metodologici da non nascondere

1. Lo storico MT4 contiene OHLC ma **non lo spread bid/ask tick-by-tick**. I valori 0,30/0,60 sono ipotesi, non costi documentati del broker.
2. Il fuso orario dell'esportazione MT4 non è verificato con un riferimento esterno; il filtro 08:00–18:00 è quello del motore precedente, non necessariamente la stessa sessione di trading nei vari anni.
3. Le operazioni con `DATA_GAP` non sono veri pareggi e non possono essere scartate silenziosamente per inferire redditività; lo stress ne illustra la sensibilità.
4. I risultati non tengono conto delle posizioni simultanee, della size, delle commissioni, del margine o del drawdown cumulato. Il fatto che F2 riduca le perdite **totali** può dipendere soprattutto dal numero minore di ingressi: serve anche confrontare l'aspettativa per trade, gli intervalli di confidenza e il capitale a rischio.
5. La strategia di partenza è stata sviluppata esaminando gli stessi mercati in passato: non dichiarare un profitto atteso reale né promuovere un filtro perché un sottoperiodo è positivo.

## Decisione e prossima fase

**Non cambiare GOLD MASTER e non inviare ordini.** Tra le quattro feature nuove, F2 merita ulteriori controlli diagnostici, ma **non è autorizzata a esecuzione**: resta negativa con spread elevato, e il campione 2014–2021 non la conferma.

La fase successiva non deve cercare altre soglie su questi stessi anni fino a trovare un saldo positivo. Prima occorre:

- recuperare o registrare candele M1 e tick bid/ask con timestamp affidabile sul broker;
- stabilire in anticipo la gestione dei gap, delle posizioni simultanee e dei costi reali;
- congelare le regole e valutare i nuovi segnali SHADOW sui dati **successivi alla definizione del filtro**, senza ritaratura retrospettiva;
- confrontare segnali, stop, uscita e rischio dei risultati con le schede di Max solo quando l'allineamento temporale è verificato.

## Riproduzione

Pacchetto `GOLD_MASTER_SHADOW_G_V4811_RICERCA_2014_2026.zip`: include codice di audit causale, 7 test, CSV delle feature e degli esiti, baseline v48.9 usata per il periodo aggiuntivo e registro dei controlli. Richiede archivio originale `XAUUSD1.zip` e pacchetto v48.9 con i segnali base.

```bash
python -m unittest -q test_feature_audit
python feature_audit.py \
  --archive /path/XAUUSD1.zip \
  --trades-zip /path/GOLD_MASTER_SHADOW_G_V489_RICERCA_2018_2026.zip \
  --additional-trades holdout_2014_2017/g1_seq_retest_trades.csv \
  --out results
```