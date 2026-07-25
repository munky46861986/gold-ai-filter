import os
import time
import json
import requests
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from flask import Flask, request, jsonify

app = Flask(__name__)

# =========================
# CONFIG
# =========================

VERSION = "v9 Max Fade + Anti Duplicate"

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

BIAS = os.getenv("BIAS", "AUTO").upper()
NEWS_BIAS = os.getenv("NEWS_BIAS", "NEUTRAL").upper()
EVENT_RISK = os.getenv("EVENT_RISK", "NORMAL").upper()
MIN_SCORE = int(os.getenv("MIN_SCORE", "6"))

NEWS_API_KEY = os.getenv("NEWS_API_KEY")
AUTO_NEWS = os.getenv("AUTO_NEWS", "FALSE").upper() == "TRUE"

TRADES_FILE = os.getenv("TRADES_FILE", "trades.json")
USER_TIMEZONE = os.getenv("USER_TIMEZONE", "Europe/Rome")

DUPLICATE_SECONDS = int(os.getenv("DUPLICATE_SECONDS", "1800"))
DUPLICATE_SCORE_DELTA = int(os.getenv("DUPLICATE_SCORE_DELTA", "4"))

NEWS_CACHE = {"time": 0, "bias": "NEUTRAL", "reasons": []}
OPEN_TRADES = []

try:
    LOCAL_TZ = ZoneInfo(USER_TIMEZONE)
except Exception:
    LOCAL_TZ = timezone.utc


# =========================
# UTILS
# =========================

def now_ts():
    return time.time()


def local_datetime(ts=None):
    if ts is None:
        ts = now_ts()
    return datetime.fromtimestamp(ts, LOCAL_TZ)


def today_key():
    return local_datetime().strftime("%Y-%m-%d")


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


def to_bool(value):
    return str(value).lower() == "true"


def send_telegram(text: str):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("TELEGRAM NON CONFIGURATO")
        print(text)
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text}

    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"ERRORE TELEGRAM: {e}")
        print(text)
        return False


# =========================
# PERSISTENCE
# =========================

def load_trades():
    global OPEN_TRADES

    if not os.path.exists(TRADES_FILE):
        OPEN_TRADES = []
        return

    try:
        with open(TRADES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            OPEN_TRADES = data
        else:
            OPEN_TRADES = []

    except Exception as e:
        print(f"Errore caricamento trades: {e}")
        OPEN_TRADES = []


def save_trades():
    try:
        tmp_file = TRADES_FILE + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(OPEN_TRADES, f, indent=2, ensure_ascii=False)
        os.replace(tmp_file, TRADES_FILE)
    except Exception as e:
        print(f"Errore salvataggio trades: {e}")


def active_trades_count():
    return sum(1 for t in OPEN_TRADES if t.get("status") in ["PENDING", "OPEN"])


def recent_trades(limit=20):
    return sorted(
        OPEN_TRADES,
        key=lambda x: x.get("created", 0),
        reverse=True
    )[:limit]


# =========================
# ROUTES BASE
# =========================

@app.route("/")
def home():
    return f"Gold AI Filter Bot {VERSION} attivo ✅"


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "version": VERSION,
        "total_trades": len(OPEN_TRADES),
        "active_trades": active_trades_count(),
        "bias": BIAS,
        "news_bias": NEWS_BIAS,
        "auto_news": AUTO_NEWS,
        "event_risk": EVENT_RISK,
        "min_score": MIN_SCORE,
        "duplicate_seconds": DUPLICATE_SECONDS,
        "duplicate_score_delta": DUPLICATE_SCORE_DELTA,
        "trades_file": TRADES_FILE,
        "timezone": USER_TIMEZONE
    })


@app.route("/test")
def test():
    ok = send_telegram(f"✅ TEST TELEGRAM DA RENDER - {VERSION}")
    return jsonify({"status": "ok", "telegram_sent": ok})


@app.route("/trades")
def trades():
    limit = int(request.args.get("limit", "30"))
    return jsonify({
        "version": VERSION,
        "count": len(OPEN_TRADES),
        "active": active_trades_count(),
        "trades": recent_trades(limit)
    })


@app.route("/stats")
def stats():
    return jsonify(get_daily_stats())


@app.route("/stats/telegram")
def stats_telegram():
    send_daily_stats_to_telegram()
    return jsonify({"status": "sent"})


