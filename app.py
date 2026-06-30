import os
import time
import json
import math
import requests
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from flask import Flask, request, jsonify

app = Flask(__name__)

# =========================
# CONFIG
# =========================

VERSION = "v14 Buy Fatigue + Conflict Resolver"

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

DUPLICATE_SECONDS = int(os.getenv("DUPLICATE_SECONDS", "1200"))
DUPLICATE_SCORE_DELTA = int(os.getenv("DUPLICATE_SCORE_DELTA", "4"))

# v10: Stop temporaneo dopo SL diretti
SL_COOLDOWN_ENABLED = os.getenv("SL_COOLDOWN_ENABLED", "TRUE").upper() == "TRUE"
SL_COOLDOWN_SIGNAL = os.getenv("SL_COOLDOWN_SIGNAL", "SELL").upper()
SL_COOLDOWN_LOSSES = int(os.getenv("SL_COOLDOWN_LOSSES", "2"))
SL_COOLDOWN_LOOKBACK_SECONDS = int(os.getenv("SL_COOLDOWN_LOOKBACK_SECONDS", "5400"))  # 90 minuti
SL_COOLDOWN_SECONDS = int(os.getenv("SL_COOLDOWN_SECONDS", "3600"))  # 60 minuti

# v11: Runner dopo TP8
RUNNER_MODE_ENABLED = os.getenv("RUNNER_MODE_ENABLED", "TRUE").upper() == "TRUE"
RUNNER_TP_LEVEL = int(os.getenv("RUNNER_TP_LEVEL", "8"))

# v11: Livelli psicologici
PSYCH_LEVEL_STEP = float(os.getenv("PSYCH_LEVEL_STEP", "25"))
PSYCH_LEVEL_DISTANCE = float(os.getenv("PSYCH_LEVEL_DISTANCE", "3.5"))

# v11: Exhaustion Control
# Dopo tanti SELL arrivati a TP8, il bot smette di inseguire SELL NORMAL bassi.
SELL_EXHAUSTION_ENABLED = os.getenv("SELL_EXHAUSTION_ENABLED", "TRUE").upper() == "TRUE"
SELL_EXHAUSTION_TP_LEVEL = int(os.getenv("SELL_EXHAUSTION_TP_LEVEL", "8"))
SELL_EXHAUSTION_COUNT = int(os.getenv("SELL_EXHAUSTION_COUNT", "2"))
SELL_EXHAUSTION_LOOKBACK_SECONDS = int(os.getenv("SELL_EXHAUSTION_LOOKBACK_SECONDS", "7200"))  # 2 ore
SELL_EXHAUSTION_MAX_FADE_MIN_SCORE = int(os.getenv("SELL_EXHAUSTION_MAX_FADE_MIN_SCORE", "14"))

# v12: Max Recovery Buy
# Serve per prendere il BUY di recupero dopo una grande discesa,
# non solo il BUY sul minimo puro.
RECOVERY_BUY_ENABLED = os.getenv("RECOVERY_BUY_ENABLED", "TRUE").upper() == "TRUE"
RECOVERY_BUY_TP_LEVEL = int(os.getenv("RECOVERY_BUY_TP_LEVEL", "8"))
RECOVERY_BUY_DEEP_SELL_COUNT = int(os.getenv("RECOVERY_BUY_DEEP_SELL_COUNT", "1"))
RECOVERY_BUY_LOOKBACK_SECONDS = int(os.getenv("RECOVERY_BUY_LOOKBACK_SECONDS", "7200"))
RECOVERY_BUY_MIN_CONFIRMATIONS = int(os.getenv("RECOVERY_BUY_MIN_CONFIRMATIONS", "3"))

# v13: Recovery Lock
# Se un BUY da fondo/recupero sta funzionando, il bot smette di combatterlo con SELL.
RECOVERY_LOCK_ENABLED = os.getenv("RECOVERY_LOCK_ENABLED", "TRUE").upper() == "TRUE"

# Se un BUY speciale prende TP3, blocco SELL NORMAL per 45 minuti.
RECOVERY_LOCK_TP3_LEVEL = int(os.getenv("RECOVERY_LOCK_TP3_LEVEL", "3"))
RECOVERY_LOCK_TP3_SECONDS = int(os.getenv("RECOVERY_LOCK_TP3_SECONDS", "2700"))

# Se un BUY speciale prende TP5/TP6, blocco più forte per 90 minuti.
RECOVERY_LOCK_TP5_LEVEL = int(os.getenv("RECOVERY_LOCK_TP5_LEVEL", "5"))
RECOVERY_LOCK_TP5_SECONDS = int(os.getenv("RECOVERY_LOCK_TP5_SECONDS", "5400"))

# Se un BUY arriva a TP8 / Runner, considero il recupero confermato per 2 ore.
RECOVERY_LOCK_RUNNER_LEVEL = int(os.getenv("RECOVERY_LOCK_RUNNER_LEVEL", "8"))
RECOVERY_LOCK_RUNNER_SECONDS = int(os.getenv("RECOVERY_LOCK_RUNNER_SECONDS", "7200"))

# Durante Recovery Lock, un MAX_FADE_SELL può passare solo se è davvero fortissimo.
RECOVERY_LOCK_MAX_FADE_MIN_SCORE = int(os.getenv("RECOVERY_LOCK_MAX_FADE_MIN_SCORE", "22"))

# Se un BUY speciale è ancora OPEN e ha già preso TP1/TP2, blocco i SELL opposti.
OPPOSITE_TRADE_LOCK_ENABLED = os.getenv("OPPOSITE_TRADE_LOCK_ENABLED", "TRUE").upper() == "TRUE"
OPPOSITE_TRADE_LOCK_MIN_TP = int(os.getenv("OPPOSITE_TRADE_LOCK_MIN_TP", "1"))

RECOVERY_LOCK_BUY_SETUPS = {
    "MAX_RECOVERY_BUY",
    "MAX_DIP_BUY",
    "REVERSAL_BUY"
}

# v14: Buy Fatigue + Conflict Resolver
# La v13 non combatte i BUY che funzionano.
# La v14 aggiunge due intelligenze:
# 1) non inseguire troppi BUY quando l'onda è già matura;
# 2) non aprire BUY e SELL quasi insieme, ma scegliere la direzione dominante.
BUY_FATIGUE_ENABLED = os.getenv("BUY_FATIGUE_ENABLED", "TRUE").upper() == "TRUE"
BUY_FATIGUE_TP_LEVEL = int(os.getenv("BUY_FATIGUE_TP_LEVEL", "5"))
BUY_FATIGUE_COUNT = int(os.getenv("BUY_FATIGUE_COUNT", "2"))
BUY_FATIGUE_LOOKBACK_SECONDS = int(os.getenv("BUY_FATIGUE_LOOKBACK_SECONDS", "7200"))
BUY_FATIGUE_ALLOW_SCORE = int(os.getenv("BUY_FATIGUE_ALLOW_SCORE", "18"))

