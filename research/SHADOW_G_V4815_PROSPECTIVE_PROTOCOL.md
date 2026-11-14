# SHADOW G v48.15 — Protocollo prospettico, filtro RR sui piani di Max
Data congelamento: 2026-11-14. STATO: PROTOCOLLO DI RICERCA; non esiste alcun nuovo motore operativo né alcun collegamento live. Non unire su main.

## Punto di partenza verificato
L'audit v48.14 ha trovato 55 ingressi storici simulati con esito noto e RR pubblicato >= 0,50, saldo +113,82 punti nominali con spread assunto 0,60 e slippage 0,10; 54 su 55 tra gennaio e luglio. Tre delle uscite sono marcature virtuali a quattro ore, non target/stop eseguiti. La soglia deriva da esplorazione dello storico (data snooping): il saldo NON misura prestazione fuori campione. Il bootstrap per giorno include anche saldi negativi. Non usare questi risultati per attivare ordini.

## Protocollo congelato — solo segnali nuovi pubblicati DOPO il 2026-11-14
1. Ogni piano di Max va registrato nel momento della pubblicazione: ID messaggio univoco, data/ora originale e timezone, direzione, bordo superiore/inferiore della zona, SL, TP1, eventuali TP2/3, data di ricezione. Vietato usare messaggi di esito successivi come dati di ingresso. Tracciare anche piani incompleti, cancellati, rifiutati e senza fill.
2. Gate geometrico, PRIMA dell'ingresso, senza usare prezzi futuri:
   BUY RR=(TP1-zone_high)/(zone_high-SL), con TP1>zone_high>SL.
   SELL RR=(zone_low-TP1)/(SL-zone_low), con SL>zone_low>TP1.
   Se direzione/livelli mancanti, errati o RR non finito: NOT_EVALUABLE, mai stimare un RR favorevole.
   Proposta qualificata solo se RR >= 0.50, soglia NON modificabile nel periodo prospettico.
3. Verificare il fuso orario Telegram/MT4 contro segnali e clock reali: +1h è ipotesi storica, NON regola garantita. Senza mapping dimostrato, stato TIME_UNVERIFIED e nessun fill giudicato.
4. Simulare l'ingresso solo se il successivo bid/ask reale attraversa la zona entro 30 minuti dalla pubblicazione; non utilizzare prezzi anteriori al messaggio. Se il primo tocco è ambiguo in una candela M1, AMBIGUOUS, non filled automatico. Nessun 'ingresso al prezzo migliore' retrospettivo.
5. Esito primaria: TP1 o SL first-touch su tick bid/ask, max osservazione 4h; se esito non raggiunto: TIMEOUT_MARK e valutazione mark-to-market separata da realized PnL. Gaps, ambiguous, unfilled e non-evaluable riportati separatamente. Spread e commissioni effettive; confrontare una sensibilità a spread 0.60 e 1.00 punti ove plausibile. Nessun trasferimento di esiti da Telegram come broker fills.
6. Metriche preregistrate: TUTTI i piani, eleggibili, non eleggibili, fill, unfilled, TP/SL, data gap, ambiguità, timeout, PnL per trade in punti e R, drawdown, peggior giornata, sovrapposizioni, modello 1 solo primo piano eleggibile/giorno, andamento mensile, confronto senza filtro RR e bootstrap per giornata. Rischio in euro solo con contract size e conversione verificati.
7. Checkpoint descrittivo dopo almeno 50 proposte QUALIFICATE e risolte su almeno 30 giornate distinte, e almeno 2 regimi mensili; questi requisiti non garantiscono significatività. Se mancano nuovi piani di Max, il campione resta insufficiente: non cambiare soglia per aumentare il conteggio.
8. Decisione: non promuovere se saldo netto, aspettativa in R o scenario di stress rimangono negativi, se i risultati sono dominati da un giorno, se mancano costi reali, oppure se campione insufficiente. Anche se positivi, richiedere ulteriore test indipendente/demo prima degli ordini.
9. Distinguere esplicitamente questa prova come FILTRO DI PIANI PUBBLICATI DA MAX. Non è una strategia XAUUSD autonoma di GOLD MASTER: per autonomia, sviluppare separatamente un generatore di zona/SL/TP1, con validazione propria, prima di aggiungere il filtro RR.

## Stato tecnico attuale
- Questa versione e' soltanto protocollo congelato nel ramo research/shadow-g-v48-8.
- Il bot su Render non legge i nuovi messaggi di Max attraverso questa ricerca.
- Nessun collegamento Telegram/MT4, nessun EA, nessun comando broker, nessun deploy, nessuna modifica a main.
- In attesa di stream certificato dei nuovi segnali di Max e dati broker bid/ask per poter misurare la validità prospettica.
