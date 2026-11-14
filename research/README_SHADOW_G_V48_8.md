# SHADOW G v48.8 — sperimentazione isolata

**NO LIVE DEPLOY. NO MT4. NO TELEGRAM.** Il codice vive su un ramo di ricerca separato, non si aggancia a `app.py` e non cambia `main`, EA, Render, o i limiti di rischio dell'account demo.

## Origine delle ipotesi

Le ipotesi traggono ispirazione dai messaggi del canale Max Gold Operativo ricevuti come HTML (7 gennaio – 13 novembre 2026), e dal riepilogo delle 905 schede di segnale. Il 17 agosto Max ha descritto fallimento di un rialzo, struttura M15, shift microstrutturale e zona di liquidità; in altri messaggi usa più ingressi e chiusure a TP progressivi. Nessuna dimostrazione di redditività è implicata.

## Motori di ricerca (prima versione, soglie da congelare per l'out-of-sample)

- **G1_FAILURE_SHIFT:** falso superamento del massimo/minimo delle 8 M15 precedenti, rientro nella M15 chiusa e microshift M5 confermato.
- **G2_BOS_RETEST:** rottura strutturale chiusa su M15 e successivo retest del livello su una M5 che torna nella direzione della rottura.
- **G3_CONTINUATION:** movimento M15 coerente con breve consolidamento M5 e rottura limitata, senza inseguire uno spike.

G1/G2/G3 sono alternative dello stesso motore: al massimo una proposta per intervallo decisionale, cooldown individuale di 30 minuti, massimo 20 proposte al giorno. Stop strutturale 2–15 punti (valori di ricerca, non risk policy di un conto). Filtro spike sui 12 M1 osservati, soglia 8 punti sulla candela o 6 punti tra close consecutivi.

## Modalità di simulazione

1. Richiede dati **XAUUSD M1 chiusi in UTC**, completi e consecutivi. Un webhook che fornisce un valore del prezzo ogni minuto **non equivale** a candele M1 storiche complete. L'implementazione corrente di GOLD MASTER memorizza snapshot ricevuti dal webhook; non è sicuro trattarli come OHLC broker M1 certificati.
2. M5/M15 vengono ricostruite solo quando sono presenti **tutte** le rispettive candele M1, senza utilizzare una candela ancora in formazione.
3. Una proposta viene registrata alla chiusura M5. L'ingresso ipotetico avviene all'**apertura M1 successiva**, solo se il gap è entro 2 punti; il prezzo di acquisto/vendita include spread e slippage configurato.
4. Per ciascun segnale sono simulati indipendentemente TP a +3, +6, +9, +15 e +25 punti; per target superiori a 6 punti, il BE scatta al +6. Questi sono **scenari alternativi**, non cinque trade né cinque lotti.
5. Se TP e SL sono toccati nella medesima candela senza tick e non è noto quale sia arrivato per primo, l'esito è `AMBIGUOUS`, non un TP assegnato automaticamente. I dati mancanti producono `DATA_GAP` e non permettono di assegnare risultati.
6. Non è ancora stimato il PnL netto (commissioni, slippage storico variabile, overnight, conversione monetaria) né il drawdown live. Non chiamare "profitto" il totale dei punti nominali.

## Esecuzione locale

```bash
python -m unittest discover -s tests -v
python replay_shadow_g_v488.py --m1 /path/to/xauusd_m1.csv --output /path/to/report
```

CSV richiesto (timestamp in **UTC della fine candela**, con timezone o secondi Unix):

```csv
end_ts,open,high,low,close,spread_points
2026-11-16T08:00:00+00:00,3900.2,3900.6,3899.9,3900.1,0.30
```

Importante: un dato senza spread reale può essere usato solo in un'analisi di sensibilità dichiarata. I segnali storici di Max non vengono caricati nel repository; rimangono nel file utente.

## Validazione necessaria prima di qualunque deploy

- Confrontare con i 905 segnali Max **solo** nei casi in cui i dati del broker permettano il replay orario, senza usare messaggi Telegram pubblicati dopo il momento dell'ingresso.
- Chiarire che l'attributo di timezone nell'export Telegram HTML è riportato come `UTC+01:00` anche per mesi estivi: l'allineamento con l'ora broker e l'ora civile è una verifica obbligatoria.
- Gennaio–agosto definizione soglie; settembre–ottobre prova out-of-sample; novembre controllo finale, senza riottimizzare sulle verifiche.
- Verificare tutti i costi, qualità di prezzo, M1/tick first-touch, drawdown e drawdown giornaliero.
- Non collegare a MT4 prima della revisione tecnica e di consenso esplicito: token esposto in una precedente schermata va ruotato prima di riattivare gli ordini automatici.