import os
import time
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

BIAS = os.getenv("BIAS", "AUTO").upper()
NEWS_BIAS = os.getenv("NEWS_BIAS", "NEUTRAL").upper()
EVENT_RISK = os.getenv("EVENT_RISK", "NORMAL").upper()
MIN_SCORE = int(os.getenv("MIN_SCORE", "6"))

NEWS_API_KEY = os.getenv("NEWS_API_KEY")
AUTO_NEWS = os.getenv("AUTO_NEWS", "FALSE").upper() == "TRUE"

NEWS_CACHE = {"time": 0, "bias": "NEUTRAL", "reasons": []}
OPEN_TRADES = []


def send_telegram(text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text}
    r = requests.post(url, json=payload, timeout=10)
    r.raise_for_status()


@app.route("/")
def home():
    return "Gold AI Filter Bot v7 Trade Tracker attivo ✅"


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "version": "v7",
        "open_trades": len(OPEN_TRADES),
        "bias": BIAS,
        "news_bias": NEWS_BIAS,
        "auto_news": AUTO_NEWS,
        "event_risk": EVENT_RISK,
        "min_score": MIN_SCORE
    })


@app.route("/test")
def test():
    send_telegram("✅ TEST TELEGRAM DA RENDER - v7")
    return "OK"


def normalize_signal(signal):
    signal = str(signal).upper()
    if signal == "LONG":
        return "BUY"
    if signal == "SHORT":
        return "SELL"
    return signal


def to_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def get_auto_news_bias():
    if not AUTO_NEWS or not NEWS_API_KEY:
        return NEWS_BIAS, ["Auto news non attiva"]

    now = time.time()
    if now - NEWS_CACHE["time"] < 900:
        return NEWS_CACHE["bias"], NEWS_CACHE["reasons"]

    query = (
        "gold OR XAUUSD OR dollar OR Federal Reserve OR Fed OR inflation OR CPI "
        "OR NFP OR Iran OR Israel OR Hormuz OR geopolitical"
    )

    try:
        r = requests.get(
            "https://newsapi.org/v2/everything",
            params={
                "q": query,
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": 20,
                "apiKey": NEWS_API_KEY
            },
            timeout=8
        )
        r.raise_for_status()
        articles = r.json().get("articles", [])
    except Exception as e:
        return NEWS_BIAS, [f"Errore NewsAPI: {e}"]

    bullish_words = [
        "war", "attack", "missile", "iran", "israel", "hormuz", "tension",
        "geopolitical", "safe haven", "risk off", "dollar falls",
        "dollar weak", "fed cut", "rate cut", "inflation rises"
    ]

    bearish_words = [
        "ceasefire", "peace", "reopens", "reopened", "dollar rises",
        "dollar strong", "fed hawkish", "rate hike", "yields rise",
        "risk on", "de-escalation", "calm"
    ]

    bullish_score = 0
    bearish_score = 0

    for article in articles:
        text = ((article.get("title") or "") + " " + (article.get("description") or "")).lower()
        for word in bullish_words:
            if word in text:
                bullish_score += 1
        for word in bearish_words:
            if word in text:
                bearish_score += 1

    if bullish_score >= bearish_score + 4:
        bias = "BULLISH_GOLD"
        reasons = [f"News favorevoli all'oro: {bullish_score} vs {bearish_score}"]
    elif bearish_score >= bullish_score + 4:
        bias = "BEARISH_GOLD"
        reasons = [f"News negative per oro: {bearish_score} vs {bullish_score}"]
    else:
        bias = "NEUTRAL"
        reasons = [f"News neutre: bullish {bullish_score}, bearish {bearish_score}"]

    NEWS_CACHE["time"] = now
    NEWS_CACHE["bias"] = bias
    NEWS_CACHE["reasons"] = reasons

    return bias, reasons