# Dopo BUY_FATIGUE attivo, il bot accetta nuovi BUY solo se sono davvero speciali
# e arrivano da zona bassa / livello psicologico / recente low.
BUY_FATIGUE_ALLOW_SETUPS = {
    "MAX_DIP_BUY",
    "MAX_RECOVERY_BUY"
}

BUY_SL_COOLDOWN_ENABLED = os.getenv("BUY_SL_COOLDOWN_ENABLED", "TRUE").upper() == "TRUE"
BUY_SL_COOLDOWN_LOSSES = int(os.getenv("BUY_SL_COOLDOWN_LOSSES", "2"))
BUY_SL_COOLDOWN_LOOKBACK_SECONDS = int(os.getenv("BUY_SL_COOLDOWN_LOOKBACK_SECONDS", "5400"))
BUY_SL_COOLDOWN_SECONDS = int(os.getenv("BUY_SL_COOLDOWN_SECONDS", "3600"))

CONFLICT_RESOLVER_ENABLED = os.getenv("CONFLICT_RESOLVER_ENABLED", "TRUE").upper() == "TRUE"
CONFLICT_WINDOW_SECONDS = int(os.getenv("CONFLICT_WINDOW_SECONDS", "300"))
CONFLICT_DOMINANCE_MARGIN = int(os.getenv("CONFLICT_DOMINANCE_MARGIN", "4"))

SETUP_WEIGHTS = {
    "MAX_RECOVERY_BUY": 5,
    "MAX_DIP_BUY": 4,
    "REVERSAL_BUY": 4,
    "MAX_FADE_SELL": 3,
    "MAX_DIP_SELL": 3,
    "REVERSAL_SELL": 3,
    "NORMAL": 1
}

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


def to_int(value, default=0):
    try:
        return int(value)
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


def get_price_from_data(data):
    price = to_float(data.get("price"), 0)

    if price:
        return price

    entry_low = to_float(data.get("entry_low"), 0)
    entry_high = to_float(data.get("entry_high"), 0)

    if entry_low and entry_high:
        return (entry_low + entry_high) / 2

    return 0