# =========================
# NEWS BIAS
# =========================

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
        "dollar weak", "fed cut", "rate cut", "inflation rises",
        "uncertainty", "crisis", "conflict"
    ]

    bearish_words = [
        "ceasefire", "peace", "reopens", "reopened", "dollar rises",
        "dollar strong", "fed hawkish", "rate hike", "yields rise",
        "risk on", "de-escalation", "calm", "deal", "truce"
    ]

    bullish_score = 0
    bearish_score = 0

    for article in articles:
        text = (
            (article.get("title") or "") + " " +
            (article.get("description") or "")
        ).lower()

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


# =========================
# SCORING
# =========================

def score_signal(data, signal):
    score = 0
    reasons = []
    setup_type = "NORMAL"

    h1_bias = str(data.get("h1_bias", "NEUTRAL")).upper()
    h4_bias = str(data.get("h4_bias", "NEUTRAL")).upper()
    day_bias = str(data.get("day_bias", "NEUTRAL")).upper()
    structure = str(data.get("structure", "NEUTRAL")).upper()

    rsi = to_float(data.get("rsi", 50), 50)
    above_ema200 = to_bool(data.get("close_above_ema200", "false"))

    candle_dir = str(data.get("candle_dir", "NEUTRAL")).upper()
    rejection = str(data.get("rejection", "NONE")).upper()
    ema20_slope = str(data.get("ema20_slope", "FLAT")).upper()
    ema50_slope = str(data.get("ema50_slope", "FLAT")).upper()
    volume_spike = to_bool(data.get("volume_spike", "false"))

    near_m15_high = to_bool(data.get("near_m15_high", "false"))
    near_m15_low = to_bool(data.get("near_m15_low", "false"))
    upper_wick_strong = to_bool(data.get("upper_wick_strong", "false"))
    lower_wick_strong = to_bool(data.get("lower_wick_strong", "false"))

    active_news_bias, news_reasons = get_auto_news_bias()

    # REVERSAL CLASSICO
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

    # MAX FADE MODE
    # Serve per prendere SELL tipo Max:
    # news bullish, prezzo in alto, rejection bearish, Daily/H4 ancora sell.
    max_fade_sell = (
        signal == "SELL"
        and active_news_bias == "BULLISH_GOLD"
        and day_bias == "SELL"
        and h4_bias == "SELL"
        and structure in ["HH", "BEARISH"]
        and (
            rejection == "UPPER_WICK"
            or upper_wick_strong
            or near_m15_high
        )
        and rsi < 68
    )

    max_fade_buy = (
        signal == "BUY"
        and active_news_bias == "BEARISH_GOLD"
        and day_bias == "BUY"
        and h4_bias == "BUY"
        and structure in ["LL", "BULLISH"]
        and (
            rejection == "LOWER_WICK"
            or lower_wick_strong
            or near_m15_low
        )
        and rsi > 32
    )

    if max_fade_sell:
        setup_type = "MAX_FADE_SELL"
        score += 5
        reasons.append("MAX FADE SELL: vendita su eccesso bullish con rejection")

    elif max_fade_buy:
        setup_type = "MAX_FADE_BUY"
        score += 5
        reasons.append("MAX FADE BUY: acquisto su eccesso bearish con rejection")

    elif reversal_buy:
        setup_type = "REVERSAL_BUY"
        score += 5
        reasons.append("Setup REVERSAL BUY stile Max")

    elif reversal_sell:
        setup_type = "REVERSAL_SELL"
        score += 5
        reasons.append("Setup REVERSAL SELL stile Max")

    # BIAS MANUALE
    if BIAS == "FORCE_SELL":
        if signal == "BUY":
            return -999, ["Bloccato: FORCE_SELL attivo"], active_news_bias, news_reasons, setup_type
        score += 4
        reasons.append("Bias manuale FORCE_SELL")

    if BIAS == "FORCE_BUY":
        if signal == "SELL":
            return -999, ["Bloccato: FORCE_BUY attivo"], active_news_bias, news_reasons, setup_type
        score += 4
        reasons.append("Bias manuale FORCE_BUY")

    # NEWS
    if active_news_bias == "BULLISH_GOLD":
        if signal == "BUY":
            score += 1
            reasons.append("News bullish gold")
        else:
            if max_fade_sell:
                reasons.append("SELL contro news bullish permesso: setup fade Max")
            else:
                score -= 2
                reasons.append("SELL contro news bullish gold")

    if active_news_bias == "BEARISH_GOLD":
        if signal == "SELL":
            score += 1
            reasons.append("News bearish gold")
        else:
            if max_fade_buy:
                reasons.append("BUY contro news bearish permesso: setup fade Max")
            else:
                score -= 2
                reasons.append("BUY contro news bearish gold")

    if EVENT_RISK == "HIGH":
        score -= 2
        reasons.append("Evento macro ad alto rischio")

    # BUY
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
            if reversal_buy:
                score -= 1
                reasons.append("BUY reversal contro Daily SELL")
            else:
                score -= 4
                reasons.append("Contro Daily SELL forte")

        if structure in ["HL", "BULLISH", "LL"]:
            score += 2
            reasons.append(f"Struttura {structure}")

        if structure == "HH":
            score -= 3
            reasons.append("BUY dopo HH")

        if rsi > 50:
            score += 1
            reasons.append("RSI sopra 50")

        if rsi > 68:
            score -= 2
            reasons.append("RSI alto")

        if above_ema200:
            score += 1
            reasons.append("Prezzo sopra EMA200")

        if candle_dir == "BULL":
            score += 1
            reasons.append("Candela bullish")

        if candle_dir == "BEAR":
            if max_fade_buy and rejection == "LOWER_WICK":
                reasons.append("Candela rossa accettata: lower wick bullish da fade")
            else:
                score -= 2
                reasons.append("Candela rossa contro BUY")

        if rejection == "LOWER_WICK":
            score += 2
            reasons.append("Rejection bullish")

        if rejection == "UPPER_WICK":
            score -= 3
            reasons.append("Wick alta")

        if ema20_slope == "UP":
            score += 1
            reasons.append("EMA20 UP")

        if ema50_slope == "UP":
            score += 1
            reasons.append("EMA50 UP")

        if ema20_slope == "DOWN":
            if reversal_buy or max_fade_buy:
                score -= 1
                reasons.append("EMA20 DOWN ma setup BUY speciale")
            else:
                score -= 4
                reasons.append("EMA20 DOWN")

        if ema50_slope == "DOWN":
            if reversal_buy or max_fade_buy:
                score -= 1
                reasons.append("EMA50 DOWN ma setup BUY speciale")
            else:
                score -= 2
                reasons.append("EMA50 DOWN")

        if volume_spike and candle_dir == "BEAR":
            score -= 3
            reasons.append("Volume spike bearish")

    # SELL
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
            if reversal_sell:
                score -= 1
                reasons.append("SELL reversal contro Daily BUY")
            else:
                score -= 3
                reasons.append("Contro Daily BUY")

        if structure in ["LH", "BEARISH", "HH"]:
            score += 2
            reasons.append(f"Struttura {structure}")

        if structure == "LL":
            score -= 3
            reasons.append("SELL dopo LL")

        if rsi < 50:
            score += 1
            reasons.append("RSI sotto 50")

        if rsi < 32:
            score -= 2
            reasons.append("RSI basso")

        if not above_ema200:
            score += 1
            reasons.append("Prezzo sotto EMA200")

        if candle_dir == "BEAR":
            score += 1
            reasons.append("Candela bearish")

        if candle_dir == "BULL":
            if max_fade_sell and rejection == "UPPER_WICK":
                reasons.append("Candela verde accettata: upper wick bearish da fade")
            else:
                score -= 2
                reasons.append("Candela verde contro SELL")

        if rejection == "UPPER_WICK":
            score += 2
            reasons.append("Rejection bearish")

        if rejection == "LOWER_WICK":
            score -= 3
            reasons.append("Wick bassa")

        if ema20_slope == "DOWN":
            score += 1
            reasons.append("EMA20 DOWN")

        if ema50_slope == "DOWN":
            score += 1
            reasons.append("EMA50 DOWN")

        if ema20_slope == "UP":
            if reversal_sell or max_fade_sell:
                score -= 1
                reasons.append("EMA20 UP ma setup SELL speciale")
            else:
                score -= 2
                reasons.append("EMA20 UP")

        if ema50_slope == "UP":
            if reversal_sell or max_fade_sell:
                score -= 1
                reasons.append("EMA50 UP ma setup SELL speciale")
            else:
                score -= 2
                reasons.append("EMA50 UP")

        if volume_spike and candle_dir == "BULL":
            score -= 3
            reasons.append("Volume spike bullish")

    return score, reasons, active_news_bias, news_reasons, setup_type


