# SHADOW G v48.8 — Audit storico esteso 2026 (14 novembre 2026)

## Fonte e integrità
L'utente ha fornito `XAUUSD1.zip`, archivio MT4 di 7.074.474 righe dal 2004-06-11 al 2026-11-13. Nel 2026 sono presenti **273.974** candele M1: **200.435** gennaio–luglio e **73.539** settembre–13 novembre; **agosto 2026 interamente assente**. Il sottoinsieme settembre–novembre è identico byte per byte al CSV originale già testato. Nessun duplicato timestamp e nessuna anomalia OHLC nell'estratto 2026.

## Metodologia e limiti
Replay offline invariato v48.8 G1/G2/G3. Ipotesi: timestamp CSV letti come Europe/Rome, Bid trasformato in Mid con mezzo spread fisso, spread 0.30 o 0.60 punti, slippage 0.10 punti, entrata virtuale alla candela successiva, target +25 punti con BE a +6. Ambiguità intrabar escluse dal conteggio nominale, o marcate come SL nello stress. Non è PnL broker: senza tick bid/ask, commissioni, swap, limite di simultaneità e conversione EUR. Ottimizzazione locale del replay verificata sulle prime 20.000 M1 e confronto del precedente campione 73.539 M1; regole del segnale inalterate.

## Totali (TP +25, BE +6) in punti nominali
| Motore | Segnali | Spread 0.30 | Spread 0.60 | Stress spread 0.60, ambigui=SL |
|---|---:|---:|---:|---:|
| G1 | 239 | -591.56 | -632.14 | -717.25 |
| G2 | 755 | -525.94 | -744.88 | -934.26 |
| G3 | 175 | -111.63 | -167.76 | -201.73 |

### G2 per gruppo temporale
| Periodo | Segnali | Spread 0.30 | Spread 0.60 | Stress spread 0.60 |
|---|---:|---:|---:|---:|
| Gen–lug | 518 | -675.44 | -821.34 | -926.15 |
| Set–nov 13 | 237 | +149.50 | +76.46 | -8.11 |
| Totale | 755 | -525.94 | -744.88 | -934.26 |

G2 è negativo in **tutti** i sette mesi gennaio–luglio nel caso spread 0.30. L'effetto favorevole nel campione recente non si generalizza al periodo aggiuntivo. Anche G3 (sottoinsieme gen–lug +37.34 a spread 0.30) passa negativo (-3.36) a spread 0.60.

Confronto temporale indicativo con Max: 832 schede nei 10 mesi coperti, circa 123 con G2 stessa direzione entro ±30 minuti, orari non verificati; non dimostra corrispondenza tra metodi.

## Decisione
**Non promuovere nessuno dei tre motori a esecuzione.** Il ramo rimane SHADOW ONLY, senza modifiche a `main`, Render o EA. Ulteriori indagini: orario broker, spread/tick reali, meccanica di retest e distinzione del regime di mercato. Nuovi filtri necessitano valutazione prospettica su dati non impiegati per ottimizzarli; agosto mancante non va inventato.