def psych_info(price):
    if not price or PSYCH_LEVEL_STEP <= 0:
        return False, None, None

    nearest = round(price / PSYCH_LEVEL_STEP) * PSYCH_LEVEL_STEP
    distance = abs(price - nearest)
    near = distance <= PSYCH_LEVEL_DISTANCE

    return near, nearest, distance


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
        "sl_cooldown_enabled": SL_COOLDOWN_ENABLED,
        "sl_cooldown_signal": SL_COOLDOWN_SIGNAL,
        "sl_cooldown_losses": SL_COOLDOWN_LOSSES,
        "sl_cooldown_lookback_seconds": SL_COOLDOWN_LOOKBACK_SECONDS,
        "sl_cooldown_seconds": SL_COOLDOWN_SECONDS,
        "runner_mode_enabled": RUNNER_MODE_ENABLED,
        "runner_tp_level": RUNNER_TP_LEVEL,
        "psych_level_step": PSYCH_LEVEL_STEP,
        "psych_level_distance": PSYCH_LEVEL_DISTANCE,
        "sell_exhaustion_enabled": SELL_EXHAUSTION_ENABLED,
        "sell_exhaustion_tp_level": SELL_EXHAUSTION_TP_LEVEL,
        "sell_exhaustion_count": SELL_EXHAUSTION_COUNT,
        "sell_exhaustion_lookback_seconds": SELL_EXHAUSTION_LOOKBACK_SECONDS,
        "sell_exhaustion_max_fade_min_score": SELL_EXHAUSTION_MAX_FADE_MIN_SCORE,
        "recovery_buy_enabled": RECOVERY_BUY_ENABLED,
        "recovery_buy_tp_level": RECOVERY_BUY_TP_LEVEL,
        "recovery_buy_deep_sell_count": RECOVERY_BUY_DEEP_SELL_COUNT,
        "recovery_buy_lookback_seconds": RECOVERY_BUY_LOOKBACK_SECONDS,
        "recovery_buy_min_confirmations": RECOVERY_BUY_MIN_CONFIRMATIONS,
        "recovery_lock_enabled": RECOVERY_LOCK_ENABLED,
        "recovery_lock_tp3_level": RECOVERY_LOCK_TP3_LEVEL,
        "recovery_lock_tp3_seconds": RECOVERY_LOCK_TP3_SECONDS,
        "recovery_lock_tp5_level": RECOVERY_LOCK_TP5_LEVEL,
        "recovery_lock_tp5_seconds": RECOVERY_LOCK_TP5_SECONDS,
        "recovery_lock_runner_level": RECOVERY_LOCK_RUNNER_LEVEL,
        "recovery_lock_runner_seconds": RECOVERY_LOCK_RUNNER_SECONDS,
        "recovery_lock_max_fade_min_score": RECOVERY_LOCK_MAX_FADE_MIN_SCORE,
        "opposite_trade_lock_enabled": OPPOSITE_TRADE_LOCK_ENABLED,
        "opposite_trade_lock_min_tp": OPPOSITE_TRADE_LOCK_MIN_TP,
        "buy_fatigue_enabled": BUY_FATIGUE_ENABLED,
        "buy_fatigue_tp_level": BUY_FATIGUE_TP_LEVEL,
        "buy_fatigue_count": BUY_FATIGUE_COUNT,
        "buy_fatigue_lookback_seconds": BUY_FATIGUE_LOOKBACK_SECONDS,
        "buy_fatigue_allow_score": BUY_FATIGUE_ALLOW_SCORE,
        "buy_sl_cooldown_enabled": BUY_SL_COOLDOWN_ENABLED,
        "buy_sl_cooldown_losses": BUY_SL_COOLDOWN_LOSSES,
        "buy_sl_cooldown_lookback_seconds": BUY_SL_COOLDOWN_LOOKBACK_SECONDS,
        "buy_sl_cooldown_seconds": BUY_SL_COOLDOWN_SECONDS,
        "conflict_resolver_enabled": CONFLICT_RESOLVER_ENABLED,
        "conflict_window_seconds": CONFLICT_WINDOW_SECONDS,
        "conflict_dominance_margin": CONFLICT_DOMINANCE_MARGIN,
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

    price = get_price_from_data(data)
    symbol = str(data.get("symbol", "XAUUSD")).upper()
    near_psych_level, nearest_psych, psych_distance = psych_info(price)

    # Campi extra mandati dal Pine v30/v31/v32
    close_above_ema20 = to_bool(data.get("close_above_ema20", "false"))
    close_above_ema50 = to_bool(data.get("close_above_ema50", "false"))
    recovery_buy_signal = to_bool(data.get("recovery_buy_signal", "false"))
    recent_low_touch = to_bool(data.get("recent_low_touch", "false"))

    # TradingView v29 manda già questi campi. Se ci sono, li uso.
    if data.get("near_psych_level") is not None:
        near_psych_level = to_bool(data.get("near_psych_level"))

    if data.get("psych_level") is not None:
        nearest_psych = to_float(data.get("psych_level"), nearest_psych or 0)

    if data.get("psych_distance") is not None:
        psych_distance = to_float(data.get("psych_distance"), psych_distance or 999)

    active_news_bias, news_reasons = get_auto_news_bias()

    # v12 context:
    # se ci sono stati SELL profondi recenti, un BUY di recupero diventa più interessante.
    recent_deep_sells = get_recent_tp_trades(
        "SELL",
        symbol,
        min_tp=RECOVERY_BUY_TP_LEVEL,
        lookback_seconds=RECOVERY_BUY_LOOKBACK_SECONDS
    )

    # =========================
    # SETUP SPECIALI
    # =========================

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

    # MAX FADE SELL v11:
    # Deve essere un vero rimbalzo/upper rejection, non un SELL basso qualsiasi.
    max_fade_sell = (
        signal == "SELL"
        and active_news_bias == "BULLISH_GOLD"
        and day_bias == "SELL"
        and h4_bias == "SELL"
        and structure in ["HH", "BEARISH"]
        and (
            near_m15_high
            or rejection == "UPPER_WICK"
            or upper_wick_strong
        )
        and rsi < 68
    )

    # MAX DIP BUY v11:
    # Più selettivo della v10.
    # Richiede almeno 2 conferme tra:
    # - vicino a minimo M15
    # - lower wick/rejection
    # - livello psicologico
    # - RSI basso
    # - candela bullish
    dip_confirmations = 0

    if near_m15_low:
        dip_confirmations += 1

    if rejection == "LOWER_WICK" or lower_wick_strong:
        dip_confirmations += 1

    if near_psych_level:
        dip_confirmations += 1

    if rsi < 42:
        dip_confirmations += 1

    if candle_dir == "BULL":
        dip_confirmations += 1

    # MAX RECOVERY BUY v12:
    # Compra il recupero dopo che il mercato ha già fatto una grande discesa.
    # È diverso dal MAX_DIP_BUY:
    # - MAX_DIP_BUY compra il fondo.
    # - MAX_RECOVERY_BUY compra il ritorno sopra zona chiave dopo il fondo.
    recovery_confirmations = 0

    if len(recent_deep_sells) >= RECOVERY_BUY_DEEP_SELL_COUNT:
        recovery_confirmations += 1

    if recovery_buy_signal or recent_low_touch:
        recovery_confirmations += 1

    if near_psych_level:
        recovery_confirmations += 1

    if candle_dir == "BULL":
        recovery_confirmations += 1

    if close_above_ema20:
        recovery_confirmations += 1

    if structure in ["LL", "BULLISH", "HL"]:
        recovery_confirmations += 1

    max_recovery_buy = (
        RECOVERY_BUY_ENABLED
        and signal == "BUY"
        and active_news_bias == "BULLISH_GOLD"
        and len(recent_deep_sells) >= RECOVERY_BUY_DEEP_SELL_COUNT
        and structure in ["LL", "BULLISH", "HL"]
        and rsi > 34
        and rsi < 70
        and recovery_confirmations >= RECOVERY_BUY_MIN_CONFIRMATIONS
        and (
            recovery_buy_signal
            or close_above_ema20
            or candle_dir == "BULL"
            or near_psych_level
        )
    )

    max_dip_buy = (
        signal == "BUY"
        and active_news_bias == "BULLISH_GOLD"
        and structure in ["LL", "BULLISH"]
        and rsi > 26
        and rsi < 62
        and dip_confirmations >= 2
    )

    max_dip_sell = (
        signal == "SELL"
        and active_news_bias == "BEARISH_GOLD"
        and structure in ["HH", "BEARISH"]
        and (
            rejection == "UPPER_WICK"
            or upper_wick_strong
            or near_m15_high
        )
        and rsi < 70
        and rsi > 38
    )

    if max_recovery_buy:
        setup_type = "MAX_RECOVERY_BUY"
        score += 9
        reasons.append(f"MAX RECOVERY BUY: recupero dopo grande discesa ({recovery_confirmations} conferme)")

        if len(recent_deep_sells) >= RECOVERY_BUY_DEEP_SELL_COUNT:
            score += 2
            reasons.append(f"Contesto post SELL profondi: {len(recent_deep_sells)} trade almeno TP{RECOVERY_BUY_TP_LEVEL}")

        if near_psych_level:
            score += 3
            reasons.append(f"Recupero vicino livello psicologico {nearest_psych}")

    elif max_dip_buy:
        setup_type = "MAX_DIP_BUY"
        score += 8
        reasons.append(f"MAX DIP BUY: fondo confermato ({dip_confirmations} conferme)")

        if near_psych_level:
            score += 3
            reasons.append(f"Vicino livello psicologico {nearest_psych}")

    elif max_fade_sell:
        setup_type = "MAX_FADE_SELL"
        score += 5
        reasons.append("MAX FADE SELL: vendita su rimbalzo alto con rejection")

    elif reversal_buy:
        setup_type = "REVERSAL_BUY"
        score += 5
        reasons.append("Setup REVERSAL BUY stile Max")

    elif reversal_sell:
        setup_type = "REVERSAL_SELL"
        score += 5
        reasons.append("Setup REVERSAL SELL stile Max")

    elif max_dip_sell:
        setup_type = "MAX_DIP_SELL"
        score += 5
        reasons.append("MAX DIP SELL: vendita da eccesso bearish")

    # =========================
    # BIAS MANUALE
    # =========================

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

    # =========================
    # NEWS
    # =========================

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
            score -= 2
            reasons.append("BUY contro news bearish gold")

    if EVENT_RISK == "HIGH":
        score -= 2
        reasons.append("Evento macro ad alto rischio")

    # =========================
    # BUY
    # =========================

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
            if max_dip_buy or max_recovery_buy:
                score -= 1
                reasons.append("BUY da fondo/recupero contro Daily SELL accettato")
            elif reversal_buy:
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
            if max_dip_buy or max_recovery_buy:
                reasons.append("Candela rossa accettata: exhaustion/recovery BUY")
            else:
                score -= 2
                reasons.append("Candela rossa contro BUY")

        if rejection == "LOWER_WICK":
            score += 2
            reasons.append("Rejection bullish")

        if rejection == "UPPER_WICK":
            if max_dip_buy or max_recovery_buy:
                score -= 1
                reasons.append("Wick alta ma BUY speciale ancora valido")
            else:
                score -= 3
                reasons.append("Wick alta")

        if ema20_slope == "UP":
            score += 1
            reasons.append("EMA20 UP")

        if ema50_slope == "UP":
            score += 1
            reasons.append("EMA50 UP")

        if ema20_slope == "DOWN":
            if max_dip_buy or max_recovery_buy:
                score -= 1
                reasons.append("EMA20 DOWN ma BUY speciale")
            elif reversal_buy:
                score -= 1
                reasons.append("EMA20 DOWN ma reversal BUY")
            else:
                score -= 4
                reasons.append("EMA20 DOWN")

        if ema50_slope == "DOWN":
            if max_dip_buy or max_recovery_buy:
                score -= 1
                reasons.append("EMA50 DOWN ma BUY speciale")
            elif reversal_buy:
                score -= 1
                reasons.append("EMA50 DOWN ma reversal BUY")
            else:
                score -= 2
                reasons.append("EMA50 DOWN")

        if volume_spike and candle_dir == "BEAR":
            if max_dip_buy or max_recovery_buy:
                score -= 1
                reasons.append("Volume bearish ma BUY speciale ancora valido")
            else:
                score -= 3
                reasons.append("Volume spike bearish")

    # =========================
    # SELL
    # =========================

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
# SL COOLDOWN v10
# =========================