# =========================
# DUPLICATE FILTER
# =========================

def find_recent_same_trade(signal, symbol):
    now = now_ts()
    symbol = str(symbol).upper()

    candidates = []

    for trade in OPEN_TRADES:
        trade_symbol = str(trade.get("symbol", "")).upper()
        trade_signal = str(trade.get("signal", "")).upper()
        trade_status = trade.get("status")

        if trade_symbol != symbol:
            continue

        if trade_signal != signal:
            continue

        if trade_status not in ["PENDING", "OPEN"]:
            continue

        created = trade.get("created", 0)

        if now - created <= DUPLICATE_SECONDS:
            candidates.append(trade)

    if not candidates:
        return None

    return sorted(candidates, key=lambda x: x.get("created", 0), reverse=True)[0]


def should_block_duplicate(signal, symbol, score):
    recent = find_recent_same_trade(signal, symbol)

    if not recent:
        return False, None

    recent_score = int(recent.get("score", 0))

    if score >= recent_score + DUPLICATE_SCORE_DELTA:
        return False, recent

    return True, recent


# =========================
# TRADE MANAGEMENT
# =========================

def save_trade(data, signal, score, setup_type):
    trade_id = str(int(time.time() * 1000))

    trade = {
        "id": trade_id,
        "signal": signal,
        "setup_type": setup_type,
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
        "tp7": to_float(data.get("tp7")),
        "tp8": to_float(data.get("tp8")),
        "score": score,
        "status": "PENDING",
        "entered": False,
        "be": False,
        "highest_tp": 0,
        "created": now_ts(),
        "created_local": local_datetime().strftime("%Y-%m-%d %H:%M:%S"),
        "activated": None,
        "closed": None
    }

    OPEN_TRADES.append(trade)
    save_trades()

    return trade