def score_signal(data, signal):
    score = 0
    reasons = []

    h1_bias = str(data.get("h1_bias", "NEUTRAL")).upper()
    h4_bias = str(data.get("h4_bias", "NEUTRAL")).upper()
    day_bias = str(data.get("day_bias", "NEUTRAL")).upper()
    structure = str(data.get("structure", "NEUTRAL")).upper()

    rsi = to_float(data.get("rsi", 50), 50)
    above_ema200 = str(data.get("close_above_ema200", "false")).lower() == "true"

    candle_dir = str(data.get("candle_dir", "NEUTRAL")).upper()
    rejection = str(data.get("rejection", "NONE")).upper()
    ema20_slope = str(data.get("ema20_slope", "FLAT")).upper()
    ema50_slope = str(data.get("ema50_slope", "FLAT")).upper()
    volume_spike = str(data.get("volume_spike", "false")).lower() == "true"

    active_news_bias, news_reasons = get_auto_news_bias()
        reversal_buy = (
        signal == "BUY"
        and active_news_bias == "BULLISH_GOLD"
        and structure in ["LL", "BULLISH"]
        and candle_dir == "BULL"
        and rsi > 42
    )

    reversal_sell = (
        signal == "SELL"
        and active_news_bias == "BEARISH_GOLD"
        and structure in ["HH", "BEARISH"]
        and candle_dir == "BEAR"
        and rsi < 58
    )

    if reversal_buy:
        score += 5
        reasons.append("Setup REVERSAL BUY stile Max")

    if reversal_sell:
        score += 5
        reasons.append("Setup REVERSAL SELL stile Max")

    if BIAS == "FORCE_SELL":
        if signal == "BUY":
            return -999, ["Bloccato: FORCE_SELL attivo"], active_news_bias, news_reasons
        score += 4
        reasons.append("Bias manuale FORCE_SELL")

    if BIAS == "FORCE_BUY":
        if signal == "SELL":
            return -999, ["Bloccato: FORCE_BUY attivo"], active_news_bias, news_reasons
        score += 4
        reasons.append("Bias manuale FORCE_BUY")

    if active_news_bias == "BULLISH_GOLD":
        if signal == "BUY":
            score += 1
            reasons.append("News bullish gold leggera")
        else:
            score -= 2
            reasons.append("SELL contro news bullish gold")

    if active_news_bias == "BEARISH_GOLD":
        if signal == "SELL":
            score += 1
            reasons.append("News bearish gold leggera")
        else:
            score -= 2
            reasons.append("BUY contro news bearish gold")

    if EVENT_RISK == "HIGH":
        score -= 2
        reasons.append("Evento macro ad alto rischio")

    if signal == "BUY":
        if h1_bias == "BUY":
            score += 2
            reasons.append("H1 BUY")
        if h4_bias == "BUY":
            score += 2
            reasons.append("H4 BUY")
        if day_bias == "BUY":
            score += 2
            reasons.append("Daily BUY")
        if day_bias == "SELL":
            score -= 4
            reasons.append("Contro Daily SELL forte")

        if structure in ["HL", "BULLISH", "LL"]:
            score += 2
            reasons.append(f"Struttura {structure}")
        if structure == "HH":
            score -= 3
            reasons.append("BUY dopo HH: rischio comprare in alto")

        if rsi > 50:
            score += 1
            reasons.append("RSI sopra 50")
        if rsi > 68:
            score -= 2
            reasons.append("RSI alto: buy in estensione")

        if above_ema200:
            score += 1
            reasons.append("Prezzo sopra EMA200")

        if candle_dir == "BULL":
            score += 1
            reasons.append("Candela bullish")
        if candle_dir == "BEAR":
            score -= 2
            reasons.append("Candela rossa contro BUY")

        if rejection == "LOWER_WICK":
            score += 2
            reasons.append("Rejection bullish con wick bassa")
        if rejection == "UPPER_WICK":
            score -= 3
            reasons.append("Wick alta: rischio rigetto BUY")

        if ema20_slope == "UP":
            score += 1
            reasons.append("EMA20 in salita")
        if ema50_slope == "UP":
            score += 1
            reasons.append("EMA50 in salita")
        if ema20_slope == "DOWN":
            score -= 4
            reasons.append("EMA20 in discesa forte contro BUY")
        if ema50_slope == "DOWN":
            score -= 2
            reasons.append("EMA50 in discesa")

        if volume_spike and candle_dir == "BEAR":
            score -= 3
            reasons.append("Volume spike su candela rossa")

    if signal == "SELL":
        if h1_bias == "SELL":
            score += 2
            reasons.append("H1 SELL")
        if h4_bias == "SELL":
            score += 2
            reasons.append("H4 SELL")
        if day_bias == "SELL":
            score += 3
            reasons.append("Daily SELL")
        if day_bias == "BUY":
            score -= 3
            reasons.append("Contro Daily BUY")

        if structure in ["LH", "BEARISH", "HH"]:
            score += 2
            reasons.append(f"Struttura {structure}")
        if structure == "LL":
            score -= 3
            reasons.append("SELL dopo LL: rischio vendere in basso")

        if rsi < 50:
            score += 1
            reasons.append("RSI sotto 50")
        if rsi < 32:
            score -= 2
            reasons.append("RSI basso: sell in estensione")

        if not above_ema200:
            score += 1
            reasons.append("Prezzo sotto EMA200")

        if candle_dir == "BEAR":
            score += 1
            reasons.append("Candela bearish")
        if candle_dir == "BULL":
            score -= 2
            reasons.append("Candela verde contro SELL")

        if rejection == "UPPER_WICK":
            score += 2
            reasons.append("Rejection bearish con wick alta")
        if rejection == "LOWER_WICK":
            score -= 3
            reasons.append("Wick bassa: rischio rigetto SELL")

        if ema20_slope == "DOWN":
            score += 1
            reasons.append("EMA20 in discesa")
        if ema50_slope == "DOWN":
            score += 1
            reasons.append("EMA50 in discesa")
        if ema20_slope == "UP":
            score -= 2
            reasons.append("EMA20 in salita")
        if ema50_slope == "UP":
            score -= 2
            reasons.append("EMA50 in salita")

        if volume_spike and candle_dir == "BULL":
            score -= 3
            reasons.append("Volume spike su candela verde")

    return score, reasons, active_news_bias, news_reasons