def get_recent_direct_losses(signal, symbol):
    now = now_ts()
    symbol = str(symbol).upper()
    signal = str(signal).upper()

    losses = []

    for trade in OPEN_TRADES:
        if str(trade.get("symbol", "")).upper() != symbol:
            continue

        if str(trade.get("signal", "")).upper() != signal:
            continue

        if trade.get("status") != "LOSS":
            continue

        # SL diretto = loss prima di TP1
        if int(trade.get("highest_tp", 0)) > 0:
            continue

        closed = trade.get("closed") or trade.get("created") or 0

        if now - closed <= SL_COOLDOWN_LOOKBACK_SECONDS:
            losses.append(trade)

    return sorted(losses, key=lambda x: x.get("closed") or x.get("created") or 0, reverse=True)


def should_block_by_sl_cooldown(signal, symbol):
    if not SL_COOLDOWN_ENABLED:
        return False, []

    signal = str(signal).upper()

    if signal != SL_COOLDOWN_SIGNAL:
        return False, []

    losses = get_recent_direct_losses(signal, symbol)

    if len(losses) < SL_COOLDOWN_LOSSES:
        return False, losses

    latest_loss = losses[0].get("closed") or losses[0].get("created") or 0

    if now_ts() - latest_loss <= SL_COOLDOWN_SECONDS:
        return True, losses

    return False, losses


# =========================
# SELL EXHAUSTION v11
# =========================

def get_recent_tp_trades(signal, symbol, min_tp=8, lookback_seconds=7200):
    now = now_ts()
    symbol = str(symbol).upper()
    signal = str(signal).upper()

    hits = []

    for trade in OPEN_TRADES:
        if str(trade.get("symbol", "")).upper() != symbol:
            continue

        if str(trade.get("signal", "")).upper() != signal:
            continue

        if int(trade.get("highest_tp", 0)) < min_tp:
            continue

        event_time = (
            trade.get(f"tp{min_tp}_time")
            or trade.get("last_tp_time")
            or trade.get("closed")
            or trade.get("created")
            or 0
        )

        if now - event_time <= lookback_seconds:
            hits.append(trade)

    return sorted(
        hits,
        key=lambda x: x.get(f"tp{min_tp}_time") or x.get("last_tp_time") or x.get("created") or 0,
        reverse=True
    )


def should_block_by_sell_exhaustion(signal, symbol, setup_type, score):
    if not SELL_EXHAUSTION_ENABLED:
        return False, []

    if str(signal).upper() != "SELL":
        return False, []

    recent_tp8_sells = get_recent_tp_trades(
        "SELL",
        symbol,
        min_tp=SELL_EXHAUSTION_TP_LEVEL,
        lookback_seconds=SELL_EXHAUSTION_LOOKBACK_SECONDS
    )

    if len(recent_tp8_sells) < SELL_EXHAUSTION_COUNT:
        return False, recent_tp8_sells

    # Dopo tanti TP8 SELL:
    # - blocca SELL NORMAL
    # - permette MAX_FADE_SELL solo se molto forte
    if setup_type == "NORMAL":
        return True, recent_tp8_sells

    if setup_type == "MAX_FADE_SELL" and score < SELL_EXHAUSTION_MAX_FADE_MIN_SCORE:
        return True, recent_tp8_sells

    return False, recent_tp8_sells




# =========================
# BUY FATIGUE + CONFLICT RESOLVER v14
# =========================

def get_recent_direct_losses_custom(signal, symbol, lookback_seconds):
    now = now_ts()
    symbol = str(symbol).upper()
    signal = str(signal).upper()

    losses = []

    for trade in OPEN_TRADES:
        if str(trade.get("symbol", "")).upper() != symbol:
            continue

        if str(trade.get("signal", "")).upper() != signal:
            continue

        if trade.get("status") != "LOSS":
            continue

        # SL diretto = loss prima di TP1
        if int(trade.get("highest_tp", 0)) > 0:
            continue

        closed = trade.get("closed") or trade.get("created") or 0

        if now - closed <= lookback_seconds:
            losses.append(trade)

    return sorted(losses, key=lambda x: x.get("closed") or x.get("created") or 0, reverse=True)


def get_recent_active_opposite_trades(signal, symbol, window_seconds):
    now = now_ts()
    symbol = str(symbol).upper()
    signal = str(signal).upper()
    opposite = "SELL" if signal == "BUY" else "BUY"

    trades = []

    for trade in OPEN_TRADES:
        if str(trade.get("symbol", "")).upper() != symbol:
            continue

        if str(trade.get("signal", "")).upper() != opposite:
            continue

        if trade.get("status") not in ["PENDING", "OPEN"]:
            continue

        created = trade.get("created") or 0

        if now - created <= window_seconds:
            trades.append(trade)

    return sorted(trades, key=lambda x: x.get("created") or 0, reverse=True)