def handle_price_update(data):
    high = to_float(data.get("high"))
    low = to_float(data.get("low"))

    updates = []
    changed = False

    for trade in OPEN_TRADES:
        if trade.get("status") not in ["OPEN", "PENDING"]:
            continue

        signal = trade.get("signal")
        trade_id = trade.get("id")
        be_was_already_active = bool(trade.get("be", False))

        # PENDING ENTRY
        if trade.get("status") == "PENDING":

            if signal == "BUY":
                entered = low <= trade["entry_high"] and high >= trade["entry_low"]

                if entered:
                    trade["status"] = "OPEN"
                    trade["entered"] = True
                    trade["activated"] = now_ts()
                    changed = True

                    updates.append(
                        f"🎯 Trade #{trade_id} BUY ATTIVATO\n"
                        f"Setup: {trade.get('setup_type', 'NORMAL')}\n"
                        f"Zona: {trade['entry_low']} - {trade['entry_high']}"
                    )
                else:
                    continue

            elif signal == "SELL":
                entered = high >= trade["entry_low"] and low <= trade["entry_high"]

                if entered:
                    trade["status"] = "OPEN"
                    trade["entered"] = True
                    trade["activated"] = now_ts()
                    changed = True

                    updates.append(
                        f"🎯 Trade #{trade_id} SELL ATTIVATO\n"
                        f"Setup: {trade.get('setup_type', 'NORMAL')}\n"
                        f"Zona: {trade['entry_low']} - {trade['entry_high']}"
                    )
                else:
                    continue

        # BUY MANAGEMENT
        if signal == "BUY":

            if not trade.get("be") and low <= trade["sl"]:
                trade["status"] = "LOSS"
                trade["closed"] = now_ts()
                changed = True

                updates.append(
                    f"❌ Trade #{trade_id} BUY chiuso in SL\n"
                    f"Setup: {trade.get('setup_type', 'NORMAL')}\n"
                    f"SL: {trade['sl']}"
                )
                continue

            for i in range(1, 9):
                tp = trade.get(f"tp{i}", 0)

                if tp and high >= tp and trade.get("highest_tp", 0) < i:
                    trade["highest_tp"] = i
                    changed = True

                    if i == 1:
                        trade["be"] = True
                        updates.append(
                            f"✅ Trade #{trade_id} BUY TP1 preso\n"
                            f"🎯 TP1: {tp}\n"
                            f"🛡 SL spostato a BE"
                        )
                    else:
                        updates.append(
                            f"✅ Trade #{trade_id} BUY TP{i} preso\n"
                            f"🎯 TP{i}: {tp}"
                        )

            if trade.get("be") and be_was_already_active and low <= trade["entry_low"]:
                trade["status"] = "BE"
                trade["closed"] = now_ts()
                changed = True

                updates.append(
                    f"🟡 Trade #{trade_id} BUY chiuso a BE dopo TP{trade.get('highest_tp', 0)}"
                )

        # SELL MANAGEMENT
        if signal == "SELL":

            if not trade.get("be") and high >= trade["sl"]:
                trade["status"] = "LOSS"
                trade["closed"] = now_ts()
                changed = True

                updates.append(
                    f"❌ Trade #{trade_id} SELL chiuso in SL\n"
                    f"Setup: {trade.get('setup_type', 'NORMAL')}\n"
                    f"SL: {trade['sl']}"
                )
                continue

            for i in range(1, 9):
                tp = trade.get(f"tp{i}", 0)

                if tp and low <= tp and trade.get("highest_tp", 0) < i:
                    trade["highest_tp"] = i
                    changed = True

                    if i == 1:
                        trade["be"] = True
                        updates.append(
                            f"✅ Trade #{trade_id} SELL TP1 preso\n"
                            f"🎯 TP1: {tp}\n"
                            f"🛡 SL spostato a BE"
                        )
                    else:
                        updates.append(
                            f"✅ Trade #{trade_id} SELL TP{i} preso\n"
                            f"🎯 TP{i}: {tp}"
                        )

            if trade.get("be") and be_was_already_active and high >= trade["entry_high"]:
                trade["status"] = "BE"
                trade["closed"] = now_ts()
                changed = True

                updates.append(
                    f"🟡 Trade #{trade_id} SELL chiuso a BE dopo TP{trade.get('highest_tp', 0)}"
                )

    if changed:
        save_trades()

    for msg in updates:
        send_telegram(msg)

    return updates


