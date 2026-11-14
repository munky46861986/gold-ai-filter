# SHADOW G v48.15 — registro prospettico dei piani Max

**SOLO RICERCA.** File locale e modulo stand-alone, non importato da `app.py`. Non accede a Telegram, MT4, Render o broker e non apre posizioni.

Input CSV: `source,message_id,published_at,captured_at,direction,zone_low,zone_high,sl,tp1`. Gli orari devono includere il fuso (`+01:00`, `+02:00` o `Z`); `captured_at` deve essere un timestamp di acquisizione effettiva (non ricostruito retroattivamente), e al massimo 5 minuti dopo `published_at` per considerare un piano prospettico. I segnali storici vengono esplicitamente scartati come non prospettici. Vanno raccolti **tutti** i piani, anche quelli non qualificati.

Esegui `python -m unittest discover -s research/shadow_g_v4815 -p 'test_*.py'` e `python research/shadow_g_v4815/prospective_rr_register.py --plans nuovi_max_piani.csv --output out_v4815`.

La formula congelata per il primo target è: BUY `(tp1-zone_high)/(zone_high-sl)`; SELL `(zone_low-tp1)/(sl-zone_low)`. Registra `RR_QUALIFIED_SHADOW` se RR >= 0,50, altrimenti `RR_REJECTED` o `NOT_EVALUABLE`. **La qualifica non è un segnale d'acquisto/vendita.** Finché mancano bid/ask reali successivi al messaggio non sono determinati fills, esiti o PnL.

L'utente ha a disposizione il grande storico XAUUSD ma non una connessione Telegram del canale Max tramite questa integrazione. Non dichiarare attiva la raccolta automatica. Evitare invio di credenziali/chat token. Per il protocollo completo consultare `research/SHADOW_G_V4815_PROSPECTIVE_PROTOCOL.md`.