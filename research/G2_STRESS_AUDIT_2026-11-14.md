# Audit G2 BOS_RETEST — 14 novembre 2026

## Ambito
Replay offline v48.8 sul CSV MT4 XAUUSD1(1).csv dell'utente, 73.539 M1, 1 settembre–13 novembre 2026. G2 segnali 237. Non è un test fuori campione autentico: G2 è stato selezionato dopo aver visto anche ottobre e novembre. Non modifica deploy, MT4 o account.

## Punti nominali G2 TP+25, BE dopo +6
- Spread fisso assunto 0,30, slippage 0,10: +149,50 punti **escludendo** 7 esiti intrabar ambigui (e 1 data gap).
- Spread fisso assunto 0,60, slippage 0,10: +76,46 punti **escludendo** 9 esiti ambigui (e 2 data gap).
- Interpretando in modo prudenziale ogni ambiguo come stop: **+77,93** punti con spread 0,30 e **−8,11** punti con spread 0,60. Non sono profitti netti; dati di spread storico, commissioni, swap e conversioni mancano.
- Interpretazione: il risultato G2 si capovolge in uno scenario di stress ancora prima di tutte le commissioni. Non è dimostrata un'aspettativa positiva.

## Stress mensile (ambiguo = stop)
| Mese | Spread 0,30 | Spread 0,60 |
|---|---:|---:|
| 2026-09 | +52,07 | +10,71 |
| 2026-10 | −57,88 | −99,86 |
| 2026-11 (1–13) | +83,74 | +81,04 |
| **Totale** | **+77,93** | **−8,11** |

## Diagnosi ottobrina con spread 0,30 (esiti ambigui esclusi)
- G2 BUY: 42 segnali, +45,7 punti nominali.
- G2 SELL: 66 segnali, −85,6 punti nominali; 5 TP +25, 33 SL, 26 BE, 1 ambiguo e 1 data gap.
- Non togliere retroattivamente i SELL, né selezionare orari o soglie usando gli stessi risultati.

## Incertezze importanti
- Il CSV non espone lo spread storico, solo prezzi OHLC e tick_volume.
- L'orario del broker non è identificato con certezza. Gli esiti sono stati calcolati sotto un'ipotesi Rome e stressati anche con offset UTC+02 fisso.
- Più ipotesi G2 possono avere esposizioni temporaneamente sovrapposte. La somma di punti non è curva equity con portafoglio o lotto a rischio fisso.
- G2 non coincide spesso con i messaggi Max: circa 41 delle 239 schede pubblicate nello stesso periodo hanno G2 dello stesso verso entro 30 minuti (assunzione di orari come Italia).
- Non è verificata l'eseguibilità broker con bid/ask tick reali.

## Prossima azione di ricerca
1. Congelare codice e soglie G2 v48.8; non ottimizzare retroattivamente ottobre.
2. Eseguire una **raccolta prospettica SHADOW ONLY** con M1 complete da una fonte broker, senza collegamento a ordini MT4. L'attuale webhook PRICE_UPDATE del backend non è uno storico M1 broker certificato.
3. Confrontare stop/target col bid/ask reale, costi e log delle decisioni; aggiungere metriche di portafoglio e rischio giornaliero.
4. Riprendere la calibrazione solo se acquisiti dati ulteriori non già usati per giudicare i risultati; mai promuovere a operatività se i controlli indipendenti non tengono.

Riferimenti file locali della sessione: SHADOW_G_BACKTEST_ROME_SPREAD03/shadow_g_signals.csv e SHADOW_G_BACKTEST_ROME_SPREAD06/shadow_g_signals.csv.