# =========================
# STATS
# =========================

def get_daily_stats():
    today = today_key()
    today_trades = []

    for trade in OPEN_TRADES:
        created = trade.get("created", 0)

        try:
            day = local_datetime(created).strftime("%Y-%m-%d")
        except Exception:
            day = ""

        if day == today:
            today_trades.append(trade)

    total = len(today_trades)
    active = sum(1 for t in today_trades if t.get("status") in ["PENDING", "OPEN"])
    losses = sum(1 for t in today_trades if t.get("status") == "LOSS")
    be = sum(1 for t in today_trades if t.get("status") == "BE")

    tp1 = sum(1 for t in today_trades if int(t.get("highest_tp", 0)) >= 1)
    tp3 = sum(1 for t in today_trades if int(t.get("highest_tp", 0)) >= 3)
    tp5 = sum(1 for t in today_trades if int(t.get("highest_tp", 0)) >= 5)
    tp8 = sum(1 for t in today_trades if int(t.get("highest_tp", 0)) >= 8)

    by_setup = {}

    for trade in today_trades:
        setup = trade.get("setup_type", "NORMAL")

        if setup not in by_setup:
            by_setup[setup] = {
                "total": 0,
                "tp1": 0,
                "tp3": 0,
                "tp5": 0,
                "loss": 0,
                "be": 0,
                "active": 0
            }

        by_setup[setup]["total"] += 1

        if int(trade.get("highest_tp", 0)) >= 1:
            by_setup[setup]["tp1"] += 1

        if int(trade.get("highest_tp", 0)) >= 3:
            by_setup[setup]["tp3"] += 1

        if int(trade.get("highest_tp", 0)) >= 5:
            by_setup[setup]["tp5"] += 1

        if trade.get("status") == "LOSS":
            by_setup[setup]["loss"] += 1

        if trade.get("status") == "BE":
            by_setup[setup]["be"] += 1

        if trade.get("status") in ["PENDING", "OPEN"]:
            by_setup[setup]["active"] += 1

    tp1_rate = round((tp1 / total) * 100, 2) if total else 0
    loss_rate = round((losses / total) * 100, 2) if total else 0

    return {
        "version": VERSION,
        "date": today,
        "timezone": USER_TIMEZONE,
        "total_today": total,
        "active_today": active,
        "losses_today": losses,
        "be_today": be,
        "tp1_hit_today": tp1,
        "tp3_hit_today": tp3,
        "tp5_hit_today": tp5,
        "tp8_hit_today": tp8,
        "tp1_rate_percent": tp1_rate,
        "loss_rate_percent": loss_rate,
        "by_setup_type": by_setup
    }


