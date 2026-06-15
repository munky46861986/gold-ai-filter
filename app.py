import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
BIAS = os.getenv("BIAS", "AUTO").upper()  # AUTO / FORCE_BUY / FORCE_SELL


def send_telegram(text: str) -> None:
    if not TELEGRAM_TOKEN or not CHAT_ID:
        raise RuntimeError("Missing TELEGRAM_TOKEN or CHAT_ID environment variables")

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text}
    response = requests.post(url, json=payload, timeout=10)
    response.raise_for_status()


@app.route("/", methods=["GET"])
def home():
    return "Gold AI Filter Bot attivo ✅"


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "bias": BIAS})


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(silent=True) or {}

    signal = str(data.get("signal", "")).upper()
    symbol = data.get("symbol", "XAUUSD")
    price = data.get("price", "")
    tf = data.get("tf", "")
    message = data.get("message", "")

    tp1 = data.get("tp1", "")
    tp2 = data.get("tp2", "")
    tp3 = data.get("tp3", "")
    tp4 = data.get("tp4", "")
    tp5 = data.get("tp5", "")
    tp6 = data.get("tp6", "")
    sl = data.get("sl", "")
    entry_low = data.get("entry_low", "")
    entry_high = data.get("entry_high", "")

    if signal not in {"BUY", "SELL", "LONG", "SHORT"}:
        return jsonify({"error": "missing or invalid signal", "received": data}), 400

    if signal == "LONG":
        signal = "BUY"
    if signal == "SHORT":
        signal = "SELL"

    if BIAS == "FORCE_SELL" and signal == "BUY":
        return jsonify({"status": "blocked", "reason": "FORCE_SELL blocks BUY", "signal": signal})

    if BIAS == "FORCE_BUY" and signal == "SELL":
        return jsonify({"status": "blocked", "reason": "FORCE_BUY blocks SELL", "signal": signal})

    emoji = "🟢" if signal == "BUY" else "🔴"

    lines = [f"{emoji} GOLD {signal} AI FILTER", ""]

    if entry_low != "" and entry_high != "":
        lines.append(f"📍 Entry Zone: {entry_low} - {entry_high}")
    elif price != "":
        lines.append(f"💰 Entry: {price}")

    if sl != "":
        lines.append(f"🛑 SL: {sl}")

    targets = [tp1, tp2, tp3, tp4, tp5, tp6]
    for i, tp in enumerate(targets, start=1):
        if tp != "":
            lines.append(f"🎯 TP{i}: {tp}")

    if tf != "":
        lines.append(f"⏱ TF: {tf}")

    if message:
        lines.extend(["", str(message)])

    lines.extend(["", f"🤖 Bias attuale: {BIAS}"])

    send_telegram("\n".join(lines))

    return jsonify({"status": "sent", "signal": signal, "bias": BIAS})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)