def directional_dominance_score(signal, setup_type, score, active_news_bias):
    signal = str(signal).upper()
    setup_type = str(setup_type).upper()
    active_news_bias = str(active_news_bias).upper()

    dominance = int(score)
    dominance += SETUP_WEIGHTS.get(setup_type, 1) * 2

    # Se le news sono bullish gold, il BUY ha una priorità naturale.
    # Il SELL è permesso, ma deve essere davvero superiore.
    if active_news_bias == "BULLISH_GOLD":
        if signal == "BUY":
            dominance += 3
        elif signal == "SELL":
            dominance -= 2

    # Se in futuro userai bearish gold, questa parte è già pronta.
    if active_news_bias == "BEARISH_GOLD":
        if signal == "SELL":
            dominance += 3
        elif signal == "BUY":
            dominance -= 2

    return dominance


def should_block_by_conflict_resolver(signal, symbol, setup_type, score, active_news_bias):
    if not CONFLICT_RESOLVER_ENABLED:
        return False, None, []

    recent_opposites = get_recent_active_opposite_trades(
        signal,
        symbol,
        CONFLICT_WINDOW_SECONDS
    )

    if not recent_opposites:
        return False, None, []

    current_dom = directional_dominance_score(signal, setup_type, score, active_news_bias)

    best_opposite = None
    best_opposite_dom = -9999

    for trade in recent_opposites:
        opp_signal = trade.get("signal", "")
        opp_setup = trade.get("setup_type", "NORMAL")
        opp_score = int(trade.get("score", 0))
        opp_dom = directional_dominance_score(opp_signal, opp_setup, opp_score, active_news_bias)

        # Se il trade opposto ha già TP1+, lo considero più forte ancora.
        if int(trade.get("highest_tp", 0)) >= 1:
            opp_dom += 4

        if opp_dom > best_opposite_dom:
            best_opposite_dom = opp_dom
            best_opposite = trade

    # Se il nuovo segnale non domina nettamente, lo blocco.
    # Questo evita BUY e SELL quasi insieme nella stessa zona.
    if current_dom < best_opposite_dom + CONFLICT_DOMINANCE_MARGIN:
        return True, best_opposite, recent_opposites

    return False, best_opposite, recent_opposites


def should_block_by_buy_sl_cooldown(signal, symbol):
    if not BUY_SL_COOLDOWN_ENABLED:
        return False, []

    if str(signal).upper() != "BUY":
        return False, []

    losses = get_recent_direct_losses_custom(
        "BUY",
        symbol,
        BUY_SL_COOLDOWN_LOOKBACK_SECONDS
    )

    if len(losses) < BUY_SL_COOLDOWN_LOSSES:
        return False, losses

    latest_loss = losses[0].get("closed") or losses[0].get("created") or 0

    if now_ts() - latest_loss <= BUY_SL_COOLDOWN_SECONDS:
        return True, losses

    return False, losses


def should_block_by_buy_fatigue(signal, symbol, setup_type, score, data):
    if not BUY_FATIGUE_ENABLED:
        return False, [], "Buy Fatigue disattivato"

    if str(signal).upper() != "BUY":
        return False, [], "Non è BUY"

    recent_big_buys = get_recent_tp_trades(
        "BUY",
        symbol,
        min_tp=BUY_FATIGUE_TP_LEVEL,
        lookback_seconds=BUY_FATIGUE_LOOKBACK_SECONDS
    )

    if len(recent_big_buys) < BUY_FATIGUE_COUNT:
        return False, recent_big_buys, "Pochi BUY profondi recenti"

    setup_type = str(setup_type).upper()
    price = get_price_from_data(data)
    near_psych_level, nearest_psych, psych_distance = psych_info(price)

    if data.get("near_psych_level") is not None:
        near_psych_level = to_bool(data.get("near_psych_level"))

    near_m15_low = to_bool(data.get("near_m15_low", "false"))
    recent_low_touch = to_bool(data.get("recent_low_touch", "false"))
    recovery_buy_signal = to_bool(data.get("recovery_buy_signal", "false"))

    # Dopo troppi BUY già pagati, accetto nuovi BUY solo se sono di qualità molto alta
    # e arrivano da una zona ragionevole, non inseguendo in alto.
    high_quality_allowed = (
        setup_type in BUY_FATIGUE_ALLOW_SETUPS
        and int(score) >= BUY_FATIGUE_ALLOW_SCORE
        and (
            near_psych_level
            or near_m15_low
            or recent_low_touch
            or recovery_buy_signal
        )
    )

    if high_quality_allowed:
        return False, recent_big_buys, "BUY fatigue attiva ma setup speciale ancora valido"

    return True, recent_big_buys, "Troppi BUY profondi recenti: rischio inseguimento onda già matura"


def buy_fatigue_status_text(recent_big_buys):
    if not recent_big_buys:
        return "Nessun BUY profondo recente"

    lines = [
        f"BUY recenti arrivati almeno a TP{BUY_FATIGUE_TP_LEVEL}: {len(recent_big_buys)}",
        f"Soglia: {BUY_FATIGUE_COUNT}",
        f"Lookback secondi: {BUY_FATIGUE_LOOKBACK_SECONDS}",
        ""
    ]

    for trade in recent_big_buys[:5]:
        lines.append(
            f"- ID {trade.get('id')} | {trade.get('setup_type')} | "
            f"TP{trade.get('highest_tp', 0)} | status {trade.get('status')}"
        )

    return "\n".join(lines)



# =========================
# RECOVERY LOCK v13
# =========================

def _trade_event_time(trade, tp_level):
    return (
        trade.get(f"tp{tp_level}_time")
        or trade.get("last_tp_time")
        or trade.get("closed")
        or trade.get("created")
        or 0
    )


def get_open_successful_buy_trades(symbol):
    symbol = str(symbol).upper()
    active_buys = []

    if not OPPOSITE_TRADE_LOCK_ENABLED:
        return active_buys

    for trade in OPEN_TRADES:
        if str(trade.get("symbol", "")).upper() != symbol:
            continue

        if str(trade.get("signal", "")).upper() != "BUY":
            continue

        if trade.get("status") != "OPEN":
            continue

        setup = trade.get("setup_type", "NORMAL")

        if setup not in RECOVERY_LOCK_BUY_SETUPS:
            continue

        if int(trade.get("highest_tp", 0)) < OPPOSITE_TRADE_LOCK_MIN_TP:
            continue

        active_buys.append(trade)

    return sorted(active_buys, key=lambda x: x.get("last_tp_time") or x.get("created") or 0, reverse=True)