def send_daily_stats_to_telegram():
    s = get_daily_stats()

    lines = [
        f"📊 GOLD AI FILTER {VERSION}",
        f"Statistiche giornaliere {s['date']}",
        "",
        f"Trade totali: {s['total_today']}",
        f"Attivi: {s['active_today']}",
        f"SL diretti: {s['losses_today']}",
        f"BE: {s['be_today']}",
        "",
        f"TP1 hit: {s['tp1_hit_today']} ({s['tp1_rate_percent']}%)",
        f"TP3 hit: {s['tp3_hit_today']}",
        f"TP5 hit: {s['tp5_hit_today']}",
        f"TP8 hit: {s['tp8_hit_today']}",
        "",
        "Setup:"
    ]

    for setup, data in s["by_setup_type"].items():
        lines.append(
            f"- {setup}: total {data['total']}, TP1 {data['tp1']}, "
            f"TP3 {data['tp3']}, TP5 {data['tp5']}, SL {data['loss']}, BE {data['be']}"
        )

    send_telegram("\n".join(lines))


# =========================
# WEBHOOK
# =========================

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(silent=True) or {}

    if str(data.get("type", "")).upper() == "PRICE_UPDATE":
        updates = handle_price_update(data)

        return jsonify({
            "status": "price_checked",
            "updates": len(updates),
            "active_trades": active_trades_count(),
            "total_trades": len(OPEN_TRADES)
        })

    signal = normalize_signal(data.get("signal", ""))
    symbol = data.get("symbol", "XAUUSD")
    price = data.get("price", "")
    tf = data.get("tf", "")

    if signal not in ["BUY", "SELL"]:
        return jsonify({"error": "invalid signal", "received": data}), 400

    score, reasons, active_news_bias, news_reasons, setup_type = score_signal(data, signal)

    # SCORE BLOCK
    if score < MIN_SCORE:
        text = f"""🚫 SEGNALE BLOCCATO {VERSION}

Segnale: {signal}
Symbol: {symbol}
Prezzo: {price}
Setup: {setup_type}
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
        return jsonify({
            "status": "blocked",
            "reason": "score_below_min",
            "score": score,
            "setup_type": setup_type
        })

    # DUPLICATE BLOCK
    block_duplicate, recent = should_block_duplicate(signal, symbol, score)

    if block_duplicate:
        text = f"""🚫 SEGNALE BLOCCATO {VERSION}

Motivo: duplicato stesso movimento

Segnale: {signal}
Symbol: {symbol}
Prezzo: {price}
Setup: {setup_type}
Score finale: {score}

Trade già attivo:
ID: {recent.get('id')}
Setup: {recent.get('setup_type')}
Score precedente: {recent.get('score')}
Status: {recent.get('status')}
Entry: {recent.get('entry_low')} - {recent.get('entry_high')}

Filtro duplicati:
Cooldown secondi: {DUPLICATE_SECONDS}
Score delta richiesto: +{DUPLICATE_SCORE_DELTA}
"""
        send_telegram(text)

        return jsonify({
            "status": "blocked_duplicate",
            "score": score,
            "setup_type": setup_type,
            "recent_trade_id": recent.get("id")
        })

    # SAVE TRADE
    trade = save_trade(data, signal, score, setup_type)
    emoji = "🟢" if signal == "BUY" else "🔴"

    entry_low = data.get("entry_low", "")
    entry_high = data.get("entry_high", "")
    sl = data.get("sl", "")

    lines = [
        f"{emoji} GOLD {signal} AI FILTER {VERSION}",
        "",
        f"🆔 Trade ID: {trade['id']}",
        f"📌 Setup: {setup_type}"
    ]

    if entry_low and entry_high:
        lines.append(f"📍 Entry Zone: {entry_low} - {entry_high}")
    else:
        lines.append(f"💰 Entry: {price}")

    if sl:
        lines.append(f"🛑 SL: {sl}")

    for i in range(1, 9):
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

    telegram_sent = send_telegram("\n".join(lines))

    return jsonify({
        "status": "sent",
        "signal": signal,
        "score": score,
        "setup_type": setup_type,
        "trade_id": trade["id"],
        "telegram_sent": telegram_sent
    })


# =========================
# STARTUP
# =========================

load_trades()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
