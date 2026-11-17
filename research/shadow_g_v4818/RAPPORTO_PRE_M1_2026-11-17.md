# SHADOW G v48.18 — Ricostruzione PRE-M1 del 17 novembre 2026

## Stato e fonti

- Fonte: log originali Render `SHADOW_V4818_RECORD`, archiviati integralmente nei due CSV qui nella stessa cartella. Data locale: Europe/Rome (UTC+1).
- Finestra rilevata: dalle 07:00 alle 22:59 circa, con periodi privi di osservazioni (non confondere assenza di log con assenza di segnali).
- Registrazioni di decisione raccolte: **759**. Il registratore memorizza snapshot di decisione, non candele complete e non ordini.
- Candidati M1: `confirmed=true`, `score>=6`: **0** osservazioni, raggruppate in **0** gruppi con regola ex ante: stesso lato, sessione e categoria, distanza <=30 minuti.
- Allineamento Forecast+Thesis+M1: **0** eventi; `BEFORE_FORECAST`: **0**; contrari a Forecast ma con Thesis/M1 concordi: **0**.
- Il giorno risulta bloccato con `BROKER_DAY_HISTORY_UNVERIFIED`: zero `campaign_triggered` tra questi snapshot. Nessun PnL o numero di trade broker viene inferito.

## Candidati (non trade)

| Ora IT | Gruppo | Sessione | M1 | Score | Prezzo osservato | Categoria |
|---|---|---|---|---:|---:|---|


## Lettura operativa da testare, non da applicare

- **G2 BUY Europa (08:06-08:51)**: più conferme M1 nella direzione Forecast/Thesis; una sola ipotesi di famiglia, non ogni snapshot come trade.
- **G3 BUY Europa (09:45-09:53)**: segnali allineati ma mappa `WEAKENING`. Verificare se la pausa durante WEAKENING salva stop o elimina opportunità; non concludere senza M1.
- **G4 SELL NY (14:38-14:47)**: score elevati ma movimento già esteso; il primo target della mappa SELL iniziale era già stato raggiunto prima di parte degli eventi. Verificare il filtro anti-inseguimento.
- **G5 BUY NY (15:04-15:22)**: Thesis/M1 BUY già concordi mentre Forecast SELL era `WEAKENING`. Revisione BUY ufficiale alle 15:34; scenario per studio PRE-REVISION, non trade qualificato.

## Protocollo fisso per il replay dopo ricezione delle M1

1. Usare timestamp Telegram/Render locali e allineare esplicitamente l'orologio MT4; non assumere offset fisso senza verifica.
2. Conservare tutti i 16 timestamp. Per la statistica principale usare **un solo primo candidato per gruppo**, così non si duplicano 5 segnali dello stesso movimento.
3. Per ciascuno: MFE, MAE e primo tocco teorico entro H10 e H30, con dati bid/ask e spread indicato; se la stessa candela tocca TP e SL segnare `AMBIGUO` o applicare scenario prudenziale.
4. Non attribuire `entry/sl/tp` al bot: sono `null` nei log a causa del blocco broker. Eventuali scenari sintetici devono essere etichettati come tali.
5. Confronto A (attuale), B (blocco con WEAKENING), C (solo Thesis contraria) solo su candidati **non eseguibili**; non proclamare vincite reali.
6. Per conoscere i risultati di v48.7 LAB e altri esperimenti indipendenti occorre il relativo stato/archivio; questi CSV attestano il registratore v48.18, non ne sostituiscono i risultati.

**Archivi:** [decisioni 06-14 UTC](SHADOW_2026-11-17_06-14UTC.csv), [decisioni 14-22 UTC](SHADOW_2026-11-17_14-22UTC.csv), [16 candidati pre-registrati](CANDIDATI_SHADOW_2026-11-17.csv).
