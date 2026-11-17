# SHADOW G v48.18 — Ricostruzione PRE-M1 del 17 novembre 2026

## Stato e fonti

- Fonte: log originali Render `SHADOW_V4818_RECORD`, archiviati integralmente nei due CSV qui nella stessa cartella. Data locale: Europe/Rome (UTC+1).
- Finestra raccolta: 07:00-22:59 (ora italiana), con periodi privi di osservazioni: mancanza di log non prova assenza di segnali.
- Snapshot di decisione recuperati: **759**. Non sono candele complete né ordini.
- Segnali M1 `confirmed=true`, `score >=6`: **16**; raggruppati in **5** gruppi osservativi. Regola congelata: stesso lato, sessione, categoria e gap <=30 minuti.
- Allineati Forecast+Thesis+M1: **12**; precedente alla mappa: **1**; contro Forecast, ma a favore della Thesis: **3**.
- Broker storico non verificato `BROKER_DAY_HISTORY_UNVERIFIED`; **nessuno dei 16 casi** ha un ingresso eseguito o una entry/sl/tp nel log. Quindi gli esiti futuri saranno solo simulazioni.

## Tutti i candidati (NON trade eseguiti)

| Ora IT | Gruppo | Sessione | M1 | Score | Prezzo | Categoria |
|---|---|---|---|---:|---:|---|
| 08:02 | G1 | EUROPE | BUY | 7 | 3877.755 | BEFORE_FORECAST |
| 08:06 | G2 | EUROPE | BUY | 6 | 3877.86 | FORECAST_THESIS_M1_ALIGNED |
| 08:14 | G2 | EUROPE | BUY | 6 | 3878.065 | FORECAST_THESIS_M1_ALIGNED |
| 08:27 | G2 | EUROPE | BUY | 6 | 3877.605 | FORECAST_THESIS_M1_ALIGNED |
| 08:51 | G2 | EUROPE | BUY | 6 | 3873.215 | FORECAST_THESIS_M1_ALIGNED |
| 09:45 | G3 | EUROPE | BUY | 8 | 3870.07 | FORECAST_THESIS_M1_ALIGNED |
| 09:47 | G3 | EUROPE | BUY | 6 | 3870.83 | FORECAST_THESIS_M1_ALIGNED |
| 09:48 | G3 | EUROPE | BUY | 6 | 3871.615 | FORECAST_THESIS_M1_ALIGNED |
| 09:53 | G3 | EUROPE | BUY | 8 | 3873.855 | FORECAST_THESIS_M1_ALIGNED |
| 14:38 | G4 | NEWYORK | SELL | 8 | 3846.86 | FORECAST_THESIS_M1_ALIGNED |
| 14:39 | G4 | NEWYORK | SELL | 8 | 3840.735 | FORECAST_THESIS_M1_ALIGNED |
| 14:40 | G4 | NEWYORK | SELL | 6 | 3839.085 | FORECAST_THESIS_M1_ALIGNED |
| 14:47 | G4 | NEWYORK | SELL | 6 | 3845.445 | FORECAST_THESIS_M1_ALIGNED |
| 15:04 | G5 | NEWYORK | BUY | 6 | 3858.2 | COUNTER_FORECAST_THESIS_M1 |
| 15:16 | G5 | NEWYORK | BUY | 6 | 3860.9 | COUNTER_FORECAST_THESIS_M1 |
| 15:22 | G5 | NEWYORK | BUY | 6 | 3862.53 | COUNTER_FORECAST_THESIS_M1 |

## Cosa indica, senza look-ahead

- **G2** BUY Europa iniziale: più conferme nella stessa direzione, evitare conteggi multipli.
- **G3** BUY Europa con Forecast WEAKENING: necessario confrontare versione B (pausa) con baseline.
- **G4** SELL NY: M1 fino a 8, ma il target 2 della mappa iniziale è stato annunciato raggiunto alle 14:39; verificare il NO CHASE.
- **G5** BUY NY: M1+Thesis BUY alle 15:04/15:16/15:22, prima della revisione BUY ufficiale alle 15:34; studiare PRE-REVISION, non dare per scontato che sarebbe stata aperta.

## Protocollo da usare domani sulle candele M1

1. Allineare timestamp dello storico MT4 ai log UTC+1, verificando un prezzo comune; **non assumere offset senza controllo**.
2. Conservare tutti i 16 snapshot. Per i risultati principali, **solo il primo segnale per gruppo**, nessun doppio conteggio.
3. Calcolare MFE/MAE e primo tocco virtuale entro H10/H30, con scenari spread/slippage dichiarati; classificare ambiguo se SL e TP sono toccati nella stessa M1.
4. Gli attributi `entry/sl/tp1/tp2` sono null a causa del blocco broker. Eventuali stop e target di prova sono *ipotesi*, mai ordini GOLD MASTER.
5. Confrontare A/B/C senza selezione retrospettiva del candidato migliore; distinguere ogni evento osservativo dal trade formalmente qualificato.
6. Questa è la **telemetria v48.18**. I report indipendenti LAB v48.7 richiedono l'estrazione dei loro stati; non vanno inventati.

[Archivi grezzi 06-14 UTC](SHADOW_2026-11-17_06-14UTC.csv) · [14-22 UTC](SHADOW_2026-11-17_14-22UTC.csv) · [Candidati congelati](CANDIDATI_SHADOW_2026-11-17.csv)
