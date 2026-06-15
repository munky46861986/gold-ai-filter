import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

BIAS = os.getenv("BIAS", "AUTO").upper()
NEWS_BIAS = os.getenv("NEWS_BIAS", "NEUTRAL").upper()
EVENT_RISK = os.getenv("EVENT_RISK", "NORMAL").upper()
MIN_SCORE = int(os.getenv("MIN_SCORE", "6"))


def send_telegram(text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text}
    r = requests.post(url, json=payload, timeout=10)
    r.raise_for_status()


@app.route("/")
def home():
    return "Gold AI Filter Bot v3 Livello 4 attivo ✅"


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "bias": BIAS,
        "news_bias": NEWS_BIAS,
        "event_risk": EVENT_RISK,
        "min_score": MIN_SCORE
    })


@app.route("/test")
def test():
    send_telegram("✅ TEST TELEGRAM DA RENDER - v3")
    return "OK"


def normalize_signal(signal):
    signal = str(signal).upper()
    if signal == "LONG":
        return "BUY"
    if signal == "SHORT":
        return "SELL"
    return signal


def to_float(value, default=50.0):
    try:
        return float(value)
    except Exception:
        return default


def score_signal(data, signal):
    score = 0
    reasons = []

    h1_bias = str(data.get("h1_bias", "NEUTRAL")).upper()
    h4_bias = str(data.get("h4_bias", "NEUTRAL")).upper()
    day_bias = str(data.get("day_bias", "NEUTRAL")).upper()
    structure = str(data.get("structure", "NEUTRAL")).upper()
    rsi = to_float(data.get("rsi", 50))
    above_ema200 = str(data.get("close_above_ema200", "false")).lower() == "true"

    # BIAS MANUALE
    if BIAS == "FORCE_SELL":
        if signal == "BUY":
            return -999, ["Bloccato: FORCE_SELL attivo"]
        score += 4
        reasons.append("Bias manuale FORCE_SELL")

    if BIAS == "FORCE_BUY":
        if signal == "SELL":
            return -999, ["Bloccato: FORCE_BUY attivo"]
        score += 4
        reasons.append("Bias manuale FORCE_BUY")

    # NEWS BIAS
    if NEWS_BIAS == "BEARISH_GOLD":
        if signal == "SELL":
            score += 3
            reasons.append("News bias bearish gold")
        else:
            score -= 4
            reasons.append("BUY contro news bearish gold")

    if NEWS_BIAS == "BULLISH_GOLD":
        if signal == "BUY":
            score += 3
            reasons.append("News bias bullish gold")
        else:
            score -= 4
            reasons.append("SELL contro news bullish gold")

    # EVENT RISK
    if EVENT_RISK == "HIGH":
        score -= 2
        reasons.append("Evento macro ad alto rischio")

    # SCORE TECNICO
    if signal == "BUY":
        if h1_bias == "BUY":
            score += 2
            reasons.append("H1 BUY")
        if h4_bias == "BUY":
            score += 2
            reasons.append("H4 BUY")
        if day_bias == "BUY":
            score += 1
            reasons.append("Daily BUY")
        if structure in ["HL", "HH", "BULLISH", "LL"]:
            score += 2
            reasons.append(f"Struttura {structure}")
        if rsi > 50:
            score += 1
            reasons.append("RSI sopra 50")
        if above_ema200:
            score += 1
            reasons.append("Prezzo sopra EMA200")
        if h4_bias == "SELL":
            score -= 3
            reasons.append("Contro H4 SELL")
        if day_bias == "SELL":
            score -= 2
            reasons.append("Contro Daily SELL")

    if signal == "SELL":
        if h1_bias == "SELL":
            score += 2
            reasons.append("H1 SELL")
        if h4_bias == "SELL":
            score += 2
            reasons.append("H4 SELL")
        if day_bias == "SELL":
            score += 1
            reasons.append("Daily SELL")
        if structure in ["LH", "LL", "BEARISH", "HH"]:
            score += 2
            reasons.append(f"Struttura {structure}")
        if rsi < 50:
            score += 1
            reasons.append("RSI sotto 50")
        if not above_ema200:
            score += 1
            reasons.append("Prezzo sotto EMA200")
        if h4_bias == "BUY":
            score -= 3
            reasons.append("Contro H4 BUY")
        if day_bias == "BUY":
            score -= 2
            reasons.append("Contro Daily BUY")

    return score, reasons


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(silent=True) or {}

    signal = normalize_signal(data.get("signal", ""))
    symbol = data.get("symbol", "XAUUSD")
    price = data.get("price", "")
    tf = data.get("tf", "")

    if signal not in ["BUY", "SELL"]:
        return jsonify({"error": "invalid signal", "received": data}), 400

    score, reasons = score_signal(data, signal)

    if score < MIN_SCORE:
        text = f"""🚫 SEGNALE BLOCCATO

Segnale: {signal}
Symbol: {symbol}
Prezzo: {price}
Score finale: {score}
Score minimo: {MIN_SCORE}

Motivi:
- """ + "\n- ".join(reasons) + f"""

🤖 BIAS: {BIAS}
📰 NEWS_BIAS: {NEWS_BIAS}
⚠️ EVENT_RISK: {EVENT_RISK}
"""
        send_telegram(text)
        return jsonify({"status": "blocked", "score": score, "reasons": reasons})

    emoji = "🟢" if signal == "BUY" else "🔴"

    entry_low = data.get("entry_low", "")
    entry_high = data.get("entry_high", "")
    sl = data.get("sl", "")

    lines = [
        f"{emoji} GOLD {signal} AI FILTER v3",
        "",
    ]

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
        f"🤖 BIAS: {BIAS}",
        f"📰 NEWS_BIAS: {NEWS_BIAS}",
        f"⚠️ EVENT_RISK: {EVENT_RISK}",
        f"⏱ TF: {tf}"
    ])

    send_telegram("\n".join(lines))

    return jsonify({"status": "sent", "signal": signal, "score": score})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