def get_recovery_lock_context(symbol):
    if not RECOVERY_LOCK_ENABLED:
        return {
            "active": False,
            "level": "NONE",
            "reason": "Recovery Lock disattivato",
            "trades": [],
            "best_trade": None
        }

    now = now_ts()
    symbol = str(symbol).upper()

    active_successful_buys = get_open_successful_buy_trades(symbol)

    if active_successful_buys:
        best = active_successful_buys[0]
        return {
            "active": True,
            "level": "ACTIVE_BUY_PROTECTION",
            "reason": f"BUY speciale ancora OPEN con TP{best.get('highest_tp', 0)} già preso",
            "trades": active_successful_buys,
            "best_trade": best
        }

    runner_hits = []
    strong_hits = []
    normal_hits = []

    for trade in OPEN_TRADES:
        if str(trade.get("symbol", "")).upper() != symbol:
            continue

        if str(trade.get("signal", "")).upper() != "BUY":
            continue

        setup = trade.get("setup_type", "NORMAL")

        if setup not in RECOVERY_LOCK_BUY_SETUPS:
            continue

        highest_tp = int(trade.get("highest_tp", 0))

        if highest_tp >= RECOVERY_LOCK_RUNNER_LEVEL or trade.get("runner"):
            event_time = _trade_event_time(trade, RECOVERY_LOCK_RUNNER_LEVEL)

            if now - event_time <= RECOVERY_LOCK_RUNNER_SECONDS:
                runner_hits.append(trade)

        elif highest_tp >= RECOVERY_LOCK_TP5_LEVEL:
            event_time = _trade_event_time(trade, RECOVERY_LOCK_TP5_LEVEL)

            if now - event_time <= RECOVERY_LOCK_TP5_SECONDS:
                strong_hits.append(trade)

        elif highest_tp >= RECOVERY_LOCK_TP3_LEVEL:
            event_time = _trade_event_time(trade, RECOVERY_LOCK_TP3_LEVEL)

            if now - event_time <= RECOVERY_LOCK_TP3_SECONDS:
                normal_hits.append(trade)

    if runner_hits:
        best = sorted(runner_hits, key=lambda x: x.get("last_tp_time") or x.get("created") or 0, reverse=True)[0]
        return {
            "active": True,
            "level": "BULL_RECOVERY_RUNNER",
            "reason": f"BUY speciale arrivato almeno a TP{RECOVERY_LOCK_RUNNER_LEVEL}/Runner",
            "trades": runner_hits,
            "best_trade": best
        }

    if strong_hits:
        best = sorted(strong_hits, key=lambda x: x.get("last_tp_time") or x.get("created") or 0, reverse=True)[0]
        return {
            "active": True,
            "level": "STRONG_RECOVERY",
            "reason": f"BUY speciale arrivato almeno a TP{RECOVERY_LOCK_TP5_LEVEL}",
            "trades": strong_hits,
            "best_trade": best
        }

    if normal_hits:
        best = sorted(normal_hits, key=lambda x: x.get("last_tp_time") or x.get("created") or 0, reverse=True)[0]
        return {
            "active": True,
            "level": "RECOVERY_TP3",
            "reason": f"BUY speciale arrivato almeno a TP{RECOVERY_LOCK_TP3_LEVEL}",
            "trades": normal_hits,
            "best_trade": best
        }

    return {
        "active": False,
        "level": "NONE",
        "reason": "Nessun BUY Recovery/Dip recente abbastanza forte",
        "trades": [],
        "best_trade": None
    }


def should_block_sell_by_recovery_lock(signal, symbol, setup_type, score):
    if not RECOVERY_LOCK_ENABLED:
        return False, get_recovery_lock_context(symbol)

    if str(signal).upper() != "SELL":
        return False, get_recovery_lock_context(symbol)

    ctx = get_recovery_lock_context(symbol)

    if not ctx["active"]:
        return False, ctx

    setup_type = str(setup_type).upper()

    # Durante Recovery Lock i SELL NORMAL non devono combattere il recupero.
    if setup_type == "NORMAL":
        return True, ctx

    # MAX_FADE_SELL può passare solo se è davvero fortissimo.
    if setup_type == "MAX_FADE_SELL" and int(score) < RECOVERY_LOCK_MAX_FADE_MIN_SCORE:
        return True, ctx

    return False, ctx


def recovery_lock_status_text(ctx):
    if not ctx or not ctx.get("active"):
        return "Recovery Lock non attivo"

    best = ctx.get("best_trade") or {}

    return (
        f"Livello lock: {ctx.get('level')}\n"
        f"Motivo: {ctx.get('reason')}\n"
        f"Trade BUY riferimento: {best.get('id', 'N/D')}\n"
        f"Setup BUY: {best.get('setup_type', 'N/D')}\n"
        f"Highest TP BUY: {best.get('highest_tp', 0)}\n"
        f"Status BUY: {best.get('status', 'N/D')}"
    )



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
        "runner": False,
        "runner_notified": False,
        "created": now_ts(),
        "created_local": local_datetime().strftime("%Y-%m-%d %H:%M:%S"),
        "activated": None,
        "activated_local": None,
        "closed": None,
        "closed_local": None,
        "last_tp_time": None,
        "last_tp_local": None
    }

    OPEN_TRADES.append(trade)
    save_trades()

    return trade


def close_trade(trade, status):
    trade["status"] = status
    trade["closed"] = now_ts()
    trade["closed_local"] = local_datetime().strftime("%Y-%m-%d %H:%M:%S")