def save_trade(data, signal, score):
    trade_id = str(int(time.time()))

    trade = {
        "id": trade_id,
        "signal": signal,
        "symbol": data.get("symbol", "XAUUSD"),
        "entry_low": to_float(data.get("entry_low")),
        "entry_high": to_float(data.get("entry_high")),
        "sl": to_float(data.get("sl")),
        "tp1": to_float(data.get("tp1")),
        "tp2": to_float(data.get("tp2")),
        "tp3": to_float(data.get("tp3")),
        "tp4": to_float(data.get("tp4")),
        "tp5": to_float(data.get("tp5")),
        "tp6": to_float(data.get("tp6")),
        "score": score,
        "status": "PENDING",
        "entered": False,
        "be": False,
        "highest_tp": 0,
        "created": time.time()
    }

    OPEN_TRADES.append(trade)
    return trade

def handle_price_update(data):
    high = to_float(data.get("high"))
    low = to_float(data.get("low"))
    close = to_float(data.get("close"))

    updates = []

    for trade in OPEN_TRADES:
        if trade["status"] not in ["OPEN", "PENDING"]:
            continue

        signal = trade["signal"]
        trade_id = trade["id"]

        # PENDING ENTRY SYSTEM
        if trade["status"] == "PENDING":
            if signal == "BUY":
                entered = low <= trade["entry_high"] and high >= trade["entry_low"]

                if entered:
                    trade["status"] = "OPEN"
                    trade["entered"] = True
                    updates.append(
                        f"🎯 Trade #{trade_id} BUY ATTIVATO\n"
                        f"Zona: {trade['entry_low']} - {trade['entry_high']}"
                    )

            if signal == "SELL":
                entered = high >= trade["entry_low"] and low <= trade["entry_high"]

                if entered:
                    trade["status"] = "OPEN"
                    trade["entered"] = True
                    updates.append(
                        f"🎯 Trade #{trade_id} SELL ATTIVATO\n"
                        f"Zona: {trade['entry_low']} - {trade['entry_high']}"
                    )

            continue

        if signal == "BUY":
            if not trade["be"] and low <= trade["sl"]:
                trade["status"] = "LOSS"
                updates.append(f"❌ Trade #{trade_id} BUY chiuso in SL\nSL: {trade['sl']}")
                continue

            for i in range(1, 7):
                tp = trade.get(f"tp{i}", 0)
                if tp and high >= tp and trade["highest_tp"] < i:
                    trade["highest_tp"] = i
                    if i == 1:
                        trade["be"] = True
                        updates.append(f"✅ Trade #{trade_id} BUY TP1 preso\n🎯 TP1: {tp}\n🛡 SL spostato a BE")
                    else:
                        updates.append(f"✅ Trade #{trade_id} BUY TP{i} preso\n🎯 TP{i}: {tp}")

            if trade["be"] and low <= trade["entry_low"]:
                trade["status"] = "BE"
                updates.append(f"🟡 Trade #{trade_id} BUY chiuso a BE dopo TP{trade['highest_tp']}")

        if signal == "SELL":
            if not trade["be"] and high >= trade["sl"]:
                trade["status"] = "LOSS"
                updates.append(f"❌ Trade #{trade_id} SELL chiuso in SL\nSL: {trade['sl']}")
                continue

            for i in range(1, 7):
                tp = trade.get(f"tp{i}", 0)
                if tp and low <= tp and trade["highest_tp"] < i:
                    trade["highest_tp"] = i
                    if i == 1:
                        trade["be"] = True
                        updates.append(f"✅ Trade #{trade_id} SELL TP1 preso\n🎯 TP1: {tp}\n🛡 SL spostato a BE")
                    else:
                        updates.append(f"✅ Trade #{trade_id} SELL TP{i} preso\n🎯 TP{i}: {tp}")

            if trade["be"] and high >= trade["entry_high"]:
                trade["status"] = "BE"
                updates.append(f"🟡 Trade #{trade_id} SELL chiuso a BE dopo TP{trade['highest_tp']}")

    for msg in updates:
        send_telegram(msg)

    return updates
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(silent=True) or {}

    if str(data.get("type", "")).upper() == "PRICE_UPDATE":
        updates = handle_price_update(data)
        return jsonify({"status": "price_checked", "updates": len(updates), "open_trades": len(OPEN_TRADES)})

    signal = normalize_signal(data.get("signal", ""))
    symbol = data.get("symbol", "XAUUSD")
    price = data.get("price", "")
    tf = data.get("tf", "")

    if signal not in ["BUY", "SELL"]:
        return jsonify({"error": "invalid signal", "received": data}), 400

    score, reasons, active_news_bias, news_reasons = score_signal(data, signal)

    if score < MIN_SCORE:
        text = f"""🚫 SEGNALE BLOCCATO v7

Segnale: {signal}
Symbol: {symbol}
Prezzo: {price}
Score finale: {score}
Score minimo: {MIN_SCORE}

Motivi:
- """ + "\n- ".join(reasons) + f"""

📰 News bias attivo: {active_news_bias}
News:
- """ + "\n- ".join(news_reasons) + f"""

🤖 BIAS: {BIAS}
⚠️ EVENT_RISK: {EVENT_RISK}
"""
        send_telegram(text)
        return jsonify({"status": "blocked", "score": score})

    trade = save_trade(data, signal, score)
    emoji = "🟢" if signal == "BUY" else "🔴"

    entry_low = data.get("entry_low", "")
    entry_high = data.get("entry_high", "")
    sl = data.get("sl", "")

    lines = [f"{emoji} GOLD {signal} AI FILTER v7", ""]

    lines.append(f"🆔 Trade ID: {trade['id']}")

    if entry_low and entry_high:
        lines.append(f"📍 Entry Zone: {entry_low} - {entry_high}")
    else:
        lines.append(f"💰 Entry: {price}")

    if sl:
        lines.append(f"🛑 SL: {sl}")

    for i in range(1, 7):
        tp = data.get(f"tp{i}", "")
        if tp:
            lines.append(f"🎯 TP{i}: {tp}")

    lines.extend([
        "",
        f"🧠 Score finale: {score}",
        f"✅ Score minimo: {MIN_SCORE}",
        "",
        "Conferme:",
        "- " + "\n- ".join(reasons),
        "",
        f"📰 News bias attivo: {active_news_bias}",
        "News:",
        "- " + "\n- ".join(news_reasons),
        "",
        f"🤖 BIAS: {BIAS}",
        f"⚠️ EVENT_RISK: {EVENT_RISK}",
        f"⏱ TF: {tf}"
    ])

    send_telegram("\n".join(lines))

    return jsonify({"status": "sent", "signal": signal, "score": score, "trade_id": trade["id"]})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
