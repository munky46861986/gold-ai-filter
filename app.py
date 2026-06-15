import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
BIAS = os.getenv("BIAS", "AUTO").upper()  # AUTO / FORCE_BUY / FORCE_SELL


def send_telegram(text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text}
    r = requests.post(url, json=payload, timeout=10)
    r.raise_for_status()


@app.route("/", methods=["GET"])
def home():
    return "Gold AI Filter Bot v2 attivo ✅"


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "bias": BIAS})


def normalize_signal(signal):
    signal = str(signal).upper()
    if signal == "LONG":
        return "BUY"
    if signal == "SHORT":
        return "SELL"
    return signal


def score_signal(data, signal):
    score = 0
    reasons = []

    h1_bias = str(data.get("h1_bias", "NEUTRAL")).upper()
    h4_bias = str(data.get("h4_bias", "NEUTRAL")).upper()
    day_bias = str(data.get("day_bias", "NEUTRAL")).upper()
    structure = str(data.get("structure", "NEUTRAL")).upper()
    rsi = float(data.get("rsi", 50))
    close_above_ema200 = str(data.get("close_above_ema200", "false")).lower() == "true"

    if BIAS == "FORCE_SELL":
        if signal == "BUY":
            return -999, ["Bloccato: giornata FORCE SELL"]
        score += 3
        reasons.append("Bias manuale FORCE SELL")

    if BIAS == "FORCE_BUY":
        if signal == "SELL":
            return -999, ["Bloccato: giornata FORCE BUY"]
        score += 3
        reasons.append("Bias manuale FORCE BUY")

    if signal == "BUY":
        if h1_bias == "BUY":
            score += 2
            reasons.append("H1 rialzista")
        if h4_bias == "BUY":
            score += 2
            reasons.append("H4 rialzista")
        if day_bias == "BUY":
            score += 1
            reasons.append("Daily rialzista")
        if structure in ["HL", "HH", "BULLISH"]:
            score += 2
            reasons.append("Struttura bullish")
        if rsi > 50:
            score += 1
            reasons.append("RSI sopra 50")
        if close_above_ema200:
            score += 1
            reasons.append("Prezzo sopra EMA200")

        if h4_bias == "SELL":
            score -= 3
            reasons.append("Contro H4 ribassista")
        if day_bias == "SELL":
            score -= 2
            reasons.append("Contro Daily ribassista")

    if signal == "SELL":
        if h1_bias == "SELL":
            score += 2
            reasons.append("H1 ribassista")
        if h4_bias == "SELL":
            score += 2
            reasons.append("H4 ribassista")
        if day_bias == "SELL":
            score += 1
            reasons.append("Daily ribassista")
        if structure in ["LH", "LL", "BEARISH"]:
            score += 2
            reasons.append("Struttura bearish")
        if rsi < 50:
            score += 1
            reasons.append("RSI sotto 50")
        if not close_above_ema200:
            score += 1
            reasons.append("Prezzo sotto EMA200")

        if h4_bias == "BUY":
            score -= 3
            reasons.append("Contro H4 rialzista")
        if day_bias == "BUY":
            score -= 2
            reasons.append("Contro Daily rialzista")

    return score, reasons


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(silent=True) or {}

    signal = normalize_signal(data.get("signal", ""))
    symbol = data.get("symbol", "XAUUSD")
    price = data.get("price", "")
    tf = data.get("tf", "")
    message = data.get("message", "")

    if signal not in ["BUY", "SELL"]:
        return jsonify({"error": "invalid signal", "received": data}), 400

    score, reasons = score_signal(data, signal)

    if score < 4:
        blocked_text = f"""🚫 SEGNALE BLOCCATO

Segnale: {signal}
Symbol: {symbol}
Prezzo: {price}
Score: {score}

Motivi:
- """ + "\n- ".join(reasons)

        send_telegram(blocked_text)
        return jsonify({"status": "blocked", "score": score, "reasons": reasons})

    emoji = "🟢" if signal == "BUY" else "🔴"

    text = f"""{emoji} GOLD {signal} AI FILTER v2

💰 Entry: {price}
📊 Symbol: {symbol}
⏱ TF: {tf}

🧠 Score AI: {score}

Conferme:
- """ + "\n- ".join(reasons)

    if message:
        text += f"\n\n{message}"

    text += f"\n\n🤖 Bias manuale: {BIAS}"

    send_telegram(text)

    return jsonify({
        "status": "sent",
        "signal": signal,
        "score": score,
        "reasons": reasons
    })

@app.route("/test")
def test():
    send_telegram("✅ TEST TELEGRAM DA RENDER")
    return "OK"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