def runner_message(trade, tp_level, tp_value):
    signal = trade.get("signal")
    trade_id = trade.get("id")
    setup = trade.get("setup_type", "NORMAL")

    return (
        f"🚀 RUNNER MODE ATTIVO\n\n"
        f"Trade #{trade_id} {signal}\n"
        f"Setup: {setup}\n"
        f"TP{tp_level} raggiunto: {tp_value}\n\n"
        f"Lettura v14:\n"
        f"Il movimento ha superato tutti i target standard.\n"
        f"Possibile giornata direzionale stile Max.\n"
        f"Valuta di lasciare una parte in RUNNER / OPEN invece di chiudere tutto."
    )


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

        # =========================
        # PENDING ENTRY
        # =========================

        if trade.get("status") == "PENDING":

            if signal == "BUY":
                entered = low <= trade["entry_high"] and high >= trade["entry_low"]

                if entered:
                    trade["status"] = "OPEN"
                    trade["entered"] = True
                    trade["activated"] = now_ts()
                    trade["activated_local"] = local_datetime().strftime("%Y-%m-%d %H:%M:%S")
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
                    trade["activated_local"] = local_datetime().strftime("%Y-%m-%d %H:%M:%S")
                    changed = True

                    updates.append(
                        f"🎯 Trade #{trade_id} SELL ATTIVATO\n"
                        f"Setup: {trade.get('setup_type', 'NORMAL')}\n"
                        f"Zona: {trade['entry_low']} - {trade['entry_high']}"
                    )
                else:
                    continue

        # =========================
        # BUY MANAGEMENT
        # =========================

        if signal == "BUY":

            if not trade.get("be") and low <= trade["sl"]:
                close_trade(trade, "LOSS")
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
                    trade["last_tp_time"] = now_ts()
                    trade["last_tp_local"] = local_datetime().strftime("%Y-%m-%d %H:%M:%S")
                    trade[f"tp{i}_time"] = trade["last_tp_time"]
                    trade[f"tp{i}_local"] = trade["last_tp_local"]
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

                    if RUNNER_MODE_ENABLED and i >= RUNNER_TP_LEVEL and not trade.get("runner_notified"):
                        trade["runner"] = True
                        trade["runner_notified"] = True
                        updates.append(runner_message(trade, i, tp))

            if trade.get("be") and be_was_already_active and low <= trade["entry_low"]:
                close_trade(trade, "BE")
                changed = True

                runner_note = " con RUNNER attivo" if trade.get("runner") else ""

                updates.append(
                    f"🟡 Trade #{trade_id} BUY chiuso a BE dopo TP{trade.get('highest_tp', 0)}{runner_note}"
                )

        # =========================
        # SELL MANAGEMENT
        # =========================

        if signal == "SELL":

            if not trade.get("be") and high >= trade["sl"]:
                close_trade(trade, "LOSS")
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
                    trade["last_tp_time"] = now_ts()
                    trade["last_tp_local"] = local_datetime().strftime("%Y-%m-%d %H:%M:%S")
                    trade[f"tp{i}_time"] = trade["last_tp_time"]
                    trade[f"tp{i}_local"] = trade["last_tp_local"]
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

                    if RUNNER_MODE_ENABLED and i >= RUNNER_TP_LEVEL and not trade.get("runner_notified"):
                        trade["runner"] = True
                        trade["runner_notified"] = True
                        updates.append(runner_message(trade, i, tp))

            if trade.get("be") and be_was_already_active and high >= trade["entry_high"]:
                close_trade(trade, "BE")
                changed = True

                runner_note = " con RUNNER attivo" if trade.get("runner") else ""

                updates.append(
                    f"🟡 Trade #{trade_id} SELL chiuso a BE dopo TP{trade.get('highest_tp', 0)}{runner_note}"
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
    direct_losses = sum(1 for t in today_trades if t.get("status") == "LOSS" and int(t.get("highest_tp", 0)) == 0)
    be = sum(1 for t in today_trades if t.get("status") == "BE")
    runners = sum(1 for t in today_trades if t.get("runner"))

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
                "tp8": 0,
                "runner": 0,
                "loss": 0,
                "direct_loss": 0,
                "be": 0,
                "active": 0
            }

        by_setup[setup]["total"] += 1

        highest_tp = int(trade.get("highest_tp", 0))

        if highest_tp >= 1:
            by_setup[setup]["tp1"] += 1

        if highest_tp >= 3:
            by_setup[setup]["tp3"] += 1

        if highest_tp >= 5:
            by_setup[setup]["tp5"] += 1

        if highest_tp >= 8:
            by_setup[setup]["tp8"] += 1

        if trade.get("runner"):
            by_setup[setup]["runner"] += 1

        if trade.get("status") == "LOSS":
            by_setup[setup]["loss"] += 1

            if highest_tp == 0:
                by_setup[setup]["direct_loss"] += 1

        if trade.get("status") == "BE":
            by_setup[setup]["be"] += 1

        if trade.get("status") in ["PENDING", "OPEN"]:
            by_setup[setup]["active"] += 1

    tp1_rate = round((tp1 / total) * 100, 2) if total else 0
    direct_loss_rate = round((direct_losses / total) * 100, 2) if total else 0

    return {
        "version": VERSION,
        "date": today,
        "timezone": USER_TIMEZONE,
        "total_today": total,
        "active_today": active,
        "losses_today": losses,
        "direct_losses_today": direct_losses,
        "be_today": be,
        "runners_today": runners,
        "tp1_hit_today": tp1,
        "tp3_hit_today": tp3,
        "tp5_hit_today": tp5,
        "tp8_hit_today": tp8,
        "tp1_rate_percent": tp1_rate,
        "direct_loss_rate_percent": direct_loss_rate,
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
        f"SL totali: {s['losses_today']}",
        f"SL diretti: {s['direct_losses_today']} ({s['direct_loss_rate_percent']}%)",
        f"BE: {s['be_today']}",
        f"Runner: {s['runners_today']}",
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
            f"TP3 {data['tp3']}, TP5 {data['tp5']}, TP8 {data['tp8']}, "
            f"Runner {data['runner']}, SL {data['loss']}, SL diretti {data['direct_loss']}, BE {data['be']}"
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

    # =========================
    # SCORE BLOCK
    # =========================

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

    # =========================
    # SL COOLDOWN BLOCK
    # =========================

    block_sl_cooldown, recent_losses = should_block_by_sl_cooldown(signal, symbol)

    if block_sl_cooldown:
        last_loss = recent_losses[0]
        last_loss_time = last_loss.get("closed_local") or "N/D"

        text = f"""🛑 SELL BLOCCATO {VERSION}

Motivo: stop temporaneo dopo SL diretti

Segnale: {signal}
Symbol: {symbol}
Prezzo: {price}
Setup: {setup_type}
Score finale: {score}

SL diretti recenti: {len(recent_losses)}
Soglia SL diretti: {SL_COOLDOWN_LOSSES}
Lookback secondi: {SL_COOLDOWN_LOOKBACK_SECONDS}
Cooldown secondi: {SL_COOLDOWN_SECONDS}
Ultimo SL: {last_loss_time}

Azione:
Nuovi SELL bloccati temporaneamente.
Il bot può ancora accettare BUY da fondo / reversal.
"""
        send_telegram(text)

        return jsonify({
            "status": "blocked_sl_cooldown",
            "score": score,
            "setup_type": setup_type,
            "recent_direct_losses": len(recent_losses)
        })

    # =========================
    # BUY SL COOLDOWN BLOCK v14
    # =========================

    block_buy_sl_cooldown, recent_buy_losses = should_block_by_buy_sl_cooldown(signal, symbol)

    if block_buy_sl_cooldown:
        last_loss = recent_buy_losses[0]
        last_loss_time = last_loss.get("closed_local") or "N/D"

        text = f"""🛑 BUY BLOCCATO {VERSION}

Motivo: stop temporaneo dopo SL diretti BUY

Segnale: {signal}
Symbol: {symbol}
Prezzo: {price}
Setup: {setup_type}
Score finale: {score}

SL BUY diretti recenti: {len(recent_buy_losses)}
Soglia SL diretti BUY: {BUY_SL_COOLDOWN_LOSSES}
Lookback secondi: {BUY_SL_COOLDOWN_LOOKBACK_SECONDS}
Cooldown secondi: {BUY_SL_COOLDOWN_SECONDS}
Ultimo SL BUY: {last_loss_time}

Azione:
Nuovi BUY bloccati temporaneamente.
Il bot evita di insistere sul recupero se il mercato ha appena negato più BUY.
"""
        send_telegram(text)

        return jsonify({
            "status": "blocked_buy_sl_cooldown",
            "score": score,
            "setup_type": setup_type,
            "recent_buy_direct_losses": len(recent_buy_losses)
        })


    # =========================
    # BUY FATIGUE BLOCK v14
    # =========================

    block_buy_fatigue, recent_big_buys, fatigue_reason = should_block_by_buy_fatigue(
        signal,
        symbol,
        setup_type,
        score,
        data
    )

    if block_buy_fatigue:
        text = f"""🟢⚠️ BUY BLOCCATO {VERSION}

Motivo: Buy Fatigue / onda già matura

Segnale: {signal}
Symbol: {symbol}
Prezzo: {price}
Setup: {setup_type}
Score finale: {score}

{buy_fatigue_status_text(recent_big_buys)}

Azione:
Il bot non insegue nuovi BUY dopo che l'onda ha già pagato molto.
Nuovi BUY ammessi solo se setup speciale, score >= {BUY_FATIGUE_ALLOW_SCORE}
e arrivo da zona bassa / livello psicologico / recovery confermata.
"""
        send_telegram(text)

        return jsonify({
            "status": "blocked_buy_fatigue",
            "score": score,
            "setup_type": setup_type,
            "recent_big_buys": len(recent_big_buys),
            "fatigue_reason": fatigue_reason
        })


    # =========================
    # CONFLICT RESOLVER BLOCK v14
    # =========================

    block_conflict, opposite_trade, recent_opposites = should_block_by_conflict_resolver(
        signal,
        symbol,
        setup_type,
        score,
        active_news_bias
    )

    if block_conflict:
        opp_id = opposite_trade.get("id") if opposite_trade else "N/D"
        opp_signal = opposite_trade.get("signal") if opposite_trade else "N/D"
        opp_setup = opposite_trade.get("setup_type") if opposite_trade else "N/D"
        opp_score = opposite_trade.get("score") if opposite_trade else "N/D"
        opp_status = opposite_trade.get("status") if opposite_trade else "N/D"
        opp_tp = opposite_trade.get("highest_tp", 0) if opposite_trade else 0

        text = f"""⚖️ SEGNALE BLOCCATO {VERSION}

Motivo: Conflict Resolver

Nuovo segnale:
- Segnale: {signal}
- Symbol: {symbol}
- Prezzo: {price}
- Setup: {setup_type}
- Score: {score}

Trade opposto recente già attivo:
- ID: {opp_id}
- Segnale: {opp_signal}
- Setup: {opp_setup}
- Score: {opp_score}
- Status: {opp_status}
- Highest TP: {opp_tp}

Finestra conflitto secondi: {CONFLICT_WINDOW_SECONDS}
Margine dominanza richiesto: {CONFLICT_DOMINANCE_MARGIN}

Azione:
Il bot evita di aprire BUY e SELL quasi insieme.
Passa solo la direzione dominante.
"""
        send_telegram(text)

        return jsonify({
            "status": "blocked_conflict_resolver",
            "score": score,
            "setup_type": setup_type,
            "opposite_trade_id": opp_id,
            "opposite_signal": opp_signal
        })



    # =========================
    # RECOVERY LOCK BLOCK v13
    # =========================

    block_recovery_lock, recovery_ctx = should_block_sell_by_recovery_lock(signal, symbol, setup_type, score)

    if block_recovery_lock:
        text = f"""🟢🔒 SELL BLOCCATO {VERSION}

Motivo: Recovery Lock attivo

Segnale: {signal}
Symbol: {symbol}
Prezzo: {price}
Setup: {setup_type}
Score finale: {score}

{recovery_lock_status_text(recovery_ctx)}

Azione:
Il bot non combatte un BUY Recovery/Dip che sta funzionando.
SELL NORMAL bloccati.
MAX_FADE_SELL consentiti solo se score >= {RECOVERY_LOCK_MAX_FADE_MIN_SCORE} e setup davvero forte.
"""
        send_telegram(text)

        return jsonify({
            "status": "blocked_recovery_lock",
            "score": score,
            "setup_type": setup_type,
            "recovery_lock_level": recovery_ctx.get("level"),
            "recovery_lock_reason": recovery_ctx.get("reason")
        })


    # =========================
    # SELL EXHAUSTION BLOCK v11
    # =========================

    block_exhaustion, recent_tp8_sells = should_block_by_sell_exhaustion(signal, symbol, setup_type, score)

    if block_exhaustion:
        text = f"""🧯 SELL BLOCCATO {VERSION}

Motivo: SELL exhaustion dopo troppi TP profondi

Segnale: {signal}
Symbol: {symbol}
Prezzo: {price}
Setup: {setup_type}
Score finale: {score}

SELL recenti arrivati almeno a TP{SELL_EXHAUSTION_TP_LEVEL}: {len(recent_tp8_sells)}
Soglia: {SELL_EXHAUSTION_COUNT}
Lookback secondi: {SELL_EXHAUSTION_LOOKBACK_SECONDS}

Azione:
Non inseguo nuovi SELL bassi dopo una discesa già molto pagata.
Accetto solo MAX_FADE_SELL molto forti da rimbalzo alto.
Favorisco MAX_DIP_BUY se il fondo viene confermato.
"""
        send_telegram(text)

        return jsonify({
            "status": "blocked_sell_exhaustion",
            "score": score,
            "setup_type": setup_type,
            "recent_tp_sells": len(recent_tp8_sells)
        })

    # =========================
    # DUPLICATE BLOCK
    # =========================

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

    # =========================
    # SAVE TRADE
    # =========================

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
