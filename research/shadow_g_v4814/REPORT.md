# GOLD MASTER — SHADOW G v48.14: audit gestione dei piani MAX

**Data:** 14 novembre 2026 · **Modalità:** ricerca offline / SHADOW ONLY. Nessun ordine sul broker, nessun collegamento a MT4, nessuna modifica a `main` o Render.

## Domanda

La simulazione meccanica dei piani Telegram di Max risulta negativa al primo target. Esistono decisioni verificabili **prima** o **durante** l'operazione, e non a posteriori, che migliorano il risultato? Sono state confrontate tre categorie: (1) stop a pareggio anticipato, (2) scadenza dell'ordine se il prezzo arriva tardi nella zona, (3) qualità del rapporto premio/rischio pubblicato.

## Dati e protocollo

- Sorgenti dell'utente: **905** piani strutturati `MAX_segnali_strutturati.csv` collegati ai messaggi Telegram originali; storico **273.974** candele M1 XAUUSD per gennaio–luglio e settembre–13 novembre 2026 estratto da `XAUUSD1.zip`; **agosto assente**.
- Si riprendono **i fill stimati del replay v48.13**, non gli ordini reali di Max: ingresso su zona dopo il messaggio (finestra 30 minuti), offset storico = messaggio Telegram +1 ora, OHLC bid approssimati con spread fisso 0,30/0,60 e slippage avverso 0,10. L'orario del broker non è confermato indipendentemente.
- Orizzonte di valutazione: **240 minuti**, primo target pubblicato e stop originario. Le candele con TP/stop raggiunti senza ordine intrabar noto rimangono `AMBIGUOUS`; gap di oltre due minuti rimangono `DATA_GAP`; i livelli dei messaggi non attestano esecuzioni broker.
- Per i nuovi break-even lo stop si sposta al **prezzo di ingresso stimato dalla candela successiva** a quella che raggiunge la soglia: non viene usata l'informazione intrabar per assumere un BE immediato. Se TP e stop attivo si trovano nella stessa candela, il trade è incerto.
- Non sono incluse commissioni, swap, slippage variabile e conversione in EUR. La somma di punti è nominale, ignora le simultaneità e non rappresenta una curva equity.

### Verifica di riproducibilità e correzione di un valore storico

**1.321 esiti** di TP1, SL o timeout del CSV di v48.13 sono stati riprodotti esattamente, punto per punto, dal nuovo simulatore (nessuna discrepanza); sono stati superati anche **11 test automatici** sull'ordine temporale, sullo spread di uscita per SELL e sulle candele ambigue.

Nella versione testuale del report v48.13 era indicato un saldo TP1 a spread 0,60 di **−781,68 punti**. Il CSV di replay v48.13 conservato contiene invece **−715,67 punti**; quest'ultimo è il valore **riproducibile** con il codice e i file attuali. Il valore nel vecchio testo non va usato senza un audit della sua origine. Questa discrepanza è documentata, non occultata.

## Esperimento A — Stop a pareggio anticipato

Per lo spread 0,60, tutti i risultati utilizzano gli stessi 663 trade con fill stimato e senza ambiguità d'ingresso:

| Uscita | TP1 | SL | BE | Ambigui / gap | Saldo punti esiti noti |
|---|---:|---:|---:|---:|---:|
| TP1 / SL originario | 437 | 221 | 0 | 0 / 1 | **−715,67** |
| BE dopo +2 punti favorevoli | 264 | 127 | 266 | 5 / 0 | **−544,63** |
| BE dopo +3 punti | 375 | 178 | 106 | 2 / 1 | **−682,76** |
| BE dopo +0,5 volte il rischio iniziale | 425 | 204 | 30 | 1 / 1 | **−683,10** |

Il BE a +2 riduce le perdite, **ma resta negativo**. Se i cinque trade incerti della variante BE +2 fossero tutti stop iniziali, il saldo diverrebbe **−600,41 punti**.

