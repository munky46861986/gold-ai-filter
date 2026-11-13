# SHADOW G v48.8 — ricerca struttura MAX (non operativo)

**Stato:** proposta tecnica isolata. Questa branch NON modifica `main`, non genera ordini MT4, non invia notifiche Telegram e non modifica il deployment Render.

## Obiettivo
Verificare se configurazioni osservabili *prima* degli ingressi dichiarati nel canale "Max Gold Operativo" siano replicabili su XAUUSD, con dati M1/M5/M15, spread e slippage. Non assumere come veritieri gli esiti TP riportati nel canale; ricostruirli dai prezzi storici.

## Input
- Esportazione Telegram: timestamp originale, direzione, intervallo di ingresso, SL, TP, modifiche successive; conserva messaggi originali e ID.
- OHLC M1 broker storico e ricostruzione M5/M15, UTC e conversione Europe/Rome con DST.
- Spread bid/ask reale (o scenario conservativo esplicitato); notizie economiche se disponibili.
- Record di segnali indipendenti del bot A/B/D/F, mantenuti separati.

## Ipotesi da verificare, senza adattarsi al futuro
- **G1 (sweep/reversal):** rottura transitoria di high/low M15 precedente e chiusura entro il range, più cambio di microstruttura M5 confermato. Non entra durante la formazione della candela non chiusa.
- **G2 (pullback):** break-of-structure M15 chiuso, ritracciamento a livello rotto o zona appena rilevata con conferma M5; SL oltre l'estremo strutturale.
- **G3 (continuation):** swing M15 coerenti, consolidamento M5 e breakout confermato, entrando solo al retest entro intervallo e timeout definito.

Le soglie, la definizione di swing, i buffer e i timeout devono essere determinati sul periodo di sviluppo, congelati prima di testare gli altri periodi.

## Protezioni per la simulazione
1. Nessuna inferenza da messaggi Telegram successivi al segnale.
2. Nessuna esecuzione automatica su broker; nessuna abilitazione di motori esistenti.
3. Ingresso solo se bid/ask ha toccato la zona dopo l'orario del segnale e prima della scadenza. Slippage e spread applicati.
4. Risoluzione SL/TP con M1 o tick. Se ambedue toccati sulla stessa barra senza ordine noto, classificazione **AMBIGUOUS** o worst-case, mai vittoria certa.
5. Evitare segnali duplicati dalla stessa mossa (chiave evento timestamp/bar/direzione/zona). Non sommare le diverse prese di profitto come trade indipendenti.
6. Misurare stop strutturale, R multiplo, drawdown, profit factor, costi, expectancy, coverage, orari di sessione; confrontare con A/B/D/F e baseline no trade.
7. Test differenti: un solo trade chiuso a TP1 (3 punti) e diversi TP 3/6/9/15/25 con BE. Non presupporre che TP multipli incrementino il profitto.
8. Per futura DEMO: cap massimo 30 EUR/giorno e lotto iniziale 0.01, validati anche dall'EA e senza recovery progressivo.

## Suddivisione dati
- Gennaio–Agosto 2026: esplorazione e calibrazione, registrando tutte le varianti provate.
- Settembre–Ottobre 2026: verifica fuori campione, soglie congelate.
- Novembre 2026: controllo finale non utilizzato per la scelta dei parametri.

## Criteri prima di un eventuale deploy DEMO
- Precedenza assoluta: risolvere vecchi comandi/forecast senza ACK broker; nessun `OPEN` se mancato `OPENED`.
- Confermare il nuovo conto DEMO MT4 e autorizzazione in Render.
- Dimostrare robustezza fuori campione, commissioni/spread inclusi; test di shock; rischio per trade e giornaliero.
- Revisione umana esplicita prima di qualsiasi merge su `main` o modifica di Render.