**Non generalizza temporalmente:** su gennaio–luglio BE+2 = −243,84 contro −484,19 della baseline; su settembre–novembre BE+2 = **−300,79** contro **−231,48** della baseline, quindi peggiora. Su dati raggruppati per giornata, il guadagno di punti del BE+2 rispetto alla baseline con ambiguità/gap penalizzati a stop è **+125,98 punti**, ma un bootstrap esplorativo per giornata (6.000 repliche) include differenze negative, intervallo percentilico 95% **[−131,97; +403,33]**. Non è una prova che il BE+2 migliori il futuro.

## Esperimento B — Annullare l'ingresso oltre 5 minuti

Con spread 0,60, tra i fill già stimati il filtro elimina 119 ingressi tardivi: **544** restano e il saldo noto è **−671,77** punti, contro **−715,67** su 663 trade senza filtro. È una riduzione della perdita **totale perché si scambiano meno operazioni**, non un miglioramento della qualità media: circa −1,23 punti per trade noto contro −1,08 della baseline. Non va promosso.

## Esperimento C — Premio/rischio del piano pubblicato

Rapporto calcolabile **al momento del messaggio**:

- BUY: `(TP1 − bordo superiore zona) / (bordo superiore zona − SL)`;
- SELL: `(bordo inferiore zona − TP1) / (SL − bordo inferiore zona)`.

**Exploratory filter:** rapporto ≥ 0,50. Nello scenario spread 0,60 sono **55 fill stimati con esito noto** e saldo **+113,82 punti nominali**. Questo è un risultato **esplorativo scelto dopo aver visto lo storico**, non una strategia validata fuori campione.

Controlli di fragilità:

| Test | Campione | Saldo punti |
|---|---:|---:|
| Tutti i fill RR ≥ 0,50 risolti | 55 | **+113,82** |
| Escludendo 3 chiusure virtuali a 4 ore senza TP/SL | 52 | +49,66 |
| Escludendo tutti i piani del 30 aprile | 49 | +79,96 |
| Escludendo i 3 guadagni più elevati | 52 | +45,66 |
| Al massimo **primo piano pubblicato** eleggibile del giorno, solo fill risolti | 41 | +65,54 |

Le tre chiusure virtuali del 30 aprile sommano **+64,16 punti**, ma non sono TP broker e non vanno confusi con guadagni incassati. I piani con RR≥0,50 e fill noto sono ripartiti su **43 giornate** e sono concentrati quasi completamente in **gennaio–giugno**: **54** su 55; **solo 1** a settembre–novembre (nessuno a settembre o ottobre). In un bootstrap esplorativo per giornata il 95% dei totali riscampionati è **[−33,71; +263,42] punti**, e quindi comprende perdite. Anche qui il bootstrap non corregge il bias da selezione e non dimostra un vantaggio futuro.

Il sottogruppo RR ≥0,75 ha soltanto 20 fill valutabili, perciò non è una base di affidabilità indipendente.

## Decisione tecnica

- **BE+2:** riduce le perdite storiche cumulate ma peggiora negli ultimi mesi e resta negativo. Non attivare.
- **Scadenza a 5 minuti:** riduce i segnali, non migliora l'aspettativa media. Non attivare.
- **RR ≥0,50:** unica pista con saldo storico positivo in questa prova, ma limitata a 55 ingressi in gran parte nei primi sei mesi, con forti correlazioni intra-giornata e senza valida conferma temporale. Da **congelare come ipotesi di filtro da osservare in SHADOW**, non da applicare a ordini o consigli operativi.
- **Passo successivo:** raccogliere nuovi segnali reali successivi al 14 novembre 2026, misurare il rapporto pre-entry senza riottimizzarlo, registrare fill e spread bid/ask broker verificabili, includere commissioni ed esposizione simultanea, e solo successivamente giudicarne la robustezza.

## Riproduzione

```bash
PYTHONPATH=/path/to/v4813 python max_management_v4814.py \
  --prices XAUUSD_M1_2026_ESTRATTO.csv \
  --trades max_plans_trades.csv \
  --output v4814_results

python fragility_audit_v4814.py \
  --plans MAX_segnali_strutturati.csv \
  --trades max_plans_trades.csv \
  --policies v4814_results/all_policy_trade_results.csv \
  --output v4814_results

PYTHONPATH=. python -m unittest -v test_max_management_v4814.py
```

Il codice non importa alcun componente broker. `main`/Render e l'EA Gold Master sulla VPS rimangono invariati.