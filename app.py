import os
import time
import json
import math
import html
import requests
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from flask import Flask, request, jsonify

app = Flask(__name__)

# =========================
# CONFIG
# =========================

VERSION = "v43 Asian Session Daily Thesis + Fast Clean 2 Points"

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

# v40: chiarezza Telegram.
# La logica operativa della v39 resta invariata: cambia soprattutto come vengono mostrati
# i messaggi, per distinguere OPERAZIONI UFFICIALI da TESI/AVVISI e DEBUG.
MESSAGE_LABELS_ENABLED = os.getenv("MESSAGE_LABELS_ENABLED", "TRUE").upper() == "TRUE"

# SMART = invia solo blocchi utili come tesi/rischio; ALL = invia tutto; OFF = nasconde tutti i blocchi.
BLOCKED_SIGNAL_VISIBILITY = os.getenv("BLOCKED_SIGNAL_VISIBILITY", "SMART").upper()

# Di default riduco rumore: duplicati e low-score banali non arrivano su Telegram.
DUPLICATE_BLOCK_TELEGRAM_ENABLED = os.getenv("DUPLICATE_BLOCK_TELEGRAM_ENABLED", "FALSE").upper() == "TRUE"
LOW_SCORE_DEBUG_TELEGRAM_ENABLED = os.getenv("LOW_SCORE_DEBUG_TELEGRAM_ENABLED", "FALSE").upper() == "TRUE"
THESIS_BLOCK_TELEGRAM_ENABLED = os.getenv("THESIS_BLOCK_TELEGRAM_ENABLED", "TRUE").upper() == "TRUE"
RISK_BLOCK_TELEGRAM_ENABLED = os.getenv("RISK_BLOCK_TELEGRAM_ENABLED", "TRUE").upper() == "TRUE"
FAST_BLOCK_TELEGRAM_ENABLED = os.getenv("FAST_BLOCK_TELEGRAM_ENABLED", "FALSE").upper() == "TRUE"

OFFICIAL_TRADE_LABEL_ENABLED = os.getenv("OFFICIAL_TRADE_LABEL_ENABLED", "TRUE").upper() == "TRUE"
THESIS_NOT_TRADE_WARNING_ENABLED = os.getenv("THESIS_NOT_TRADE_WARNING_ENABLED", "TRUE").upper() == "TRUE"

# v41: Max Discipline + One Campaign Mode.
# Obiettivo: meno operazioni ufficiali, meno layering automatico, più gestione stile Max.
# Tutte le variabili hanno default nel codice: su Render NON devi aggiungere nulla.
MAX_DISCIPLINE_ENABLED = os.getenv("MAX_DISCIPLINE_ENABLED", "TRUE").upper() == "TRUE"
MAX_DISCIPLINE_WINDOW_SECONDS = int(os.getenv("MAX_DISCIPLINE_WINDOW_SECONDS", "3600"))
MAX_DISCIPLINE_MAX_OFFICIAL_PER_DIRECTION = int(os.getenv("MAX_DISCIPLINE_MAX_OFFICIAL_PER_DIRECTION", "3"))
MAX_DISCIPLINE_MAX_NORMAL_PER_DIRECTION = int(os.getenv("MAX_DISCIPLINE_MAX_NORMAL_PER_DIRECTION", "1"))
MAX_DISCIPLINE_MIN_NEW_ENTRY_DISTANCE = float(os.getenv("MAX_DISCIPLINE_MIN_NEW_ENTRY_DISTANCE", "4.0"))
MAX_DISCIPLINE_REENTRY_MIN_SCORE = int(os.getenv("MAX_DISCIPLINE_REENTRY_MIN_SCORE", "24"))
MAX_DISCIPLINE_NORMAL_AFTER_TP_BLOCK = os.getenv("MAX_DISCIPLINE_NORMAL_AFTER_TP_BLOCK", "TRUE").upper() == "TRUE"
MAX_DISCIPLINE_SPECIAL_AFTER_TP_BLOCK = os.getenv("MAX_DISCIPLINE_SPECIAL_AFTER_TP_BLOCK", "TRUE").upper() == "TRUE"
MAX_DISCIPLINE_SPECIAL_TP_LOCK_LEVEL = int(os.getenv("MAX_DISCIPLINE_SPECIAL_TP_LOCK_LEVEL", "3"))
MAX_DISCIPLINE_CONTINUATION_NEEDS_RETEST = os.getenv("MAX_DISCIPLINE_CONTINUATION_NEEDS_RETEST", "TRUE").upper() == "TRUE"
MAX_DISCIPLINE_CONTINUATION_LOW_POSITION = float(os.getenv("MAX_DISCIPLINE_CONTINUATION_LOW_POSITION", "0.48"))
MAX_DISCIPLINE_EARLY_DAILY_GUARD = os.getenv("MAX_DISCIPLINE_EARLY_DAILY_GUARD", "TRUE").upper() == "TRUE"
MAX_DISCIPLINE_DIRECT_SL_LIMIT = int(os.getenv("MAX_DISCIPLINE_DIRECT_SL_LIMIT", "2"))
MAX_DISCIPLINE_DIRECT_SL_LOOKBACK_SECONDS = int(os.getenv("MAX_DISCIPLINE_DIRECT_SL_LOOKBACK_SECONDS", "7200"))
MAX_DISCIPLINE_EVENT_MAX_NORMAL_SCORE = int(os.getenv("MAX_DISCIPLINE_EVENT_MAX_NORMAL_SCORE", "13"))
MAX_DISCIPLINE_BLOCK_NORMAL_IN_EVENT = os.getenv("MAX_DISCIPLINE_BLOCK_NORMAL_IN_EVENT", "TRUE").upper() == "TRUE"
MAX_DISCIPLINE_A_PLUS_SETUPS = {
    "MAX_DIP_BUY",
    "MAX_RECOVERY_BUY",
    "MAX_PULLBACK_REARM_BUY",
    "MAX_FLIP_BUY",
    "DEEP_REBOUND_BUY",
    "BEAR_CAMPAIGN_SELL",
    "BEAR_CONTINUATION_SELL",
    "EXTREME_SPIKE_FADE_SELL",
    "MAX_FAILED_RETEST_SELL",
    "MAX_EVENT_SPIKE_SELL",
    "PRE_BEAR_SELL"
}

# v42: FAST più presente ma ancora filtrato. Obiettivo: più scalp puliti da 2 punti, senza copiare i blocchi.
FAST_DISCIPLINE_ENABLED = os.getenv("FAST_DISCIPLINE_ENABLED", "TRUE").upper() == "TRUE"
FAST_MAX_PER_DIRECTION_WINDOW = int(os.getenv("FAST_MAX_PER_DIRECTION_WINDOW", "3"))
FAST_DISCIPLINE_WINDOW_SECONDS = int(os.getenv("FAST_DISCIPLINE_WINDOW_SECONDS", "1200"))
FAST_REQUIRE_MAIN_CONTEXT = os.getenv("FAST_REQUIRE_MAIN_CONTEXT", "FALSE").upper() == "TRUE"
FAST_MAIN_CONTEXT_MIN_TP = int(os.getenv("FAST_MAIN_CONTEXT_MIN_TP", "0"))
FAST_DISCIPLINE_A_PLUS_SCORE = int(os.getenv("FAST_DISCIPLINE_A_PLUS_SCORE", "8"))


# v43: Asian Session Daily Thesis.
# Obiettivo: dalle 00:05 il bot non guarda solo il singolo segnale, ma costruisce
# una tesi giornaliera stile Max: Asia scarica/accumula, Londra conferma o ribalta,
# NY gestisce estensione/fade. Serve soprattutto a non vendere basso dopo Asia ribassista
# se Londra sta recuperando, e a non comprare spike alto dopo Asia rialzista già pagata.
ASIAN_THESIS_ENABLED = os.getenv("ASIAN_THESIS_ENABLED", "TRUE").upper() == "TRUE"
ASIAN_THESIS_ALERT_ENABLED = os.getenv("ASIAN_THESIS_ALERT_ENABLED", "TRUE").upper() == "TRUE"
ASIAN_THESIS_START_HOUR = int(os.getenv("ASIAN_THESIS_START_HOUR", "0"))
ASIAN_THESIS_START_MINUTE = int(os.getenv("ASIAN_THESIS_START_MINUTE", "5"))
ASIAN_THESIS_END_HOUR = int(os.getenv("ASIAN_THESIS_END_HOUR", "7"))
ASIAN_THESIS_END_MINUTE = int(os.getenv("ASIAN_THESIS_END_MINUTE", "30"))
ASIAN_THESIS_MIN_POINTS = float(os.getenv("ASIAN_THESIS_MIN_POINTS", "18.0"))
ASIAN_THESIS_STRONG_POINTS = float(os.getenv("ASIAN_THESIS_STRONG_POINTS", "28.0"))
ASIAN_THESIS_RECOVERY_POINTS = float(os.getenv("ASIAN_THESIS_RECOVERY_POINTS", "8.0"))
ASIAN_THESIS_RECOVERY_RATIO = float(os.getenv("ASIAN_THESIS_RECOVERY_RATIO", "0.38"))
ASIAN_THESIS_BREAKOUT_BUFFER = float(os.getenv("ASIAN_THESIS_BREAKOUT_BUFFER", "2.0"))
ASIAN_THESIS_LOW_POSITION_BLOCK_SELL = float(os.getenv("ASIAN_THESIS_LOW_POSITION_BLOCK_SELL", "0.34"))
ASIAN_THESIS_HIGH_POSITION_BLOCK_BUY = float(os.getenv("ASIAN_THESIS_HIGH_POSITION_BLOCK_BUY", "0.66"))
ASIAN_THESIS_REVERSAL_BUY_MIN_SCORE = int(os.getenv("ASIAN_THESIS_REVERSAL_BUY_MIN_SCORE", "7"))
ASIAN_THESIS_REVERSAL_SELL_MIN_SCORE = int(os.getenv("ASIAN_THESIS_REVERSAL_SELL_MIN_SCORE", "7"))
ASIAN_THESIS_COUNTER_FAST_MIN_SCORE = int(os.getenv("ASIAN_THESIS_COUNTER_FAST_MIN_SCORE", "9"))
ASIAN_THESIS_FAST_BLOCK_ENABLED = os.getenv("ASIAN_THESIS_FAST_BLOCK_ENABLED", "TRUE").upper() == "TRUE"
ASIAN_THESIS_MAIN_BLOCK_ENABLED = os.getenv("ASIAN_THESIS_MAIN_BLOCK_ENABLED", "TRUE").upper() == "TRUE"
ASIAN_THESIS_MASTER_OVERRIDE_ENABLED = os.getenv("ASIAN_THESIS_MASTER_OVERRIDE_ENABLED", "TRUE").upper() == "TRUE"
ASIAN_THESIS_AFTER_TP_LOCK_ENABLED = os.getenv("ASIAN_THESIS_AFTER_TP_LOCK_ENABLED", "TRUE").upper() == "TRUE"
ASIAN_THESIS_AFTER_TP_LOCK_LEVEL = int(os.getenv("ASIAN_THESIS_AFTER_TP_LOCK_LEVEL", "3"))
ASIAN_THESIS_AFTER_TP_LOCK_SECONDS = int(os.getenv("ASIAN_THESIS_AFTER_TP_LOCK_SECONDS", "5400"))
ASIAN_THESIS_BUY_SETUPS = {
    "NORMAL",
    "REVERSAL_BUY",
    "MAX_DIP_BUY",
    "MAX_RECOVERY_BUY",
    "MAX_PULLBACK_REARM_BUY",
    "MAX_FLIP_BUY",
    "DEEP_REBOUND_BUY",
}
ASIAN_THESIS_SELL_SETUPS = {
    "NORMAL",
    "BEAR_CAMPAIGN_SELL",
    "BEAR_CONTINUATION_SELL",
    "PRE_BEAR_SELL",
    "MAX_FAILED_RETEST_SELL",
    "MAX_EVENT_SPIKE_SELL",
    "EXTREME_SPIKE_FADE_SELL",
    "SYNTHETIC_BEAR_CONTINUATION_SELL",
    "SYNTHETIC_FAILED_RETEST_SELL",
}

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
    "MAX_FLIP_BUY",
    "DEEP_REBOUND_BUY",
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
    "MAX_RECOVERY_BUY",
    "MAX_FLIP_BUY",
    "DEEP_REBOUND_BUY"
}

BUY_SL_COOLDOWN_ENABLED = os.getenv("BUY_SL_COOLDOWN_ENABLED", "TRUE").upper() == "TRUE"
BUY_SL_COOLDOWN_LOSSES = int(os.getenv("BUY_SL_COOLDOWN_LOSSES", "2"))
BUY_SL_COOLDOWN_LOOKBACK_SECONDS = int(os.getenv("BUY_SL_COOLDOWN_LOOKBACK_SECONDS", "5400"))
BUY_SL_COOLDOWN_SECONDS = int(os.getenv("BUY_SL_COOLDOWN_SECONDS", "3600"))

CONFLICT_RESOLVER_ENABLED = os.getenv("CONFLICT_RESOLVER_ENABLED", "TRUE").upper() == "TRUE"
CONFLICT_WINDOW_SECONDS = int(os.getenv("CONFLICT_WINDOW_SECONDS", "300"))
CONFLICT_DOMINANCE_MARGIN = int(os.getenv("CONFLICT_DOMINANCE_MARGIN", "4"))

SETUP_WEIGHTS = {
    "PRE_BEAR_SELL": 24,
    "BEAR_CAMPAIGN_SELL": 22,
    "SYNTHETIC_BEAR_CONTINUATION_SELL": 20,
    "BEAR_CONTINUATION_SELL": 16,
    "SYNTHETIC_FAILED_RETEST_SELL": 18,
    "MAX_FAILED_RETEST_SELL": 14,
    "MAX_EVENT_SPIKE_SELL": 10,
    "EXTREME_SPIKE_FADE_SELL": 15,
    "MAX_VIEW_SELL": 8,
    "MAX_RECOVERY_BUY": 5,
    "MAX_FLIP_BUY": 6,
    "DEEP_REBOUND_BUY": 5,
    "MAX_DIP_BUY": 4,
    "REVERSAL_BUY": 4,
    "MAX_FADE_SELL": 3,
    "MAX_DIP_SELL": 3,
    "REVERSAL_SELL": 3,
    "NORMAL": 1
}

# v15: Chaos Day + Extreme Zone Filter
# Serve per giornate tossiche tipo 01-07-26:
# tanti fake, inversioni violente, SL diretti, squeeze e segnali validi solo da zone estreme.
CHAOS_MODE_ENABLED = os.getenv("CHAOS_MODE_ENABLED", "TRUE").upper() == "TRUE"

# Se ci sono almeno 3 SL diretti nelle ultime 3 ore, attivo Chaos Mode.
CHAOS_DIRECT_SL_COUNT = int(os.getenv("CHAOS_DIRECT_SL_COUNT", "3"))
CHAOS_LOOKBACK_SECONDS = int(os.getenv("CHAOS_LOOKBACK_SECONDS", "10800"))
CHAOS_LOCK_SECONDS = int(os.getenv("CHAOS_LOCK_SECONDS", "5400"))

# Stop totale se la giornata diventa davvero ingestibile.
DAILY_KILL_SWITCH_ENABLED = os.getenv("DAILY_KILL_SWITCH_ENABLED", "TRUE").upper() == "TRUE"
DAILY_MAX_DIRECT_SL = int(os.getenv("DAILY_MAX_DIRECT_SL", "5"))

# In Chaos Mode non si entra nel mezzo.
CHAOS_EXTREME_ZONE_REQUIRED = os.getenv("CHAOS_EXTREME_ZONE_REQUIRED", "TRUE").upper() == "TRUE"
CHAOS_EXTREME_DISTANCE = float(os.getenv("CHAOS_EXTREME_DISTANCE", "8"))
CHAOS_EXTREME_ATR_MULT = float(os.getenv("CHAOS_EXTREME_ATR_MULT", "2.5"))
CHAOS_SELL_DAY_POSITION_MIN = float(os.getenv("CHAOS_SELL_DAY_POSITION_MIN", "0.70"))
CHAOS_BUY_DAY_POSITION_MAX = float(os.getenv("CHAOS_BUY_DAY_POSITION_MAX", "0.30"))

# In Chaos Mode devono passare solo setup speciali e abbastanza forti.
CHAOS_MIN_SCORE = int(os.getenv("CHAOS_MIN_SCORE", "10"))
CHAOS_ALLOW_NORMAL_EXTREME = os.getenv("CHAOS_ALLOW_NORMAL_EXTREME", "FALSE").upper() == "TRUE"
CHAOS_NORMAL_MIN_SCORE = int(os.getenv("CHAOS_NORMAL_MIN_SCORE", "18"))

CHAOS_SELL_SETUPS = {
    "PRE_BEAR_SELL",
    "BEAR_CAMPAIGN_SELL",
    "SYNTHETIC_BEAR_CONTINUATION_SELL",
    "BEAR_CONTINUATION_SELL",
    "SYNTHETIC_FAILED_RETEST_SELL",
    "MAX_FAILED_RETEST_SELL",
    "MAX_EVENT_SPIKE_SELL",
    "EXTREME_SPIKE_FADE_SELL",
    "MAX_VIEW_SELL",
    "MAX_FADE_SELL",
    "REVERSAL_SELL",
    "MAX_DIP_SELL"
}

CHAOS_BUY_SETUPS = {
    "MAX_DIP_BUY",
    "MAX_RECOVERY_BUY",
    "MAX_FLIP_BUY",
    "REVERSAL_BUY"
}

# Evita che Runner/lock vecchi del giorno prima influenzino troppo la nuova sessione.
SESSION_LOCK_RESET_ENABLED = os.getenv("SESSION_LOCK_RESET_ENABLED", "TRUE").upper() == "TRUE"
LOCK_IGNORE_PREVIOUS_DAY = os.getenv("LOCK_IGNORE_PREVIOUS_DAY", "TRUE").upper() == "TRUE"
STALE_TRADE_LOCK_SECONDS = int(os.getenv("STALE_TRADE_LOCK_SECONDS", "21600"))

# v16: Max View + NFP Exhaustion Sell
# Serve per leggere il cambio di contesto visto nei file:
# il bot prende bene la salita, ma Max vende i rimbalzi alti perché vede esaurimento / NFP / view 3980.
MAX_VIEW_SELL_ENABLED = os.getenv("MAX_VIEW_SELL_ENABLED", "TRUE").upper() == "TRUE"

# Se ci sono già BUY profondi recenti, una salita può diventare zona di esaurimento da vendere.
MAX_VIEW_BUY_TP_LEVEL = int(os.getenv("MAX_VIEW_BUY_TP_LEVEL", "5"))
MAX_VIEW_BUY_COUNT = int(os.getenv("MAX_VIEW_BUY_COUNT", "2"))
MAX_VIEW_LOOKBACK_SECONDS = int(os.getenv("MAX_VIEW_LOOKBACK_SECONDS", "7200"))

# Zona alta stile Max: non vendo basso, vendo solo rimbalzi alti / top di giornata.
MAX_VIEW_SELL_DAY_POSITION_MIN = float(os.getenv("MAX_VIEW_SELL_DAY_POSITION_MIN", "0.70"))
MAX_VIEW_MIN_RSI = float(os.getenv("MAX_VIEW_MIN_RSI", "50"))

# In giornate NFP / evento macro, questo setup prende più priorità.
# Puoi attivarlo manualmente da Render con MAX_VIEW_EVENT_MODE=TRUE,
# oppure da TradingView con l'input Event Mode nel Pine v34.
MAX_VIEW_EVENT_MODE = os.getenv("MAX_VIEW_EVENT_MODE", "FALSE").upper() == "TRUE"
MAX_VIEW_EVENT_BONUS = int(os.getenv("MAX_VIEW_EVENT_BONUS", "3"))

# Quanto deve essere forte il setup per passare.
MAX_VIEW_SELL_BASE_BONUS = int(os.getenv("MAX_VIEW_SELL_BASE_BONUS", "10"))
MAX_VIEW_SELL_MIN_SCORE = int(os.getenv("MAX_VIEW_SELL_MIN_SCORE", "10"))

# Permette SELL contro news bullish se è un vero top/exhaustion.
MAX_VIEW_ALLOW_SELL_AGAINST_BULLISH_NEWS = os.getenv("MAX_VIEW_ALLOW_SELL_AGAINST_BULLISH_NEWS", "TRUE").upper() == "TRUE"

# v17: Auto Event Mode
# Attiva automaticamente la modalità evento/NFP in base a:
# - parole chiave macro nelle news;
# - volatilità improvvisa ricevuta dal Pine;
# - EVENT_RISK=HIGH;
# - eventuale input manuale dal Pine.
AUTO_EVENT_MODE_ENABLED = os.getenv("AUTO_EVENT_MODE_ENABLED", "TRUE").upper() == "TRUE"
AUTO_EVENT_KEYWORDS_ENABLED = os.getenv("AUTO_EVENT_KEYWORDS_ENABLED", "TRUE").upper() == "TRUE"
AUTO_EVENT_VOLATILITY_ENABLED = os.getenv("AUTO_EVENT_VOLATILITY_ENABLED", "TRUE").upper() == "TRUE"

AUTO_EVENT_DURATION_SECONDS = int(os.getenv("AUTO_EVENT_DURATION_SECONDS", "7200"))
AUTO_EVENT_CANDLE_ATR_MULT = float(os.getenv("AUTO_EVENT_CANDLE_ATR_MULT", "2.2"))
AUTO_EVENT_M15_RANGE_ATR_MULT = float(os.getenv("AUTO_EVENT_M15_RANGE_ATR_MULT", "3.0"))
AUTO_EVENT_DAY_RANGE_ATR_MULT = float(os.getenv("AUTO_EVENT_DAY_RANGE_ATR_MULT", "4.0"))
AUTO_EVENT_VOLUME_SPIKE_REQUIRED = os.getenv("AUTO_EVENT_VOLUME_SPIKE_REQUIRED", "FALSE").upper() == "TRUE"

AUTO_EVENT_KEYWORDS = [
    "nfp",
    "nonfarm payroll",
    "non-farm payroll",
    "payrolls",
    "jobs report",
    "unemployment",
    "jobless claims",
    "cpi",
    "ppi",
    "inflation",
    "fomc",
    "fed decision",
    "federal reserve",
    "powell",
    "interest rate",
    "rate decision",
    "yields",
    "gdp",
    "ism",
    "pmi"
]

NEWS_CACHE = {"time": 0, "bias": "NEUTRAL", "reasons": []}
AUTO_EVENT_CACHE = {
    "until": 0,
    "reasons": [],
    "start_time": 0,
    "start_price": 0,
    "high": 0,
    "low": 0,
    "high_time": 0,
    "low_time": 0,
    "pullback_low_after_high": 0,
    "max_pullback_after_high": 0,
    "pullback_time": 0
}

# v18: NFP Spike Reversal + Event Memory
# La v17 capiva che c'era evento, ma non capiva bene lo spike.
# La v18 memorizza il prezzo pre-evento e cerca SELL da top dopo spike verticale.
EVENT_SPIKE_REVERSAL_ENABLED = os.getenv("EVENT_SPIKE_REVERSAL_ENABLED", "TRUE").upper() == "TRUE"

EVENT_SPIKE_LOOKBACK_SECONDS = int(os.getenv("EVENT_SPIKE_LOOKBACK_SECONDS", "7200"))
EVENT_SPIKE_MIN_UP_POINTS = float(os.getenv("EVENT_SPIKE_MIN_UP_POINTS", "35"))
EVENT_SPIKE_TOP_POSITION_MIN = float(os.getenv("EVENT_SPIKE_TOP_POSITION_MIN", "0.65"))
EVENT_SPIKE_SELL_RETRACE_POINTS = float(os.getenv("EVENT_SPIKE_SELL_RETRACE_POINTS", "2.5"))

EVENT_SPIKE_SELL_BASE_BONUS = int(os.getenv("EVENT_SPIKE_SELL_BASE_BONUS", "14"))
EVENT_SPIKE_SELL_MIN_SCORE = int(os.getenv("EVENT_SPIKE_SELL_MIN_SCORE", "10"))
EVENT_SPIKE_EVENT_BONUS = int(os.getenv("EVENT_SPIKE_EVENT_BONUS", "5"))

# Durante uno spike-up da evento, blocca i BUY nella parte alta dello spike.
EVENT_SPIKE_BLOCK_TOP_BUY_ENABLED = os.getenv("EVENT_SPIKE_BLOCK_TOP_BUY_ENABLED", "TRUE").upper() == "TRUE"
EVENT_SPIKE_BLOCK_BUY_TOP_POSITION_MIN = float(os.getenv("EVENT_SPIKE_BLOCK_BUY_TOP_POSITION_MIN", "0.55"))
EVENT_SPIKE_BLOCK_BUY_MIN_UP_POINTS = float(os.getenv("EVENT_SPIKE_BLOCK_BUY_MIN_UP_POINTS", "30"))
EVENT_SPIKE_ALLOW_BUY_BELOW_POSITION = float(os.getenv("EVENT_SPIKE_ALLOW_BUY_BELOW_POSITION", "0.45"))

# In questo setup accetto SELL anche se EMA20/EMA50 sono UP o news ancora bullish.
EVENT_SPIKE_ALLOW_SELL_AGAINST_BULLISH_NEWS = os.getenv("EVENT_SPIKE_ALLOW_SELL_AGAINST_BULLISH_NEWS", "TRUE").upper() == "TRUE"

# v19: Max Failed Retest Sell
# La v18 capisce lo spike e blocca i BUY in alto.
# La v19 aggiunge pazienza: vende il retest alto fallito, non il primo top casuale.
FAILED_RETEST_SELL_ENABLED = os.getenv("FAILED_RETEST_SELL_ENABLED", "TRUE").upper() == "TRUE"
FAILED_RETEST_MIN_PULLBACK_POINTS = float(os.getenv("FAILED_RETEST_MIN_PULLBACK_POINTS", "10"))
FAILED_RETEST_TOP_POSITION_MIN = float(os.getenv("FAILED_RETEST_TOP_POSITION_MIN", "0.72"))
FAILED_RETEST_TOP_POSITION_MAX = float(os.getenv("FAILED_RETEST_TOP_POSITION_MAX", "0.96"))
FAILED_RETEST_NEAR_HIGH_DISTANCE = float(os.getenv("FAILED_RETEST_NEAR_HIGH_DISTANCE", "14"))
FAILED_RETEST_MIN_DISTANCE_FROM_HIGH = float(os.getenv("FAILED_RETEST_MIN_DISTANCE_FROM_HIGH", "1.5"))
FAILED_RETEST_MIN_SECONDS_AFTER_HIGH = int(os.getenv("FAILED_RETEST_MIN_SECONDS_AFTER_HIGH", "60"))

FAILED_RETEST_REJECTION_REQUIRED = os.getenv("FAILED_RETEST_REJECTION_REQUIRED", "TRUE").upper() == "TRUE"
FAILED_RETEST_SELL_BASE_BONUS = int(os.getenv("FAILED_RETEST_SELL_BASE_BONUS", "18"))
FAILED_RETEST_SELL_MIN_SCORE = int(os.getenv("FAILED_RETEST_SELL_MIN_SCORE", "12"))
FAILED_RETEST_EVENT_BONUS = int(os.getenv("FAILED_RETEST_EVENT_BONUS", "5"))

# Se TRUE, evita i MAX_VIEW_SELL / MAX_EVENT_SPIKE_SELL troppo anticipati finché non c'è stato pullback.
FAILED_RETEST_BLOCK_EARLY_SELLS = os.getenv("FAILED_RETEST_BLOCK_EARLY_SELLS", "TRUE").upper() == "TRUE"
FAILED_RETEST_ALLOW_SELL_AGAINST_BULLISH_NEWS = os.getenv("FAILED_RETEST_ALLOW_SELL_AGAINST_BULLISH_NEWS", "TRUE").upper() == "TRUE"
FAILED_RETEST_ALLOW_AGAINST_DAILY_BUY = os.getenv("FAILED_RETEST_ALLOW_AGAINST_DAILY_BUY", "TRUE").upper() == "TRUE"


# v38: Extreme Spike Fade SELL
# Patch nata dal caso Max 4167-4174: dopo un BUY enorme/runner e uno spike evento alto,
# il bot non deve solo bloccare nuovi BUY; deve anche poter vendere il failed retest alto,
# senza farsi bloccare dal Recovery Lock del BUY già pagato.
EXTREME_SPIKE_FADE_SELL_ENABLED = os.getenv("EXTREME_SPIKE_FADE_SELL_ENABLED", "TRUE").upper() == "TRUE"
EXTREME_SPIKE_FADE_MIN_BUY_TP = int(os.getenv("EXTREME_SPIKE_FADE_MIN_BUY_TP", "6"))
EXTREME_SPIKE_FADE_BUY_LOOKBACK_SECONDS = int(os.getenv("EXTREME_SPIKE_FADE_BUY_LOOKBACK_SECONDS", "7200"))
EXTREME_SPIKE_FADE_MIN_UP_POINTS = float(os.getenv("EXTREME_SPIKE_FADE_MIN_UP_POINTS", "55"))
EXTREME_SPIKE_FADE_TOP_POSITION_MIN = float(os.getenv("EXTREME_SPIKE_FADE_TOP_POSITION_MIN", "0.82"))
EXTREME_SPIKE_FADE_RETRACE_MIN = float(os.getenv("EXTREME_SPIKE_FADE_RETRACE_MIN", "2.0"))
EXTREME_SPIKE_FADE_NEAR_HIGH_MAX_DISTANCE = float(os.getenv("EXTREME_SPIKE_FADE_NEAR_HIGH_MAX_DISTANCE", "18.0"))
EXTREME_SPIKE_FADE_MIN_CONFIRMATIONS = int(os.getenv("EXTREME_SPIKE_FADE_MIN_CONFIRMATIONS", "5"))
EXTREME_SPIKE_FADE_BASE_BONUS = int(os.getenv("EXTREME_SPIKE_FADE_BASE_BONUS", "22"))
EXTREME_SPIKE_FADE_EVENT_BONUS = int(os.getenv("EXTREME_SPIKE_FADE_EVENT_BONUS", "5"))
EXTREME_SPIKE_FADE_ALLOW_AGAINST_DAILY_BUY = os.getenv("EXTREME_SPIKE_FADE_ALLOW_AGAINST_DAILY_BUY", "TRUE").upper() == "TRUE"
EXTREME_SPIKE_FADE_ALLOW_AGAINST_BULLISH_NEWS = os.getenv("EXTREME_SPIKE_FADE_ALLOW_AGAINST_BULLISH_NEWS", "TRUE").upper() == "TRUE"
EXTREME_SPIKE_FADE_BYPASS_RECOVERY_LOCK_SCORE = int(os.getenv("EXTREME_SPIKE_FADE_BYPASS_RECOVERY_LOCK_SCORE", "18"))
EXTREME_SPIKE_FADE_REQUIRE_EVENT = os.getenv("EXTREME_SPIKE_FADE_REQUIRE_EVENT", "TRUE").upper() == "TRUE"

# v39: Post Super BUY Guard
# Dopo un BUY speciale arrivato a TP8/runner, non apro subito BEAR_CAMPAIGN/CONTINUATION
# contro il movimento. Max prima lascia correre, poi eventualmente cerca un fade solo su failed retest alto.
# Valori già incorporati nel codice: non devi per forza aggiungere nuove variabili su Render.
POST_SUPER_BUY_GUARD_ENABLED = os.getenv("POST_SUPER_BUY_GUARD_ENABLED", "TRUE").upper() == "TRUE"
POST_SUPER_BUY_GUARD_MIN_TP = int(os.getenv("POST_SUPER_BUY_GUARD_MIN_TP", "8"))
POST_SUPER_BUY_GUARD_SECONDS = int(os.getenv("POST_SUPER_BUY_GUARD_SECONDS", "14400"))  # 4 ore
POST_SUPER_BUY_GUARD_MIN_SCORE = int(os.getenv("POST_SUPER_BUY_GUARD_MIN_SCORE", "22"))
POST_SUPER_BUY_GUARD_REQUIRE_FAILED_RETEST = os.getenv("POST_SUPER_BUY_GUARD_REQUIRE_FAILED_RETEST", "TRUE").upper() == "TRUE"
POST_SUPER_BUY_GUARD_REQUIRE_BEARISH_CANDLE_OR_REJECTION = os.getenv("POST_SUPER_BUY_GUARD_REQUIRE_BEARISH_CANDLE_OR_REJECTION", "TRUE").upper() == "TRUE"
POST_SUPER_BUY_GUARD_REQUIRE_MICRO_BOS = os.getenv("POST_SUPER_BUY_GUARD_REQUIRE_MICRO_BOS", "FALSE").upper() == "TRUE"
POST_SUPER_BUY_GUARD_BLOCK_SETUPS = {
    "NORMAL",
    "MAX_FADE_SELL",
    "BEAR_CAMPAIGN_SELL",
    "BEAR_CONTINUATION_SELL",
    "SYNTHETIC_BEAR_CONTINUATION_SELL",
    "PRE_BEAR_SELL",
    "MAX_FAILED_RETEST_SELL",
    "MAX_EVENT_SPIKE_SELL",
    "SYNTHETIC_FAILED_RETEST_SELL",
}
POST_SUPER_BUY_GUARD_ALLOW_SETUPS = {"EXTREME_SPIKE_FADE_SELL"}


# v20: Event State Machine + Synthetic Failed Retest Sell
# Il Python non aspetta più obbligatoriamente un SELL dal Pine.
# I PRICE_UPDATE fanno avanzare una macchina a stati:
# SPIKE_UP -> PULLBACK_CONFIRMED -> RETEST_ARMED -> SELL_TRIGGERED.
SYNTHETIC_RETEST_ENGINE_ENABLED = os.getenv("SYNTHETIC_RETEST_ENGINE_ENABLED", "TRUE").upper() == "TRUE"

SYNTHETIC_RETEST_SPIKE_MIN_UP_POINTS = float(os.getenv("SYNTHETIC_RETEST_SPIKE_MIN_UP_POINTS", "35"))
SYNTHETIC_RETEST_PULLBACK_POINTS = float(os.getenv("SYNTHETIC_RETEST_PULLBACK_POINTS", "10"))
SYNTHETIC_RETEST_ARM_POSITION_MIN = float(os.getenv("SYNTHETIC_RETEST_ARM_POSITION_MIN", "0.72"))
SYNTHETIC_RETEST_ARM_POSITION_MAX = float(os.getenv("SYNTHETIC_RETEST_ARM_POSITION_MAX", "0.96"))
SYNTHETIC_RETEST_NEAR_HIGH_DISTANCE = float(os.getenv("SYNTHETIC_RETEST_NEAR_HIGH_DISTANCE", "14"))
SYNTHETIC_RETEST_MIN_SECONDS_AFTER_HIGH = int(os.getenv("SYNTHETIC_RETEST_MIN_SECONDS_AFTER_HIGH", "60"))
SYNTHETIC_RETEST_FAILURE_POINTS = float(os.getenv("SYNTHETIC_RETEST_FAILURE_POINTS", "2.5"))
SYNTHETIC_RETEST_REQUIRE_BEAR_CONFIRMATION = os.getenv("SYNTHETIC_RETEST_REQUIRE_BEAR_CONFIRMATION", "TRUE").upper() == "TRUE"

SYNTHETIC_RETEST_BLOCK_BUYS_WHEN_ARMED = os.getenv("SYNTHETIC_RETEST_BLOCK_BUYS_WHEN_ARMED", "TRUE").upper() == "TRUE"
SYNTHETIC_RETEST_COOLDOWN_SECONDS = int(os.getenv("SYNTHETIC_RETEST_COOLDOWN_SECONDS", "1800"))
SYNTHETIC_RETEST_SCORE = int(os.getenv("SYNTHETIC_RETEST_SCORE", "28"))

# Costruzione trade sintetico SELL
SYNTHETIC_RETEST_ENTRY_HALF_ZONE = float(os.getenv("SYNTHETIC_RETEST_ENTRY_HALF_ZONE", "1.5"))
SYNTHETIC_RETEST_HIGH_SL_BUFFER = float(os.getenv("SYNTHETIC_RETEST_HIGH_SL_BUFFER", "3"))
SYNTHETIC_RETEST_MIN_SL_DISTANCE = float(os.getenv("SYNTHETIC_RETEST_MIN_SL_DISTANCE", "8"))
SYNTHETIC_RETEST_MAX_RISK_POINTS = float(os.getenv("SYNTHETIC_RETEST_MAX_RISK_POINTS", "22"))

SYNTHETIC_RETEST_TP1 = float(os.getenv("SYNTHETIC_RETEST_TP1", "3"))
SYNTHETIC_RETEST_TP2 = float(os.getenv("SYNTHETIC_RETEST_TP2", "5"))
SYNTHETIC_RETEST_TP3 = float(os.getenv("SYNTHETIC_RETEST_TP3", "8"))
SYNTHETIC_RETEST_TP4 = float(os.getenv("SYNTHETIC_RETEST_TP4", "11"))
SYNTHETIC_RETEST_TP5 = float(os.getenv("SYNTHETIC_RETEST_TP5", "14"))
SYNTHETIC_RETEST_TP6 = float(os.getenv("SYNTHETIC_RETEST_TP6", "17"))
SYNTHETIC_RETEST_TP7 = float(os.getenv("SYNTHETIC_RETEST_TP7", "20"))
SYNTHETIC_RETEST_TP8 = float(os.getenv("SYNTHETIC_RETEST_TP8", "25"))

# Stato runtime per simbolo. Viene alimentato da PRICE_UPDATE.
EVENT_STATE_MACHINE = {}

# v21: Bearish Continuation + Lower High State Machine
# Serve per il pattern visto con Max:
# forte impulso ribassista -> rimbalzo tecnico -> lower high -> nuova continuazione SELL.
BEAR_CONTINUATION_ENGINE_ENABLED = os.getenv("BEAR_CONTINUATION_ENGINE_ENABLED", "TRUE").upper() == "TRUE"

BEAR_HISTORY_SECONDS = int(os.getenv("BEAR_HISTORY_SECONDS", "5400"))
BEAR_HISTORY_MAX_POINTS = int(os.getenv("BEAR_HISTORY_MAX_POINTS", "240"))
BEAR_IMPULSE_LOOKBACK_SECONDS = int(os.getenv("BEAR_IMPULSE_LOOKBACK_SECONDS", "1800"))

BEAR_IMPULSE_MIN_DROP_POINTS = float(os.getenv("BEAR_IMPULSE_MIN_DROP_POINTS", "12"))
BEAR_IMPULSE_ATR_MULT = float(os.getenv("BEAR_IMPULSE_ATR_MULT", "4.0"))

BEAR_RELIEF_MIN_POINTS = float(os.getenv("BEAR_RELIEF_MIN_POINTS", "4"))
BEAR_RELIEF_MIN_RETRACE = float(os.getenv("BEAR_RELIEF_MIN_RETRACE", "0.15"))
BEAR_RELIEF_MAX_RETRACE = float(os.getenv("BEAR_RELIEF_MAX_RETRACE", "0.65"))
BEAR_LOWER_HIGH_MIN_GAP = float(os.getenv("BEAR_LOWER_HIGH_MIN_GAP", "4"))

BEAR_CONTINUATION_FAILURE_POINTS = float(os.getenv("BEAR_CONTINUATION_FAILURE_POINTS", "2.5"))
BEAR_CONTINUATION_MIN_SECONDS = int(os.getenv("BEAR_CONTINUATION_MIN_SECONDS", "30"))
BEAR_STATE_TIMEOUT_SECONDS = int(os.getenv("BEAR_STATE_TIMEOUT_SECONDS", "5400"))

BEAR_CONTINUATION_BASE_BONUS = int(os.getenv("BEAR_CONTINUATION_BASE_BONUS", "12"))
BEAR_CONTINUATION_SELL_MIN_SCORE = int(os.getenv("BEAR_CONTINUATION_SELL_MIN_SCORE", "10"))
BEAR_CONTINUATION_IGNORE_BULLISH_NEWS = os.getenv("BEAR_CONTINUATION_IGNORE_BULLISH_NEWS", "TRUE").upper() == "TRUE"
BEAR_CONTINUATION_ALLOW_AGAINST_DAILY_BUY = os.getenv("BEAR_CONTINUATION_ALLOW_AGAINST_DAILY_BUY", "TRUE").upper() == "TRUE"

# Blocca BUY dentro l'impulso/rimbalzo ribassista.
BEAR_BLOCK_BUYS_ENABLED = os.getenv("BEAR_BLOCK_BUYS_ENABLED", "TRUE").upper() == "TRUE"
BEAR_BLOCK_MAX_DIP_BUY = os.getenv("BEAR_BLOCK_MAX_DIP_BUY", "TRUE").upper() == "TRUE"
BEAR_BLOCK_REVERSAL_BUY = os.getenv("BEAR_BLOCK_REVERSAL_BUY", "TRUE").upper() == "TRUE"

# Eccezione molto selettiva per vero recovery BUY.
BEAR_ALLOW_STRONG_RECOVERY_BUY = os.getenv("BEAR_ALLOW_STRONG_RECOVERY_BUY", "TRUE").upper() == "TRUE"
BEAR_STRONG_RECOVERY_MIN_SCORE = int(os.getenv("BEAR_STRONG_RECOVERY_MIN_SCORE", "24"))

# Synthetic SELL autonomo della seconda macchina a stati.
BEAR_SYNTHETIC_SELL_ENABLED = os.getenv("BEAR_SYNTHETIC_SELL_ENABLED", "TRUE").upper() == "TRUE"
BEAR_SYNTHETIC_SCORE = int(os.getenv("BEAR_SYNTHETIC_SCORE", "26"))
BEAR_SYNTHETIC_COOLDOWN_SECONDS = int(os.getenv("BEAR_SYNTHETIC_COOLDOWN_SECONDS", "1800"))

BEAR_SYNTHETIC_ENTRY_HALF_ZONE = float(os.getenv("BEAR_SYNTHETIC_ENTRY_HALF_ZONE", "1.5"))
BEAR_SYNTHETIC_RALLY_SL_BUFFER = float(os.getenv("BEAR_SYNTHETIC_RALLY_SL_BUFFER", "3"))
BEAR_SYNTHETIC_MIN_SL_DISTANCE = float(os.getenv("BEAR_SYNTHETIC_MIN_SL_DISTANCE", "8"))
BEAR_SYNTHETIC_MAX_RISK_POINTS = float(os.getenv("BEAR_SYNTHETIC_MAX_RISK_POINTS", "20"))

BEAR_SYNTHETIC_TP1 = float(os.getenv("BEAR_SYNTHETIC_TP1", "3"))
BEAR_SYNTHETIC_TP2 = float(os.getenv("BEAR_SYNTHETIC_TP2", "5"))
BEAR_SYNTHETIC_TP3 = float(os.getenv("BEAR_SYNTHETIC_TP3", "8"))
BEAR_SYNTHETIC_TP4 = float(os.getenv("BEAR_SYNTHETIC_TP4", "11"))
BEAR_SYNTHETIC_TP5 = float(os.getenv("BEAR_SYNTHETIC_TP5", "14"))
BEAR_SYNTHETIC_TP6 = float(os.getenv("BEAR_SYNTHETIC_TP6", "17"))
BEAR_SYNTHETIC_TP7 = float(os.getenv("BEAR_SYNTHETIC_TP7", "20"))
BEAR_SYNTHETIC_TP8 = float(os.getenv("BEAR_SYNTHETIC_TP8", "25"))

# Runtime memory, alimentata da PRICE_UPDATE.
BEAR_CONTINUATION_STATE = {}
PRICE_HISTORY = {}
DAILY_THESIS_STATE = {}

# v22: Campaign Manager / Thesis Persistence
# Una campagna SELL gestisce una sola tesi ribassista con più leg controllate.
# Non è un invito ad aumentare l'esposizione: ogni leg ha un peso rischio separato
# e la somma resta sotto un cap totale configurabile.
CAMPAIGN_MANAGER_ENABLED = os.getenv("CAMPAIGN_MANAGER_ENABLED", "TRUE").upper() == "TRUE"
CAMPAIGN_DIRECTION = "SELL"

CAMPAIGN_MAX_LEGS = int(os.getenv("CAMPAIGN_MAX_LEGS", "3"))
CAMPAIGN_TOTAL_RISK_CAP = float(os.getenv("CAMPAIGN_TOTAL_RISK_CAP", "1.0"))
CAMPAIGN_LEG_WEIGHTS_RAW = os.getenv("CAMPAIGN_LEG_WEIGHTS", "0.40,0.35,0.25")

CAMPAIGN_FIRST_LEG_MIN_SCORE = int(os.getenv("CAMPAIGN_FIRST_LEG_MIN_SCORE", "14"))
CAMPAIGN_REENTRY_MIN_SCORE = int(os.getenv("CAMPAIGN_REENTRY_MIN_SCORE", "18"))
CAMPAIGN_BETTER_PRICE_POINTS = float(os.getenv("CAMPAIGN_BETTER_PRICE_POINTS", "3"))
CAMPAIGN_NEW_RETEST_POINTS = float(os.getenv("CAMPAIGN_NEW_RETEST_POINTS", "2"))
CAMPAIGN_LEG_COOLDOWN_SECONDS = int(os.getenv("CAMPAIGN_LEG_COOLDOWN_SECONDS", "300"))
CAMPAIGN_TIMEOUT_SECONDS = int(os.getenv("CAMPAIGN_TIMEOUT_SECONDS", "14400"))
CAMPAIGN_INVALIDATION_BUFFER = float(os.getenv("CAMPAIGN_INVALIDATION_BUFFER", "3"))

CAMPAIGN_ELIGIBLE_SETUPS = {
    "BEAR_CAMPAIGN_SELL",
    "BEAR_CONTINUATION_SELL",
    "SYNTHETIC_BEAR_CONTINUATION_SELL",
    "MAX_FAILED_RETEST_SELL",
    "SYNTHETIC_FAILED_RETEST_SELL",
    "MAX_EVENT_SPIKE_SELL",
    "EXTREME_SPIKE_FADE_SELL",
    "MAX_VIEW_SELL",
    "MAX_FADE_SELL"
}

# Override controllato dei filtri vecchi.
CAMPAIGN_KILL_SWITCH_OVERRIDE_ENABLED = os.getenv("CAMPAIGN_KILL_SWITCH_OVERRIDE_ENABLED", "TRUE").upper() == "TRUE"
CAMPAIGN_KILL_SWITCH_MIN_SCORE = int(os.getenv("CAMPAIGN_KILL_SWITCH_MIN_SCORE", "18"))
CAMPAIGN_KILL_OVERRIDE_RISK_WEIGHT = float(os.getenv("CAMPAIGN_KILL_OVERRIDE_RISK_WEIGHT", "0.25"))

CAMPAIGN_SL_COOLDOWN_OVERRIDE_ENABLED = os.getenv("CAMPAIGN_SL_COOLDOWN_OVERRIDE_ENABLED", "TRUE").upper() == "TRUE"
CAMPAIGN_SL_COOLDOWN_MIN_SCORE = int(os.getenv("CAMPAIGN_SL_COOLDOWN_MIN_SCORE", "20"))
CAMPAIGN_MAX_SL_OVERRIDES = int(os.getenv("CAMPAIGN_MAX_SL_OVERRIDES", "1"))

# Extreme-zone fallback quando day_position / day_high / day_low non arrivano.
CAMPAIGN_EXTREME_FALLBACK_ENABLED = os.getenv("CAMPAIGN_EXTREME_FALLBACK_ENABLED", "TRUE").upper() == "TRUE"
CAMPAIGN_EXTREME_POSITION_MIN = float(os.getenv("CAMPAIGN_EXTREME_POSITION_MIN", "0.65"))
CAMPAIGN_RALLY_PEAK_DISTANCE = float(os.getenv("CAMPAIGN_RALLY_PEAK_DISTANCE", "14"))

# Promuove un SELL già coerente con la tesi della campagna.
CAMPAIGN_SELL_PROMOTION_ENABLED = os.getenv("CAMPAIGN_SELL_PROMOTION_ENABLED", "TRUE").upper() == "TRUE"
CAMPAIGN_SELL_BASE_BONUS = int(os.getenv("CAMPAIGN_SELL_BASE_BONUS", "8"))
CAMPAIGN_SELL_MIN_SCORE = int(os.getenv("CAMPAIGN_SELL_MIN_SCORE", "12"))

# Gestione basket solo informativa: segnala quando proteggere le leg peggiori
# e lasciare correre le entry migliori.
CAMPAIGN_TRIM_ENABLED = os.getenv("CAMPAIGN_TRIM_ENABLED", "TRUE").upper() == "TRUE"
CAMPAIGN_TRIM_TRIGGER_POINTS = float(os.getenv("CAMPAIGN_TRIM_TRIGGER_POINTS", "6"))

BEAR_CAMPAIGN_STATE = {}

# v23: Pre-Bear Thesis
# Anticipa il grande SELL quando il recupero fallisce prima che il bear impulse
# sia già completamente visibile. Pattern:
# prior drop -> recovery rally -> lower high / failed recovery -> SELL thesis.
PRE_BEAR_THESIS_ENABLED = os.getenv("PRE_BEAR_THESIS_ENABLED", "TRUE").upper() == "TRUE"
PRE_BEAR_LOOKBACK_SECONDS = int(os.getenv("PRE_BEAR_LOOKBACK_SECONDS", "3600"))
PRE_BEAR_MIN_PRIOR_DROP_POINTS = float(os.getenv("PRE_BEAR_MIN_PRIOR_DROP_POINTS", "10"))
PRE_BEAR_MIN_RECOVERY_POINTS = float(os.getenv("PRE_BEAR_MIN_RECOVERY_POINTS", "6"))
PRE_BEAR_MIN_RETRACE = float(os.getenv("PRE_BEAR_MIN_RETRACE", "0.25"))
PRE_BEAR_MAX_RETRACE = float(os.getenv("PRE_BEAR_MAX_RETRACE", "0.88"))
PRE_BEAR_LOWER_HIGH_GAP = float(os.getenv("PRE_BEAR_LOWER_HIGH_GAP", "3"))
PRE_BEAR_FAILURE_POINTS = float(os.getenv("PRE_BEAR_FAILURE_POINTS", "2.5"))
PRE_BEAR_MACRO_VOTES = int(os.getenv("PRE_BEAR_MACRO_VOTES", "3"))
PRE_BEAR_TIMEOUT_SECONDS = int(os.getenv("PRE_BEAR_TIMEOUT_SECONDS", "3600"))
PRE_BEAR_INVALIDATION_BUFFER = float(os.getenv("PRE_BEAR_INVALIDATION_BUFFER", "2.5"))
PRE_BEAR_SELL_BASE_BONUS = int(os.getenv("PRE_BEAR_SELL_BASE_BONUS", "12"))
PRE_BEAR_SELL_MIN_SCORE = int(os.getenv("PRE_BEAR_SELL_MIN_SCORE", "12"))
PRE_BEAR_BLOCK_BUYS_ENABLED = os.getenv("PRE_BEAR_BLOCK_BUYS_ENABLED", "TRUE").upper() == "TRUE"
PRE_BEAR_ALLOW_RECOVERY_BUY_SCORE = int(os.getenv("PRE_BEAR_ALLOW_RECOVERY_BUY_SCORE", "24"))
PRE_BEAR_STATE = {}

# v23: Deep Extension Flip
# Dopo TP8 / drop enorme il bot smette di vendere il minimo e aumenta la priorità
# del recovery BUY. I SELL possono riarmarsi solo dopo un rimbalzo reale.
DEEP_EXTENSION_FLIP_ENABLED = os.getenv("DEEP_EXTENSION_FLIP_ENABLED", "TRUE").upper() == "TRUE"
DEEP_EXTENSION_TP_LEVEL = int(os.getenv("DEEP_EXTENSION_TP_LEVEL", "8"))
DEEP_EXTENSION_SELL_COUNT = int(os.getenv("DEEP_EXTENSION_SELL_COUNT", "1"))
DEEP_EXTENSION_LOOKBACK_SECONDS = int(os.getenv("DEEP_EXTENSION_LOOKBACK_SECONDS", "7200"))
DEEP_EXTENSION_MIN_DROP_POINTS = float(os.getenv("DEEP_EXTENSION_MIN_DROP_POINTS", "35"))
DEEP_EXTENSION_LOW_POSITION_MAX = float(os.getenv("DEEP_EXTENSION_LOW_POSITION_MAX", "0.28"))
DEEP_EXTENSION_NEAR_LOW_POINTS = float(os.getenv("DEEP_EXTENSION_NEAR_LOW_POINTS", "10"))
DEEP_EXTENSION_REARM_REBOUND_POINTS = float(os.getenv("DEEP_EXTENSION_REARM_REBOUND_POINTS", "3.5"))
DEEP_EXTENSION_BLOCK_LOW_SELLS = os.getenv("DEEP_EXTENSION_BLOCK_LOW_SELLS", "TRUE").upper() == "TRUE"
DEEP_EXTENSION_RECOVERY_BONUS = int(os.getenv("DEEP_EXTENSION_RECOVERY_BONUS", "8"))
DEEP_EXTENSION_SELL_PENALTY = int(os.getenv("DEEP_EXTENSION_SELL_PENALTY", "10"))

DEEP_EXTENSION_ALWAYS_ALLOW_SELL_SETUPS = {
    "MAX_VIEW_SELL",
    "MAX_FAILED_RETEST_SELL",
    "SYNTHETIC_FAILED_RETEST_SELL",
    "MAX_EVENT_SPIKE_SELL",
    "MAX_FADE_SELL",
    "PRE_BEAR_SELL"
}

# v24: Persistent Runtime State
# Salva la memoria di mercato costruita dai PRICE_UPDATE.
# Per sopravvivere a un deploy/restart su Render, RUNTIME_STATE_FILE deve puntare
# a uno storage realmente persistente. Se il file non sopravvive, interviene il warmup.
RUNTIME_STATE_ENABLED = os.getenv("RUNTIME_STATE_ENABLED", "TRUE").upper() == "TRUE"
RUNTIME_STATE_FILE = os.getenv("RUNTIME_STATE_FILE", "runtime_state.json")
RUNTIME_STATE_MAX_AGE_SECONDS = int(os.getenv("RUNTIME_STATE_MAX_AGE_SECONDS", "21600"))
RUNTIME_STATE_SAVE_INTERVAL_SECONDS = int(os.getenv("RUNTIME_STATE_SAVE_INTERVAL_SECONDS", "15"))

# v24: Cold Start Warmup
STATE_WARMUP_ENABLED = os.getenv("STATE_WARMUP_ENABLED", "TRUE").upper() == "TRUE"
STATE_WARMUP_SECONDS = int(os.getenv("STATE_WARMUP_SECONDS", "900"))
STATE_WARMUP_MIN_PRICE_UPDATES = int(os.getenv("STATE_WARMUP_MIN_PRICE_UPDATES", "20"))
STATE_WARMUP_NORMAL_SELL_MIN_SCORE = int(os.getenv("STATE_WARMUP_NORMAL_SELL_MIN_SCORE", "10"))
STATE_WARMUP_BLOCK_AUTONOMOUS = os.getenv("STATE_WARMUP_BLOCK_AUTONOMOUS", "TRUE").upper() == "TRUE"

# v24: Trigger Maturity per Bear Continuation
# Non vende più il primo micro-cedimento dopo il rally peak.
BEAR_RALLY_PEAK_STABILITY_SECONDS = int(os.getenv("BEAR_RALLY_PEAK_STABILITY_SECONDS", "90"))
BEAR_CONTINUATION_DYNAMIC_FAILURE_ENABLED = os.getenv("BEAR_CONTINUATION_DYNAMIC_FAILURE_ENABLED", "TRUE").upper() == "TRUE"
BEAR_CONTINUATION_FAILURE_MIN_POINTS = float(os.getenv("BEAR_CONTINUATION_FAILURE_MIN_POINTS", "4.0"))
BEAR_CONTINUATION_FAILURE_ATR_MULT = float(os.getenv("BEAR_CONTINUATION_FAILURE_ATR_MULT", "0.8"))
BEAR_CONTINUATION_MIN_CONFIRMATIONS = int(os.getenv("BEAR_CONTINUATION_MIN_CONFIRMATIONS", "2"))
BEAR_CONTINUATION_MICRO_BOS_REQUIRED = os.getenv("BEAR_CONTINUATION_MICRO_BOS_REQUIRED", "TRUE").upper() == "TRUE"

# v24: Trigger Maturity anche per Event Failed Retest
SYNTHETIC_RETEST_PEAK_STABILITY_SECONDS = int(os.getenv("SYNTHETIC_RETEST_PEAK_STABILITY_SECONDS", "90"))
SYNTHETIC_RETEST_DYNAMIC_FAILURE_ENABLED = os.getenv("SYNTHETIC_RETEST_DYNAMIC_FAILURE_ENABLED", "TRUE").upper() == "TRUE"
SYNTHETIC_RETEST_FAILURE_MIN_POINTS = float(os.getenv("SYNTHETIC_RETEST_FAILURE_MIN_POINTS", "4.0"))
SYNTHETIC_RETEST_FAILURE_ATR_MULT = float(os.getenv("SYNTHETIC_RETEST_FAILURE_ATR_MULT", "0.8"))
SYNTHETIC_RETEST_MIN_CONFIRMATIONS = int(os.getenv("SYNTHETIC_RETEST_MIN_CONFIRMATIONS", "2"))
SYNTHETIC_RETEST_MICRO_BOS_REQUIRED = os.getenv("SYNTHETIC_RETEST_MICRO_BOS_REQUIRED", "TRUE").upper() == "TRUE"

# v24: Micro Break of Structure M1
MICRO_BOS_LOOKBACK_UPDATES = int(os.getenv("MICRO_BOS_LOOKBACK_UPDATES", "5"))
MICRO_BOS_BUFFER_POINTS = float(os.getenv("MICRO_BOS_BUFFER_POINTS", "0.1"))

# v25: Regime Arbiter
# Un arbitro centrale decide quale tesi domina ADESSO.
REGIME_ARBITER_ENABLED = os.getenv("REGIME_ARBITER_ENABLED", "TRUE").upper() == "TRUE"

REGIME_MATURITY_REQUIRED_SETUPS = {
    "BEAR_CAMPAIGN_SELL",
    "BEAR_CONTINUATION_SELL",
    "SYNTHETIC_BEAR_CONTINUATION_SELL"
}

# v26: Special BUY Dominance
# Non protegge più solo MAX_RECOVERY_BUY.
# Se un BUY speciale funziona, il bot non lo combatte con SELL deboli o prematuri.
RECOVERY_DOMINANCE_ENABLED = os.getenv("RECOVERY_DOMINANCE_ENABLED", "TRUE").upper() == "TRUE"
RECOVERY_DOMINANCE_MIN_TP = int(os.getenv("RECOVERY_DOMINANCE_MIN_TP", "3"))
RECOVERY_DOMINANCE_LOOKBACK_SECONDS = int(os.getenv("RECOVERY_DOMINANCE_LOOKBACK_SECONDS", "7200"))
RECOVERY_DOMINANCE_INVALIDATION_BUFFER = float(os.getenv("RECOVERY_DOMINANCE_INVALIDATION_BUFFER", "2.5"))
RECOVERY_DOMINANCE_SETUPS = {
    "MAX_RECOVERY_BUY",
    "MAX_PULLBACK_REARM_BUY",
    "MAX_FLIP_BUY",
    "DEEP_REBOUND_BUY",
    "MAX_DIP_BUY",
    "REVERSAL_BUY"
}
RECOVERY_DOMINANCE_BLOCK_SELL_SETUPS = {
    "BEAR_CAMPAIGN_SELL",
    "BEAR_CONTINUATION_SELL",
    "SYNTHETIC_BEAR_CONTINUATION_SELL"
}

# v26: protezione più precoce contro SELL NORMAL.
# Default 0 = blocca SELL NORMAL anche se il BUY speciale è appena OPEN
# e non ha ancora preso TP1. Serve per evitare BUY buono + SELL normale debole.
SPECIAL_BUY_NORMAL_SELL_MIN_TP = int(os.getenv("SPECIAL_BUY_NORMAL_SELL_MIN_TP", "0"))
SPECIAL_BUY_BLOCK_NORMAL_SELL = os.getenv("SPECIAL_BUY_BLOCK_NORMAL_SELL", "TRUE").upper() == "TRUE"

# Un SELL contro un BUY speciale attivo passa solo se è veramente da zona Max:
# setup speciale, score alto, zona alta e micro-BOS.
SPECIAL_BUY_COUNTER_SELL_MIN_SCORE = int(os.getenv("SPECIAL_BUY_COUNTER_SELL_MIN_SCORE", "22"))
SPECIAL_BUY_COUNTER_SELL_REQUIRE_ZONE = os.getenv("SPECIAL_BUY_COUNTER_SELL_REQUIRE_ZONE", "TRUE").upper() == "TRUE"
SPECIAL_BUY_COUNTER_SELL_REQUIRE_MICRO_BOS = os.getenv("SPECIAL_BUY_COUNTER_SELL_REQUIRE_MICRO_BOS", "TRUE").upper() == "TRUE"
SPECIAL_BUY_COUNTER_SELL_ALLOWED_SETUPS = {
    "PRE_BEAR_SELL",
    "MAX_FADE_SELL",
    "MAX_VIEW_SELL",
    "MAX_FAILED_RETEST_SELL",
    "SYNTHETIC_FAILED_RETEST_SELL",
    "BEAR_CAMPAIGN_SELL",
    "BEAR_CONTINUATION_SELL",
    "SYNTHETIC_BEAR_CONTINUATION_SELL"
}

# v26: Max Zone Gate per SELL NORMAL.
# I SELL NORMAL non devono nascere nel mezzo: o sono su zona alta/rejection,
# oppure restano bloccati.
MAX_ZONE_SELL_GATE_ENABLED = os.getenv("MAX_ZONE_SELL_GATE_ENABLED", "TRUE").upper() == "TRUE"
MAX_ZONE_SELL_MIN_SCORE = int(os.getenv("MAX_ZONE_SELL_MIN_SCORE", "8"))
MAX_ZONE_SELL_REQUIRE_HIGH_ZONE = os.getenv("MAX_ZONE_SELL_REQUIRE_HIGH_ZONE", "TRUE").upper() == "TRUE"
MAX_ZONE_SELL_SETUPS = {
    "NORMAL"
}

# v27: Trade Compression / Sell Profit Lock
# Quando la view SELL ha già pagato molto, il bot smette di spezzare
# la stessa idea in troppi SELL consecutivi. Rientra solo su nuova zona Max
# o su continuation/campaign veramente riarmata.
SELL_PROFIT_LOCK_ENABLED = os.getenv("SELL_PROFIT_LOCK_ENABLED", "TRUE").upper() == "TRUE"
SELL_PROFIT_LOCK_TP_LEVEL = int(os.getenv("SELL_PROFIT_LOCK_TP_LEVEL", "8"))
SELL_PROFIT_LOCK_TP5_LEVEL = int(os.getenv("SELL_PROFIT_LOCK_TP5_LEVEL", "5"))
SELL_PROFIT_LOCK_TP5_COUNT = int(os.getenv("SELL_PROFIT_LOCK_TP5_COUNT", "2"))
SELL_PROFIT_LOCK_LOOKBACK_SECONDS = int(os.getenv("SELL_PROFIT_LOCK_LOOKBACK_SECONDS", "7200"))
SELL_PROFIT_LOCK_SECONDS = int(os.getenv("SELL_PROFIT_LOCK_SECONDS", "5400"))
SELL_PROFIT_LOCK_REARM_REBOUND_POINTS = float(os.getenv("SELL_PROFIT_LOCK_REARM_REBOUND_POINTS", "15"))

# Cosa bloccare dopo che il SELL ha già pagato.
SELL_PROFIT_LOCK_BLOCK_NORMAL = os.getenv("SELL_PROFIT_LOCK_BLOCK_NORMAL", "TRUE").upper() == "TRUE"
SELL_PROFIT_LOCK_BLOCK_SYNTHETIC = os.getenv("SELL_PROFIT_LOCK_BLOCK_SYNTHETIC", "TRUE").upper() == "TRUE"

# Eccezioni controllate: nuove vendite consentite solo se davvero in zona Max.
SELL_PROFIT_LOCK_ALLOW_MAX_FADE_SCORE = int(os.getenv("SELL_PROFIT_LOCK_ALLOW_MAX_FADE_SCORE", "18"))
SELL_PROFIT_LOCK_ALLOW_PRE_BEAR_SCORE = int(os.getenv("SELL_PROFIT_LOCK_ALLOW_PRE_BEAR_SCORE", "20"))
SELL_PROFIT_LOCK_ALLOW_CAMPAIGN_SCORE = int(os.getenv("SELL_PROFIT_LOCK_ALLOW_CAMPAIGN_SCORE", "22"))
SELL_PROFIT_LOCK_REQUIRE_MICRO_BOS = os.getenv("SELL_PROFIT_LOCK_REQUIRE_MICRO_BOS", "TRUE").upper() == "TRUE"
SELL_PROFIT_LOCK_REQUIRE_MAX_ZONE = os.getenv("SELL_PROFIT_LOCK_REQUIRE_MAX_ZONE", "TRUE").upper() == "TRUE"

# v28: Loss Recovery + True Max Zone Re-entry
# Dopo 2 SL SELL diretti il bot non deve vendere il primo rimbalzo medio.
# Deve aspettare una zona premium vera, come Max: rimbalzo ampio, day position alta,
# rejection / high context e micro-BOS.
LOSS_RECOVERY_TRUE_MAX_ZONE_ENABLED = os.getenv("LOSS_RECOVERY_TRUE_MAX_ZONE_ENABLED", "TRUE").upper() == "TRUE"
LOSS_RECOVERY_SELL_LOSSES = int(os.getenv("LOSS_RECOVERY_SELL_LOSSES", "2"))
LOSS_RECOVERY_LOOKBACK_SECONDS = int(os.getenv("LOSS_RECOVERY_LOOKBACK_SECONDS", "7200"))
TRUE_MAX_ZONE_MIN_DAY_POSITION = float(os.getenv("TRUE_MAX_ZONE_MIN_DAY_POSITION", "0.85"))
TRUE_MAX_ZONE_MIN_REBOUND_POINTS = float(os.getenv("TRUE_MAX_ZONE_MIN_REBOUND_POINTS", "25"))
TRUE_MAX_ZONE_MIN_SCORE = int(os.getenv("TRUE_MAX_ZONE_MIN_SCORE", "22"))
TRUE_MAX_ZONE_REQUIRE_MICRO_BOS = os.getenv("TRUE_MAX_ZONE_REQUIRE_MICRO_BOS", "TRUE").upper() == "TRUE"
TRUE_MAX_ZONE_REQUIRE_REJECTION = os.getenv("TRUE_MAX_ZONE_REQUIRE_REJECTION", "TRUE").upper() == "TRUE"
TRUE_MAX_ZONE_ALLOWED_SETUPS = {
    "PRE_BEAR_SELL",
    "BEAR_CAMPAIGN_SELL",
    "BEAR_CONTINUATION_SELL",
    "MAX_FADE_SELL",
    "MAX_VIEW_SELL",
    "MAX_FAILED_RETEST_SELL",
    "SYNTHETIC_FAILED_RETEST_SELL",
    "MAX_EVENT_SPIKE_SELL",
    "EXTREME_SPIKE_FADE_SELL"
}

# v28: Big Move Thesis Engine.
# Non predice con certezza le news; segnala solo quando ci sono condizioni da
# movimento grosso: trade già protetto, TP3+, evento/news/volatilità, compressione
# o breakout e target psicologico libero.
BIG_MOVE_THESIS_ENABLED = os.getenv("BIG_MOVE_THESIS_ENABLED", "TRUE").upper() == "TRUE"
BIG_MOVE_ALERTS_ENABLED = os.getenv("BIG_MOVE_ALERTS_ENABLED", "TRUE").upper() == "TRUE"
BIG_MOVE_MIN_TP_LEVEL = int(os.getenv("BIG_MOVE_MIN_TP_LEVEL", "3"))
BIG_MOVE_CONFIRMED_TP_LEVEL = int(os.getenv("BIG_MOVE_CONFIRMED_TP_LEVEL", "5"))
BIG_MOVE_LOOKBACK_SECONDS = int(os.getenv("BIG_MOVE_LOOKBACK_SECONDS", "7200"))
BIG_MOVE_ALERT_COOLDOWN_SECONDS = int(os.getenv("BIG_MOVE_ALERT_COOLDOWN_SECONDS", "1800"))
BIG_MOVE_MIN_CONFLUENCES = int(os.getenv("BIG_MOVE_MIN_CONFLUENCES", "4"))
BIG_MOVE_REQUIRE_BE_PROTECTED = os.getenv("BIG_MOVE_REQUIRE_BE_PROTECTED", "TRUE").upper() == "TRUE"
BIG_MOVE_EVENT_OR_NEWS_REQUIRED = os.getenv("BIG_MOVE_EVENT_OR_NEWS_REQUIRED", "FALSE").upper() == "TRUE"
BIG_MOVE_COMPRESSION_MAX_M15_ATR = float(os.getenv("BIG_MOVE_COMPRESSION_MAX_M15_ATR", "1.8"))
BIG_MOVE_BREAKOUT_M15_ATR = float(os.getenv("BIG_MOVE_BREAKOUT_M15_ATR", "3.0"))
BIG_MOVE_TARGET_STEP = float(os.getenv("BIG_MOVE_TARGET_STEP", "20"))
BIG_MOVE_TARGET_COUNT = int(os.getenv("BIG_MOVE_TARGET_COUNT", "3"))
BIG_MOVE_SPECIAL_SETUPS = {
    "MAX_RECOVERY_BUY",
    "MAX_PULLBACK_REARM_BUY",
    "MAX_FLIP_BUY",
    "DEEP_REBOUND_BUY",
    "MAX_DIP_BUY",
    "REVERSAL_BUY",
    "PRE_BEAR_SELL",
    "BEAR_CAMPAIGN_SELL",
    "BEAR_CONTINUATION_SELL",
    "MAX_FADE_SELL",
    "MAX_VIEW_SELL",
    "MAX_FAILED_RETEST_SELL",
    "SYNTHETIC_FAILED_RETEST_SELL",
    "MAX_EVENT_SPIKE_SELL",
    "EXTREME_SPIKE_FADE_SELL"
}

# v29: Event Trap Flip / Big Move Direction Flip.
# Se il bot è innamorato di un BUY recovery già a TP5/TP6 ma l'evento crea spike alto
# e compare un SELL A+ da vera zona Max, può FLIPPARE la tesi e non bloccare il SELL.
EVENT_TRAP_FLIP_ENABLED = os.getenv("EVENT_TRAP_FLIP_ENABLED", "TRUE").upper() == "TRUE"
EVENT_TRAP_FLIP_MIN_SCORE = int(os.getenv("EVENT_TRAP_FLIP_MIN_SCORE", "24"))
EVENT_TRAP_FLIP_MIN_BUY_TP = int(os.getenv("EVENT_TRAP_FLIP_MIN_BUY_TP", "5"))
EVENT_TRAP_FLIP_REQUIRE_EVENT = os.getenv("EVENT_TRAP_FLIP_REQUIRE_EVENT", "TRUE").upper() == "TRUE"
EVENT_TRAP_FLIP_REQUIRE_ZONE = os.getenv("EVENT_TRAP_FLIP_REQUIRE_ZONE", "TRUE").upper() == "TRUE"
EVENT_TRAP_FLIP_REQUIRE_REJECTION = os.getenv("EVENT_TRAP_FLIP_REQUIRE_REJECTION", "FALSE").upper() == "TRUE"
EVENT_TRAP_FLIP_REQUIRE_MICRO_OR_BREAKDOWN = os.getenv("EVENT_TRAP_FLIP_REQUIRE_MICRO_OR_BREAKDOWN", "FALSE").upper() == "TRUE"
EVENT_TRAP_FLIP_MIN_RETRACE_FROM_HIGH = float(os.getenv("EVENT_TRAP_FLIP_MIN_RETRACE_FROM_HIGH", "2.5"))
EVENT_TRAP_FLIP_MAX_EVENT_CLOSE_POSITION = float(os.getenv("EVENT_TRAP_FLIP_MAX_EVENT_CLOSE_POSITION", "0.62"))
EVENT_TRAP_FLIP_ALLOWED_SETUPS = {
    "PRE_BEAR_SELL",
    "MAX_FADE_SELL",
    "MAX_VIEW_SELL",
    "MAX_FAILED_RETEST_SELL",
    "SYNTHETIC_FAILED_RETEST_SELL",
    "BEAR_CAMPAIGN_SELL",
    "BEAR_CONTINUATION_SELL",
    "SYNTHETIC_BEAR_CONTINUATION_SELL",
    "MAX_EVENT_SPIKE_SELL",
    "EXTREME_SPIKE_FADE_SELL"
}

# v31: Max Flip Window.
# Caso reale 27/07: BUY speciale a TP3/TP5, poi Max flippa SELL 4049-4054.
# La v30 proteggeva troppo il BUY; qui autorizziamo solo un SELL speciale,
# da zona alta/rejection/evento, con score più umano e non necessariamente micro-BOS.
SPECIAL_BUY_FLIP_WINDOW_ENABLED = os.getenv("SPECIAL_BUY_FLIP_WINDOW_ENABLED", "TRUE").upper() == "TRUE"
SPECIAL_BUY_FLIP_MIN_SCORE = int(os.getenv("SPECIAL_BUY_FLIP_MIN_SCORE", "19"))
SPECIAL_BUY_FLIP_MIN_BUY_TP = int(os.getenv("SPECIAL_BUY_FLIP_MIN_BUY_TP", "3"))
SPECIAL_BUY_FLIP_MAX_BUY_TP = int(os.getenv("SPECIAL_BUY_FLIP_MAX_BUY_TP", "6"))
SPECIAL_BUY_FLIP_REQUIRE_EVENT_OR_REJECTION = os.getenv("SPECIAL_BUY_FLIP_REQUIRE_EVENT_OR_REJECTION", "TRUE").upper() == "TRUE"
SPECIAL_BUY_FLIP_MIN_EVENT_CLOSE_POSITION = float(os.getenv("SPECIAL_BUY_FLIP_MIN_EVENT_CLOSE_POSITION", "0.75"))
SPECIAL_BUY_FLIP_REQUIRE_ZONE = os.getenv("SPECIAL_BUY_FLIP_REQUIRE_ZONE", "TRUE").upper() == "TRUE"
SPECIAL_BUY_FLIP_REQUIRE_MICRO_BOS = os.getenv("SPECIAL_BUY_FLIP_REQUIRE_MICRO_BOS", "FALSE").upper() == "TRUE"
SPECIAL_BUY_FLIP_ALLOWED_SETUPS = {
    "PRE_BEAR_SELL",
    "MAX_FADE_SELL",
    "MAX_VIEW_SELL",
    "MAX_FAILED_RETEST_SELL",
    "SYNTHETIC_FAILED_RETEST_SELL",
    "MAX_EVENT_SPIKE_SELL",
    "EXTREME_SPIKE_FADE_SELL"
}

# v32: Max Rebound Buy Unlock.
# Dopo un SELL già molto pagato (TP6/TP7/TP8 o runner), Max spesso compra il rimbalzo da zona low.
# Non compra ogni minimo: serve discesa profonda recente + prezzo vicino ai low/psicologico + conferme minime.
POST_SELL_REBOUND_UNLOCK_ENABLED = os.getenv("POST_SELL_REBOUND_UNLOCK_ENABLED", "TRUE").upper() == "TRUE"
POST_SELL_REBOUND_MIN_SCORE = int(os.getenv("POST_SELL_REBOUND_MIN_SCORE", "11"))
POST_SELL_REBOUND_MIN_SELL_TP = int(os.getenv("POST_SELL_REBOUND_MIN_SELL_TP", "6"))
POST_SELL_REBOUND_LOOKBACK_SECONDS = int(os.getenv("POST_SELL_REBOUND_LOOKBACK_SECONDS", "7200"))
POST_SELL_REBOUND_MIN_IMPULSE_DROP = float(os.getenv("POST_SELL_REBOUND_MIN_IMPULSE_DROP", "18"))
POST_SELL_REBOUND_MAX_DISTANCE_FROM_LOW = float(os.getenv("POST_SELL_REBOUND_MAX_DISTANCE_FROM_LOW", "7"))
POST_SELL_REBOUND_ALLOWED_SETUPS = {
    "MAX_RECOVERY_BUY",
    "MAX_PULLBACK_REARM_BUY",
    "MAX_FLIP_BUY",
    "DEEP_REBOUND_BUY",
    "MAX_DIP_BUY",
    "REVERSAL_BUY",
    "DEEP_REBOUND_BUY"
}

# v32: setup BUY speciale costruito dal server quando il Pine manda un BUY normale
# dentro una gamba ribassista già pagata. Serve per non perdere il rimbalzo 4020/4017
# dopo un SELL profondo stile Max, ma resta bloccato se siamo lontani dal low o troppo alti.
DEEP_REBOUND_BUY_ENABLED = os.getenv("DEEP_REBOUND_BUY_ENABLED", "TRUE").upper() == "TRUE"
DEEP_REBOUND_BUY_BASE_BONUS = int(os.getenv("DEEP_REBOUND_BUY_BASE_BONUS", "18"))
DEEP_REBOUND_BUY_MIN_SELL_TP = int(os.getenv("DEEP_REBOUND_BUY_MIN_SELL_TP", "6"))
DEEP_REBOUND_BUY_LOOKBACK_SECONDS = int(os.getenv("DEEP_REBOUND_BUY_LOOKBACK_SECONDS", "7200"))
DEEP_REBOUND_BUY_MIN_IMPULSE_DROP = float(os.getenv("DEEP_REBOUND_BUY_MIN_IMPULSE_DROP", "18"))
DEEP_REBOUND_BUY_MAX_DISTANCE_FROM_LOW = float(os.getenv("DEEP_REBOUND_BUY_MAX_DISTANCE_FROM_LOW", "7"))
DEEP_REBOUND_BUY_MAX_DAY_POSITION = float(os.getenv("DEEP_REBOUND_BUY_MAX_DAY_POSITION", "0.38"))
DEEP_REBOUND_BUY_MIN_CONFIRMATIONS = int(os.getenv("DEEP_REBOUND_BUY_MIN_CONFIRMATIONS", "2"))
DEEP_REBOUND_BUY_REQUIRE_BULLISH_NEWS = os.getenv("DEEP_REBOUND_BUY_REQUIRE_BULLISH_NEWS", "TRUE").upper() == "TRUE"

# v33: Max Flip BUY dopo SELL pagato/BE.
# Caso reale 30/07: Max chiude/gestisce SELL, poi compra il recupero 4052-4047.
# Questa logica NON tocca la strategia base: è un generatore autonomo solo su PRICE_UPDATE,
# dopo SELL già protetto e invalidato al rialzo.
MAX_FLIP_BUY_AFTER_SELL_BE_ENABLED = os.getenv("MAX_FLIP_BUY_AFTER_SELL_BE_ENABLED", "TRUE").upper() == "TRUE"
MAX_FLIP_BUY_AFTER_SELL_BE_LOOKBACK_SECONDS = int(os.getenv("MAX_FLIP_BUY_AFTER_SELL_BE_LOOKBACK_SECONDS", "5400"))
MAX_FLIP_BUY_AFTER_SELL_BE_MIN_SELL_TP = int(os.getenv("MAX_FLIP_BUY_AFTER_SELL_BE_MIN_SELL_TP", "1"))
MAX_FLIP_BUY_AFTER_SELL_BE_MIN_SCORE = int(os.getenv("MAX_FLIP_BUY_AFTER_SELL_BE_MIN_SCORE", "12"))
MAX_FLIP_BUY_AFTER_SELL_BE_INVALIDATION_POINTS = float(os.getenv("MAX_FLIP_BUY_AFTER_SELL_BE_INVALIDATION_POINTS", "2.0"))
MAX_FLIP_BUY_AFTER_SELL_BE_MAX_DAY_POSITION = float(os.getenv("MAX_FLIP_BUY_AFTER_SELL_BE_MAX_DAY_POSITION", "0.72"))
MAX_FLIP_BUY_AFTER_SELL_BE_MIN_CONFIRMATIONS = int(os.getenv("MAX_FLIP_BUY_AFTER_SELL_BE_MIN_CONFIRMATIONS", "3"))
MAX_FLIP_BUY_AFTER_SELL_BE_COOLDOWN_SECONDS = int(os.getenv("MAX_FLIP_BUY_AFTER_SELL_BE_COOLDOWN_SECONDS", "2400"))
MAX_FLIP_BUY_AFTER_SELL_BE_ENTRY_HALF_ZONE = float(os.getenv("MAX_FLIP_BUY_AFTER_SELL_BE_ENTRY_HALF_ZONE", "3.0"))
MAX_FLIP_BUY_AFTER_SELL_BE_SL_POINTS = float(os.getenv("MAX_FLIP_BUY_AFTER_SELL_BE_SL_POINTS", "12.0"))
MAX_FLIP_BUY_AFTER_SELL_BE_REQUIRE_BULLISH_CONTEXT = os.getenv("MAX_FLIP_BUY_AFTER_SELL_BE_REQUIRE_BULLISH_CONTEXT", "TRUE").upper() == "TRUE"
MAX_FLIP_BUY_AFTER_SELL_BE_REQUIRE_RECOVERY_ABOVE_SELL = os.getenv("MAX_FLIP_BUY_AFTER_SELL_BE_REQUIRE_RECOVERY_ABOVE_SELL", "TRUE").upper() == "TRUE"
MAX_FLIP_BUY_AFTER_SELL_BE_TP_DISTANCES = [6, 8, 11, 14, 17, 19, 22, 26]
MAX_FLIP_BUY_AFTER_SELL_BE_SETUPS_TO_FLIP = {
    "BEAR_CAMPAIGN_SELL",
    "BEAR_CONTINUATION_SELL",
    "SYNTHETIC_BEAR_CONTINUATION_SELL",
    "MAX_FADE_SELL",
    "MAX_FAILED_RETEST_SELL",
    "SYNTHETIC_FAILED_RETEST_SELL",
    "NORMAL"
}

# v33: Runner virtuale.
# Se un trade TP2/TP3+ si chiude a BE, la tesi resta viva per permettere flip/re-entry.
VIRTUAL_RUNNER_ENABLED = os.getenv("VIRTUAL_RUNNER_ENABLED", "TRUE").upper() == "TRUE"
VIRTUAL_RUNNER_MIN_TP = int(os.getenv("VIRTUAL_RUNNER_MIN_TP", "2"))
VIRTUAL_RUNNER_LOOKBACK_SECONDS = int(os.getenv("VIRTUAL_RUNNER_LOOKBACK_SECONDS", "7200"))
VIRTUAL_RUNNER_STATE = {}

# v34: Master Regime / One Direction Control.
# Obiettivo: leggere la giornata prima del singolo segnale.
# Se il mercato passa in SELL_CONTROL, il bot smette di comprare ogni rimbalzo
# e il FAST può lavorare solo nella direzione dominante.
# Le variabili restano nel codice: se su Render non puoi aggiungerle, i default qui sotto sono già attivi.
MASTER_REGIME_ENABLED = os.getenv("MASTER_REGIME_ENABLED", "TRUE").upper() == "TRUE"
MASTER_REGIME_PRICE_DOMINATES_NEWS = os.getenv("MASTER_REGIME_PRICE_DOMINATES_NEWS", "TRUE").upper() == "TRUE"
MASTER_REGIME_SELL_CONTROL_BEAR_VOTES = int(os.getenv("MASTER_REGIME_SELL_CONTROL_BEAR_VOTES", "5"))
MASTER_REGIME_BUY_CONTROL_BULL_VOTES = int(os.getenv("MASTER_REGIME_BUY_CONTROL_BULL_VOTES", "6"))
MASTER_REGIME_BUY_LOCK_DIRECT_SL = int(os.getenv("MASTER_REGIME_BUY_LOCK_DIRECT_SL", "2"))
MASTER_REGIME_BUY_LOCK_LOOKBACK_SECONDS = int(os.getenv("MASTER_REGIME_BUY_LOCK_LOOKBACK_SECONDS", "7200"))
MASTER_REGIME_SELL_SCORE_BONUS = int(os.getenv("MASTER_REGIME_SELL_SCORE_BONUS", "6"))
MASTER_REGIME_NORMAL_SELL_EXTRA_BONUS = int(os.getenv("MASTER_REGIME_NORMAL_SELL_EXTRA_BONUS", "2"))
MASTER_REGIME_BLOCK_BUY_SCORE_PENALTY = int(os.getenv("MASTER_REGIME_BLOCK_BUY_SCORE_PENALTY", "14"))
MASTER_REGIME_ALLOW_NORMAL_SELL_IN_SELL_CONTROL = os.getenv("MASTER_REGIME_ALLOW_NORMAL_SELL_IN_SELL_CONTROL", "TRUE").upper() == "TRUE"
MASTER_REGIME_SELL_CONTROL_NORMAL_MIN_SCORE = int(os.getenv("MASTER_REGIME_SELL_CONTROL_NORMAL_MIN_SCORE", "6"))
MASTER_REGIME_SELL_CONTROL_SPECIAL_MIN_SCORE = int(os.getenv("MASTER_REGIME_SELL_CONTROL_SPECIAL_MIN_SCORE", "19"))
MASTER_REGIME_ALLOW_SELL_AFTER_BUY_FAILURE = os.getenv("MASTER_REGIME_ALLOW_SELL_AFTER_BUY_FAILURE", "TRUE").upper() == "TRUE"
MASTER_REGIME_BLOCK_BUY_IN_SELL_CONTROL = os.getenv("MASTER_REGIME_BLOCK_BUY_IN_SELL_CONTROL", "TRUE").upper() == "TRUE"
MASTER_REGIME_REBOUND_BUY_MIN_SELL_TP = int(os.getenv("MASTER_REGIME_REBOUND_BUY_MIN_SELL_TP", "6"))
MASTER_REGIME_REBOUND_BUY_LOOKBACK_SECONDS = int(os.getenv("MASTER_REGIME_REBOUND_BUY_LOOKBACK_SECONDS", "7200"))
MASTER_REGIME_REBOUND_BUY_MAX_DISTANCE_FROM_LOW = float(os.getenv("MASTER_REGIME_REBOUND_BUY_MAX_DISTANCE_FROM_LOW", "8.0"))
MASTER_REGIME_REBOUND_BUY_MAX_DAY_POSITION = float(os.getenv("MASTER_REGIME_REBOUND_BUY_MAX_DAY_POSITION", "0.38"))
MASTER_REGIME_REBOUND_BUY_MIN_SCORE = int(os.getenv("MASTER_REGIME_REBOUND_BUY_MIN_SCORE", "16"))
MASTER_REGIME_BLOCK_COUNTER_SELL_IN_BUY_CONTROL = os.getenv("MASTER_REGIME_BLOCK_COUNTER_SELL_IN_BUY_CONTROL", "TRUE").upper() == "TRUE"
MASTER_REGIME_BUY_CONTROL_COUNTER_SELL_MIN_SCORE = int(os.getenv("MASTER_REGIME_BUY_CONTROL_COUNTER_SELL_MIN_SCORE", "22"))
MASTER_REGIME_FAST_FOLLOWS_MASTER = os.getenv("MASTER_REGIME_FAST_FOLLOWS_MASTER", "TRUE").upper() == "TRUE"
MASTER_REGIME_FAST_ALLOW_REBOUND_BUY = os.getenv("MASTER_REGIME_FAST_ALLOW_REBOUND_BUY", "TRUE").upper() == "TRUE"
MASTER_REGIME_MAX_BUY_DIRECT_SL_BEFORE_CHAOS = int(os.getenv("MASTER_REGIME_MAX_BUY_DIRECT_SL_BEFORE_CHAOS", "3"))
MASTER_REGIME_MAX_SELL_DIRECT_SL_BEFORE_CHAOS = int(os.getenv("MASTER_REGIME_MAX_SELL_DIRECT_SL_BEFORE_CHAOS", "3"))
MASTER_REGIME_LOW_POSITION_SELL_SKIP_GUARD = float(os.getenv("MASTER_REGIME_LOW_POSITION_SELL_SKIP_GUARD", "0.20"))
MASTER_REGIME_TRUE_REBOUND_FOR_NEW_SELL = float(os.getenv("MASTER_REGIME_TRUE_REBOUND_FOR_NEW_SELL", "6.0"))

MASTER_REGIME_SELL_SPECIAL_SETUPS = {
    "PRE_BEAR_SELL",
    "BEAR_CAMPAIGN_SELL",
    "BEAR_CONTINUATION_SELL",
    "SYNTHETIC_BEAR_CONTINUATION_SELL",
    "SYNTHETIC_FAILED_RETEST_SELL",
    "MAX_FAILED_RETEST_SELL",
    "MAX_EVENT_SPIKE_SELL",
    "EXTREME_SPIKE_FADE_SELL",
    "MAX_VIEW_SELL",
    "MAX_FADE_SELL",
    "REVERSAL_SELL",
    "MAX_DIP_SELL",
    "EXTREME_SPIKE_FADE_SELL"
}

MASTER_REGIME_REBOUND_BUY_SETUPS = {
    "MAX_FLIP_BUY",
    "MAX_PULLBACK_REARM_BUY",
    "DEEP_REBOUND_BUY",
    "MAX_RECOVERY_BUY"
}


# v29: non vendere basso con campaign/continuation deboli dopo un grande drop.
DEEP_EXTENSION_SELL_GUARD_ENABLED = os.getenv("DEEP_EXTENSION_SELL_GUARD_ENABLED", "TRUE").upper() == "TRUE"
DEEP_EXTENSION_SELL_GUARD_MIN_SCORE = int(os.getenv("DEEP_EXTENSION_SELL_GUARD_MIN_SCORE", "19"))
DEEP_EXTENSION_SELL_GUARD_MAX_DAY_POSITION = float(os.getenv("DEEP_EXTENSION_SELL_GUARD_MAX_DAY_POSITION", "0.35"))
DEEP_EXTENSION_SELL_GUARD_SETUPS = {
    "BEAR_CAMPAIGN_SELL",
    "BEAR_CONTINUATION_SELL",
    "SYNTHETIC_BEAR_CONTINUATION_SELL"
}

# Smart Daily Kill Switch Override per PRE_BEAR_SELL:
# una sola eccezione controllata, solo da zona estrema e con score alto.
SMART_KILL_PRE_BEAR_OVERRIDE_ENABLED = os.getenv("SMART_KILL_PRE_BEAR_OVERRIDE_ENABLED", "TRUE").upper() == "TRUE"
SMART_KILL_PRE_BEAR_MIN_SCORE = int(os.getenv("SMART_KILL_PRE_BEAR_MIN_SCORE", "20"))
SMART_KILL_PRE_BEAR_MAX_ATTEMPTS = int(os.getenv("SMART_KILL_PRE_BEAR_MAX_ATTEMPTS", "1"))
SMART_KILL_PRE_BEAR_RISK_WEIGHT = float(os.getenv("SMART_KILL_PRE_BEAR_RISK_WEIGHT", "0.25"))
SMART_KILL_PRE_BEAR_COOLDOWN_SECONDS = int(os.getenv("SMART_KILL_PRE_BEAR_COOLDOWN_SECONDS", "7200"))

# =========================
# v37: ANTI WHIPSAW + POST SL QUARANTINE
# =========================
# Obiettivo: evitare il caso visto su v36:
# BUY MAX_DIP preso in SL -> subito SELL NORMAL dal basso -> SL.
# Dopo uno SL diretto il bot non deve cambiare direzione in modo impulsivo.
# I default sono nel codice: se Render non ti fa aggiungere variabili nuove, funziona comunque.
POST_SL_QUARANTINE_ENABLED = os.getenv("POST_SL_QUARANTINE_ENABLED", "TRUE").upper() == "TRUE"
POST_SL_QUARANTINE_SECONDS = int(os.getenv("POST_SL_QUARANTINE_SECONDS", "1800"))  # 30 minuti
POST_SL_SAME_DIRECTION_SECONDS = int(os.getenv("POST_SL_SAME_DIRECTION_SECONDS", "900"))  # 15 minuti
POST_SL_BLOCK_NORMAL_OPPOSITE = os.getenv("POST_SL_BLOCK_NORMAL_OPPOSITE", "TRUE").upper() == "TRUE"
POST_SL_OPPOSITE_MIN_SCORE = int(os.getenv("POST_SL_OPPOSITE_MIN_SCORE", "20"))
POST_SL_REENTRY_MIN_SCORE = int(os.getenv("POST_SL_REENTRY_MIN_SCORE", "24"))
POST_SL_REQUIRE_MICRO_BOS = os.getenv("POST_SL_REQUIRE_MICRO_BOS", "TRUE").upper() == "TRUE"
POST_SL_REQUIRE_RETEST_ZONE = os.getenv("POST_SL_REQUIRE_RETEST_ZONE", "TRUE").upper() == "TRUE"
POST_SL_SELL_MIN_DAY_POSITION = float(os.getenv("POST_SL_SELL_MIN_DAY_POSITION", "0.45"))
POST_SL_BUY_MAX_DAY_POSITION = float(os.getenv("POST_SL_BUY_MAX_DAY_POSITION", "0.55"))

POST_SL_OPPOSITE_ALLOW_SETUPS = {
    "MAX_FADE_SELL",
    "MAX_VIEW_SELL",
    "MAX_FAILED_RETEST_SELL",
    "MAX_EVENT_SPIKE_SELL",
    "PRE_BEAR_SELL",
    "BEAR_CAMPAIGN_SELL",
    "BEAR_CONTINUATION_SELL",
    "SYNTHETIC_BEAR_CONTINUATION_SELL",
    "SYNTHETIC_FAILED_RETEST_SELL",
    "MAX_FLIP_BUY",
    "MAX_PULLBACK_REARM_BUY",
    "DEEP_REBOUND_BUY",
    "MAX_RECOVERY_BUY"
}

POST_SL_REENTRY_CAUTION_SETUPS = {
    "NORMAL",
    "MAX_DIP_BUY",
    "REVERSAL_BUY",
    "MAX_RECOVERY_BUY",
    "MAX_PULLBACK_REARM_BUY",
    "MAX_FADE_SELL",
    "REVERSAL_SELL",
    "MAX_DIP_SELL"
}

# =========================
# FAST SCALPER PARALLELO v1
# =========================
# Non modifica la strategia v29: è un secondo motore separato.
# Usa lo stesso Pine/TradingView, ma webhook separato: /webhook_fast
# TP piccolo: esempio BUY 4140 -> TP 4142.
FAST_VERSION = "Fast Scalper v12 Clean 2-Point + Daily Thesis"
FAST_ENGINE_ENABLED = os.getenv("FAST_ENGINE_ENABLED", "TRUE").upper() == "TRUE"
FAST_TRADES_FILE = os.getenv("FAST_TRADES_FILE", "fast_trades.json")
FAST_TP_POINTS = float(os.getenv("FAST_TP_POINTS", "2.0"))
FAST_SL_POINTS = max(float(os.getenv("FAST_SL_POINTS", "4.5")), 4.5)
FAST_ENTRY_OFFSET = float(os.getenv("FAST_ENTRY_OFFSET", "0.0"))
FAST_MIN_SCORE = int(os.getenv("FAST_MIN_SCORE", "7"))
FAST_MAX_ACTIVE_TRADES = int(os.getenv("FAST_MAX_ACTIVE_TRADES", "2"))
FAST_DUPLICATE_SECONDS = int(os.getenv("FAST_DUPLICATE_SECONDS", "240"))
FAST_DUPLICATE_PRICE_DISTANCE = float(os.getenv("FAST_DUPLICATE_PRICE_DISTANCE", "0.8"))
FAST_MAX_TRADES_PER_DAY = int(os.getenv("FAST_MAX_TRADES_PER_DAY", "18"))
FAST_MAX_DIRECT_SL_PER_DAY = int(os.getenv("FAST_MAX_DIRECT_SL_PER_DAY", "4"))
FAST_MAX_CONSECUTIVE_SL = int(os.getenv("FAST_MAX_CONSECUTIVE_SL", "2"))
FAST_STOP_AFTER_CONSECUTIVE_SL_SECONDS = int(os.getenv("FAST_STOP_AFTER_CONSECUTIVE_SL_SECONDS", "2700"))
FAST_PAUSE_ALERT_ENABLED = os.getenv("FAST_PAUSE_ALERT_ENABLED", "TRUE").upper() == "TRUE"
FAST_PAUSE_ALERT_COOLDOWN_SECONDS = int(os.getenv("FAST_PAUSE_ALERT_COOLDOWN_SECONDS", "900"))
FAST_PAUSE_NOTIFIED = {}
FAST_ALLOWED_TFS = {"1", "3", "5"}
FAST_ONLY_WITH_MAIN_DIRECTION = os.getenv("FAST_ONLY_WITH_MAIN_DIRECTION", "TRUE").upper() == "TRUE"
FAST_BLOCK_COUNTER_BIG_MOVE = os.getenv("FAST_BLOCK_COUNTER_BIG_MOVE", "TRUE").upper() == "TRUE"
FAST_MAIN_DOMINANCE_TP_LEVEL = int(os.getenv("FAST_MAIN_DOMINANCE_TP_LEVEL", "3"))
FAST_MAIN_DOMINANCE_LOOKBACK_SECONDS = int(os.getenv("FAST_MAIN_DOMINANCE_LOOKBACK_SECONDS", "7200"))
FAST_BLOCK_HIGH_SPIKE_BUY = os.getenv("FAST_BLOCK_HIGH_SPIKE_BUY", "TRUE").upper() == "TRUE"
FAST_BLOCK_LOW_SPIKE_SELL = os.getenv("FAST_BLOCK_LOW_SPIKE_SELL", "TRUE").upper() == "TRUE"
FAST_HIGH_POSITION_BLOCK = float(os.getenv("FAST_HIGH_POSITION_BLOCK", "0.91"))
FAST_LOW_POSITION_BLOCK = float(os.getenv("FAST_LOW_POSITION_BLOCK", "0.09"))
FAST_REQUIRE_PRICE_FRESH = os.getenv("FAST_REQUIRE_PRICE_FRESH", "TRUE").upper() == "TRUE"
FAST_MAX_ALERT_PRICE_DISTANCE = float(os.getenv("FAST_MAX_ALERT_PRICE_DISTANCE", "8.0"))
FAST_USE_HTML_COPY_FORMAT = os.getenv("FAST_USE_HTML_COPY_FORMAT", "TRUE").upper() == "TRUE"
FAST_AUTO_FROM_MAIN_WEBHOOK = os.getenv("FAST_AUTO_FROM_MAIN_WEBHOOK", "TRUE").upper() == "TRUE"
# v31: il FAST può nascere anche se il main bot poi blocca il segnale.
# Così è davvero parallelo: TP/SL piccoli, più operazioni, senza rovinare la view Max principale.
FAST_AUTO_BEFORE_MAIN_BLOCKS = os.getenv("FAST_AUTO_BEFORE_MAIN_BLOCKS", "TRUE").upper() == "TRUE"
FAST_ALLOW_DEEP_REBOUND_COUNTER = os.getenv("FAST_ALLOW_DEEP_REBOUND_COUNTER", "TRUE").upper() == "TRUE"
FAST_SEND_BLOCKED_FROM_MAIN = os.getenv("FAST_SEND_BLOCKED_FROM_MAIN", "FALSE").upper() == "TRUE"
# v32: il fast resta parallelo ma non deve sparare segnali 50/50.
FAST_QUALITY_GATE_ENABLED = os.getenv("FAST_QUALITY_GATE_ENABLED", "TRUE").upper() == "TRUE"
FAST_MIN_REASON_COUNT = int(os.getenv("FAST_MIN_REASON_COUNT", "6"))
# v35: il FAST è parallelo, ma non deve più andare contro il Master Regime.
# I default sono già dentro il codice: se Render non ti fa aggiungere variabili, funziona lo stesso.
FAST_MASTER_GATE_ENABLED = os.getenv("FAST_MASTER_GATE_ENABLED", "TRUE").upper() == "TRUE"
FAST_BLOCK_BUY_IN_SELL_CONTROL = os.getenv("FAST_BLOCK_BUY_IN_SELL_CONTROL", "TRUE").upper() == "TRUE"
FAST_BLOCK_SELL_IN_BUY_CONTROL = os.getenv("FAST_BLOCK_SELL_IN_BUY_CONTROL", "TRUE").upper() == "TRUE"
FAST_BLOCK_CHAOS_CONTROL = os.getenv("FAST_BLOCK_CHAOS_CONTROL", "TRUE").upper() == "TRUE"
FAST_BLOCK_COUNTER_BIG_MOVE_THESIS = os.getenv("FAST_BLOCK_COUNTER_BIG_MOVE_THESIS", "TRUE").upper() == "TRUE"
FAST_BIG_MOVE_BLOCK_FROM_TP = int(os.getenv("FAST_BIG_MOVE_BLOCK_FROM_TP", "5"))
FAST_SELL_CONTROL_MIN_SCORE = int(os.getenv("FAST_SELL_CONTROL_MIN_SCORE", "7"))
FAST_BUY_CONTROL_MIN_SCORE = int(os.getenv("FAST_BUY_CONTROL_MIN_SCORE", "7"))
FAST_USE_DYNAMIC_SL = os.getenv("FAST_USE_DYNAMIC_SL", "TRUE").upper() == "TRUE"
FAST_MIN_SL_POINTS = max(float(os.getenv("FAST_MIN_SL_POINTS", "4.5")), 4.5)
FAST_EVENT_SL_POINTS = max(float(os.getenv("FAST_EVENT_SL_POINTS", "6.0")), 6.0)
FAST_MAX_SL_POINTS = max(float(os.getenv("FAST_MAX_SL_POINTS", "8.0")), 8.0)
FAST_ATR_SL_MULT = max(float(os.getenv("FAST_ATR_SL_MULT", "1.3")), 1.3)
FAST_REQUIRE_MOMENTUM_OR_REJECTION = os.getenv("FAST_REQUIRE_MOMENTUM_OR_REJECTION", "TRUE").upper() == "TRUE"
FAST_BLOCK_MIDDLE_WITHOUT_BIG_MOVE = os.getenv("FAST_BLOCK_MIDDLE_WITHOUT_BIG_MOVE", "TRUE").upper() == "TRUE"
# v39: il FAST non deve nascere contro una campagna principale viva.
FAST_BLOCK_OPPOSITE_MAIN_CAMPAIGN = os.getenv("FAST_BLOCK_OPPOSITE_MAIN_CAMPAIGN", "TRUE").upper() == "TRUE"
FAST_BLOCK_OPPOSITE_MAIN_MIN_TP = int(os.getenv("FAST_BLOCK_OPPOSITE_MAIN_MIN_TP", "0"))
FAST_BLOCK_OPPOSITE_MAIN_SECONDS = int(os.getenv("FAST_BLOCK_OPPOSITE_MAIN_SECONDS", "2400"))
FAST_BLOCK_OPPOSITE_MAIN_SETUPS = {
    "NORMAL",
    "MAX_FADE_SELL",
    "BEAR_CAMPAIGN_SELL",
    "BEAR_CONTINUATION_SELL",
    "SYNTHETIC_BEAR_CONTINUATION_SELL",
    "PRE_BEAR_SELL",
    "MAX_FAILED_RETEST_SELL",
    "EXTREME_SPIKE_FADE_SELL",
    "MAX_RECOVERY_BUY",
    "MAX_PULLBACK_REARM_BUY",
    "MAX_FLIP_BUY",
    "DEEP_REBOUND_BUY",
    "MAX_DIP_BUY",
    "REVERSAL_BUY",
}
FAST_MIDDLE_LOW = float(os.getenv("FAST_MIDDLE_LOW", "0.42"))
FAST_MIDDLE_HIGH = float(os.getenv("FAST_MIDDLE_HIGH", "0.58"))
FAST_MIDDLE_A_PLUS_SCORE = int(os.getenv("FAST_MIDDLE_A_PLUS_SCORE", "9"))
FAST_MAIN_ALLOWED_SETUPS = {
    "NORMAL",
    "MAX_PULLBACK_REARM_BUY",
    "REVERSAL_BUY",
    "MAX_DIP_BUY",
    "MAX_RECOVERY_BUY",
    "DEEP_REBOUND_BUY",
    "MAX_FADE_SELL",
    "MAX_VIEW_SELL",
    "MAX_FAILED_RETEST_SELL",
    "PRE_BEAR_SELL",
    "BEAR_CAMPAIGN_SELL",
    "BEAR_CONTINUATION_SELL",
    "SYNTHETIC_BEAR_CONTINUATION_SELL",
    "SYNTHETIC_FAILED_RETEST_SELL",
    "MAX_EVENT_SPIKE_SELL",
    "EXTREME_SPIKE_FADE_SELL"
}

# v30: Campaign Lock stile Max.
# Se un trade ha già preso TP1 ed è protetto a BE, il bot non apre subito il contrario.
CAMPAIGN_PROFIT_LOCK_ENABLED = os.getenv("CAMPAIGN_PROFIT_LOCK_ENABLED", "TRUE").upper() == "TRUE"
CAMPAIGN_PROFIT_LOCK_SECONDS = int(os.getenv("CAMPAIGN_PROFIT_LOCK_SECONDS", "1800"))
CAMPAIGN_PROFIT_LOCK_MIN_TP = int(os.getenv("CAMPAIGN_PROFIT_LOCK_MIN_TP", "1"))
CAMPAIGN_PROFIT_LOCK_INVALIDATION_POINTS = float(os.getenv("CAMPAIGN_PROFIT_LOCK_INVALIDATION_POINTS", "2.0"))
CAMPAIGN_PROFIT_LOCK_ALLOW_SCORE = int(os.getenv("CAMPAIGN_PROFIT_LOCK_ALLOW_SCORE", "24"))
CAMPAIGN_PROFIT_LOCK_SELL_AFTER_BUY_ALLOW_SETUPS = {
    "MAX_FADE_SELL",
    "MAX_VIEW_SELL",
    "MAX_FAILED_RETEST_SELL",
    "PRE_BEAR_SELL",
    "BEAR_CAMPAIGN_SELL",
    "BEAR_CONTINUATION_SELL",
    "SYNTHETIC_BEAR_CONTINUATION_SELL",
    "SYNTHETIC_FAILED_RETEST_SELL",
    "MAX_EVENT_SPIKE_SELL",
    "EXTREME_SPIKE_FADE_SELL"
}
CAMPAIGN_PROFIT_LOCK_BUY_AFTER_SELL_ALLOW_SETUPS = {
    "MAX_RECOVERY_BUY",
    "MAX_PULLBACK_REARM_BUY",
    "MAX_FLIP_BUY",
    "DEEP_REBOUND_BUY",
    "REVERSAL_BUY",
    "MAX_DIP_BUY"
}

# v30: non inseguire BUY alti dopo una campagna BUY già pagata.
BUY_CAMPAIGN_EXHAUSTION_ENABLED = os.getenv("BUY_CAMPAIGN_EXHAUSTION_ENABLED", "TRUE").upper() == "TRUE"
BUY_CAMPAIGN_EXHAUSTION_MIN_TP = int(os.getenv("BUY_CAMPAIGN_EXHAUSTION_MIN_TP", "3"))
BUY_CAMPAIGN_EXHAUSTION_LOOKBACK_SECONDS = int(os.getenv("BUY_CAMPAIGN_EXHAUSTION_LOOKBACK_SECONDS", "7200"))
BUY_CAMPAIGN_EXHAUSTION_MIN_DAY_POSITION = float(os.getenv("BUY_CAMPAIGN_EXHAUSTION_MIN_DAY_POSITION", "0.62"))
BUY_CAMPAIGN_EXHAUSTION_ALLOW_SCORE = int(os.getenv("BUY_CAMPAIGN_EXHAUSTION_ALLOW_SCORE", "18"))
BUY_CAMPAIGN_EXHAUSTION_ALLOW_LOW_POSITION = float(os.getenv("BUY_CAMPAIGN_EXHAUSTION_ALLOW_LOW_POSITION", "0.45"))

# v36: Max Pullback Re-Arm + Anti-Fade Super BUY.
# Patch nata dal caso 31/07 + 04/08:
# il bot aveva preso bene la campagna BUY, poi ha confuso il pullback con SELL_CONTROL
# e ha aperto MAX_FADE_SELL troppo presto. Ora una campagna BUY forte può riarmare
# un nuovo BUY da pullback; i SELL contro SUPER BUY passano solo con invalidazione vera.
MAX_PULLBACK_REARM_ENABLED = os.getenv("MAX_PULLBACK_REARM_ENABLED", "TRUE").upper() == "TRUE"
MAX_PULLBACK_REARM_MIN_BUY_TP = int(os.getenv("MAX_PULLBACK_REARM_MIN_BUY_TP", "5"))
MAX_PULLBACK_REARM_LOOKBACK_SECONDS = int(os.getenv("MAX_PULLBACK_REARM_LOOKBACK_SECONDS", "7200"))
MAX_PULLBACK_REARM_MIN_PULLBACK_POINTS = float(os.getenv("MAX_PULLBACK_REARM_MIN_PULLBACK_POINTS", "4.0"))
MAX_PULLBACK_REARM_MAX_DAY_POSITION = float(os.getenv("MAX_PULLBACK_REARM_MAX_DAY_POSITION", "0.78"))
MAX_PULLBACK_REARM_INVALIDATION_BUFFER = float(os.getenv("MAX_PULLBACK_REARM_INVALIDATION_BUFFER", "5.0"))
MAX_PULLBACK_REARM_MIN_CONFIRMATIONS = int(os.getenv("MAX_PULLBACK_REARM_MIN_CONFIRMATIONS", "4"))
MAX_PULLBACK_REARM_BASE_BONUS = int(os.getenv("MAX_PULLBACK_REARM_BASE_BONUS", "12"))
MAX_PULLBACK_REARM_SCORE_FLOOR = int(os.getenv("MAX_PULLBACK_REARM_SCORE_FLOOR", "11"))
MAX_PULLBACK_REARM_ALLOW_IN_SELL_CONTROL = os.getenv("MAX_PULLBACK_REARM_ALLOW_IN_SELL_CONTROL", "TRUE").upper() == "TRUE"

ANTI_FADE_SUPER_BUY_ENABLED = os.getenv("ANTI_FADE_SUPER_BUY_ENABLED", "TRUE").upper() == "TRUE"
ANTI_FADE_SUPER_BUY_MIN_BUY_TP = int(os.getenv("ANTI_FADE_SUPER_BUY_MIN_BUY_TP", "5"))
ANTI_FADE_SUPER_BUY_LOOKBACK_SECONDS = int(os.getenv("ANTI_FADE_SUPER_BUY_LOOKBACK_SECONDS", "7200"))
ANTI_FADE_SUPER_BUY_SUPPORT_BUFFER = float(os.getenv("ANTI_FADE_SUPER_BUY_SUPPORT_BUFFER", "5.0"))
ANTI_FADE_SUPER_BUY_ALLOW_SCORE = int(os.getenv("ANTI_FADE_SUPER_BUY_ALLOW_SCORE", "28"))
ANTI_FADE_SUPER_BUY_MIN_BEAR_CONFIRMATIONS = int(os.getenv("ANTI_FADE_SUPER_BUY_MIN_BEAR_CONFIRMATIONS", "5"))
ANTI_FADE_SUPER_BUY_REQUIRE_MICRO_BOS = os.getenv("ANTI_FADE_SUPER_BUY_REQUIRE_MICRO_BOS", "TRUE").upper() == "TRUE"
ANTI_FADE_SUPER_BUY_REQUIRE_TRUE_HIGH_ZONE = os.getenv("ANTI_FADE_SUPER_BUY_REQUIRE_TRUE_HIGH_ZONE", "TRUE").upper() == "TRUE"
ANTI_FADE_SUPER_BUY_MIN_DAY_POSITION = float(os.getenv("ANTI_FADE_SUPER_BUY_MIN_DAY_POSITION", "0.82"))
ANTI_FADE_SUPER_BUY_BLOCK_SETUPS = {
    "NORMAL",
    "MAX_FADE_SELL",
    "MAX_VIEW_SELL"
}

FAST_TRADES = []

# Stato persistente dell'arbitro.
REGIME_ARBITER_STATE = {}

# Runtime meta
RUNTIME_STATE_LAST_SAVE = 0
RUNTIME_STATE_RESTORED = False
RUNTIME_STATE_RESTORED_AT = 0
RUNTIME_STATE_SAVED_AT = 0
WARMUP_TRACKER = {}

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



def _text_has_any(value, tokens):
    haystack = str(value or "").lower()
    return any(str(token).lower() in haystack for token in tokens)


def _classify_blocked_message(text):
    """Classifica i messaggi bloccati per non confonderli con trade copiabili.

    Ritorna: (category, send_allowed, header)
    - thesis: lettura utile / tesi direzionale, ma NON entry
    - risk: filtro rischio operativo, utile ma NON entry
    - debug_duplicate/debug_low_score: rumore tecnico, nascosto di default
    """
    raw = str(text or "")
    low = raw.lower()

    if "duplicato stesso movimento" in low or "duplicato fast" in low:
        header = (
            "🧾 DEBUG / DUPLICATO — NON È UNA NUOVA OPERAZIONE\n"
            "Serve solo a dire che il bot ha visto lo stesso movimento già coperto.\n"
        )
        return "debug_duplicate", DUPLICATE_BLOCK_TELEGRAM_ENABLED, header

    thesis_tokens = [
        "score finale: -999",
        "parte alta dello spike",
        "event active:",
        "failed retest",
        "event trap flip",
        "master regime",
        "one direction control",
        "sell_control",
        "buy_control",
        "regime arbiter",
        "bear state",
        "bearish continuation",
        "lower high",
        "deep extension",
        "big move thesis",
        "super buy",
        "post super buy",
        "max pullback re-arm",
        "anti-fade super buy",
        "sell profit lock",
        "recovery lock",
        "buy fatigue",
        "campaign",
        "exhaustion",
        "chaos day",
        "extreme zone",
        "event state machine",
        "pre-bear",
        "cold start warmup",
        "post sl quarantine",
    ]

    if _text_has_any(raw, thesis_tokens):
        header = (
            "🧭 TESI / AVVISO — NON COPIARE SU MT4\n"
            "È una lettura del contesto: utile per capire la direzione o il rischio, "
            "ma NON è un'entry ufficiale.\n"
        )
        return "thesis", THESIS_BLOCK_TELEGRAM_ENABLED, header

    risk_tokens = [
        "conflict resolver",
        "stop temporaneo",
        "sl cooldown",
        "daily kill",
        "quarantine",
        "bloccato",
    ]

    if _text_has_any(raw, risk_tokens):
        header = (
            "🛡 FILTRO RISCHIO — NON COPIARE SU MT4\n"
            "Il bot ha scelto di NON entrare. Usa questo messaggio solo come controllo rischio.\n"
        )
        return "risk", RISK_BLOCK_TELEGRAM_ENABLED, header

    header = (
        "🧾 DEBUG BASSO SCORE — NON OPERATIVO\n"
        "Segnale grezzo scartato: non usarlo come trade.\n"
    )
    return "debug_low_score", LOW_SCORE_DEBUG_TELEGRAM_ENABLED, header


def _blocked_message_allowed(category, default_allowed):
    mode = str(BLOCKED_SIGNAL_VISIBILITY or "SMART").upper()
    if mode == "ALL":
        return True
    if mode in ["OFF", "SILENT", "NONE"]:
        return False
    return bool(default_allowed)


def prepare_telegram_message(text: str):
    """Aggiunge etichette operative e può silenziare debug non utili.

    Non cambia la logica trading: modifica solo il modo in cui il messaggio viene mostrato.
    """
    if not MESSAGE_LABELS_ENABLED:
        return text, True

    raw = str(text or "")
    stripped = raw.strip()
    if not stripped:
        return text, True

    already_labeled = any(label in stripped for label in [
        "OPERAZIONE UFFICIALE",
        "FAST UFFICIALE",
        "TESI / AVVISO",
        "FILTRO RISCHIO",
        "DEBUG / DUPLICATO",
        "DEBUG BASSO SCORE",
    ])
    if already_labeled:
        return text, True

    official_trade_tokens = [
        "GOLD BUY AI FILTER",
        "GOLD SELL AI FILTER",
        "GOLD BUY AUTONOMO",
        "GOLD SELL AUTONOMO",
    ]
    if OFFICIAL_TRADE_LABEL_ENABLED and _text_has_any(stripped, official_trade_tokens) and "trade id" in stripped.lower():
        header = (
            "✅ OPERAZIONE UFFICIALE — COPIABILE SU MT4\n"
            "Usa Entry/SL/TP di questo messaggio. I messaggi BLOCCATI sotto sono solo filtri/tesi.\n\n"
        )
        return header + raw, True

    if OFFICIAL_TRADE_LABEL_ENABLED and "Fast Scalper" in stripped and "Apro una nuova operazione" in stripped:
        header = (
            "⚡ FAST UFFICIALE — TP PICCOLO COPIABILE\n"
            "Motore veloce separato: Entry/SL/TP sono pensati per scalp rapido.\n\n"
        )
        return header + raw, True

    if "FAST SCALP BLOCCATO" in stripped:
        allowed = _blocked_message_allowed("debug_fast", FAST_BLOCK_TELEGRAM_ENABLED)
        header = (
            "🧾 DEBUG FAST BLOCCATO — NON È UNA NUOVA OPERAZIONE\n"
            "Il fast non ha le condizioni minime: niente copia su MT4.\n\n"
        )
        return header + raw, allowed

    blocked_tokens = [
        "SEGNALE BLOCCATO",
        "BUY BLOCCATO",
        "SELL BLOCCATO",
    ]
    if _text_has_any(stripped, blocked_tokens):
        category, default_allowed, header = _classify_blocked_message(raw)
        allowed = _blocked_message_allowed(category, default_allowed)
        warning = ""
        if THESIS_NOT_TRADE_WARNING_ENABLED and category in ["thesis", "risk"]:
            warning = "Regola pratica: aspetta OPERAZIONE UFFICIALE prima di copiare.\n\n"
        return header + warning + raw, allowed

    return text, True

def send_telegram(text: str, parse_mode: str = None):
    text, should_send = prepare_telegram_message(text)

    if not should_send:
        print("TELEGRAM SKIPPED BY MESSAGE FILTER")
        print(str(text)[:1200])
        return True

    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("TELEGRAM NON CONFIGURATO")
        print(text)
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "disable_web_page_preview": True
    }

    # Usato solo dal motore FAST per rendere Entry/SL/TP facilmente copiabili da telefono.
    # I messaggi storici v29 restano testo normale.
    if parse_mode:
        payload["parse_mode"] = parse_mode

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

    close = to_float(data.get("close"), 0)

    if close:
        return close

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

def _restore_dict(target, value):
    if isinstance(value, dict):
        target.clear()
        target.update(value)


def runtime_state_payload():
    return {
        "version": VERSION,
        "saved_at": now_ts(),
        "auto_event_cache": AUTO_EVENT_CACHE,
        "event_state_machine": EVENT_STATE_MACHINE,
        "bear_continuation_state": BEAR_CONTINUATION_STATE,
        "price_history": PRICE_HISTORY,
        "bear_campaign_state": BEAR_CAMPAIGN_STATE,
        "pre_bear_state": PRE_BEAR_STATE,
        "regime_arbiter_state": REGIME_ARBITER_STATE,
        "warmup_tracker": WARMUP_TRACKER,
        "daily_thesis_state": DAILY_THESIS_STATE
    }


def save_runtime_state(force=False):
    global RUNTIME_STATE_LAST_SAVE, RUNTIME_STATE_SAVED_AT

    if not RUNTIME_STATE_ENABLED:
        return False

    now = now_ts()

    if (
        not force
        and RUNTIME_STATE_LAST_SAVE
        and now - RUNTIME_STATE_LAST_SAVE < RUNTIME_STATE_SAVE_INTERVAL_SECONDS
    ):
        return False

    try:
        payload = runtime_state_payload()
        tmp_file = RUNTIME_STATE_FILE + ".tmp"

        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

        os.replace(tmp_file, RUNTIME_STATE_FILE)

        RUNTIME_STATE_LAST_SAVE = now
        RUNTIME_STATE_SAVED_AT = payload.get("saved_at", now)
        return True

    except Exception as e:
        print(f"Errore salvataggio runtime state: {e}")
        return False


def load_runtime_state():
    global RUNTIME_STATE_RESTORED
    global RUNTIME_STATE_RESTORED_AT
    global RUNTIME_STATE_SAVED_AT
    global RUNTIME_STATE_LAST_SAVE

    RUNTIME_STATE_RESTORED = False

    if not RUNTIME_STATE_ENABLED:
        return False

    if not os.path.exists(RUNTIME_STATE_FILE):
        return False

    try:
        with open(RUNTIME_STATE_FILE, "r", encoding="utf-8") as f:
            payload = json.load(f)

        if not isinstance(payload, dict):
            return False

        saved_at = to_float(payload.get("saved_at"), 0)
        age = now_ts() - saved_at if saved_at else 999999999

        if age > RUNTIME_STATE_MAX_AGE_SECONDS:
            print(
                f"Runtime state ignorato: troppo vecchio "
                f"({round(age, 1)}s > {RUNTIME_STATE_MAX_AGE_SECONDS}s)"
            )
            return False

        # Mantengo i default nuovi e sovrascrivo solo i campi salvati.
        saved_auto_event = payload.get("auto_event_cache")
        if isinstance(saved_auto_event, dict):
            AUTO_EVENT_CACHE.update(saved_auto_event)

        _restore_dict(
            EVENT_STATE_MACHINE,
            payload.get("event_state_machine")
        )
        _restore_dict(
            BEAR_CONTINUATION_STATE,
            payload.get("bear_continuation_state")
        )
        _restore_dict(
            PRICE_HISTORY,
            payload.get("price_history")
        )
        _restore_dict(
            BEAR_CAMPAIGN_STATE,
            payload.get("bear_campaign_state")
        )
        _restore_dict(
            PRE_BEAR_STATE,
            payload.get("pre_bear_state")
        )
        _restore_dict(
            REGIME_ARBITER_STATE,
            payload.get("regime_arbiter_state")
        )
        _restore_dict(
            WARMUP_TRACKER,
            payload.get("warmup_tracker")
        )

        # Pruning difensivo dello storico.
        cutoff = now_ts() - BEAR_HISTORY_SECONDS
        for symbol, history in list(PRICE_HISTORY.items()):
            if not isinstance(history, list):
                PRICE_HISTORY[symbol] = []
                continue

            PRICE_HISTORY[symbol] = [
                p for p in history
                if isinstance(p, dict)
                and p.get("time", 0) >= cutoff
            ][-BEAR_HISTORY_MAX_POINTS:]

        RUNTIME_STATE_RESTORED = True
        RUNTIME_STATE_RESTORED_AT = now_ts()
        RUNTIME_STATE_SAVED_AT = saved_at
        RUNTIME_STATE_LAST_SAVE = now_ts()

        print(
            f"Runtime state ripristinato da {RUNTIME_STATE_FILE} "
            f"(age {round(age, 1)}s)"
        )
        return True

    except Exception as e:
        print(f"Errore caricamento runtime state: {e}")
        return False


def note_price_update_for_warmup(data):
    symbol = str(data.get("symbol", "XAUUSD")).upper()
    tracker = WARMUP_TRACKER.setdefault(
        symbol,
        {
            "first_update": now_ts(),
            "last_update": 0,
            "update_count": 0
        }
    )

    if not tracker.get("first_update"):
        tracker["first_update"] = now_ts()

    tracker["last_update"] = now_ts()
    tracker["update_count"] = int(tracker.get("update_count", 0)) + 1

    return tracker


def warmup_status(symbol):
    symbol = str(symbol or "XAUUSD").upper()
    tracker = WARMUP_TRACKER.setdefault(
        symbol,
        {
            "first_update": now_ts(),
            "last_update": 0,
            "update_count": 0
        }
    )

    first_update = to_float(tracker.get("first_update"), now_ts())
    elapsed = max(0, now_ts() - first_update)
    count = int(tracker.get("update_count", 0))

    history = PRICE_HISTORY.get(symbol, [])
    history_count = len(history) if isinstance(history, list) else 0

    restored_ready = bool(
        RUNTIME_STATE_RESTORED
        and history_count >= STATE_WARMUP_MIN_PRICE_UPDATES
    )

    warm = bool(
        not STATE_WARMUP_ENABLED
        or restored_ready
        or count >= STATE_WARMUP_MIN_PRICE_UPDATES
        or elapsed >= STATE_WARMUP_SECONDS
    )

    return {
        "warm": warm,
        "restored_ready": restored_ready,
        "elapsed_seconds": elapsed,
        "update_count": count,
        "history_count": history_count,
        "required_seconds": STATE_WARMUP_SECONDS,
        "required_updates": STATE_WARMUP_MIN_PRICE_UPDATES
    }


def is_state_warm(symbol):
    return bool(warmup_status(symbol).get("warm"))


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

        # v22: ricostruisce le campaign legs persistite nei trade.
        try:
            rebuild_bear_campaigns_from_trades()
        except Exception as campaign_error:
            print(f"Errore ricostruzione campaign: {campaign_error}")

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
        "message_labels_enabled": MESSAGE_LABELS_ENABLED,
        "blocked_signal_visibility": BLOCKED_SIGNAL_VISIBILITY,
        "duplicate_block_telegram_enabled": DUPLICATE_BLOCK_TELEGRAM_ENABLED,
        "low_score_debug_telegram_enabled": LOW_SCORE_DEBUG_TELEGRAM_ENABLED,
        "thesis_block_telegram_enabled": THESIS_BLOCK_TELEGRAM_ENABLED,
        "risk_block_telegram_enabled": RISK_BLOCK_TELEGRAM_ENABLED,
        "fast_block_telegram_enabled": FAST_BLOCK_TELEGRAM_ENABLED,
        "official_trade_label_enabled": OFFICIAL_TRADE_LABEL_ENABLED,
        "fast_version": FAST_VERSION,
        "fast_engine_enabled": FAST_ENGINE_ENABLED,
        "max_discipline_enabled": MAX_DISCIPLINE_ENABLED,
        "max_discipline_window_seconds": MAX_DISCIPLINE_WINDOW_SECONDS,
        "max_discipline_max_official_per_direction": MAX_DISCIPLINE_MAX_OFFICIAL_PER_DIRECTION,
        "max_discipline_direct_sl_limit": MAX_DISCIPLINE_DIRECT_SL_LIMIT,
        "fast_discipline_enabled": FAST_DISCIPLINE_ENABLED,
        "fast_max_per_direction_window": FAST_MAX_PER_DIRECTION_WINDOW,
        "fast_total_trades": len(FAST_TRADES),
        "fast_active_trades": len(fast_active_trades()),
        "fast_tp_points": FAST_TP_POINTS,
        "fast_sl_points": FAST_SL_POINTS,
        "fast_min_sl_points": FAST_MIN_SL_POINTS,
        "fast_event_sl_points": FAST_EVENT_SL_POINTS,
        "fast_master_gate_enabled": FAST_MASTER_GATE_ENABLED,
        "fast_auto_from_main_webhook": FAST_AUTO_FROM_MAIN_WEBHOOK,
        "fast_auto_before_main_blocks": FAST_AUTO_BEFORE_MAIN_BLOCKS,
        "fast_allow_deep_rebound_counter": FAST_ALLOW_DEEP_REBOUND_COUNTER,
        "fast_send_blocked_from_main": FAST_SEND_BLOCKED_FROM_MAIN,
        "fast_quality_gate_enabled": FAST_QUALITY_GATE_ENABLED,
        "fast_min_reason_count": FAST_MIN_REASON_COUNT,
        "asian_thesis_enabled": ASIAN_THESIS_ENABLED,
        "asian_thesis_state": DAILY_THESIS_STATE,
        "max_flip_buy_after_sell_be_enabled": MAX_FLIP_BUY_AFTER_SELL_BE_ENABLED,
        "virtual_runner_enabled": VIRTUAL_RUNNER_ENABLED,
        "special_buy_flip_window_enabled": SPECIAL_BUY_FLIP_WINDOW_ENABLED,
        "post_sell_rebound_unlock_enabled": POST_SELL_REBOUND_UNLOCK_ENABLED,
        "post_sl_quarantine_enabled": POST_SL_QUARANTINE_ENABLED,
        "post_sl_quarantine_seconds": POST_SL_QUARANTINE_SECONDS,
        "post_sl_opposite_min_score": POST_SL_OPPOSITE_MIN_SCORE,
        "post_sl_reentry_min_score": POST_SL_REENTRY_MIN_SCORE,
        "post_sl_require_micro_bos": POST_SL_REQUIRE_MICRO_BOS,
        "post_sl_require_retest_zone": POST_SL_REQUIRE_RETEST_ZONE,
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
        "chaos_mode_enabled": CHAOS_MODE_ENABLED,
        "chaos_direct_sl_count": CHAOS_DIRECT_SL_COUNT,
        "chaos_lookback_seconds": CHAOS_LOOKBACK_SECONDS,
        "chaos_lock_seconds": CHAOS_LOCK_SECONDS,
        "daily_kill_switch_enabled": DAILY_KILL_SWITCH_ENABLED,
        "daily_max_direct_sl": DAILY_MAX_DIRECT_SL,
        "chaos_extreme_zone_required": CHAOS_EXTREME_ZONE_REQUIRED,
        "chaos_extreme_distance": CHAOS_EXTREME_DISTANCE,
        "chaos_extreme_atr_mult": CHAOS_EXTREME_ATR_MULT,
        "chaos_sell_day_position_min": CHAOS_SELL_DAY_POSITION_MIN,
        "chaos_buy_day_position_max": CHAOS_BUY_DAY_POSITION_MAX,
        "chaos_min_score": CHAOS_MIN_SCORE,
        "chaos_allow_normal_extreme": CHAOS_ALLOW_NORMAL_EXTREME,
        "chaos_normal_min_score": CHAOS_NORMAL_MIN_SCORE,
        "session_lock_reset_enabled": SESSION_LOCK_RESET_ENABLED,
        "lock_ignore_previous_day": LOCK_IGNORE_PREVIOUS_DAY,
        "stale_trade_lock_seconds": STALE_TRADE_LOCK_SECONDS,
        "max_view_sell_enabled": MAX_VIEW_SELL_ENABLED,
        "max_view_buy_tp_level": MAX_VIEW_BUY_TP_LEVEL,
        "max_view_buy_count": MAX_VIEW_BUY_COUNT,
        "max_view_lookback_seconds": MAX_VIEW_LOOKBACK_SECONDS,
        "max_view_sell_day_position_min": MAX_VIEW_SELL_DAY_POSITION_MIN,
        "max_view_min_rsi": MAX_VIEW_MIN_RSI,
        "max_view_event_mode": MAX_VIEW_EVENT_MODE,
        "max_view_event_bonus": MAX_VIEW_EVENT_BONUS,
        "max_view_sell_base_bonus": MAX_VIEW_SELL_BASE_BONUS,
        "max_view_sell_min_score": MAX_VIEW_SELL_MIN_SCORE,
        "max_view_allow_sell_against_bullish_news": MAX_VIEW_ALLOW_SELL_AGAINST_BULLISH_NEWS,
        "auto_event_mode_enabled": AUTO_EVENT_MODE_ENABLED,
        "auto_event_keywords_enabled": AUTO_EVENT_KEYWORDS_ENABLED,
        "auto_event_volatility_enabled": AUTO_EVENT_VOLATILITY_ENABLED,
        "auto_event_duration_seconds": AUTO_EVENT_DURATION_SECONDS,
        "auto_event_candle_atr_mult": AUTO_EVENT_CANDLE_ATR_MULT,
        "auto_event_m15_range_atr_mult": AUTO_EVENT_M15_RANGE_ATR_MULT,
        "auto_event_day_range_atr_mult": AUTO_EVENT_DAY_RANGE_ATR_MULT,
        "auto_event_volume_spike_required": AUTO_EVENT_VOLUME_SPIKE_REQUIRED,
        "auto_event_active": now_ts() < AUTO_EVENT_CACHE.get("until", 0),
        "auto_event_until": AUTO_EVENT_CACHE.get("until", 0),
        "auto_event_reasons": AUTO_EVENT_CACHE.get("reasons", []),
        "auto_event_start_price": AUTO_EVENT_CACHE.get("start_price", 0),
        "auto_event_high": AUTO_EVENT_CACHE.get("high", 0),
        "auto_event_low": AUTO_EVENT_CACHE.get("low", 0),
        "auto_event_spike_up_points": max(0, AUTO_EVENT_CACHE.get("high", 0) - AUTO_EVENT_CACHE.get("start_price", 0)) if AUTO_EVENT_CACHE.get("start_price", 0) else 0,
        "event_spike_reversal_enabled": EVENT_SPIKE_REVERSAL_ENABLED,
        "event_spike_lookback_seconds": EVENT_SPIKE_LOOKBACK_SECONDS,
        "event_spike_min_up_points": EVENT_SPIKE_MIN_UP_POINTS,
        "event_spike_top_position_min": EVENT_SPIKE_TOP_POSITION_MIN,
        "event_spike_sell_retrace_points": EVENT_SPIKE_SELL_RETRACE_POINTS,
        "event_spike_sell_base_bonus": EVENT_SPIKE_SELL_BASE_BONUS,
        "event_spike_sell_min_score": EVENT_SPIKE_SELL_MIN_SCORE,
        "event_spike_block_top_buy_enabled": EVENT_SPIKE_BLOCK_TOP_BUY_ENABLED,
        "event_spike_block_buy_top_position_min": EVENT_SPIKE_BLOCK_BUY_TOP_POSITION_MIN,
        "event_spike_block_buy_min_up_points": EVENT_SPIKE_BLOCK_BUY_MIN_UP_POINTS,
        "failed_retest_sell_enabled": FAILED_RETEST_SELL_ENABLED,
        "failed_retest_min_pullback_points": FAILED_RETEST_MIN_PULLBACK_POINTS,
        "failed_retest_top_position_min": FAILED_RETEST_TOP_POSITION_MIN,
        "failed_retest_top_position_max": FAILED_RETEST_TOP_POSITION_MAX,
        "failed_retest_near_high_distance": FAILED_RETEST_NEAR_HIGH_DISTANCE,
        "failed_retest_min_distance_from_high": FAILED_RETEST_MIN_DISTANCE_FROM_HIGH,
        "failed_retest_min_seconds_after_high": FAILED_RETEST_MIN_SECONDS_AFTER_HIGH,
        "failed_retest_sell_base_bonus": FAILED_RETEST_SELL_BASE_BONUS,
        "failed_retest_sell_min_score": FAILED_RETEST_SELL_MIN_SCORE,
        "failed_retest_block_early_sells": FAILED_RETEST_BLOCK_EARLY_SELLS,
        "synthetic_retest_engine_enabled": SYNTHETIC_RETEST_ENGINE_ENABLED,
        "synthetic_retest_spike_min_up_points": SYNTHETIC_RETEST_SPIKE_MIN_UP_POINTS,
        "synthetic_retest_pullback_points": SYNTHETIC_RETEST_PULLBACK_POINTS,
        "synthetic_retest_arm_position_min": SYNTHETIC_RETEST_ARM_POSITION_MIN,
        "synthetic_retest_arm_position_max": SYNTHETIC_RETEST_ARM_POSITION_MAX,
        "synthetic_retest_near_high_distance": SYNTHETIC_RETEST_NEAR_HIGH_DISTANCE,
        "synthetic_retest_failure_points": SYNTHETIC_RETEST_FAILURE_POINTS,
        "synthetic_retest_block_buys_when_armed": SYNTHETIC_RETEST_BLOCK_BUYS_WHEN_ARMED,
        "synthetic_retest_cooldown_seconds": SYNTHETIC_RETEST_COOLDOWN_SECONDS,
        "synthetic_event_states": EVENT_STATE_MACHINE,
        "bear_continuation_engine_enabled": BEAR_CONTINUATION_ENGINE_ENABLED,
        "bear_impulse_min_drop_points": BEAR_IMPULSE_MIN_DROP_POINTS,
        "bear_impulse_atr_mult": BEAR_IMPULSE_ATR_MULT,
        "bear_relief_min_points": BEAR_RELIEF_MIN_POINTS,
        "bear_relief_min_retrace": BEAR_RELIEF_MIN_RETRACE,
        "bear_relief_max_retrace": BEAR_RELIEF_MAX_RETRACE,
        "bear_lower_high_min_gap": BEAR_LOWER_HIGH_MIN_GAP,
        "bear_continuation_failure_points": BEAR_CONTINUATION_FAILURE_POINTS,
        "bear_block_buys_enabled": BEAR_BLOCK_BUYS_ENABLED,
        "bear_block_max_dip_buy": BEAR_BLOCK_MAX_DIP_BUY,
        "bear_block_reversal_buy": BEAR_BLOCK_REVERSAL_BUY,
        "bear_allow_strong_recovery_buy": BEAR_ALLOW_STRONG_RECOVERY_BUY,
        "bear_strong_recovery_min_score": BEAR_STRONG_RECOVERY_MIN_SCORE,
        "bear_synthetic_sell_enabled": BEAR_SYNTHETIC_SELL_ENABLED,
        "bear_synthetic_score": BEAR_SYNTHETIC_SCORE,
        "bear_synthetic_cooldown_seconds": BEAR_SYNTHETIC_COOLDOWN_SECONDS,
        "bear_continuation_states": BEAR_CONTINUATION_STATE,
        "campaign_manager_enabled": CAMPAIGN_MANAGER_ENABLED,
        "campaign_max_legs": CAMPAIGN_MAX_LEGS,
        "campaign_total_risk_cap": CAMPAIGN_TOTAL_RISK_CAP,
        "campaign_leg_weights": CAMPAIGN_LEG_WEIGHTS_RAW,
        "campaign_first_leg_min_score": CAMPAIGN_FIRST_LEG_MIN_SCORE,
        "campaign_reentry_min_score": CAMPAIGN_REENTRY_MIN_SCORE,
        "campaign_better_price_points": CAMPAIGN_BETTER_PRICE_POINTS,
        "campaign_new_retest_points": CAMPAIGN_NEW_RETEST_POINTS,
        "campaign_kill_switch_override_enabled": CAMPAIGN_KILL_SWITCH_OVERRIDE_ENABLED,
        "campaign_kill_switch_min_score": CAMPAIGN_KILL_SWITCH_MIN_SCORE,
        "campaign_sl_cooldown_override_enabled": CAMPAIGN_SL_COOLDOWN_OVERRIDE_ENABLED,
        "campaign_extreme_fallback_enabled": CAMPAIGN_EXTREME_FALLBACK_ENABLED,
        "campaign_states": BEAR_CAMPAIGN_STATE,
        "pre_bear_thesis_enabled": PRE_BEAR_THESIS_ENABLED,
        "pre_bear_min_prior_drop_points": PRE_BEAR_MIN_PRIOR_DROP_POINTS,
        "pre_bear_min_recovery_points": PRE_BEAR_MIN_RECOVERY_POINTS,
        "pre_bear_min_retrace": PRE_BEAR_MIN_RETRACE,
        "pre_bear_max_retrace": PRE_BEAR_MAX_RETRACE,
        "pre_bear_failure_points": PRE_BEAR_FAILURE_POINTS,
        "pre_bear_macro_votes": PRE_BEAR_MACRO_VOTES,
        "pre_bear_states": PRE_BEAR_STATE,
        "deep_extension_flip_enabled": DEEP_EXTENSION_FLIP_ENABLED,
        "deep_extension_tp_level": DEEP_EXTENSION_TP_LEVEL,
        "deep_extension_min_drop_points": DEEP_EXTENSION_MIN_DROP_POINTS,
        "deep_extension_low_position_max": DEEP_EXTENSION_LOW_POSITION_MAX,
        "deep_extension_rearm_rebound_points": DEEP_EXTENSION_REARM_REBOUND_POINTS,
        "runtime_state_enabled": RUNTIME_STATE_ENABLED,
        "runtime_state_file": RUNTIME_STATE_FILE,
        "runtime_state_restored": RUNTIME_STATE_RESTORED,
        "runtime_state_saved_at": RUNTIME_STATE_SAVED_AT,
        "runtime_state_max_age_seconds": RUNTIME_STATE_MAX_AGE_SECONDS,
        "state_warmup_enabled": STATE_WARMUP_ENABLED,
        "state_warmup_seconds": STATE_WARMUP_SECONDS,
        "state_warmup_min_price_updates": STATE_WARMUP_MIN_PRICE_UPDATES,
        "warmup_xauusd": warmup_status("XAUUSD"),
        "bear_rally_peak_stability_seconds": BEAR_RALLY_PEAK_STABILITY_SECONDS,
        "bear_continuation_failure_min_points": BEAR_CONTINUATION_FAILURE_MIN_POINTS,
        "bear_continuation_failure_atr_mult": BEAR_CONTINUATION_FAILURE_ATR_MULT,
        "bear_continuation_min_confirmations": BEAR_CONTINUATION_MIN_CONFIRMATIONS,
        "bear_continuation_micro_bos_required": BEAR_CONTINUATION_MICRO_BOS_REQUIRED,
        "synthetic_retest_peak_stability_seconds": SYNTHETIC_RETEST_PEAK_STABILITY_SECONDS,
        "synthetic_retest_failure_min_points": SYNTHETIC_RETEST_FAILURE_MIN_POINTS,
        "synthetic_retest_min_confirmations": SYNTHETIC_RETEST_MIN_CONFIRMATIONS,
        "micro_bos_lookback_updates": MICRO_BOS_LOOKBACK_UPDATES,
        "micro_bos_buffer_points": MICRO_BOS_BUFFER_POINTS,
        "regime_arbiter_enabled": REGIME_ARBITER_ENABLED,
        "recovery_dominance_enabled": RECOVERY_DOMINANCE_ENABLED,
        "recovery_dominance_min_tp": RECOVERY_DOMINANCE_MIN_TP,
        "recovery_dominance_lookback_seconds": RECOVERY_DOMINANCE_LOOKBACK_SECONDS,
        "recovery_dominance_invalidation_buffer": RECOVERY_DOMINANCE_INVALIDATION_BUFFER,
        "recovery_dominance_setups": list(RECOVERY_DOMINANCE_SETUPS),
        "special_buy_normal_sell_min_tp": SPECIAL_BUY_NORMAL_SELL_MIN_TP,
        "special_buy_block_normal_sell": SPECIAL_BUY_BLOCK_NORMAL_SELL,
        "special_buy_counter_sell_min_score": SPECIAL_BUY_COUNTER_SELL_MIN_SCORE,
        "special_buy_counter_sell_require_zone": SPECIAL_BUY_COUNTER_SELL_REQUIRE_ZONE,
        "special_buy_counter_sell_require_micro_bos": SPECIAL_BUY_COUNTER_SELL_REQUIRE_MICRO_BOS,
        "max_zone_sell_gate_enabled": MAX_ZONE_SELL_GATE_ENABLED,
        "max_zone_sell_min_score": MAX_ZONE_SELL_MIN_SCORE,
        "sell_profit_lock_enabled": SELL_PROFIT_LOCK_ENABLED,
        "sell_profit_lock_tp_level": SELL_PROFIT_LOCK_TP_LEVEL,
        "sell_profit_lock_tp5_level": SELL_PROFIT_LOCK_TP5_LEVEL,
        "sell_profit_lock_tp5_count": SELL_PROFIT_LOCK_TP5_COUNT,
        "sell_profit_lock_seconds": SELL_PROFIT_LOCK_SECONDS,
        "sell_profit_lock_rearm_rebound_points": SELL_PROFIT_LOCK_REARM_REBOUND_POINTS,
        "sell_profit_lock_allow_max_fade_score": SELL_PROFIT_LOCK_ALLOW_MAX_FADE_SCORE,
        "sell_profit_lock_allow_campaign_score": SELL_PROFIT_LOCK_ALLOW_CAMPAIGN_SCORE,
        "loss_recovery_true_max_zone_enabled": LOSS_RECOVERY_TRUE_MAX_ZONE_ENABLED,
        "loss_recovery_sell_losses": LOSS_RECOVERY_SELL_LOSSES,
        "true_max_zone_min_day_position": TRUE_MAX_ZONE_MIN_DAY_POSITION,
        "true_max_zone_min_rebound_points": TRUE_MAX_ZONE_MIN_REBOUND_POINTS,
        "true_max_zone_min_score": TRUE_MAX_ZONE_MIN_SCORE,
        "true_max_zone_require_micro_bos": TRUE_MAX_ZONE_REQUIRE_MICRO_BOS,
        "big_move_thesis_enabled": BIG_MOVE_THESIS_ENABLED,
        "big_move_alerts_enabled": BIG_MOVE_ALERTS_ENABLED,
        "big_move_min_tp_level": BIG_MOVE_MIN_TP_LEVEL,
        "big_move_confirmed_tp_level": BIG_MOVE_CONFIRMED_TP_LEVEL,
        "big_move_min_confluences": BIG_MOVE_MIN_CONFLUENCES,
        "big_move_target_step": BIG_MOVE_TARGET_STEP,
        "event_trap_flip_enabled": EVENT_TRAP_FLIP_ENABLED,
        "event_trap_flip_min_score": EVENT_TRAP_FLIP_MIN_SCORE,
        "event_trap_flip_min_buy_tp": EVENT_TRAP_FLIP_MIN_BUY_TP,
        "event_trap_flip_min_retrace_from_high": EVENT_TRAP_FLIP_MIN_RETRACE_FROM_HIGH,
        "event_trap_flip_max_event_close_position": EVENT_TRAP_FLIP_MAX_EVENT_CLOSE_POSITION,
        "deep_extension_sell_guard_enabled": DEEP_EXTENSION_SELL_GUARD_ENABLED,
        "deep_extension_sell_guard_min_score": DEEP_EXTENSION_SELL_GUARD_MIN_SCORE,
        "smart_kill_pre_bear_override_enabled": SMART_KILL_PRE_BEAR_OVERRIDE_ENABLED,
        "smart_kill_pre_bear_min_score": SMART_KILL_PRE_BEAR_MIN_SCORE,
        "smart_kill_pre_bear_max_attempts": SMART_KILL_PRE_BEAR_MAX_ATTEMPTS,
        "smart_kill_pre_bear_risk_weight": SMART_KILL_PRE_BEAR_RISK_WEIGHT,
        "campaign_profit_lock_enabled": CAMPAIGN_PROFIT_LOCK_ENABLED,
        "campaign_profit_lock_seconds": CAMPAIGN_PROFIT_LOCK_SECONDS,
        "campaign_profit_lock_min_tp": CAMPAIGN_PROFIT_LOCK_MIN_TP,
        "campaign_profit_lock_invalidation_points": CAMPAIGN_PROFIT_LOCK_INVALIDATION_POINTS,
        "campaign_profit_lock_allow_score": CAMPAIGN_PROFIT_LOCK_ALLOW_SCORE,
        "buy_campaign_exhaustion_enabled": BUY_CAMPAIGN_EXHAUSTION_ENABLED,
        "buy_campaign_exhaustion_min_tp": BUY_CAMPAIGN_EXHAUSTION_MIN_TP,
        "buy_campaign_exhaustion_min_day_position": BUY_CAMPAIGN_EXHAUSTION_MIN_DAY_POSITION,
        "buy_campaign_exhaustion_allow_score": BUY_CAMPAIGN_EXHAUSTION_ALLOW_SCORE,
        "max_pullback_rearm_enabled": MAX_PULLBACK_REARM_ENABLED,
        "max_pullback_rearm_min_buy_tp": MAX_PULLBACK_REARM_MIN_BUY_TP,
        "anti_fade_super_buy_enabled": ANTI_FADE_SUPER_BUY_ENABLED,
        "anti_fade_super_buy_min_buy_tp": ANTI_FADE_SUPER_BUY_MIN_BUY_TP,
        "regime_arbiter_states": REGIME_ARBITER_STATE,
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
# AUTO EVENT MODE v17
# =========================

def normalize_text_for_event(value):
    return str(value or "").lower()


def event_keyword_hits(text):
    text = normalize_text_for_event(text)
    hits = []

    for keyword in AUTO_EVENT_KEYWORDS:
        if keyword in text:
            hits.append(keyword)

    # Rimuovo duplicati preservando ordine
    unique = []
    for hit in hits:
        if hit not in unique:
            unique.append(hit)

    return unique


def reset_auto_event_memory_if_expired():
    if now_ts() <= AUTO_EVENT_CACHE.get("until", 0):
        return

    AUTO_EVENT_CACHE["start_time"] = 0
    AUTO_EVENT_CACHE["start_price"] = 0
    AUTO_EVENT_CACHE["high"] = 0
    AUTO_EVENT_CACHE["low"] = 0
    AUTO_EVENT_CACHE["high_time"] = 0
    AUTO_EVENT_CACHE["low_time"] = 0
    AUTO_EVENT_CACHE["pullback_low_after_high"] = 0
    AUTO_EVENT_CACHE["max_pullback_after_high"] = 0
    AUTO_EVENT_CACHE["pullback_time"] = 0


def update_auto_event_memory(data):
    if not AUTO_EVENT_MODE_ENABLED:
        return

    if now_ts() > AUTO_EVENT_CACHE.get("until", 0):
        reset_auto_event_memory_if_expired()
        return

    price = get_price_from_data(data)
    if not price:
        return

    now = now_ts()

    # Il primo prezzo dopo l'attivazione diventa il prezzo pre-evento / anchor.
    if not AUTO_EVENT_CACHE.get("start_price", 0):
        AUTO_EVENT_CACHE["start_price"] = price
        AUTO_EVENT_CACHE["start_time"] = now
        AUTO_EVENT_CACHE["high"] = price
        AUTO_EVENT_CACHE["low"] = price
        AUTO_EVENT_CACHE["high_time"] = now
        AUTO_EVENT_CACHE["low_time"] = now
        AUTO_EVENT_CACHE["pullback_low_after_high"] = price
        AUTO_EVENT_CACHE["max_pullback_after_high"] = 0
        AUTO_EVENT_CACHE["pullback_time"] = 0

    day_high = to_float(data.get("day_high"), 0)
    day_low = to_float(data.get("day_low"), 0)
    bar_high = to_float(data.get("high"), 0)
    bar_low = to_float(data.get("low"), 0)

    anchor = AUTO_EVENT_CACHE.get("start_price", 0)

    high_candidates = [price]
    low_candidates = [price]

    if bar_high:
        high_candidates.append(bar_high)

    if bar_low:
        low_candidates.append(bar_low)

    if day_high and day_high >= anchor:
        high_candidates.append(day_high)

    if day_low and day_low <= anchor:
        low_candidates.append(day_low)

    current_high = max(high_candidates)
    current_low = min(low_candidates)

    old_high = AUTO_EVENT_CACHE.get("high", 0)

    if not old_high or current_high > old_high:
        AUTO_EVENT_CACHE["high"] = current_high
        AUTO_EVENT_CACHE["high_time"] = now

        # Nuovo massimo = il retest non è ancora confermato.
        # Da questo punto aspettiamo prima un vero pullback e poi un ritorno vicino al top.
        AUTO_EVENT_CACHE["pullback_low_after_high"] = current_high
        AUTO_EVENT_CACHE["max_pullback_after_high"] = 0
        AUTO_EVENT_CACHE["pullback_time"] = 0
    else:
        high_now = AUTO_EVENT_CACHE.get("high", 0)

        if high_now:
            current_pullback = max(0, high_now - current_low)

            if current_pullback > AUTO_EVENT_CACHE.get("max_pullback_after_high", 0):
                AUTO_EVENT_CACHE["max_pullback_after_high"] = current_pullback
                AUTO_EVENT_CACHE["pullback_low_after_high"] = current_low
                AUTO_EVENT_CACHE["pullback_time"] = now

    if not AUTO_EVENT_CACHE.get("low", 0) or current_low < AUTO_EVENT_CACHE.get("low", 0):
        AUTO_EVENT_CACHE["low"] = current_low
        AUTO_EVENT_CACHE["low_time"] = now


def get_event_spike_context(data):
    active, reasons = auto_event_cache_active()

    if active:
        update_auto_event_memory(data)

    price = get_price_from_data(data)
    start_price = AUTO_EVENT_CACHE.get("start_price", 0)
    start_time = AUTO_EVENT_CACHE.get("start_time", 0)
    high = AUTO_EVENT_CACHE.get("high", 0)
    low = AUTO_EVENT_CACHE.get("low", 0)
    high_time = AUTO_EVENT_CACHE.get("high_time", 0)
    max_pullback_after_high = AUTO_EVENT_CACHE.get("max_pullback_after_high", 0)
    pullback_low_after_high = AUTO_EVENT_CACHE.get("pullback_low_after_high", 0)
    pullback_time = AUTO_EVENT_CACHE.get("pullback_time", 0)

    up_points = max(0, high - start_price) if start_price and high else 0
    down_points = max(0, start_price - low) if start_price and low else 0
    age = now_ts() - start_time if start_time else 999999
    seconds_after_high = now_ts() - high_time if high_time else 999999

    top_position = 0
    retrace_from_high = 0

    if start_price and high and high > start_price and price:
        top_position = (price - start_price) / (high - start_price)
        top_position = max(0, min(1, top_position))
        retrace_from_high = max(0, high - price)

    pullback_done = max_pullback_after_high >= FAILED_RETEST_MIN_PULLBACK_POINTS

    failed_retest_zone = (
        pullback_done
        and top_position >= FAILED_RETEST_TOP_POSITION_MIN
        and top_position <= FAILED_RETEST_TOP_POSITION_MAX
        and retrace_from_high <= FAILED_RETEST_NEAR_HIGH_DISTANCE
        and retrace_from_high >= FAILED_RETEST_MIN_DISTANCE_FROM_HIGH
        and seconds_after_high >= FAILED_RETEST_MIN_SECONDS_AFTER_HIGH
    )

    ctx = {
        "active": active,
        "reasons": reasons,
        "start_price": start_price,
        "start_time": start_time,
        "high": high,
        "low": low,
        "high_time": high_time,
        "price": price,
        "up_points": up_points,
        "down_points": down_points,
        "age": age,
        "top_position": top_position,
        "retrace_from_high": retrace_from_high,
        "seconds_after_high": seconds_after_high,
        "max_pullback_after_high": max_pullback_after_high,
        "pullback_low_after_high": pullback_low_after_high,
        "pullback_time": pullback_time,
        "pullback_done": pullback_done,
        "failed_retest_zone": failed_retest_zone,
        "up_confirmed": (
            active
            and age <= EVENT_SPIKE_LOOKBACK_SECONDS
            and up_points >= EVENT_SPIKE_MIN_UP_POINTS
        )
    }

    return ctx


def event_spike_status_text(ctx):
    if not ctx:
        return "Nessuna memoria evento"

    return (
        f"Event active: {ctx.get('active')} | "
        f"Anchor: {round(ctx.get('start_price', 0), 3)} | "
        f"High: {round(ctx.get('high', 0), 3)} | "
        f"Low: {round(ctx.get('low', 0), 3)} | "
        f"Up points: {round(ctx.get('up_points', 0), 2)} | "
        f"Top position: {round(ctx.get('top_position', 0), 2)} | "
        f"Retrace high: {round(ctx.get('retrace_from_high', 0), 2)} | "
        f"Pullback dopo high: {round(ctx.get('max_pullback_after_high', 0), 2)} | "
        f"Failed retest zone: {ctx.get('failed_retest_zone')}"
    )


def activate_auto_event_mode(reasons, data=None):
    if not AUTO_EVENT_MODE_ENABLED:
        return False, []

    clean_reasons = []

    for reason in reasons:
        if reason and reason not in clean_reasons:
            clean_reasons.append(str(reason))

    if not clean_reasons:
        return False, []

    AUTO_EVENT_CACHE["until"] = max(
        AUTO_EVENT_CACHE.get("until", 0),
        now_ts() + AUTO_EVENT_DURATION_SECONDS
    )
    AUTO_EVENT_CACHE["reasons"] = clean_reasons

    if data is not None:
        update_auto_event_memory(data)

    return True, clean_reasons


def auto_event_cache_active():
    if not AUTO_EVENT_MODE_ENABLED:
        return False, []

    if now_ts() < AUTO_EVENT_CACHE.get("until", 0):
        return True, AUTO_EVENT_CACHE.get("reasons", [])

    return False, []


def detect_auto_event_from_data(data):
    if not AUTO_EVENT_MODE_ENABLED:
        return False, []

    reasons = []

    # Se l'utente attiva manualmente Event Mode nel Pine, lo trasformo in cache temporanea.
    if to_bool(data.get("event_mode", "false")):
        reasons.append("Event Mode attivo da Pine/TradingView")

    if EVENT_RISK == "HIGH":
        reasons.append("EVENT_RISK=HIGH su Render")

    if AUTO_EVENT_VOLATILITY_ENABLED:
        atr = to_float(data.get("atr"), 0)
        volume_spike = to_bool(data.get("volume_spike", "false"))

        candle_range = to_float(data.get("candle_range"), 0)
        range_atr = to_float(data.get("range_atr"), 0)
        m15_range_atr = to_float(data.get("m15_range_atr"), 0)

        day_range = to_float(data.get("day_range"), 0)
        day_range_atr = (day_range / atr) if atr and day_range else 0

        if not range_atr and atr and candle_range:
            range_atr = candle_range / atr

        volatility_ok = True

        if AUTO_EVENT_VOLUME_SPIKE_REQUIRED and not volume_spike:
            volatility_ok = False

        if volatility_ok and range_atr >= AUTO_EVENT_CANDLE_ATR_MULT:
            reasons.append(f"Candela forte: range/ATR {round(range_atr, 2)}")

        if volatility_ok and m15_range_atr >= AUTO_EVENT_M15_RANGE_ATR_MULT:
            reasons.append(f"Range M15 esploso: M15/ATR {round(m15_range_atr, 2)}")

        if volatility_ok and day_range_atr >= AUTO_EVENT_DAY_RANGE_ATR_MULT:
            reasons.append(f"Range giornaliero elevato: DayRange/ATR {round(day_range_atr, 2)}")

        if volume_spike and (range_atr >= 1.5 or m15_range_atr >= 2.2):
            reasons.append("Volume spike con volatilità sopra media")

    if reasons:
        return activate_auto_event_mode(reasons, data)

    active, cached_reasons = auto_event_cache_active()
    if active:
        update_auto_event_memory(data)

    return active, cached_reasons


def auto_event_status_text(active, reasons):
    if not active:
        return "Auto Event Mode non attivo"

    until = AUTO_EVENT_CACHE.get("until", 0)

    try:
        until_local = local_datetime(until).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        until_local = str(until)

    lines = [
        "⚡ Auto Event Mode ATTIVO",
        f"Attivo fino a: {until_local}",
        "Motivi:"
    ]

    for reason in reasons:
        lines.append(f"- {reason}")

    return "\n".join(lines)



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
    auto_event_keyword_hits = []

    for article in articles:
        text = (
            (article.get("title") or "") + " " +
            (article.get("description") or "")
        ).lower()

        if AUTO_EVENT_MODE_ENABLED and AUTO_EVENT_KEYWORDS_ENABLED:
            hits = event_keyword_hits(text)
            for hit in hits:
                if hit not in auto_event_keyword_hits:
                    auto_event_keyword_hits.append(hit)

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

    if auto_event_keyword_hits:
        activate_auto_event_mode([
            "News macro keyword: " + ", ".join(auto_event_keyword_hits[:6])
        ])
        reasons.append("Auto Event keyword: " + ", ".join(auto_event_keyword_hits[:6]))

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

    # Campi extra mandati dal Pine v30/v31/v32/v33/v34/v35/v36/v37/v38/v39/v40/v41/v42/v43/v44/v45/v46
    close_above_ema20 = to_bool(data.get("close_above_ema20", "false"))
    close_above_ema50 = to_bool(data.get("close_above_ema50", "false"))
    recovery_buy_signal = to_bool(data.get("recovery_buy_signal", "false"))
    recent_low_touch = to_bool(data.get("recent_low_touch", "false"))

    # v16: campi per Max View / NFP Exhaustion Sell
    event_mode_from_pine = to_bool(data.get("event_mode", "false"))
    near_day_high = to_bool(data.get("near_day_high", "false"))
    near_day_low = to_bool(data.get("near_day_low", "false"))
    day_position = to_float(data.get("day_position"), -1)

    auto_event_active, auto_event_reasons = detect_auto_event_from_data(data)
    macro_event_mode = (
        MAX_VIEW_EVENT_MODE
        or event_mode_from_pine
        or EVENT_RISK == "HIGH"
        or auto_event_active
    )

    # TradingView v29 manda già questi campi. Se ci sono, li uso.
    if data.get("near_psych_level") is not None:
        near_psych_level = to_bool(data.get("near_psych_level"))

    if data.get("psych_level") is not None:
        nearest_psych = to_float(data.get("psych_level"), nearest_psych or 0)

    if data.get("psych_distance") is not None:
        psych_distance = to_float(data.get("psych_distance"), psych_distance or 999)

    active_news_bias, news_reasons = get_auto_news_bias()

    # v18: dopo le news, aggiorno ancora Auto Event.
    # Questo serve quando la keyword macro attiva l'evento proprio in questa candela.
    auto_event_active, auto_event_reasons = detect_auto_event_from_data(data)
    macro_event_mode = (
        MAX_VIEW_EVENT_MODE
        or event_mode_from_pine
        or EVENT_RISK == "HIGH"
        or auto_event_active
    )
    event_spike_ctx = get_event_spike_context(data)

    # v21: contesto bearish continuation già costruito dai PRICE_UPDATE.
    bear_state_ctx = get_bear_continuation_state(symbol)
    bear_state_name = str(bear_state_ctx.get("state", "IDLE")).upper()
    bear_state_active = bear_state_name in [
        "BEAR_IMPULSE",
        "RELIEF_RALLY",
        "LOWER_HIGH_ARMED",
        "SELL_TRIGGERED"
    ]

    # v22: tesi persistente della campagna.
    campaign_ctx = sync_bear_campaign(symbol, data)
    campaign_active = campaign_is_active(campaign_ctx)

    # v23: pre-bear thesis e deep extension flip.
    pre_bear_ctx = get_pre_bear_state(symbol)
    pre_bear_status = str(pre_bear_ctx.get("status", "IDLE")).upper()
    pre_bear_active = pre_bear_status in ["FAILED_RECOVERY_ARMED", "CONFIRMED"]
    deep_extension_ctx = get_deep_extension_context(symbol, data)

    # v25: continuation/campaign solo con trigger maturo.
    bear_maturity_ctx = bear_trigger_maturity_context(symbol, data)
    bear_trigger_mature = bool(bear_maturity_ctx.get("mature"))

    # v12 context:
    # se ci sono stati SELL profondi recenti, un BUY di recupero diventa più interessante.
    recent_deep_sells = get_recent_tp_trades(
        "SELL",
        symbol,
        min_tp=RECOVERY_BUY_TP_LEVEL,
        lookback_seconds=RECOVERY_BUY_LOOKBACK_SECONDS
    )

    # v16 context:
    # se la salita ha già pagato molto, Max spesso cerca SELL dai top/rimbalzi alti.
    recent_big_buys_for_view = get_recent_tp_trades(
        "BUY",
        symbol,
        min_tp=MAX_VIEW_BUY_TP_LEVEL,
        lookback_seconds=MAX_VIEW_LOOKBACK_SECONDS
    )

    # v38 context:
    # se un BUY ha già pagato TP6/TP8, lo spike alto può diventare zona fade SELL stile Max.
    recent_spike_fade_buys = get_recent_tp_trades(
        "BUY",
        symbol,
        min_tp=EXTREME_SPIKE_FADE_MIN_BUY_TP,
        lookback_seconds=EXTREME_SPIKE_FADE_BUY_LOOKBACK_SECONDS
    )

    # =========================
    # SETUP SPECIALI
    # =========================

    reversal_buy = (
        signal == "BUY"
        and not bear_state_active
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

    # MAX EVENT SPIKE SELL v18:
    # Questa è la lettura stile Max durante NFP:
    # il mercato esplode verso l'alto, prende liquidità sui massimi,
    # poi il top diventa zona di SELL anche se news/EMA sono bullish.
    event_spike_up_confirmed = bool(event_spike_ctx.get("up_confirmed"))
    event_spike_top_zone = (
        event_spike_up_confirmed
        and (
            event_spike_ctx.get("top_position", 0) >= EVENT_SPIKE_TOP_POSITION_MIN
            or near_day_high
            or near_m15_high
        )
    )

    event_spike_reversal_confirmed = (
        candle_dir == "BEAR"
        or structure in ["BEARISH", "HH", "LH"]
        or rejection == "UPPER_WICK"
        or upper_wick_strong
        or event_spike_ctx.get("retrace_from_high", 0) >= EVENT_SPIKE_SELL_RETRACE_POINTS
    )

    failed_retest_rejection = (
        candle_dir == "BEAR"
        or rejection == "UPPER_WICK"
        or upper_wick_strong
        or structure in ["BEARISH", "LH"]
        or event_spike_ctx.get("retrace_from_high", 0) >= FAILED_RETEST_MIN_DISTANCE_FROM_HIGH
    )

    failed_retest_ready = (
        FAILED_RETEST_SELL_ENABLED
        and macro_event_mode
        and event_spike_up_confirmed
        and event_spike_ctx.get("pullback_done")
        and event_spike_ctx.get("failed_retest_zone")
        and (
            failed_retest_rejection
            or not FAILED_RETEST_REJECTION_REQUIRED
        )
    )

    failed_retest_confirmations = 0

    if event_spike_up_confirmed:
        failed_retest_confirmations += 1

    if event_spike_ctx.get("pullback_done"):
        failed_retest_confirmations += 1

    if event_spike_ctx.get("failed_retest_zone"):
        failed_retest_confirmations += 1

    if failed_retest_rejection:
        failed_retest_confirmations += 1

    if macro_event_mode:
        failed_retest_confirmations += 1

    max_failed_retest_sell = (
        FAILED_RETEST_SELL_ENABLED
        and signal == "SELL"
        and failed_retest_ready
        and (
            structure in ["HH", "BEARISH", "LH"]
            or candle_dir == "BEAR"
            or rejection == "UPPER_WICK"
            or upper_wick_strong
        )
    )

    # Se v19 richiede retest, i SELL da top troppo anticipati vengono spenti.
    # Così evitiamo di vendere il primo top casuale: prima pullback, poi retest alto fallito.
    event_sell_retest_guard_ok = (
        not FAILED_RETEST_BLOCK_EARLY_SELLS
        or not event_spike_up_confirmed
        or event_spike_ctx.get("pullback_done")
    )

    event_spike_confirmations = 0

    if event_spike_up_confirmed:
        event_spike_confirmations += 1

    if event_spike_top_zone:
        event_spike_confirmations += 1

    if event_spike_reversal_confirmed:
        event_spike_confirmations += 1

    if day_bias == "SELL":
        event_spike_confirmations += 1

    if macro_event_mode:
        event_spike_confirmations += 1

    max_event_spike_sell = (
        EVENT_SPIKE_REVERSAL_ENABLED
        and signal == "SELL"
        and macro_event_mode
        and event_spike_up_confirmed
        and event_spike_top_zone
        and event_spike_reversal_confirmed
        and event_sell_retest_guard_ok
        and day_bias == "SELL"
        and structure in ["HH", "BEARISH", "LH"]
    )

    # v38 EXTREME SPIKE FADE SELL:
    # Caso Max: il prezzo esplode al rialzo da evento/news, il BUY ha già pagato TP6/TP8,
    # poi in area alta nasce un SELL da exhaustion/failed retest anche se Daily/EMA/news restano bullish.
    extreme_spike_fade_confirmations = 0
    extreme_spike_fade_rejection = bool(
        candle_dir == "BEAR"
        or rejection == "UPPER_WICK"
        or upper_wick_strong
        or structure in ["BEARISH", "LH", "HH"]
        or event_spike_ctx.get("failed_retest_zone")
        or event_spike_ctx.get("retrace_from_high", 0) >= EXTREME_SPIKE_FADE_RETRACE_MIN
    )
    extreme_spike_fade_zone = bool(
        event_spike_ctx.get("top_position", 0) >= EXTREME_SPIKE_FADE_TOP_POSITION_MIN
        or near_day_high
        or near_m15_high
        or (day_position >= 0.82 if day_position >= 0 else False)
    )
    extreme_spike_fade_near_high = bool(
        event_spike_ctx.get("retrace_from_high", 999999) <= EXTREME_SPIKE_FADE_NEAR_HIGH_MAX_DISTANCE
    )

    if event_spike_up_confirmed and event_spike_ctx.get("up_points", 0) >= EXTREME_SPIKE_FADE_MIN_UP_POINTS:
        extreme_spike_fade_confirmations += 1
    if extreme_spike_fade_zone:
        extreme_spike_fade_confirmations += 1
    if extreme_spike_fade_near_high:
        extreme_spike_fade_confirmations += 1
    if extreme_spike_fade_rejection:
        extreme_spike_fade_confirmations += 1
    if len(recent_spike_fade_buys) >= 1:
        extreme_spike_fade_confirmations += 1
    if macro_event_mode:
        extreme_spike_fade_confirmations += 1
    if event_spike_ctx.get("pullback_done") or event_spike_ctx.get("failed_retest_zone"):
        extreme_spike_fade_confirmations += 1

    extreme_spike_fade_sell = (
        EXTREME_SPIKE_FADE_SELL_ENABLED
        and signal == "SELL"
        and (macro_event_mode or not EXTREME_SPIKE_FADE_REQUIRE_EVENT)
        and event_spike_up_confirmed
        and event_spike_ctx.get("up_points", 0) >= EXTREME_SPIKE_FADE_MIN_UP_POINTS
        and len(recent_spike_fade_buys) >= 1
        and extreme_spike_fade_zone
        and extreme_spike_fade_near_high
        and extreme_spike_fade_rejection
        and extreme_spike_fade_confirmations >= EXTREME_SPIKE_FADE_MIN_CONFIRMATIONS
    )

    # MAX VIEW SELL v16:
    # Questa è la lettura stile Max di oggi:
    # dopo una salita forte e BUY già pagati, il rimbalzo alto diventa zona di SELL,
    # specialmente con NFP / evento macro / Daily ancora SELL.
    max_view_top_zone = (
        near_m15_high
        or near_day_high
        or (day_position >= MAX_VIEW_SELL_DAY_POSITION_MIN if day_position >= 0 else False)
    )

    max_view_rejection = (
        rejection == "UPPER_WICK"
        or upper_wick_strong
        or candle_dir == "BEAR"
        or rsi >= MAX_VIEW_MIN_RSI
        or volume_spike
    )

    max_view_confirmations = 0

    if len(recent_big_buys_for_view) >= MAX_VIEW_BUY_COUNT:
        max_view_confirmations += 1

    if max_view_top_zone:
        max_view_confirmations += 1

    if max_view_rejection:
        max_view_confirmations += 1

    if day_bias == "SELL":
        max_view_confirmations += 1

    if macro_event_mode:
        max_view_confirmations += 1

    if event_spike_up_confirmed:
        max_view_confirmations += 1

    max_view_sell = (
        MAX_VIEW_SELL_ENABLED
        and signal == "SELL"
        and day_bias == "SELL"
        and (
            len(recent_big_buys_for_view) >= MAX_VIEW_BUY_COUNT
            or event_spike_up_confirmed
        )
        and max_view_top_zone
        and max_view_rejection
        and event_sell_retest_guard_ok
        and structure in ["HH", "BEARISH", "LH"]
        and rsi > 38
    )

    # PRE-BEAR SELL v23:
    # Vende il failed recovery prima che il bear impulse completo sia già evidente.
    pre_bear_sell = (
        PRE_BEAR_THESIS_ENABLED
        and signal == "SELL"
        and pre_bear_active
        and not bear_state_active
        and (
            str(data.get("pre_bear_sell_candidate", "false")).lower() == "true"
            or candle_dir == "BEAR"
            or rejection == "UPPER_WICK"
            or upper_wick_strong
            or structure in ["LH", "BEARISH", "HH"]
        )
    )

    # BEAR CAMPAIGN SELL v22:
    # Promuove un SELL coerente con una tesi ribassista già attiva,
    # soprattutto su nuovo retest alto / lower high.
    bear_campaign_sell = (
        CAMPAIGN_MANAGER_ENABLED
        and CAMPAIGN_SELL_PROMOTION_ENABLED
        and signal == "SELL"
        and campaign_active
        and bear_trigger_mature
        and bear_state_name in ["LOWER_HIGH_ARMED", "SELL_TRIGGERED"]
        and (
            structure in ["BEARISH", "LH", "HH"]
            or candle_dir == "BEAR"
            or rejection == "UPPER_WICK"
            or upper_wick_strong
        )
    )

    # BEAR CONTINUATION SELL v21:
    # Classifica i SELL normali come continuation SELL quando la macchina a stati
    # ha già visto impulso/rally/lower-high.
    bear_continuation_sell = (
        BEAR_CONTINUATION_ENGINE_ENABLED
        and signal == "SELL"
        and bear_trigger_mature
        and bear_state_name in [
            "LOWER_HIGH_ARMED",
            "SELL_TRIGGERED"
        ]
        and (
            structure in ["BEARISH", "LH", "HH"]
            or candle_dir == "BEAR"
        )
        and (
            ema20_slope == "DOWN"
            or ema50_slope == "DOWN"
            or candle_dir == "BEAR"
            or bear_state_name in ["LOWER_HIGH_ARMED", "SELL_TRIGGERED"]
        )
    )

    # v25: se il contesto bearish esiste ma non è ancora maturo,
    # non promuovo il SELL a continuation/campaign.
    if signal == "SELL" and bear_state_active and not bear_trigger_mature:
        reasons.append("Regime Arbiter: continuation declassata, trigger non maturo")

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

    if deep_extension_ctx.get("active"):
        recovery_confirmations += 1

    max_recovery_buy = (
        RECOVERY_BUY_ENABLED
        and signal == "BUY"
        and active_news_bias == "BULLISH_GOLD"
        and (
            len(recent_deep_sells) >= RECOVERY_BUY_DEEP_SELL_COUNT
            or deep_extension_ctx.get("active")
        )
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
        and not bear_state_active
        and active_news_bias == "BULLISH_GOLD"
        and structure in ["LL", "BULLISH"]
        and rsi > 26
        and rsi < 62
        and dip_confirmations >= 2
    )

    # v32: BUY di rimbalzo dopo SELL profondo stile Max.
    # Serve quando il Pine manda un BUY normale dentro bear state, ma il SELL ha già pagato TP6+/runner
    # e il prezzo è in zona low/psicologica.
    deep_rebound_buy_ctx = deep_rebound_buy_candidate_context(signal, symbol, data)
    deep_rebound_buy = bool(deep_rebound_buy_ctx.get("allow"))

    # v36: se una campagna BUY ha già pagato bene e il prezzo fa pullback controllato,
    # non considero automaticamente quel rimbalzo un SELL_CONTROL. Può diventare nuovo BUY stile Max.
    max_pullback_rearm_ctx = max_pullback_rearm_buy_context(signal, symbol, data)
    max_pullback_rearm_buy = bool(max_pullback_rearm_ctx.get("allow"))

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

    if pre_bear_sell:
        setup_type = "PRE_BEAR_SELL"
        score += PRE_BEAR_SELL_BASE_BONUS
        reasons.append(
            f"PRE-BEAR SELL: failed recovery prima del bear impulse ({pre_bear_status})"
        )
        reasons.append(
            f"Prior drop {round(to_float(pre_bear_ctx.get('prior_drop')), 2)} | "
            f"Retrace {round(to_float(pre_bear_ctx.get('retrace')), 2)} | "
            f"Lower-high gap {round(to_float(pre_bear_ctx.get('lower_high_gap')), 2)}"
        )
        if rejection == "UPPER_WICK" or upper_wick_strong:
            score += 3
            reasons.append("Pre-Bear: upper rejection confermata")
        if candle_dir == "BEAR":
            score += 2
            reasons.append("Pre-Bear: candela bearish di fallimento")

    elif bear_campaign_sell:
        setup_type = "BEAR_CAMPAIGN_SELL"
        score += CAMPAIGN_SELL_BASE_BONUS
        reasons.append(
            f"BEAR CAMPAIGN SELL: tesi persistente {campaign_ctx.get('campaign_id')}"
        )
        reasons.append(
            f"Campagna legs {len(campaign_ctx.get('legs', []))}/{CAMPAIGN_MAX_LEGS}"
        )

        if bear_state_name == "LOWER_HIGH_ARMED":
            score += 4
            reasons.append("Campaign: lower high armato")

        if candle_dir == "BEAR":
            score += 2
            reasons.append("Campaign: conferma bearish")

    elif bear_continuation_sell:
        setup_type = "BEAR_CONTINUATION_SELL"
        score += BEAR_CONTINUATION_BASE_BONUS
        reasons.append(
            f"BEAR CONTINUATION SELL: state {bear_state_name}"
        )
        reasons.append(
            f"Impulse drop: {round(to_float(bear_state_ctx.get('impulse_drop')), 2)} | "
            f"Rally peak: {round(to_float(bear_state_ctx.get('rally_peak')), 2)}"
        )

        if bear_state_name == "LOWER_HIGH_ARMED":
            score += 4
            reasons.append("Lower high armato")

        if candle_dir == "BEAR":
            score += 2
            reasons.append("Conferma candela bearish su continuation")

    elif extreme_spike_fade_sell:
        setup_type = "EXTREME_SPIKE_FADE_SELL"
        score += EXTREME_SPIKE_FADE_BASE_BONUS
        reasons.append(
            f"EXTREME SPIKE FADE SELL: top evento dopo BUY TP{EXTREME_SPIKE_FADE_MIN_BUY_TP}+ ({extreme_spike_fade_confirmations} conferme)"
        )
        reasons.append(event_spike_status_text(event_spike_ctx))
        reasons.append(
            f"BUY già pagati: {len(recent_spike_fade_buys)} trade almeno TP{EXTREME_SPIKE_FADE_MIN_BUY_TP}"
        )
        if macro_event_mode:
            score += EXTREME_SPIKE_FADE_EVENT_BONUS
            reasons.append("Evento/news attivo: spike maturo, possibile fade stile Max")
        if extreme_spike_fade_zone:
            score += 3
            reasons.append("Zona alta estrema / top spike confermato")
        if extreme_spike_fade_rejection:
            score += 3
            reasons.append("Rejection/fallimento retest alto confermato")
        if day_bias == "BUY" and EXTREME_SPIKE_FADE_ALLOW_AGAINST_DAILY_BUY:
            reasons.append("Daily BUY ignorato: SELL da extreme spike fade post-runner")
        if active_news_bias == "BULLISH_GOLD" and EXTREME_SPIKE_FADE_ALLOW_AGAINST_BULLISH_NEWS:
            reasons.append("News bullish ignorate: BUY già pagato e spike in zona estrema")

    elif max_failed_retest_sell:
        setup_type = "MAX_FAILED_RETEST_SELL"
        score += FAILED_RETEST_SELL_BASE_BONUS
        reasons.append(f"MAX FAILED RETEST SELL: retest alto fallito dopo spike ({failed_retest_confirmations} conferme)")

        score += FAILED_RETEST_EVENT_BONUS
        reasons.append(event_spike_status_text(event_spike_ctx))

        if day_bias == "BUY" and FAILED_RETEST_ALLOW_AGAINST_DAILY_BUY:
            reasons.append("Daily BUY ignorato: SELL da failed retest post-evento")

        if active_news_bias == "BULLISH_GOLD" and FAILED_RETEST_ALLOW_SELL_AGAINST_BULLISH_NEWS:
            reasons.append("News bullish ignorate: spike già maturo, retest alto fallito")

        if failed_retest_rejection:
            score += 3
            reasons.append("Conferma rejection/fallimento retest")

    elif max_event_spike_sell:
        setup_type = "MAX_EVENT_SPIKE_SELL"
        score += EVENT_SPIKE_SELL_BASE_BONUS
        reasons.append(f"MAX EVENT SPIKE SELL: spike NFP/evento da top ({event_spike_confirmations} conferme)")

        score += EVENT_SPIKE_EVENT_BONUS
        reasons.append(event_spike_status_text(event_spike_ctx))

        if near_day_high or near_m15_high:
            score += 3
            reasons.append("Prezzo in zona massimi / liquidity sweep")

        if event_spike_ctx.get("retrace_from_high", 0) >= EVENT_SPIKE_SELL_RETRACE_POINTS:
            score += 2
            reasons.append(f"Rifiuto dal top: retrace {round(event_spike_ctx.get('retrace_from_high', 0), 2)} punti")

    elif max_view_sell:
        setup_type = "MAX_VIEW_SELL"
        score += MAX_VIEW_SELL_BASE_BONUS
        reasons.append(f"MAX VIEW SELL: top/rimbalzo alto dopo BUY profondi ({max_view_confirmations} conferme)")

        if len(recent_big_buys_for_view) >= MAX_VIEW_BUY_COUNT:
            score += 3
            reasons.append(f"Contesto post BUY forti: {len(recent_big_buys_for_view)} BUY almeno TP{MAX_VIEW_BUY_TP_LEVEL}")

        if max_view_top_zone:
            score += 3
            if day_position >= 0:
                reasons.append(f"Prezzo in zona alta del giorno: day position {round(day_position, 2)}")
            else:
                reasons.append("Prezzo vicino massimo M15/giorno")

        if macro_event_mode:
            score += MAX_VIEW_EVENT_BONUS
            if auto_event_active and auto_event_reasons:
                reasons.append("Auto Event Mode: " + " | ".join(auto_event_reasons[:3]))
            else:
                reasons.append("Modalità evento/NFP: possibile exhaustion sell")

    elif max_pullback_rearm_buy:
        setup_type = "MAX_PULLBACK_REARM_BUY"
        score += MAX_PULLBACK_REARM_BASE_BONUS
        reasons.append(
            f"MAX PULLBACK RE-ARM BUY: campagna BUY già pagata + pullback controllato ({max_pullback_rearm_ctx.get('confirmations')}/{MAX_PULLBACK_REARM_MIN_CONFIRMATIONS})"
        )
        reasons.append(max_pullback_rearm_ctx.get("reason", "Pullback re-arm attivo"))
        for item in (max_pullback_rearm_ctx.get("reasons") or [])[:5]:
            reasons.append(item)

    elif deep_rebound_buy:
        setup_type = "DEEP_REBOUND_BUY"
        score += DEEP_REBOUND_BUY_BASE_BONUS
        reasons.append("DEEP REBOUND BUY: rimbalzo dopo SELL TP6+/runner stile Max")
        reasons.append(
            f"SELL già pagato | drop {round(to_float(deep_rebound_buy_ctx.get('impulse_drop')), 2)} | "
            f"dist low {round(to_float(deep_rebound_buy_ctx.get('distance_from_low')), 2)} | "
            f"conferme {deep_rebound_buy_ctx.get('confirmations')}/{DEEP_REBOUND_BUY_MIN_CONFIRMATIONS}"
        )
        if deep_rebound_buy_ctx.get("near_low"):
            score += 3
            reasons.append("Prezzo vicino low/psicologico per rebound")
        if candle_dir == "BULL" or recovery_buy_signal:
            score += 2
            reasons.append("Prima reazione BUY confermata")

    elif max_recovery_buy:
        setup_type = "MAX_RECOVERY_BUY"
        score += 9
        reasons.append(f"MAX RECOVERY BUY: recupero dopo grande discesa ({recovery_confirmations} conferme)")

        if len(recent_deep_sells) >= RECOVERY_BUY_DEEP_SELL_COUNT:
            score += 2
            reasons.append(f"Contesto post SELL profondi: {len(recent_deep_sells)} trade almeno TP{RECOVERY_BUY_TP_LEVEL}")

        if near_psych_level:
            score += 3
            reasons.append(f"Recupero vicino livello psicologico {nearest_psych}")

        if deep_extension_ctx.get("active"):
            score += DEEP_EXTENSION_RECOVERY_BONUS
            reasons.append(
                f"DEEP EXTENSION FLIP: SELL già molto pagato / prezzo vicino low (+{DEEP_EXTENSION_RECOVERY_BONUS})"
            )

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
    # BEARISH STATE SCORE CONTROL v21
    # =========================

    if signal == "BUY" and bear_state_active:
        if setup_type in ["MAX_RECOVERY_BUY", "DEEP_REBOUND_BUY", "MAX_PULLBACK_REARM_BUY"]:
            if deep_extension_ctx.get("active") or setup_type in ["DEEP_REBOUND_BUY", "MAX_PULLBACK_REARM_BUY"]:
                reasons.append(
                    f"Bear state {bear_state_name} declassato: BUY da deep/pullback re-arm ammesso"
                )
            else:
                score -= 4
                reasons.append(
                    f"Bear state {bear_state_name}: recovery BUY penalizzato"
                )
        elif setup_type in ["MAX_DIP_BUY", "REVERSAL_BUY"]:
            score -= 10
            reasons.append(
                f"Bear state {bear_state_name}: BUY speciale contro continuation"
            )
        else:
            score -= 8
            reasons.append(
                f"Bear state {bear_state_name}: BUY contro impulso/continuazione"
            )

    # =========================
    # DEEP EXTENSION SCORE CONTROL v23
    # =========================

    if signal == "SELL" and deep_extension_ctx.get("active"):
        if setup_type not in DEEP_EXTENSION_ALWAYS_ALLOW_SELL_SETUPS:
            score -= DEEP_EXTENSION_SELL_PENALTY
            reasons.append(
                f"Deep Extension: nuovo SELL basso penalizzato (-{DEEP_EXTENSION_SELL_PENALTY})"
            )

    # =========================
    # EVENT SPIKE TOP BUY BLOCK v18
    # =========================

    if (
        EVENT_SPIKE_BLOCK_TOP_BUY_ENABLED
        and signal == "BUY"
        and macro_event_mode
        and event_spike_ctx.get("up_points", 0) >= EVENT_SPIKE_BLOCK_BUY_MIN_UP_POINTS
        and event_spike_ctx.get("top_position", 0) >= EVENT_SPIKE_BLOCK_BUY_TOP_POSITION_MIN
        and not near_day_low
        and not near_m15_low
    ):
        return -999, [
            "BUY bloccato: prezzo nella parte alta dello spike da evento/NFP",
            event_spike_status_text(event_spike_ctx),
            "La v19 non compra lo spike: aspetta pullback basso o SELL da failed retest"
        ], active_news_bias, news_reasons, setup_type

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
            if bear_state_active and not max_pullback_rearm_buy:
                reasons.append(
                    f"News bullish declassate: bear state {bear_state_name} attivo"
                )
            else:
                score += 1
                if max_pullback_rearm_buy and bear_state_active:
                    reasons.append("News bullish riabilitate: Pullback Re-Arm BUY attivo")
                else:
                    reasons.append("News bullish gold")
        else:
            if (
                pre_bear_sell
                or bear_campaign_sell
                or bear_continuation_sell
                or max_fade_sell
                or (extreme_spike_fade_sell and EXTREME_SPIKE_FADE_ALLOW_AGAINST_BULLISH_NEWS)
                or (max_failed_retest_sell and FAILED_RETEST_ALLOW_SELL_AGAINST_BULLISH_NEWS)
                or (max_view_sell and MAX_VIEW_ALLOW_SELL_AGAINST_BULLISH_NEWS)
                or (max_event_spike_sell and EVENT_SPIKE_ALLOW_SELL_AGAINST_BULLISH_NEWS)
            ):
                if pre_bear_sell:
                    reasons.append("SELL contro news bullish permesso: PRE-BEAR FAILED RECOVERY")
                elif bear_campaign_sell:
                    reasons.append("SELL contro news bullish permesso: BEAR CAMPAIGN")
                elif bear_continuation_sell and BEAR_CONTINUATION_IGNORE_BULLISH_NEWS:
                    reasons.append("SELL contro news bullish permesso: BEAR CONTINUATION")
                elif extreme_spike_fade_sell:
                    reasons.append("SELL contro news bullish permesso: EXTREME SPIKE FADE dopo BUY già pagato")
                elif max_failed_retest_sell:
                    reasons.append("SELL contro news bullish permesso: MAX FAILED RETEST SELL")
                elif max_event_spike_sell:
                    reasons.append("SELL contro news bullish permesso: MAX EVENT SPIKE SELL")
                elif max_view_sell:
                    reasons.append("SELL contro news bullish permesso: MAX VIEW SELL da top")
                else:
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
            if max_dip_buy or max_recovery_buy or max_pullback_rearm_buy:
                score -= 1
                reasons.append("BUY da fondo/recupero/pullback re-arm contro Daily SELL accettato")
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
            if max_dip_buy or max_recovery_buy or max_pullback_rearm_buy:
                reasons.append("Candela rossa accettata: exhaustion/recovery/pullback re-arm BUY")
            else:
                score -= 2
                reasons.append("Candela rossa contro BUY")

        if rejection == "LOWER_WICK":
            score += 2
            reasons.append("Rejection bullish")

        if rejection == "UPPER_WICK":
            if max_dip_buy or max_recovery_buy or max_pullback_rearm_buy:
                score -= 1
                reasons.append("Wick alta ma BUY speciale/re-arm ancora valido")
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
            if max_dip_buy or max_recovery_buy or max_pullback_rearm_buy:
                score -= 1
                reasons.append("EMA20 DOWN ma BUY speciale/re-arm")
            elif reversal_buy:
                score -= 1
                reasons.append("EMA20 DOWN ma reversal BUY")
            else:
                score -= 4
                reasons.append("EMA20 DOWN")

        if ema50_slope == "DOWN":
            if max_dip_buy or max_recovery_buy or max_pullback_rearm_buy:
                score -= 1
                reasons.append("EMA50 DOWN ma BUY speciale/re-arm")
            elif reversal_buy:
                score -= 1
                reasons.append("EMA50 DOWN ma reversal BUY")
            else:
                score -= 2
                reasons.append("EMA50 DOWN")

        if volume_spike and candle_dir == "BEAR":
            if max_dip_buy or max_recovery_buy or max_pullback_rearm_buy:
                score -= 1
                reasons.append("Volume bearish ma BUY speciale/re-arm ancora valido")
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
            if pre_bear_sell:
                score -= 1
                reasons.append("Daily BUY ma failed recovery pre-bear confermato")
            elif bear_campaign_sell:
                score -= 1
                reasons.append("Daily BUY ma campagna bearish persistente già confermata")
            elif bear_continuation_sell and BEAR_CONTINUATION_ALLOW_AGAINST_DAILY_BUY:
                score -= 1
                reasons.append("Daily BUY ma bearish continuation già confermata")
            elif extreme_spike_fade_sell and EXTREME_SPIKE_FADE_ALLOW_AGAINST_DAILY_BUY:
                score -= 1
                reasons.append("Daily BUY ma extreme spike fade SELL post-runner")
            elif max_failed_retest_sell and FAILED_RETEST_ALLOW_AGAINST_DAILY_BUY:
                score -= 1
                reasons.append("Daily BUY ma failed retest SELL post-evento")
            elif reversal_sell:
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
            if (
                (pre_bear_sell and pre_bear_active)
                or (bear_continuation_sell and bear_state_name in ["RELIEF_RALLY", "LOWER_HIGH_ARMED"])
                or (max_fade_sell and rejection == "UPPER_WICK")
                or (max_failed_retest_sell and event_spike_ctx.get("failed_retest_zone"))
                or (extreme_spike_fade_sell and extreme_spike_fade_zone)
                or (max_view_sell and max_view_top_zone)
                or (max_event_spike_sell and event_spike_top_zone)
            ):
                if pre_bear_sell:
                    reasons.append("Candela verde accettata: failed recovery / upper rejection pre-bear")
                elif bear_continuation_sell:
                    reasons.append("Candela verde accettata: relief rally/lower high SELL")
                elif max_failed_retest_sell:
                    reasons.append("Candela verde accettata: failed retest SELL")
                elif max_event_spike_sell:
                    reasons.append("Candela verde accettata: SELL post spike evento")
                elif extreme_spike_fade_sell:
                    reasons.append("Candela verde accettata: fade da spike estremo già maturo")
                elif max_view_sell:
                    reasons.append("Candela verde accettata: SELL da top/exhaustion")
                else:
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
            if reversal_sell or pre_bear_sell or bear_campaign_sell or bear_continuation_sell or max_fade_sell or max_failed_retest_sell or extreme_spike_fade_sell or max_view_sell or max_event_spike_sell:
                score -= 1
                reasons.append("EMA20 UP ma setup SELL speciale")
            else:
                score -= 2
                reasons.append("EMA20 UP")

        if ema50_slope == "UP":
            if reversal_sell or pre_bear_sell or bear_campaign_sell or bear_continuation_sell or max_fade_sell or max_failed_retest_sell or extreme_spike_fade_sell or max_view_sell or max_event_spike_sell:
                score -= 1
                reasons.append("EMA50 UP ma setup SELL speciale")
            else:
                score -= 2
                reasons.append("EMA50 UP")

        if volume_spike and candle_dir == "BULL":
            if pre_bear_sell:
                score -= 1
                reasons.append("Volume spike bullish ma pre-bear failed recovery ancora valido")
            elif bear_campaign_sell:
                score -= 1
                reasons.append("Volume spike bullish ma campagna bearish ancora valida")
            elif bear_continuation_sell:
                score -= 1
                reasons.append("Volume spike bullish ma bearish continuation ancora valida")
            elif max_failed_retest_sell:
                score -= 1
                reasons.append("Volume spike bullish ma failed retest SELL ancora valido")
            elif max_event_spike_sell:
                score -= 1
                reasons.append("Volume spike bullish ma SELL post-evento ancora valido")
            elif extreme_spike_fade_sell:
                score -= 1
                reasons.append("Volume bullish ma extreme spike fade SELL ancora valido")
            elif max_view_sell:
                score -= 1
                reasons.append("Volume spike bullish ma SELL da exhaustion/top ancora valido")
            else:
                score -= 3
                reasons.append("Volume spike bullish")

    # v34 Master Regime: il prezzo domina le news.
    # Se la giornata passa in SELL_CONTROL, le news bullish non devono più impedire
    # un SELL da lower-high / bear impulse; al contrario i BUY vengono penalizzati.
    if MASTER_REGIME_ENABLED:
        master_ctx = get_master_regime_context(symbol, data)
        master_mode = str(master_ctx.get("mode", "MIXED")).upper()

        if signal == "SELL" and master_mode == "SELL_CONTROL":
            if MASTER_REGIME_PRICE_DOMINATES_NEWS and active_news_bias == "BULLISH_GOLD":
                score += MASTER_REGIME_SELL_SCORE_BONUS
                reasons.append(
                    f"Master Regime SELL_CONTROL: price action domina news bullish (+{MASTER_REGIME_SELL_SCORE_BONUS})"
                )
            elif master_ctx.get("allow_lower_high_sell"):
                score += max(2, MASTER_REGIME_SELL_SCORE_BONUS // 2)
                reasons.append("Master Regime SELL_CONTROL: lower-high / impulso bearish confermato")

            if setup_type == "NORMAL" and MASTER_REGIME_ALLOW_NORMAL_SELL_IN_SELL_CONTROL:
                score += MASTER_REGIME_NORMAL_SELL_EXTRA_BONUS
                reasons.append(
                    f"Master Regime: NORMAL SELL consentito in SELL_CONTROL (+{MASTER_REGIME_NORMAL_SELL_EXTRA_BONUS})"
                )

        if signal == "BUY" and master_mode == "SELL_CONTROL" and not (master_ctx.get("allow_rebound_buy") or max_pullback_rearm_buy):
            score -= MASTER_REGIME_BLOCK_BUY_SCORE_PENALTY
            reasons.append(
                f"Master Regime SELL_CONTROL: BUY contro giornata sell (-{MASTER_REGIME_BLOCK_BUY_SCORE_PENALTY})"
            )
        elif signal == "BUY" and master_mode == "SELL_CONTROL" and max_pullback_rearm_buy:
            score += max(0, MAX_PULLBACK_REARM_SCORE_FLOOR - int(score))
            reasons.append("Master Regime SELL_CONTROL declassato: Pullback Re-Arm BUY stile Max")

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
# v37: ANTI WHIPSAW + POST SL QUARANTINE
# =========================

def latest_direct_loss_any(symbol, lookback_seconds):
    now = now_ts()
    symbol = str(symbol or "XAUUSD").upper()
    losses = []

    for trade in OPEN_TRADES:
        if str(trade.get("symbol", "")).upper() != symbol:
            continue
        if trade.get("status") != "LOSS":
            continue
        if int(trade.get("highest_tp", 0) or 0) > 0:
            continue

        closed = to_float(trade.get("closed") or trade.get("created") or 0, 0)
        if closed and now - closed <= lookback_seconds:
            losses.append(trade)

    if not losses:
        return None

    return sorted(
        losses,
        key=lambda x: to_float(x.get("closed") or x.get("created") or 0, 0),
        reverse=True
    )[0]


def post_sl_confirmation_ok(signal, data):
    signal = normalize_signal(signal)
    data = data or {}

    day_position = to_float(data.get("day_position"), 0.5)
    near_m15_high = to_bool(data.get("near_m15_high"))
    near_m15_low = to_bool(data.get("near_m15_low"))
    upper_wick = to_bool(data.get("upper_wick_strong")) or str(data.get("rejection", "")).upper() == "UPPER_WICK"
    lower_wick = to_bool(data.get("lower_wick_strong")) or str(data.get("rejection", "")).upper() == "LOWER_WICK"
    candle_dir = str(data.get("candle_dir", "")).upper()
    ema20_slope = str(data.get("ema20_slope", "")).upper()
    ema50_slope = str(data.get("ema50_slope", "")).upper()

    micro_bos_bear = bool(
        to_bool(data.get("micro_bos_bear"))
        or to_bool(data.get("bear_micro_bos"))
        or to_bool(data.get("bearish_micro_bos"))
    )
    micro_bos_bull = bool(
        to_bool(data.get("micro_bos_bull"))
        or to_bool(data.get("bull_micro_bos"))
        or to_bool(data.get("bullish_micro_bos"))
    )

    if signal == "SELL":
        bos_ok = (not POST_SL_REQUIRE_MICRO_BOS) or micro_bos_bear or candle_dir == "BEAR"
        retest_ok = (not POST_SL_REQUIRE_RETEST_ZONE) or near_m15_high or upper_wick or day_position >= POST_SL_SELL_MIN_DAY_POSITION
        momentum_ok = candle_dir == "BEAR" or ema20_slope == "DOWN" or ema50_slope == "DOWN"
        return bool(bos_ok and retest_ok and momentum_ok), {
            "micro_bos": micro_bos_bear,
            "retest_zone": retest_ok,
            "momentum": momentum_ok,
            "day_position": day_position,
            "near_m15_high": near_m15_high,
            "upper_wick": upper_wick
        }

    if signal == "BUY":
        bos_ok = (not POST_SL_REQUIRE_MICRO_BOS) or micro_bos_bull or candle_dir == "BULL"
        retest_ok = (not POST_SL_REQUIRE_RETEST_ZONE) or near_m15_low or lower_wick or day_position <= POST_SL_BUY_MAX_DAY_POSITION
        momentum_ok = candle_dir == "BULL" or ema20_slope == "UP" or ema50_slope == "UP"
        return bool(bos_ok and retest_ok and momentum_ok), {
            "micro_bos": micro_bos_bull,
            "retest_zone": retest_ok,
            "momentum": momentum_ok,
            "day_position": day_position,
            "near_m15_low": near_m15_low,
            "lower_wick": lower_wick
        }

    return False, {"reason": "invalid signal"}


def post_sl_quarantine_context(signal, symbol, setup_type, score, data):
    """
    v37: dopo uno SL diretto non si flippa subito direzione.
    - Opposto NORMAL: bloccato durante la quarantena.
    - Opposto speciale: passa solo con score alto + conferma/retest.
    - Stessa direzione dopo SL: prudenza per evitare martellate ripetute.
    """
    ctx = {
        "enabled": POST_SL_QUARANTINE_ENABLED,
        "active": False,
        "block": False,
        "reason": "",
        "last_loss": None,
        "last_loss_signal": None,
        "last_loss_setup": None,
        "age_seconds": None,
        "remaining_seconds": 0,
        "confirmation_ok": False,
        "confirmation": {}
    }

    if not POST_SL_QUARANTINE_ENABLED:
        ctx["reason"] = "POST_SL_QUARANTINE disattivata"
        return False, ctx

    signal = normalize_signal(signal)
    symbol = str(symbol or "XAUUSD").upper()
    setup_type = str(setup_type or "NORMAL")
    score = to_int(score, 0)

    last_loss = latest_direct_loss_any(symbol, max(POST_SL_QUARANTINE_SECONDS, POST_SL_SAME_DIRECTION_SECONDS))
    if not last_loss:
        ctx["reason"] = "nessuno SL diretto recente"
        return False, ctx

    closed = to_float(last_loss.get("closed") or last_loss.get("created") or 0, 0)
    age = now_ts() - closed if closed else 999999
    last_signal = str(last_loss.get("signal", "")).upper()
    last_setup = str(last_loss.get("setup_type", "NORMAL"))
    opposite = signal in ["BUY", "SELL"] and last_signal in ["BUY", "SELL"] and signal != last_signal
    same_direction = signal == last_signal
    confirmation_ok, confirmation = post_sl_confirmation_ok(signal, data)

    ctx.update({
        "active": True,
        "last_loss": last_loss,
        "last_loss_signal": last_signal,
        "last_loss_setup": last_setup,
        "age_seconds": int(age),
        "confirmation_ok": confirmation_ok,
        "confirmation": confirmation
    })

    if opposite and age <= POST_SL_QUARANTINE_SECONDS:
        ctx["remaining_seconds"] = int(max(0, POST_SL_QUARANTINE_SECONDS - age))

        if setup_type == "NORMAL" and POST_SL_BLOCK_NORMAL_OPPOSITE:
            ctx["block"] = True
            ctx["reason"] = (
                f"SL diretto {last_signal} appena chiuso: blocco {signal} NORMAL per evitare flip impulsivo"
            )
            return True, ctx

        if setup_type not in POST_SL_OPPOSITE_ALLOW_SETUPS:
            ctx["block"] = True
            ctx["reason"] = (
                f"setup {setup_type} non autorizzato durante quarantena post-SL"
            )
            return True, ctx

        if score < POST_SL_OPPOSITE_MIN_SCORE:
            ctx["block"] = True
            ctx["reason"] = (
                f"opposto post-SL con score basso {score}/{POST_SL_OPPOSITE_MIN_SCORE}"
            )
            return True, ctx

        if not confirmation_ok:
            ctx["block"] = True
            ctx["reason"] = (
                "opposto post-SL senza micro BOS/retest/momentum sufficiente"
            )
            return True, ctx

        ctx["reason"] = "opposto post-SL consentito: setup speciale, score alto e conferma valida"
        return False, ctx

    if same_direction and age <= POST_SL_SAME_DIRECTION_SECONDS and setup_type in POST_SL_REENTRY_CAUTION_SETUPS:
        ctx["remaining_seconds"] = int(max(0, POST_SL_SAME_DIRECTION_SECONDS - age))
        if score < POST_SL_REENTRY_MIN_SCORE or not confirmation_ok:
            ctx["block"] = True
            ctx["reason"] = (
                f"re-entry {signal} troppo presto dopo SL diretto: serve score {POST_SL_REENTRY_MIN_SCORE}+ e conferma pulita"
            )
            return True, ctx

    ctx["reason"] = "quarantena non applicabile o conferme sufficienti"
    return False, ctx


def post_sl_quarantine_text(ctx):
    last_loss = ctx.get("last_loss") or {}
    confirmation = ctx.get("confirmation") or {}
    mins = int((ctx.get("remaining_seconds") or 0) // 60)

    return f"""Ultimo SL diretto:
- ID: {last_loss.get('id', 'N/D')}
- Direzione: {ctx.get('last_loss_signal')}
- Setup: {ctx.get('last_loss_setup')}
- Età: {ctx.get('age_seconds')} sec
- Quarantena restante: {mins} min

Conferma nuova direzione:
- ok: {ctx.get('confirmation_ok')}
- micro BOS: {confirmation.get('micro_bos')}
- retest/zona: {confirmation.get('retest_zone')}
- momentum: {confirmation.get('momentum')}
- day_position: {confirmation.get('day_position')}

Motivo:
{ctx.get('reason')}"""

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

    # v23: PRE_BEAR_SELL nasce da un recovery alto fallito, non da inseguimento basso.
    if setup_type == "PRE_BEAR_SELL":
        return False, recent_tp8_sells

    # v21: un lower-high/continuation SELL confermato non è "inseguimento basso".
    if setup_type in [
        "BEAR_CAMPAIGN_SELL",
        "BEAR_CONTINUATION_SELL",
        "SYNTHETIC_BEAR_CONTINUATION_SELL"
    ]:
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

    # v23: pre-bear thesis anticipa il failed recovery.
    if setup_type == "PRE_BEAR_SELL":
        dominance += 28

    # v22: campaign manager / thesis persistence.
    if setup_type == "BEAR_CAMPAIGN_SELL":
        dominance += 26

    # v21: seconda macchina a stati per bearish continuation / lower high.
    if setup_type == "SYNTHETIC_BEAR_CONTINUATION_SELL":
        dominance += 24

    if setup_type == "BEAR_CONTINUATION_SELL":
        dominance += 18

    # v20: il SELL sintetico nasce da una macchina a stati confermata sui PRICE_UPDATE.
    if setup_type == "SYNTHETIC_FAILED_RETEST_SELL":
        dominance += 20

    # v19: MAX_FAILED_RETEST_SELL è il setup più forte per vendere top/retest post-evento.
    if setup_type == "MAX_FAILED_RETEST_SELL":
        dominance += 16

    # v18: MAX_EVENT_SPIKE_SELL e MAX_VIEW_SELL ribaltano la lettura dopo spike/top.
    if setup_type == "MAX_EVENT_SPIKE_SELL":
        dominance += 12

    if setup_type == "MAX_VIEW_SELL":
        dominance += 8

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
# CHAOS DAY + EXTREME ZONE FILTER v15
# =========================

def trade_event_reference_time(trade):
    return (
        trade.get("last_tp_time")
        or trade.get("activated")
        or trade.get("closed")
        or trade.get("created")
        or 0
    )


def trade_is_stale_for_lock(trade):
    if not SESSION_LOCK_RESET_ENABLED:
        return False

    event_time = trade_event_reference_time(trade)

    if not event_time:
        return False

    if LOCK_IGNORE_PREVIOUS_DAY:
        try:
            if local_datetime(event_time).strftime("%Y-%m-%d") != today_key():
                return True
        except Exception:
            pass

    if now_ts() - event_time > STALE_TRADE_LOCK_SECONDS:
        return True

    return False


def get_recent_direct_losses_total(symbol, lookback_seconds):
    now = now_ts()
    symbol = str(symbol).upper()

    losses = []

    for trade in OPEN_TRADES:
        if str(trade.get("symbol", "")).upper() != symbol:
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


def get_today_direct_losses(symbol):
    symbol = str(symbol).upper()
    today = today_key()
    losses = []

    for trade in OPEN_TRADES:
        if str(trade.get("symbol", "")).upper() != symbol:
            continue

        if trade.get("status") != "LOSS":
            continue

        if int(trade.get("highest_tp", 0)) > 0:
            continue

        closed = trade.get("closed") or trade.get("created") or 0

        try:
            closed_day = local_datetime(closed).strftime("%Y-%m-%d")
        except Exception:
            closed_day = ""

        if closed_day == today:
            losses.append(trade)

    return sorted(losses, key=lambda x: x.get("closed") or x.get("created") or 0, reverse=True)


def get_chaos_context(symbol, data):
    if not CHAOS_MODE_ENABLED:
        return {
            "active": False,
            "reason": "Chaos Mode disattivato",
            "recent_losses": [],
            "today_losses": [],
            "day_range_atr": 0
        }

    recent_losses = get_recent_direct_losses_total(symbol, CHAOS_LOOKBACK_SECONDS)
    today_losses = get_today_direct_losses(symbol)

    latest_loss_time = recent_losses[0].get("closed") or recent_losses[0].get("created") or 0 if recent_losses else 0

    chaos_by_losses = (
        len(recent_losses) >= CHAOS_DIRECT_SL_COUNT
        and latest_loss_time
        and now_ts() - latest_loss_time <= CHAOS_LOCK_SECONDS
    )

    atr = to_float(data.get("atr"), 0)
    day_range = to_float(data.get("day_range"), 0)

    if not day_range:
        day_high = to_float(data.get("day_high"), 0)
        day_low = to_float(data.get("day_low"), 0)
        if day_high and day_low and day_high > day_low:
            day_range = day_high - day_low

    day_range_atr = day_range / atr if atr and day_range else 0

    if DAILY_KILL_SWITCH_ENABLED and len(today_losses) >= DAILY_MAX_DIRECT_SL:
        return {
            "active": True,
            "kill": True,
            "reason": f"Daily Kill Switch: {len(today_losses)} SL diretti oggi",
            "recent_losses": recent_losses,
            "today_losses": today_losses,
            "day_range_atr": day_range_atr
        }

    if chaos_by_losses:
        return {
            "active": True,
            "kill": False,
            "reason": f"Chaos Mode: {len(recent_losses)} SL diretti recenti",
            "recent_losses": recent_losses,
            "today_losses": today_losses,
            "day_range_atr": day_range_atr
        }

    return {
        "active": False,
        "kill": False,
        "reason": "Nessun trigger chaos attivo",
        "recent_losses": recent_losses,
        "today_losses": today_losses,
        "day_range_atr": day_range_atr
    }


def extreme_zone_info(signal, data):
    signal = str(signal).upper()

    price = get_price_from_data(data)
    atr = to_float(data.get("atr"), 0)
    symbol = str(data.get("symbol", "XAUUSD")).upper()

    near_m15_high = to_bool(data.get("near_m15_high", "false"))
    near_m15_low = to_bool(data.get("near_m15_low", "false"))

    near_day_high = to_bool(data.get("near_day_high", "false"))
    near_day_low = to_bool(data.get("near_day_low", "false"))

    day_high = to_float(data.get("day_high"), 0)
    day_low = to_float(data.get("day_low"), 0)
    day_position = to_float(data.get("day_position"), -1)

    if day_position < 0 and day_high and day_low and day_high > day_low and price:
        day_position = (price - day_low) / (day_high - day_low)

    threshold = CHAOS_EXTREME_DISTANCE

    if atr:
        threshold = max(threshold, atr * CHAOS_EXTREME_ATR_MULT)

    if signal == "SELL":
        computed_near_day_high = bool(
            day_high and price and (day_high - price) <= threshold
        )
        high_position = bool(
            day_position >= CHAOS_SELL_DAY_POSITION_MIN
        ) if day_position >= 0 else False

        # v22 fallback: usa la struttura bearish runtime quando i campi day
        # sono mancanti o inaffidabili.
        bear_state = get_bear_continuation_state(symbol)
        impulse_high = to_float(bear_state.get("impulse_high"), 0)
        impulse_low = to_float(bear_state.get("impulse_low"), 0)
        rally_peak = to_float(bear_state.get("rally_peak"), 0)

        bear_position = -1
        if (
            CAMPAIGN_EXTREME_FALLBACK_ENABLED
            and price
            and impulse_high
            and impulse_low
            and impulse_high > impulse_low
        ):
            bear_position = (
                (price - impulse_low)
                / (impulse_high - impulse_low)
            )

        near_rally_peak = bool(
            CAMPAIGN_EXTREME_FALLBACK_ENABLED
            and price
            and rally_peak
            and abs(rally_peak - price) <= max(
                threshold,
                CAMPAIGN_RALLY_PEAK_DISTANCE
            )
        )

        bear_high_position = bool(
            bear_position >= CAMPAIGN_EXTREME_POSITION_MIN
        ) if bear_position >= 0 else False

        fallback_ok = near_rally_peak or bear_high_position

        ok = (
            near_m15_high
            or near_day_high
            or computed_near_day_high
            or high_position
            or fallback_ok
        )

        side = (
            "SELL_BEAR_FALLBACK"
            if fallback_ok and not (
                near_m15_high
                or near_day_high
                or computed_near_day_high
                or high_position
            )
            else "SELL_HIGH"
        )

        details = {
            "side": side,
            "near_m15_high": near_m15_high,
            "near_day_high": near_day_high or computed_near_day_high,
            "day_position": day_position,
            "bear_position": bear_position,
            "near_rally_peak": near_rally_peak,
            "fallback_ok": fallback_ok,
            "threshold": threshold,
            "ok": ok
        }

        return ok, details

    if signal == "BUY":
        computed_near_day_low = bool(
            day_low and price and (price - day_low) <= threshold
        )
        low_position = bool(
            day_position <= CHAOS_BUY_DAY_POSITION_MAX
        ) if day_position >= 0 else False

        ok = (
            near_m15_low
            or near_day_low
            or computed_near_day_low
            or low_position
            or to_bool(data.get("recent_low_touch", "false"))
        )

        details = {
            "side": "BUY_LOW",
            "near_m15_low": near_m15_low,
            "near_day_low": near_day_low or computed_near_day_low,
            "day_position": day_position,
            "threshold": threshold,
            "ok": ok
        }

        return ok, details

    return False, {
        "side": "UNKNOWN",
        "day_position": day_position,
        "threshold": threshold,
        "ok": False
    }


def should_block_by_chaos_mode(signal, symbol, setup_type, score, data, smart_kill_decision=None):
    ctx = get_chaos_context(symbol, data)

    setup_type = str(setup_type).upper()
    signal = str(signal).upper()

    extreme_ok, extreme_info = extreme_zone_info(signal, data)

    if not ctx.get("active"):
        return False, ctx, extreme_info, "Chaos non attivo"

    # v22: Daily Kill Switch non viene eliminato.
    # Può essere superato una sola volta da una campaign leg molto forte,
    # con score alto e rischio ridotto.
    if ctx.get("kill"):
        campaign_decision = evaluate_campaign_leg(
            signal,
            symbol,
            setup_type,
            score,
            data
        )

        if (
            campaign_decision.get("allow")
            and campaign_decision.get("kill_override")
        ):
            return (
                False,
                ctx,
                extreme_info,
                "Campaign override controllato del Daily Kill Switch"
            )

        if smart_kill_decision is None:
            smart_kill_decision = smart_kill_pre_bear_decision(
                signal, symbol, setup_type, score, data, extreme_info=extreme_info
            )

        if smart_kill_decision.get("allow"):
            return False, ctx, extreme_info, "Smart Kill override PRE_BEAR da zona estrema"

        return True, ctx, extreme_info, "Daily Kill Switch attivo"

    if CHAOS_EXTREME_ZONE_REQUIRED and not extreme_ok:
        return True, ctx, extreme_info, "No Mid-Range Trading: prezzo non in zona estrema"

    if setup_type == "NORMAL":
        if not CHAOS_ALLOW_NORMAL_EXTREME:
            return True, ctx, extreme_info, "Chaos Mode: setup NORMAL bloccato"

        if int(score) < CHAOS_NORMAL_MIN_SCORE:
            return True, ctx, extreme_info, f"Chaos Mode: NORMAL ammesso solo con score >= {CHAOS_NORMAL_MIN_SCORE}"

    if signal == "SELL":
        if setup_type not in CHAOS_SELL_SETUPS and setup_type != "NORMAL":
            return True, ctx, extreme_info, "Chaos Mode: SELL non è setup speciale da zona alta"

    if signal == "BUY":
        if setup_type not in CHAOS_BUY_SETUPS and setup_type != "NORMAL":
            return True, ctx, extreme_info, "Chaos Mode: BUY non è setup speciale da zona bassa"

    if setup_type == "PRE_BEAR_SELL" and int(score) < PRE_BEAR_SELL_MIN_SCORE:
        return True, ctx, extreme_info, f"PRE_BEAR_SELL sotto soglia {PRE_BEAR_SELL_MIN_SCORE}"

    if setup_type == "BEAR_CAMPAIGN_SELL" and int(score) < CAMPAIGN_SELL_MIN_SCORE:
        return True, ctx, extreme_info, f"BEAR_CAMPAIGN_SELL sotto soglia {CAMPAIGN_SELL_MIN_SCORE}"

    if setup_type == "SYNTHETIC_BEAR_CONTINUATION_SELL" and int(score) < BEAR_SYNTHETIC_SCORE:
        return True, ctx, extreme_info, f"SYNTHETIC_BEAR_CONTINUATION_SELL sotto score {BEAR_SYNTHETIC_SCORE}"

    if setup_type == "BEAR_CONTINUATION_SELL" and int(score) < BEAR_CONTINUATION_SELL_MIN_SCORE:
        return True, ctx, extreme_info, f"BEAR_CONTINUATION_SELL sotto soglia {BEAR_CONTINUATION_SELL_MIN_SCORE}"

    if setup_type == "SYNTHETIC_FAILED_RETEST_SELL" and int(score) < SYNTHETIC_RETEST_SCORE:
        return True, ctx, extreme_info, f"SYNTHETIC_FAILED_RETEST_SELL sotto score {SYNTHETIC_RETEST_SCORE}"

    if setup_type == "MAX_FAILED_RETEST_SELL" and int(score) < FAILED_RETEST_SELL_MIN_SCORE:
        return True, ctx, extreme_info, f"MAX_FAILED_RETEST_SELL sotto soglia {FAILED_RETEST_SELL_MIN_SCORE}"

    if setup_type == "MAX_EVENT_SPIKE_SELL" and int(score) < EVENT_SPIKE_SELL_MIN_SCORE:
        return True, ctx, extreme_info, f"MAX_EVENT_SPIKE_SELL sotto soglia {EVENT_SPIKE_SELL_MIN_SCORE}"

    if setup_type == "MAX_VIEW_SELL" and int(score) < MAX_VIEW_SELL_MIN_SCORE:
        return True, ctx, extreme_info, f"MAX_VIEW_SELL sotto soglia {MAX_VIEW_SELL_MIN_SCORE}"

    if int(score) < CHAOS_MIN_SCORE:
        return True, ctx, extreme_info, f"Chaos Mode: score sotto soglia {CHAOS_MIN_SCORE}"

    return False, ctx, extreme_info, "Setup ammesso in Chaos Mode"


def chaos_status_text(ctx, extreme_info, block_reason):
    recent_losses = ctx.get("recent_losses", []) or []
    today_losses = ctx.get("today_losses", []) or []

    lines = [
        f"Motivo: {block_reason}",
        f"Chaos reason: {ctx.get('reason')}",
        f"SL diretti recenti: {len(recent_losses)} / soglia {CHAOS_DIRECT_SL_COUNT}",
        f"SL diretti oggi: {len(today_losses)} / kill switch {DAILY_MAX_DIRECT_SL}",
        f"Lookback chaos secondi: {CHAOS_LOOKBACK_SECONDS}",
        f"Lock chaos secondi: {CHAOS_LOCK_SECONDS}",
        "",
        "Zona estrema:",
        f"- Tipo: {extreme_info.get('side')}",
        f"- OK zona estrema: {extreme_info.get('ok')}",
        f"- Day position: {round(extreme_info.get('day_position', -1), 3) if isinstance(extreme_info.get('day_position', -1), (int, float)) else extreme_info.get('day_position')}",
        f"- Bear position fallback: {round(extreme_info.get('bear_position', -1), 3) if isinstance(extreme_info.get('bear_position', -1), (int, float)) else extreme_info.get('bear_position')}",
        f"- Near rally peak: {extreme_info.get('near_rally_peak', False)}",
        f"- Threshold: {round(extreme_info.get('threshold', 0), 2) if isinstance(extreme_info.get('threshold', 0), (int, float)) else extreme_info.get('threshold')}",
    ]

    if recent_losses:
        lines.append("")
        lines.append("Ultimi SL diretti:")
        for trade in recent_losses[:5]:
            lines.append(
                f"- ID {trade.get('id')} | {trade.get('signal')} | {trade.get('setup_type')} | {trade.get('closed_local', 'N/D')}"
            )

    return "\n".join(lines)








# =========================
# REGIME ARBITER v25
# =========================

def _latest_price_for_symbol(symbol):
    symbol = str(symbol or "XAUUSD").upper()
    history = PRICE_HISTORY.get(symbol, [])

    if isinstance(history, list) and history:
        return to_float(history[-1].get("close"), 0)

    return 0


def bear_trigger_maturity_context(symbol, data=None):
    """Maturità obbligatoria per tutti i setup continuation/campaign."""
    symbol = str(symbol or "XAUUSD").upper()
    data = data or {}

    state = get_bear_continuation_state(symbol)
    state_name = str(state.get("state", "IDLE")).upper()
    price = get_price_from_data(data) or _latest_price_for_symbol(symbol)

    history = PRICE_HISTORY.get(symbol, [])
    previous_price = 0
    if isinstance(history, list) and len(history) >= 2:
        previous_price = to_float(history[-2].get("close"), 0)
    elif isinstance(history, list) and history:
        previous_price = to_float(history[-1].get("close"), 0)

    rally_peak = to_float(state.get("rally_peak"), 0)
    rally_peak_time = to_float(state.get("rally_peak_time"), 0)
    stability_age = max(0, now_ts() - rally_peak_time) if rally_peak_time else 0
    failure_points = max(0, rally_peak - price) if rally_peak and price else 0

    failure_threshold = effective_failure_threshold(
        data,
        BEAR_CONTINUATION_FAILURE_POINTS,
        BEAR_CONTINUATION_FAILURE_MIN_POINTS,
        BEAR_CONTINUATION_FAILURE_ATR_MULT,
        BEAR_CONTINUATION_DYNAMIC_FAILURE_ENABLED
    )

    confirmation_ctx = bearish_confirmation_details(data, previous_price=previous_price)
    micro_bos_ctx = micro_bos_bear_context(symbol, data)
    warmup_ctx = warmup_status(symbol)

    state_ready = state_name in ["LOWER_HIGH_ARMED", "SELL_TRIGGERED"]
    stability_ok = rally_peak > 0 and stability_age >= BEAR_RALLY_PEAK_STABILITY_SECONDS
    failure_ok = failure_points >= failure_threshold
    confirmations_ok = confirmation_ctx.get("count", 0) >= BEAR_CONTINUATION_MIN_CONFIRMATIONS
    micro_bos_ok = micro_bos_ctx.get("confirmed") or not BEAR_CONTINUATION_MICRO_BOS_REQUIRED
    warmup_ok = warmup_ctx.get("warm") or not STATE_WARMUP_BLOCK_AUTONOMOUS

    mature = bool(
        state_ready and stability_ok and failure_ok and
        confirmations_ok and micro_bos_ok and warmup_ok
    )

    return {
        "mature": mature,
        "state": state_name,
        "state_ready": state_ready,
        "rally_peak": rally_peak,
        "stability_age": stability_age,
        "stability_ok": stability_ok,
        "failure_points": failure_points,
        "failure_threshold": failure_threshold,
        "failure_ok": failure_ok,
        "confirmations": confirmation_ctx.get("count", 0),
        "confirmation_items": confirmation_ctx.get("items", []),
        "confirmations_ok": confirmations_ok,
        "micro_bos": bool(micro_bos_ctx.get("confirmed")),
        "micro_bos_source": micro_bos_ctx.get("source"),
        "micro_bos_reference_low": micro_bos_ctx.get("reference_low"),
        "micro_bos_ok": micro_bos_ok,
        "warm": warmup_ctx.get("warm"),
        "warmup_ok": warmup_ok
    }


def bear_trigger_maturity_text(ctx):
    return (
        f"State: {ctx.get('state')}\n"
        f"Mature: {ctx.get('mature')}\n"
        f"Stability: {round(to_float(ctx.get('stability_age')), 1)}/{BEAR_RALLY_PEAK_STABILITY_SECONDS}s\n"
        f"Failure: {round(to_float(ctx.get('failure_points')), 2)}/{round(to_float(ctx.get('failure_threshold')), 2)}\n"
        f"Conferme: {ctx.get('confirmations', 0)}/{BEAR_CONTINUATION_MIN_CONFIRMATIONS}\n"
        f"Micro BOS: {ctx.get('micro_bos')}\n"
        f"Warm: {ctx.get('warm')}"
    )


def get_recovery_dominance_context(symbol, data=None, min_tp=None, setup_filter=None):
    """
    v26:
    - Default min_tp=RECOVERY_DOMINANCE_MIN_TP crea il regime RECOVERY_DOMINANT.
    - min_tp=SPECIAL_BUY_NORMAL_SELL_MIN_TP protegge prima contro SELL NORMAL.
    - setup_filter consente future personalizzazioni.
    """
    symbol = str(symbol or "XAUUSD").upper()
    data = data or {}

    if not RECOVERY_DOMINANCE_ENABLED:
        return {
            "active": False,
            "reason": "Special BUY Dominance disattivata",
            "best_trade": None,
            "trades": []
        }

    effective_min_tp = (
        RECOVERY_DOMINANCE_MIN_TP
        if min_tp is None
        else int(min_tp)
    )
    effective_setups = set(
        setup_filter
        if setup_filter is not None
        else RECOVERY_DOMINANCE_SETUPS
    )

    price = get_price_from_data(data) or _latest_price_for_symbol(symbol)
    now = now_ts()
    candidates = []

    for trade in OPEN_TRADES:
        if str(trade.get("symbol", "")).upper() != symbol:
            continue

        if str(trade.get("signal", "")).upper() != "BUY":
            continue

        setup_name = str(trade.get("setup_type", "")).upper()

        if setup_name not in effective_setups:
            continue

        if trade.get("status") not in ["OPEN", "PENDING"]:
            continue

        if now - (trade.get("created") or 0) > RECOVERY_DOMINANCE_LOOKBACK_SECONDS:
            continue

        highest_tp = int(trade.get("highest_tp", 0))

        if highest_tp < effective_min_tp:
            continue

        entry_low = to_float(trade.get("entry_low"), 0)
        entry_high = to_float(trade.get("entry_high"), 0)

        if not entry_low and entry_high:
            entry_low = entry_high

        invalidation_price = (
            entry_low - RECOVERY_DOMINANCE_INVALIDATION_BUFFER
            if entry_low
            else 0
        )

        invalidated = bool(
            invalidation_price
            and price
            and price <= invalidation_price
        )

        candidates.append({
            "trade": trade,
            "setup": setup_name,
            "highest_tp": highest_tp,
            "entry_low": entry_low,
            "entry_high": entry_high,
            "invalidation_price": invalidation_price,
            "invalidated": invalidated,
            "price": price,
            "effective_min_tp": effective_min_tp
        })

    if not candidates:
        return {
            "active": False,
            "reason": f"Nessun BUY speciale OPEN con TP >= {effective_min_tp}",
            "best_trade": None,
            "trades": [],
            "effective_min_tp": effective_min_tp
        }

    candidates = sorted(
        candidates,
        key=lambda x: (
            x.get("highest_tp", 0),
            x.get("trade", {}).get("last_tp_time")
            or x.get("trade", {}).get("created")
            or 0
        ),
        reverse=True
    )

    active_candidates = [
        item for item in candidates
        if not item.get("invalidated")
    ]

    if not active_candidates:
        best_ctx = candidates[0]
        return {
            "active": False,
            "reason": "BUY speciale invalidato sotto zona ingresso",
            "best_trade": best_ctx.get("trade"),
            "trades": candidates,
            "invalidation_price": best_ctx.get("invalidation_price"),
            "price": price,
            "effective_min_tp": effective_min_tp
        }

    best_ctx = active_candidates[0]
    best = best_ctx.get("trade") or {}
    best_setup = best_ctx.get("setup", best.get("setup_type", "BUY"))

    return {
        "active": True,
        "reason": (
            f"{best_setup} OPEN con TP{best_ctx.get('highest_tp')} "
            f"e struttura non invalidata"
        ),
        "best_trade": best,
        "trades": active_candidates,
        "highest_tp": best_ctx.get("highest_tp"),
        "invalidation_price": best_ctx.get("invalidation_price"),
        "price": price,
        "effective_min_tp": effective_min_tp
    }


def recovery_dominance_text(ctx):
    best = (ctx or {}).get("best_trade") or {}
    return (
        f"Active: {(ctx or {}).get('active')}\n"
        f"Reason: {(ctx or {}).get('reason')}\n"
        f"Trade BUY: {best.get('id', 'N/D')}\n"
        f"Setup BUY: {best.get('setup_type', 'N/D')}\n"
        f"Highest TP: {best.get('highest_tp', 0)}\n"
        f"Status BUY: {best.get('status', 'N/D')}\n"
        f"Invalidation: {round(to_float((ctx or {}).get('invalidation_price')), 3)}\n"
        f"Prezzo: {round(to_float((ctx or {}).get('price')), 3)}"
    )



def special_buy_counter_sell_override_context(symbol, setup_type, score, data, special_ctx=None):
    """
    Decide se un SELL può combattere un BUY speciale attivo.
    Regola v26:
    - setup speciale
    - score alto
    - zona alta Max
    - micro-BOS, se richiesto
    """
    symbol = str(symbol or "XAUUSD").upper()
    setup_type = str(setup_type or "NORMAL").upper()
    data = data or {}

    if special_ctx is None:
        special_ctx = get_recovery_dominance_context(
            symbol,
            data,
            min_tp=SPECIAL_BUY_NORMAL_SELL_MIN_TP
        )

    extreme_ok, extreme_info = extreme_zone_info("SELL", data)
    micro_ctx = micro_bos_bear_context(symbol, data)

    setup_ok = setup_type in SPECIAL_BUY_COUNTER_SELL_ALLOWED_SETUPS
    score_ok = int(score) >= SPECIAL_BUY_COUNTER_SELL_MIN_SCORE
    zone_ok = bool(
        extreme_ok
        or to_bool(data.get("near_m15_high", "false"))
        or to_bool(data.get("near_day_high", "false"))
        or str(data.get("rejection", "")).upper() == "UPPER_WICK"
        or to_bool(data.get("upper_wick_strong", "false"))
    )
    micro_ok = bool(
        micro_ctx.get("confirmed")
        or not SPECIAL_BUY_COUNTER_SELL_REQUIRE_MICRO_BOS
    )

    allow = bool(
        setup_ok
        and score_ok
        and (
            zone_ok
            or not SPECIAL_BUY_COUNTER_SELL_REQUIRE_ZONE
        )
        and micro_ok
    )

    return {
        "allow": allow,
        "setup_ok": setup_ok,
        "score_ok": score_ok,
        "zone_ok": zone_ok,
        "micro_ok": micro_ok,
        "score": score,
        "required_score": SPECIAL_BUY_COUNTER_SELL_MIN_SCORE,
        "setup_type": setup_type,
        "extreme_info": extreme_info,
        "micro_bos": micro_ctx,
        "special_buy": special_ctx
    }


def special_buy_counter_sell_text(ctx):
    best = (ctx or {}).get("special_buy", {}).get("best_trade") or {}
    extreme = (ctx or {}).get("extreme_info") or {}
    micro = (ctx or {}).get("micro_bos") or {}

    return (
        f"Allow: {(ctx or {}).get('allow')}\n"
        f"Setup ok: {(ctx or {}).get('setup_ok')}\n"
        f"Score ok: {(ctx or {}).get('score_ok')} "
        f"({(ctx or {}).get('score')}/{(ctx or {}).get('required_score')})\n"
        f"Zona Max ok: {(ctx or {}).get('zone_ok')}\n"
        f"Micro BOS ok: {(ctx or {}).get('micro_ok')}\n"
        f"BUY riferimento: {best.get('id', 'N/D')}\n"
        f"Setup BUY: {best.get('setup_type', 'N/D')}\n"
        f"Highest TP BUY: {best.get('highest_tp', 0)}\n"
        f"Zona side: {extreme.get('side', 'N/D')}\n"
        f"Day position: {round(to_float(extreme.get('day_position')), 3)}\n"
        f"Micro BOS: {micro.get('confirmed')}"
    )


def max_zone_sell_gate_context(signal, symbol, setup_type, score, data):
    signal = str(signal or "").upper()
    symbol = str(symbol or "XAUUSD").upper()
    setup_type = str(setup_type or "NORMAL").upper()
    data = data or {}

    if not MAX_ZONE_SELL_GATE_ENABLED:
        return {"block": False, "reason": "Max Zone Gate disattivato"}

    if signal != "SELL":
        return {"block": False, "reason": "Non è SELL"}

    if setup_type not in MAX_ZONE_SELL_SETUPS:
        return {"block": False, "reason": "Setup esente dal Max Zone Gate"}

    extreme_ok, extreme_info = extreme_zone_info("SELL", data)
    upper_rejection = bool(
        str(data.get("rejection", "")).upper() == "UPPER_WICK"
        or to_bool(data.get("upper_wick_strong", "false"))
    )
    near_high = bool(
        to_bool(data.get("near_m15_high", "false"))
        or to_bool(data.get("near_day_high", "false"))
    )

    zone_ok = bool(
        extreme_ok
        or near_high
        or upper_rejection
    )

    score_ok = int(score) >= MAX_ZONE_SELL_MIN_SCORE

    block = bool(
        not (
            score_ok
            and (
                zone_ok
                or not MAX_ZONE_SELL_REQUIRE_HIGH_ZONE
            )
        )
    )

    return {
        "block": block,
        "reason": (
            "SELL NORMAL non è in zona Max alta"
            if block
            else "SELL NORMAL in zona Max valida"
        ),
        "score_ok": score_ok,
        "zone_ok": zone_ok,
        "upper_rejection": upper_rejection,
        "near_high": near_high,
        "extreme_info": extreme_info,
        "score": score,
        "required_score": MAX_ZONE_SELL_MIN_SCORE
    }


def max_zone_sell_gate_text(ctx):
    extreme = (ctx or {}).get("extreme_info") or {}

    return (
        f"Block: {(ctx or {}).get('block')}\n"
        f"Reason: {(ctx or {}).get('reason')}\n"
        f"Score: {(ctx or {}).get('score')}/{(ctx or {}).get('required_score')}\n"
        f"Score ok: {(ctx or {}).get('score_ok')}\n"
        f"Zona ok: {(ctx or {}).get('zone_ok')}\n"
        f"Near high: {(ctx or {}).get('near_high')}\n"
        f"Upper rejection: {(ctx or {}).get('upper_rejection')}\n"
        f"Extreme side: {extreme.get('side', 'N/D')}\n"
        f"Day position: {round(to_float(extreme.get('day_position')), 3)}"
    )



def _tp_event_time_for_level(trade, level):
    return (
        trade.get(f"tp{level}_time")
        or trade.get("last_tp_time")
        or trade.get("closed")
        or trade.get("created")
        or 0
    )


def get_sell_profit_lock_context(symbol, data=None):
    """
    v27 Trade Compression.
    Attivo quando:
    - almeno 1 SELL recente ha preso TP8/runner
    oppure
    - almeno N SELL recenti hanno preso TP5+
    Poi blocca nuove entrate simili finché non c'è nuovo rimbalzo/zona Max.
    """
    symbol = str(symbol or "XAUUSD").upper()
    data = data or {}

    if not SELL_PROFIT_LOCK_ENABLED:
        return {
            "active": False,
            "reason": "Sell Profit Lock disattivato",
            "recent_tp_deep": [],
            "recent_tp5": []
        }

    recent_deep = get_recent_tp_trades(
        "SELL",
        symbol,
        min_tp=SELL_PROFIT_LOCK_TP_LEVEL,
        lookback_seconds=SELL_PROFIT_LOCK_LOOKBACK_SECONDS
    )

    recent_tp5 = get_recent_tp_trades(
        "SELL",
        symbol,
        min_tp=SELL_PROFIT_LOCK_TP5_LEVEL,
        lookback_seconds=SELL_PROFIT_LOCK_LOOKBACK_SECONDS
    )

    recent_runner = [
        t for t in OPEN_TRADES
        if str(t.get("symbol", "")).upper() == symbol
        and str(t.get("signal", "")).upper() == "SELL"
        and bool(t.get("runner"))
        and now_ts() - (t.get("last_tp_time") or t.get("created") or 0) <= SELL_PROFIT_LOCK_LOOKBACK_SECONDS
    ]

    trigger_deep = len(recent_deep) >= 1 or len(recent_runner) >= 1
    trigger_cluster = len(recent_tp5) >= SELL_PROFIT_LOCK_TP5_COUNT

    event_times = []
    for trade in recent_deep:
        event_times.append(_tp_event_time_for_level(trade, SELL_PROFIT_LOCK_TP_LEVEL))
    for trade in recent_tp5:
        event_times.append(_tp_event_time_for_level(trade, SELL_PROFIT_LOCK_TP5_LEVEL))
    for trade in recent_runner:
        event_times.append(trade.get("last_tp_time") or trade.get("created") or 0)

    latest_event = max(event_times) if event_times else 0
    seconds_since_event = now_ts() - latest_event if latest_event else 999999999

    lock_by_time = bool(
        latest_event
        and seconds_since_event <= SELL_PROFIT_LOCK_SECONDS
    )

    deep_ctx = get_deep_extension_context(symbol, data)
    rebound_from_low = to_float(deep_ctx.get("rebound_from_low"), 0)
    rearmed_by_rebound = bool(
        rebound_from_low >= SELL_PROFIT_LOCK_REARM_REBOUND_POINTS
    )

    active = bool(
        (trigger_deep or trigger_cluster)
        and lock_by_time
        and not rearmed_by_rebound
    )

    if trigger_deep:
        reason = f"SELL già arrivato a TP{SELL_PROFIT_LOCK_TP_LEVEL}/Runner"
    elif trigger_cluster:
        reason = f"{len(recent_tp5)} SELL recenti arrivati almeno a TP{SELL_PROFIT_LOCK_TP5_LEVEL}"
    else:
        reason = "Nessun profitto SELL profondo recente"

    return {
        "active": active,
        "trigger_deep": trigger_deep,
        "trigger_cluster": trigger_cluster,
        "reason": reason,
        "recent_tp_deep": recent_deep,
        "recent_tp5": recent_tp5,
        "recent_runner": recent_runner,
        "latest_event": latest_event,
        "seconds_since_event": seconds_since_event,
        "lock_by_time": lock_by_time,
        "deep_extension": deep_ctx,
        "rebound_from_low": rebound_from_low,
        "rearmed_by_rebound": rearmed_by_rebound,
        "rearm_rebound_required": SELL_PROFIT_LOCK_REARM_REBOUND_POINTS
    }


def sell_profit_lock_status_text(ctx):
    return (
        f"Active: {ctx.get('active')}\n"
        f"Reason: {ctx.get('reason')}\n"
        f"Recent SELL TP{SELL_PROFIT_LOCK_TP_LEVEL}+: {len(ctx.get('recent_tp_deep', []))}\n"
        f"Recent SELL TP{SELL_PROFIT_LOCK_TP5_LEVEL}+: {len(ctx.get('recent_tp5', []))}\n"
        f"Runner SELL recenti: {len(ctx.get('recent_runner', []))}\n"
        f"Seconds since event: {round(to_float(ctx.get('seconds_since_event')), 1)} / {SELL_PROFIT_LOCK_SECONDS}\n"
        f"Rebound low: {round(to_float(ctx.get('rebound_from_low')), 2)} / {SELL_PROFIT_LOCK_REARM_REBOUND_POINTS}\n"
        f"Rearmed by rebound: {ctx.get('rearmed_by_rebound')}"
    )


def sell_profit_lock_allow_context(symbol, setup_type, score, data, lock_ctx=None):
    """
    Decide se un nuovo SELL può passare durante Sell Profit Lock.
    Default: blocca i SELL simili; consente solo rientri stile Max su nuova zona.
    """
    symbol = str(symbol or "XAUUSD").upper()
    setup_type = str(setup_type or "NORMAL").upper()
    data = data or {}

    if lock_ctx is None:
        lock_ctx = get_sell_profit_lock_context(symbol, data)

    if not lock_ctx.get("active"):
        return {
            "allow": True,
            "reason": "Sell Profit Lock non attivo",
            "setup_type": setup_type
        }

    max_zone_ctx = max_zone_sell_gate_context(
        "SELL",
        symbol,
        setup_type,
        score,
        data
    )
    micro_ctx = micro_bos_bear_context(symbol, data)
    maturity_ctx = bear_trigger_maturity_context(symbol, data)

    zone_ok = bool(
        max_zone_ctx.get("zone_ok")
        or max_zone_ctx.get("near_high")
        or max_zone_ctx.get("upper_rejection")
    )
    micro_ok = bool(
        micro_ctx.get("confirmed")
        or not SELL_PROFIT_LOCK_REQUIRE_MICRO_BOS
    )
    required_zone_ok = bool(
        zone_ok
        or not SELL_PROFIT_LOCK_REQUIRE_MAX_ZONE
    )
    rebound_ok = bool(lock_ctx.get("rearmed_by_rebound"))

    allow = False
    reason = "SELL bloccato: campagna già pagata, attendo nuova zona Max"

    if setup_type == "NORMAL":
        allow = not SELL_PROFIT_LOCK_BLOCK_NORMAL
        reason = (
            "SELL NORMAL permesso perché blocco NORMAL disattivato"
            if allow
            else "SELL NORMAL bloccato: dopo TP profondi non inseguo altri SELL normali"
        )

    elif setup_type == "MAX_FADE_SELL":
        allow = bool(
            int(score) >= SELL_PROFIT_LOCK_ALLOW_MAX_FADE_SCORE
            and required_zone_ok
            and micro_ok
        )
        reason = (
            "MAX_FADE_SELL ammesso: nuova zona Max confermata"
            if allow
            else "MAX_FADE_SELL bloccato: serve score/zona Max/micro-BOS migliori"
        )

    elif setup_type == "PRE_BEAR_SELL":
        allow = bool(
            int(score) >= SELL_PROFIT_LOCK_ALLOW_PRE_BEAR_SCORE
            and required_zone_ok
            and micro_ok
        )
        reason = (
            "PRE_BEAR_SELL ammesso: failed recovery forte da zona alta"
            if allow
            else "PRE_BEAR_SELL bloccato: non abbastanza forte dopo profitto SELL"
        )

    elif setup_type in [
        "BEAR_CAMPAIGN_SELL",
        "BEAR_CONTINUATION_SELL",
        "SYNTHETIC_BEAR_CONTINUATION_SELL"
    ]:
        if SELL_PROFIT_LOCK_BLOCK_SYNTHETIC:
            allow = bool(
                int(score) >= SELL_PROFIT_LOCK_ALLOW_CAMPAIGN_SCORE
                and rebound_ok
                and required_zone_ok
                and micro_ok
                and maturity_ctx.get("mature")
            )
            reason = (
                "Continuation/Campaign ammessa: nuovo rimbalzo riarmato e trigger maturo"
                if allow
                else "Continuation/Campaign bloccata: movimento SELL già pagato, manca nuovo rimbalzo maturo"
            )
        else:
            allow = True
            reason = "Continuation/Campaign permessa perché blocco synthetic disattivato"

    elif setup_type in [
        "MAX_VIEW_SELL",
        "MAX_FAILED_RETEST_SELL",
        "SYNTHETIC_FAILED_RETEST_SELL",
        "MAX_EVENT_SPIKE_SELL"
    ]:
        allow = bool(
            int(score) >= SELL_PROFIT_LOCK_ALLOW_CAMPAIGN_SCORE
            and required_zone_ok
            and micro_ok
        )
        reason = (
            "SELL speciale ammesso durante profit lock"
            if allow
            else "SELL speciale bloccato: serve nuova zona Max più pulita"
        )

    else:
        allow = bool(
            int(score) >= SELL_PROFIT_LOCK_ALLOW_CAMPAIGN_SCORE
            and required_zone_ok
            and micro_ok
        )
        reason = (
            "SELL non standard ammesso durante profit lock"
            if allow
            else "SELL non standard bloccato durante profit lock"
        )

    return {
        "allow": allow,
        "reason": reason,
        "setup_type": setup_type,
        "score": score,
        "zone_ok": zone_ok,
        "required_zone_ok": required_zone_ok,
        "micro_ok": micro_ok,
        "micro_bos": micro_ctx,
        "maturity": maturity_ctx,
        "max_zone": max_zone_ctx,
        "rebound_ok": rebound_ok,
        "lock": lock_ctx
    }


def sell_profit_lock_allow_text(ctx):
    max_zone = (ctx or {}).get("max_zone") or {}
    micro = (ctx or {}).get("micro_bos") or {}
    maturity = (ctx or {}).get("maturity") or {}

    return (
        f"Allow: {(ctx or {}).get('allow')}\n"
        f"Reason: {(ctx or {}).get('reason')}\n"
        f"Setup: {(ctx or {}).get('setup_type')}\n"
        f"Score: {(ctx or {}).get('score')}\n"
        f"Zona ok: {(ctx or {}).get('zone_ok')}\n"
        f"Micro BOS ok: {(ctx or {}).get('micro_ok')}\n"
        f"Rebound ok: {(ctx or {}).get('rebound_ok')}\n"
        f"Max Zone day position: {round(to_float((max_zone.get('extreme_info') or {}).get('day_position')), 3)}\n"
        f"Micro BOS: {micro.get('confirmed')}\n"
        f"Bear maturity: {maturity.get('mature')}"
    )



# =========================
# v28 - TRUE MAX ZONE + BIG MOVE THESIS
# =========================

def _true_max_zone_targets(price, signal, step=None, count=None):
    price = to_float(price, 0)
    step = to_float(step or BIG_MOVE_TARGET_STEP, BIG_MOVE_TARGET_STEP)
    count = int(count or BIG_MOVE_TARGET_COUNT)

    if not price or not step:
        return []

    targets = []
    signal = str(signal or "").upper()

    if signal == "BUY":
        base_level = math.ceil(price / step) * step
        if base_level <= price:
            base_level += step
        for i in range(count):
            targets.append(round(base_level + i * step, 3))
    else:
        base_level = math.floor(price / step) * step
        if base_level >= price:
            base_level -= step
        for i in range(count):
            targets.append(round(base_level - i * step, 3))

    return targets


def true_max_zone_reentry_context(signal, symbol, setup_type, score, data):
    signal = str(signal or "").upper()
    symbol = str(symbol or "XAUUSD").upper()
    setup_type = str(setup_type or "NORMAL").upper()
    data = data or {}

    if not LOSS_RECOVERY_TRUE_MAX_ZONE_ENABLED:
        return {
            "active": False,
            "block": False,
            "allow": True,
            "reason": "True Max Zone Recovery disattivato",
            "recent_losses": []
        }

    if signal != "SELL":
        return {
            "active": False,
            "block": False,
            "allow": True,
            "reason": "Non è SELL",
            "recent_losses": []
        }

    recent_losses = get_recent_direct_losses_custom(
        "SELL",
        symbol,
        LOSS_RECOVERY_LOOKBACK_SECONDS
    )

    active = len(recent_losses) >= LOSS_RECOVERY_SELL_LOSSES

    if not active:
        return {
            "active": False,
            "block": False,
            "allow": True,
            "reason": f"SL SELL diretti recenti {len(recent_losses)}/{LOSS_RECOVERY_SELL_LOSSES}",
            "recent_losses": recent_losses
        }

    price = get_price_from_data(data) or _latest_price_for_symbol(symbol)
    day_position = to_float(data.get("day_position"), -1)
    deep_ctx = get_deep_extension_context(symbol, data)
    rebound_from_low = to_float(deep_ctx.get("rebound_from_low"), 0)
    micro_ctx = micro_bos_bear_context(symbol, data)

    near_high = bool(
        to_bool(data.get("near_m15_high", "false"))
        or to_bool(data.get("near_day_high", "false"))
        or to_bool(data.get("max_zone_sell_local", "false"))
        or day_position >= TRUE_MAX_ZONE_MIN_DAY_POSITION
    )

    rejection_ok = bool(
        str(data.get("rejection", "")).upper() == "UPPER_WICK"
        or to_bool(data.get("upper_wick_strong", "false"))
        or not TRUE_MAX_ZONE_REQUIRE_REJECTION
    )

    micro_ok = bool(
        micro_ctx.get("confirmed")
        or not TRUE_MAX_ZONE_REQUIRE_MICRO_BOS
    )

    setup_ok = setup_type in TRUE_MAX_ZONE_ALLOWED_SETUPS
    score_ok = int(score) >= TRUE_MAX_ZONE_MIN_SCORE
    rebound_ok = rebound_from_low >= TRUE_MAX_ZONE_MIN_REBOUND_POINTS
    day_ok = day_position >= TRUE_MAX_ZONE_MIN_DAY_POSITION or near_high

    allow = bool(
        setup_ok
        and score_ok
        and day_ok
        and rebound_ok
        and rejection_ok
        and micro_ok
    )

    reason = (
        "True Max Zone confermata dopo SL: rientro SELL permesso"
        if allow
        else "Loss Recovery: dopo SL diretti serve vera zona Max alta, non primo rimbalzo"
    )

    return {
        "active": True,
        "block": not allow,
        "allow": allow,
        "reason": reason,
        "recent_losses": recent_losses,
        "recent_loss_count": len(recent_losses),
        "setup_ok": setup_ok,
        "score_ok": score_ok,
        "day_ok": day_ok,
        "rebound_ok": rebound_ok,
        "rejection_ok": rejection_ok,
        "micro_ok": micro_ok,
        "setup_type": setup_type,
        "score": score,
        "required_score": TRUE_MAX_ZONE_MIN_SCORE,
        "day_position": day_position,
        "required_day_position": TRUE_MAX_ZONE_MIN_DAY_POSITION,
        "rebound_from_low": rebound_from_low,
        "required_rebound": TRUE_MAX_ZONE_MIN_REBOUND_POINTS,
        "near_high": near_high,
        "micro_bos": micro_ctx,
        "deep_extension": deep_ctx,
        "price": price
    }


def true_max_zone_reentry_text(ctx):
    ctx = ctx or {}
    micro = ctx.get("micro_bos") or {}

    return (
        f"Active: {ctx.get('active')}\n"
        f"Allow: {ctx.get('allow')}\n"
        f"Reason: {ctx.get('reason')}\n"
        f"SL SELL diretti: {len(ctx.get('recent_losses', []) or [])}/{LOSS_RECOVERY_SELL_LOSSES}\n"
        f"Setup: {ctx.get('setup_type')} | ok: {ctx.get('setup_ok')}\n"
        f"Score: {ctx.get('score')}/{ctx.get('required_score')} | ok: {ctx.get('score_ok')}\n"
        f"Day position: {round(to_float(ctx.get('day_position')), 3)}/{TRUE_MAX_ZONE_MIN_DAY_POSITION} | ok: {ctx.get('day_ok')}\n"
        f"Rebound from low: {round(to_float(ctx.get('rebound_from_low')), 2)}/{TRUE_MAX_ZONE_MIN_REBOUND_POINTS} | ok: {ctx.get('rebound_ok')}\n"
        f"Near high: {ctx.get('near_high')}\n"
        f"Rejection ok: {ctx.get('rejection_ok')}\n"
        f"Micro BOS: {micro.get('confirmed')} | ok: {ctx.get('micro_ok')}"
    )


def _big_move_best_trade(symbol):
    symbol = str(symbol or "XAUUSD").upper()
    now = now_ts()
    candidates = []

    for trade in OPEN_TRADES:
        if str(trade.get("symbol", "")).upper() != symbol:
            continue
        if str(trade.get("status")) not in ["OPEN", "PENDING"]:
            continue
        if now - (trade.get("created") or 0) > BIG_MOVE_LOOKBACK_SECONDS:
            continue

        setup = str(trade.get("setup_type", "NORMAL")).upper()
        if setup not in BIG_MOVE_SPECIAL_SETUPS:
            continue

        highest_tp = int(trade.get("highest_tp", 0))
        if highest_tp < BIG_MOVE_MIN_TP_LEVEL:
            continue

        if BIG_MOVE_REQUIRE_BE_PROTECTED and not trade.get("be"):
            continue

        candidates.append(trade)

    return sorted(
        candidates,
        key=lambda t: (
            int(t.get("highest_tp", 0)),
            t.get("last_tp_time") or t.get("created") or 0
        ),
        reverse=True
    )[0] if candidates else None


def get_big_move_thesis_context(symbol, data=None):
    symbol = str(symbol or "XAUUSD").upper()
    data = data or {}

    if not BIG_MOVE_THESIS_ENABLED:
        return {"active": False, "reason": "Big Move Thesis disattivata"}

    trade = _big_move_best_trade(symbol)
    price = get_price_from_data(data) or _latest_price_for_symbol(symbol)

    if not trade:
        return {
            "active": False,
            "reason": f"Nessun trade speciale protetto a TP{BIG_MOVE_MIN_TP_LEVEL}+",
            "price": price
        }

    signal = str(trade.get("signal", "")).upper()
    highest_tp = int(trade.get("highest_tp", 0))
    setup = str(trade.get("setup_type", "NORMAL")).upper()

    auto_event_active, event_reasons = auto_event_cache_active()
    event_active = bool(
        auto_event_active
        or to_bool(data.get("event_mode", "false"))
        or to_bool(data.get("auto_event_pine", "false"))
        or to_float(data.get("range_atr"), 0) >= 2.2
        or to_float(data.get("m15_range_atr"), 0) >= BIG_MOVE_BREAKOUT_M15_ATR
        or to_bool(data.get("volume_spike", "false"))
    )

    m15_range_atr = to_float(data.get("m15_range_atr"), 0)
    range_atr = to_float(data.get("range_atr"), 0)
    compression_ok = bool(
        0 < m15_range_atr <= BIG_MOVE_COMPRESSION_MAX_M15_ATR
    )
    breakout_ok = bool(
        m15_range_atr >= BIG_MOVE_BREAKOUT_M15_ATR
        or range_atr >= 2.2
    )

    h1 = str(data.get("h1_bias", "NEUTRAL")).upper()
    h4 = str(data.get("h4_bias", "NEUTRAL")).upper()
    day = str(data.get("day_bias", "NEUTRAL")).upper()
    ema20 = str(data.get("ema20_slope", "FLAT")).upper()
    ema50 = str(data.get("ema50_slope", "FLAT")).upper()
    candle = str(data.get("candle_dir", "")).upper()

    if signal == "BUY":
        direction_ok = bool(
            h1 == "BUY" or h4 == "BUY" or day == "BUY"
            or ema20 == "UP" or ema50 == "UP"
            or candle == "BULL"
        )
    else:
        direction_ok = bool(
            h1 == "SELL" or h4 == "SELL" or day == "SELL"
            or ema20 == "DOWN" or ema50 == "DOWN"
            or candle == "BEAR"
        )

    runner_ready = highest_tp >= BIG_MOVE_CONFIRMED_TP_LEVEL or bool(trade.get("runner"))
    protected = bool(trade.get("be"))
    target_levels = _true_max_zone_targets(price, signal)

    confluences = []
    if protected:
        confluences.append("SL già protetto/BE")
    if highest_tp >= BIG_MOVE_MIN_TP_LEVEL:
        confluences.append(f"Trade già a TP{highest_tp}")
    if setup in BIG_MOVE_SPECIAL_SETUPS:
        confluences.append(f"Setup speciale {setup}")
    if event_active:
        confluences.append("Evento/news/volatilità attiva")
    if compression_ok:
        confluences.append("Mercato compresso/lento")
    if breakout_ok:
        confluences.append("Breakout o range M15 espanso")
    if direction_ok:
        confluences.append("Direzione tecnica coerente")
    if target_levels:
        confluences.append("Target psicologici disponibili")

    event_requirement_ok = event_active or not BIG_MOVE_EVENT_OR_NEWS_REQUIRED

    active = bool(
        len(confluences) >= BIG_MOVE_MIN_CONFLUENCES
        and event_requirement_ok
    )

    status = "CONFIRMED" if active and runner_ready and (breakout_ok or event_active) else "WATCH"

    if not active:
        status = "IDLE"

    reason = (
        "Possibile movimento grosso in preparazione"
        if status == "WATCH"
        else "Movimento grosso confermato / runner da proteggere"
        if status == "CONFIRMED"
        else f"Confluenze insufficienti {len(confluences)}/{BIG_MOVE_MIN_CONFLUENCES}"
    )

    return {
        "active": active,
        "status": status,
        "reason": reason,
        "symbol": symbol,
        "signal": signal,
        "trade": trade,
        "trade_id": trade.get("id"),
        "setup": setup,
        "highest_tp": highest_tp,
        "price": price,
        "event_active": event_active,
        "event_reasons": event_reasons,
        "compression_ok": compression_ok,
        "breakout_ok": breakout_ok,
        "direction_ok": direction_ok,
        "protected": protected,
        "runner_ready": runner_ready,
        "confluences": confluences,
        "confluence_count": len(confluences),
        "target_levels": target_levels,
        "m15_range_atr": m15_range_atr,
        "range_atr": range_atr
    }


def big_move_thesis_text(ctx):
    ctx = ctx or {}
    trade = ctx.get("trade") or {}
    targets = ctx.get("target_levels") or []
    target_text = ", ".join(str(t) for t in targets) if targets else "N/D"
    confluence_text = "\n".join(f"- {item}" for item in (ctx.get("confluences") or [])) or "- N/D"

    return (
        f"Status: {ctx.get('status')}\n"
        f"Reason: {ctx.get('reason')}\n"
        f"Trade: {ctx.get('trade_id')} | {ctx.get('signal')} | {ctx.get('setup')}\n"
        f"Highest TP: {ctx.get('highest_tp')}\n"
        f"Prezzo: {round(to_float(ctx.get('price')), 3)}\n"
        f"Evento/news: {ctx.get('event_active')}\n"
        f"Compressione: {ctx.get('compression_ok')} | Breakout: {ctx.get('breakout_ok')}\n"
        f"Direzione coerente: {ctx.get('direction_ok')}\n"
        f"Protetto BE: {ctx.get('protected')}\n"
        f"Target scenario: {target_text}\n"
        f"Confluenze {ctx.get('confluence_count')}/{BIG_MOVE_MIN_CONFLUENCES}:\n{confluence_text}"
    )


def maybe_big_move_thesis_alert(symbol, data, ctx=None):
    symbol = str(symbol or "XAUUSD").upper()
    data = data or {}

    if not BIG_MOVE_ALERTS_ENABLED:
        return None

    ctx = ctx or get_big_move_thesis_context(symbol, data)

    if not ctx.get("active"):
        return None

    state = get_regime_arbiter_state(symbol)
    now = now_ts()
    last_time = to_float(state.get("big_move_last_alert_time"), 0)

    if now - last_time < BIG_MOVE_ALERT_COOLDOWN_SECONDS:
        return None

    signature = f"{ctx.get('signal')}:{ctx.get('status')}:{ctx.get('trade_id')}:TP{ctx.get('highest_tp')}"

    if state.get("big_move_last_signature") == signature:
        return None

    state["big_move_last_alert_time"] = now
    state["big_move_last_signature"] = signature

    emoji = "🚀" if ctx.get("status") == "CONFIRMED" else "⚡"
    title = "BIG MOVE CONFIRMED" if ctx.get("status") == "CONFIRMED" else "BIG MOVE WATCH"
    side = "SUPER BUY" if ctx.get("signal") == "BUY" else "SUPER SELL"

    return f"""{emoji} {title} {VERSION}

Scenario: {side}
Symbol: {symbol}

{big_move_thesis_text(ctx)}

Lettura:
Il bot non considera questo una garanzia.
Sta dicendo che ci sono condizioni da movimento grosso stile Max:
trade già protetto, TP avanzati, evento/news/volatilità o compressione,
e target psicologici disponibili.

Gestione:
- non inseguire nuove entrate nel mezzo
- proteggi il rischio
- valuta runner solo se hai già TP/BE
- step by step, come Max
"""



def event_trap_flip_context(signal, symbol, setup_type, score, data, special_ctx=None, big_move_ctx=None):
    """
    v29 Event Trap Flip:
    Consente un SELL A+ contro un BUY speciale/Big Move BUY quando l'evento fa spike alto
    e poi mostra segnali di trappola/ribaltamento. Serve a non perdere casi tipo
    SELL 4038-4044 dopo un BUY arrivato a TP6.
    """
    signal = str(signal or "").upper()
    symbol = str(symbol or "XAUUSD").upper()
    setup_type = str(setup_type or "NORMAL").upper()
    data = data or {}

    base = {
        "active": False,
        "allow": False,
        "reason": "Event Trap Flip non attivo",
        "setup_type": setup_type,
        "score": score,
        "required_score": EVENT_TRAP_FLIP_MIN_SCORE
    }

    if not EVENT_TRAP_FLIP_ENABLED:
        base["reason"] = "Event Trap Flip disattivato"
        return base

    if signal != "SELL":
        base["reason"] = "Non è un SELL flip"
        return base

    if setup_type not in EVENT_TRAP_FLIP_ALLOWED_SETUPS:
        base["reason"] = f"Setup {setup_type} non abilitato al flip evento"
        return base

    special_ctx = special_ctx or get_recovery_dominance_context(
        symbol,
        data,
        min_tp=EVENT_TRAP_FLIP_MIN_BUY_TP
    )
    big_move_ctx = big_move_ctx or get_big_move_thesis_context(symbol, data)

    best_buy = special_ctx.get("best_trade") or {}
    buy_tp = int(special_ctx.get("highest_tp") or best_buy.get("highest_tp") or 0)

    buy_dominant = bool(special_ctx.get("active") and buy_tp >= EVENT_TRAP_FLIP_MIN_BUY_TP)
    big_move_buy = bool(
        big_move_ctx.get("active")
        and str(big_move_ctx.get("signal", "")).upper() == "BUY"
        and str(big_move_ctx.get("status", "")).upper() in ["WATCH", "CONFIRMED"]
    )

    conflict_ok = buy_dominant or big_move_buy

    auto_event_active, event_reasons = auto_event_cache_active()
    range_atr = to_float(data.get("range_atr"), 0)
    m15_range_atr = to_float(data.get("m15_range_atr"), 0)
    event_active = bool(
        auto_event_active
        or to_bool(data.get("event_mode", "false"))
        or to_bool(data.get("auto_event_pine", "false"))
        or to_bool(data.get("volume_spike", "false"))
        or range_atr >= 2.2
        or m15_range_atr >= BIG_MOVE_BREAKOUT_M15_ATR
    )

    extreme_ok, extreme_info = extreme_zone_info("SELL", data)
    event_spike_ctx = get_event_spike_context(data)
    day_position = to_float(data.get("day_position"), -1)
    zone_ok = bool(
        extreme_ok
        or to_bool(data.get("near_m15_high", "false"))
        or to_bool(data.get("near_day_high", "false"))
        or to_bool(data.get("max_zone_sell_local", "false"))
        or to_bool(data.get("true_max_zone_sell_local", "false"))
        or event_spike_ctx.get("top_position", 0) >= EXTREME_SPIKE_FADE_TOP_POSITION_MIN
        or str(data.get("rejection", "")).upper() == "UPPER_WICK"
        or to_bool(data.get("upper_wick_strong", "false"))
    )

    event_retrace_from_high = to_float(data.get("event_retrace_from_high"), 0)
    event_close_position = to_float(data.get("event_close_position"), 0.5)
    candle_bear = str(data.get("candle_dir", "")).upper() == "BEAR"
    upper_rejection = bool(
        str(data.get("rejection", "")).upper() == "UPPER_WICK"
        or to_bool(data.get("upper_wick_strong", "false"))
    )

    rejection_ok = bool(
        upper_rejection
        or candle_bear
        or event_retrace_from_high >= EVENT_TRAP_FLIP_MIN_RETRACE_FROM_HIGH
        or event_spike_ctx.get("failed_retest_zone")
        or event_spike_ctx.get("retrace_from_high", 0) >= EXTREME_SPIKE_FADE_RETRACE_MIN
        or not EVENT_TRAP_FLIP_REQUIRE_REJECTION
    )

    micro_ctx = micro_bos_bear_context(symbol, data)
    event_breakdown_ok = bool(
        event_retrace_from_high >= EVENT_TRAP_FLIP_MIN_RETRACE_FROM_HIGH
        or event_spike_ctx.get("retrace_from_high", 0) >= EXTREME_SPIKE_FADE_RETRACE_MIN
        or event_spike_ctx.get("failed_retest_zone")
        or event_close_position <= EVENT_TRAP_FLIP_MAX_EVENT_CLOSE_POSITION
        or candle_bear
        or to_bool(data.get("event_trap_flip_sell_local", "false"))
    )
    micro_or_breakdown_ok = bool(
        micro_ctx.get("confirmed")
        or event_breakdown_ok
        or not EVENT_TRAP_FLIP_REQUIRE_MICRO_OR_BREAKDOWN
    )

    score_ok = int(score) >= EVENT_TRAP_FLIP_MIN_SCORE
    event_ok = event_active or not EVENT_TRAP_FLIP_REQUIRE_EVENT
    required_zone_ok = zone_ok or not EVENT_TRAP_FLIP_REQUIRE_ZONE

    allow = bool(
        conflict_ok
        and score_ok
        and event_ok
        and required_zone_ok
        and rejection_ok
        and micro_or_breakdown_ok
    )

    missing = []
    if not conflict_ok:
        missing.append(f"nessun BUY TP{EVENT_TRAP_FLIP_MIN_BUY_TP}+ / Big Move BUY da flippare")
    if not score_ok:
        missing.append(f"score {score} sotto {EVENT_TRAP_FLIP_MIN_SCORE}")
    if not event_ok:
        missing.append("evento/news non attivo")
    if not required_zone_ok:
        missing.append("zona Max alta non confermata")
    if not rejection_ok:
        missing.append("rejection/trap non confermata")
    if not micro_or_breakdown_ok:
        missing.append("manca micro BOS o breakdown evento")

    return {
        "active": conflict_ok,
        "allow": allow,
        "reason": (
            "EVENT TRAP FLIP: SELL A+ autorizzato contro BUY recovery / Big Move BUY"
            if allow else "Event Trap Flip non autorizzato: " + "; ".join(missing)
        ),
        "setup_type": setup_type,
        "setup_ok": setup_type in EVENT_TRAP_FLIP_ALLOWED_SETUPS,
        "score": score,
        "required_score": EVENT_TRAP_FLIP_MIN_SCORE,
        "score_ok": score_ok,
        "event_active": event_active,
        "event_ok": event_ok,
        "event_reasons": event_reasons,
        "zone_ok": zone_ok,
        "rejection_ok": rejection_ok,
        "micro_or_breakdown_ok": micro_or_breakdown_ok,
        "micro_bos": micro_ctx,
        "event_breakdown_ok": event_breakdown_ok,
        "event_retrace_from_high": event_retrace_from_high,
        "event_close_position": event_close_position,
        "day_position": day_position,
        "upper_rejection": upper_rejection,
        "candle_bear": candle_bear,
        "special_buy": special_ctx,
        "big_move": big_move_ctx,
        "buy_dominant": buy_dominant,
        "big_move_buy": big_move_buy,
        "buy_highest_tp": buy_tp,
        "extreme_info": extreme_info,
        "missing": missing
    }


def event_trap_flip_text(ctx):
    ctx = ctx or {}
    micro = ctx.get("micro_bos") or {}
    special = ctx.get("special_buy") or {}
    best = special.get("best_trade") or {}
    return (
        f"Active: {ctx.get('active')}\n"
        f"Allow: {ctx.get('allow')}\n"
        f"Reason: {ctx.get('reason')}\n"
        f"Setup: {ctx.get('setup_type')} | Score: {ctx.get('score')}/{ctx.get('required_score')} | ok: {ctx.get('score_ok')}\n"
        f"Evento/news: {ctx.get('event_active')} | ok: {ctx.get('event_ok')}\n"
        f"Zona Max ok: {ctx.get('zone_ok')} | Rejection ok: {ctx.get('rejection_ok')}\n"
        f"Micro/Breakdown ok: {ctx.get('micro_or_breakdown_ok')} | Micro BOS: {micro.get('confirmed')} | Event breakdown: {ctx.get('event_breakdown_ok')}\n"
        f"Retrace da high evento: {round(to_float(ctx.get('event_retrace_from_high')), 2)} / {EVENT_TRAP_FLIP_MIN_RETRACE_FROM_HIGH}\n"
        f"Event close position: {round(to_float(ctx.get('event_close_position')), 3)} / max {EVENT_TRAP_FLIP_MAX_EVENT_CLOSE_POSITION}\n"
        f"BUY da flippare: {best.get('id', 'N/D')} | {best.get('setup_type', 'N/D')} | TP{ctx.get('buy_highest_tp', 0)}\n"
        f"Big Move BUY: {ctx.get('big_move_buy')}"
    )



def special_buy_flip_window_context(symbol, setup_type, score, data, special_ctx=None, event_trap_ctx=None):
    """
    v31 Max Flip Window.
    Serve quando un BUY speciale è già in profitto (TP3/TP6), ma il prezzo torna su una
    zona di vendita/rejection e Max avrebbe flippato SELL senza aspettare una invalidazione piena.
    Non autorizza SELL NORMAL: solo setup speciali.
    """
    symbol = str(symbol or "XAUUSD").upper()
    setup_type = str(setup_type or "NORMAL").upper()
    data = data or {}

    ctx = {
        "active": False,
        "allow": False,
        "reason": "Max Flip Window non attiva",
        "setup_type": setup_type,
        "score": int(score or 0),
        "required_score": SPECIAL_BUY_FLIP_MIN_SCORE,
        "buy_tp": 0,
        "score_ok": False,
        "setup_ok": False,
        "tp_ok": False,
        "zone_ok": False,
        "event_or_rejection_ok": False,
        "micro_ok": False,
        "event_close_position": 0,
        "day_position": 0,
        "special_buy": special_ctx or {},
        "micro_bos": {},
        "event_trap": event_trap_ctx or {}
    }

    if not SPECIAL_BUY_FLIP_WINDOW_ENABLED:
        ctx["reason"] = "SPECIAL_BUY_FLIP_WINDOW_ENABLED = FALSE"
        return ctx

    if special_ctx is None:
        special_ctx = get_recovery_dominance_context(symbol, data, min_tp=SPECIAL_BUY_FLIP_MIN_BUY_TP)
    ctx["special_buy"] = special_ctx or {}

    if not (special_ctx or {}).get("active"):
        ctx["reason"] = "nessun BUY speciale da flippare"
        return ctx

    buy_tp = int((special_ctx or {}).get("highest_tp", 0) or 0)
    ctx["buy_tp"] = buy_tp
    tp_ok = SPECIAL_BUY_FLIP_MIN_BUY_TP <= buy_tp <= SPECIAL_BUY_FLIP_MAX_BUY_TP
    setup_ok = setup_type in SPECIAL_BUY_FLIP_ALLOWED_SETUPS
    score_ok = int(score or 0) >= SPECIAL_BUY_FLIP_MIN_SCORE

    extreme_ok, extreme_info = extreme_zone_info("SELL", data)
    micro_ctx = micro_bos_bear_context(symbol, data)
    ctx["micro_bos"] = micro_ctx

    upper_rejection = bool(
        str(data.get("rejection", "")).upper() == "UPPER_WICK"
        or to_bool(data.get("upper_wick_strong", "false"))
    )
    near_high = bool(
        to_bool(data.get("near_m15_high", "false"))
        or to_bool(data.get("near_day_high", "false"))
    )
    day_position = to_float(data.get("day_position"), 0.5)
    event_active = bool(
        to_bool(data.get("event_mode"))
        or to_bool(data.get("auto_event_pine"))
        or to_bool(data.get("event_risk"))
    )
    event_close_position = to_float(data.get("event_close_position"), to_float(data.get("close_position"), 0))
    event_breakdown = to_bool(data.get("event_breakdown")) or to_bool(data.get("micro_breakdown"))
    candle_bear = str(data.get("candle_dir", "")).upper() == "BEAR"

    zone_ok = bool(extreme_ok or near_high or upper_rejection or event_close_position >= SPECIAL_BUY_FLIP_MIN_EVENT_CLOSE_POSITION)
    event_or_rejection_ok = bool(
        event_active
        or upper_rejection
        or event_breakdown
        or candle_bear
        or event_close_position >= SPECIAL_BUY_FLIP_MIN_EVENT_CLOSE_POSITION
    )
    micro_ok = bool(micro_ctx.get("confirmed") or event_breakdown or not SPECIAL_BUY_FLIP_REQUIRE_MICRO_BOS)

    ctx.update({
        "active": True,
        "setup_ok": setup_ok,
        "score_ok": score_ok,
        "tp_ok": tp_ok,
        "zone_ok": zone_ok,
        "event_or_rejection_ok": event_or_rejection_ok,
        "micro_ok": micro_ok,
        "day_position": day_position,
        "event_close_position": event_close_position,
        "event_breakdown": event_breakdown,
        "upper_rejection": upper_rejection,
        "near_high": near_high,
        "extreme_info": extreme_info
    })

    allow = bool(
        setup_ok
        and score_ok
        and tp_ok
        and (zone_ok or not SPECIAL_BUY_FLIP_REQUIRE_ZONE)
        and (event_or_rejection_ok or not SPECIAL_BUY_FLIP_REQUIRE_EVENT_OR_REJECTION)
        and micro_ok
    )
    ctx["allow"] = allow

    missing = []
    if not setup_ok:
        missing.append("setup non abilitato")
    if not score_ok:
        missing.append(f"score {score}/{SPECIAL_BUY_FLIP_MIN_SCORE}")
    if not tp_ok:
        missing.append(f"BUY TP{buy_tp} fuori finestra {SPECIAL_BUY_FLIP_MIN_BUY_TP}-{SPECIAL_BUY_FLIP_MAX_BUY_TP}")
    if SPECIAL_BUY_FLIP_REQUIRE_ZONE and not zone_ok:
        missing.append("zona Max/rejection non confermata")
    if SPECIAL_BUY_FLIP_REQUIRE_EVENT_OR_REJECTION and not event_or_rejection_ok:
        missing.append("manca evento/rejection/candela bearish")
    if SPECIAL_BUY_FLIP_REQUIRE_MICRO_BOS and not micro_ok:
        missing.append("manca micro-BOS")

    ctx["reason"] = (
        "MAX FLIP WINDOW: SELL speciale autorizzato contro BUY già pagato"
        if allow else "Max Flip Window non autorizzata: " + "; ".join(missing)
    )
    return ctx


def special_buy_flip_window_text(ctx):
    ctx = ctx or {}
    best = (ctx.get("special_buy") or {}).get("best_trade") or {}
    micro = ctx.get("micro_bos") or {}
    return (
        f"Active: {ctx.get('active')}\n"
        f"Allow: {ctx.get('allow')}\n"
        f"Reason: {ctx.get('reason')}\n"
        f"Setup: {ctx.get('setup_type')} | Score: {ctx.get('score')}/{ctx.get('required_score')} | ok: {ctx.get('score_ok')}\n"
        f"BUY da flippare: {best.get('id', 'N/D')} | {best.get('setup_type', 'N/D')} | TP{ctx.get('buy_tp', 0)} | ok: {ctx.get('tp_ok')}\n"
        f"Zona ok: {ctx.get('zone_ok')} | Evento/Rejection ok: {ctx.get('event_or_rejection_ok')} | Micro ok: {ctx.get('micro_ok')}\n"
        f"Day position: {round(to_float(ctx.get('day_position')), 3)} | Event close pos: {round(to_float(ctx.get('event_close_position')), 3)}\n"
        f"Near high: {ctx.get('near_high')} | Upper rejection: {ctx.get('upper_rejection')} | Event breakdown: {ctx.get('event_breakdown')}\n"
        f"Micro BOS: {micro.get('confirmed')}"
    )


def deep_rebound_buy_candidate_context(signal, symbol, data):
    """
    v32 Max Rebound Buy candidate.
    Costruisce un BUY speciale quando il SELL precedente è già molto pagato
    e il prezzo torna su una zona low/psicologica. È l'equivalente server-side
    del rimbalzo stile Max dopo TP6/TP7/TP8 SELL.
    """
    symbol = str(symbol or "XAUUSD").upper()
    signal = normalize_signal(signal)
    data = data or {}
    price = get_price_from_data(data)
    state = get_bear_continuation_state(symbol)

    active_news_bias, _ = get_auto_news_bias()
    day_position = to_float(data.get("day_position"), -1)
    rsi = to_float(data.get("rsi", 50), 50)
    candle_dir = str(data.get("candle_dir", "NEUTRAL")).upper()
    rejection = str(data.get("rejection", "NONE")).upper()
    structure = str(data.get("structure", "NEUTRAL")).upper()
    near_day_low = to_bool(data.get("near_day_low"))
    near_m15_low = to_bool(data.get("near_m15_low"))
    lower_wick = to_bool(data.get("lower_wick_strong"))
    close_above_ema20 = to_bool(data.get("close_above_ema20"))
    recent_low_touch = to_bool(data.get("recent_low_touch"))
    recovery_buy_signal = to_bool(data.get("recovery_buy_signal"))
    near_psych, psych_level, psych_distance = psych_info(price)

    ctx = {
        "allow": False,
        "reason": "Deep Rebound BUY non attivo",
        "price": price,
        "state": state.get("state"),
        "recent_ok": False,
        "impulse_drop": 0.0,
        "distance_from_low": 999999.0,
        "confirmations": 0,
        "near_low": False,
        "day_position": day_position,
        "psych_level": psych_level,
        "psych_distance": psych_distance
    }

    if not DEEP_REBOUND_BUY_ENABLED:
        ctx["reason"] = "DEEP_REBOUND_BUY_ENABLED = FALSE"
        return ctx
    if signal != "BUY":
        ctx["reason"] = "non è BUY"
        return ctx
    if DEEP_REBOUND_BUY_REQUIRE_BULLISH_NEWS and active_news_bias != "BULLISH_GOLD":
        ctx["reason"] = f"news non bullish ({active_news_bias})"
        return ctx

    recent_sells = get_recent_tp_trades(
        "SELL",
        symbol,
        min_tp=DEEP_REBOUND_BUY_MIN_SELL_TP,
        lookback_seconds=DEEP_REBOUND_BUY_LOOKBACK_SECONDS
    )
    recent_runner_sells = [
        t for t in OPEN_TRADES
        if str(t.get("symbol", "")).upper() == symbol
        and normalize_signal(t.get("signal")) == "SELL"
        and bool(t.get("runner"))
        and now_ts() - to_float(t.get("created", 0), 0) <= DEEP_REBOUND_BUY_LOOKBACK_SECONDS
    ]
    recent_ok = bool(recent_sells or recent_runner_sells)

    impulse_high = to_float(state.get("impulse_high"), 0)
    impulse_low = to_float(state.get("impulse_low"), 0)
    history = recent_bear_history(symbol, BEAR_IMPULSE_LOOKBACK_SECONDS)
    if history:
        if not impulse_high:
            impulse_high = max(to_float(p.get("high"), 0) for p in history)
        if not impulse_low:
            impulse_low = min(to_float(p.get("low"), 999999) for p in history)

    impulse_drop = max(0.0, impulse_high - impulse_low)
    distance_from_low = abs(price - impulse_low) if price and impulse_low else 999999.0
    near_low = bool(
        distance_from_low <= DEEP_REBOUND_BUY_MAX_DISTANCE_FROM_LOW
        or near_day_low
        or near_m15_low
        or lower_wick
        or rejection == "LOWER_WICK"
        or (near_psych and psych_distance <= PSYCH_LEVEL_DISTANCE)
    )

    confirmations = 0
    if near_low:
        confirmations += 1
    if candle_dir == "BULL" or recovery_buy_signal:
        confirmations += 1
    if lower_wick or rejection == "LOWER_WICK" or recent_low_touch:
        confirmations += 1
    if near_psych:
        confirmations += 1
    if close_above_ema20:
        confirmations += 1
    if rsi <= 48:
        confirmations += 1
    if structure in ["LL", "HL", "BULLISH"]:
        confirmations += 1

    day_pos_ok = bool(day_position < 0 or day_position <= DEEP_REBOUND_BUY_MAX_DAY_POSITION)
    impulse_ok = impulse_drop >= DEEP_REBOUND_BUY_MIN_IMPULSE_DROP
    confirmation_ok = confirmations >= DEEP_REBOUND_BUY_MIN_CONFIRMATIONS

    allow = bool(recent_ok and impulse_ok and near_low and day_pos_ok and confirmation_ok)
    ctx.update({
        "allow": allow,
        "reason": (
            "DEEP REBOUND BUY: rimbalzo Max dopo SELL già molto pagato"
            if allow else "Deep Rebound BUY non autorizzato"
        ),
        "recent_ok": recent_ok,
        "recent_sell_count": len(recent_sells),
        "recent_runner_sell_count": len(recent_runner_sells),
        "impulse_drop": impulse_drop,
        "distance_from_low": distance_from_low,
        "near_low": near_low,
        "day_pos_ok": day_pos_ok,
        "impulse_ok": impulse_ok,
        "confirmation_ok": confirmation_ok,
        "confirmations": confirmations,
        "impulse_high": impulse_high,
        "impulse_low": impulse_low
    })

    if not allow:
        missing = []
        if not recent_ok:
            missing.append(f"nessun SELL TP{DEEP_REBOUND_BUY_MIN_SELL_TP}/runner recente")
        if not impulse_ok:
            missing.append(f"drop {round(impulse_drop, 2)}/{DEEP_REBOUND_BUY_MIN_IMPULSE_DROP}")
        if not near_low:
            missing.append(f"lontano dal low {round(distance_from_low, 2)}/{DEEP_REBOUND_BUY_MAX_DISTANCE_FROM_LOW}")
        if not day_pos_ok:
            missing.append(f"day position alta {round(day_position, 2)}/{DEEP_REBOUND_BUY_MAX_DAY_POSITION}")
        if not confirmation_ok:
            missing.append(f"conferme {confirmations}/{DEEP_REBOUND_BUY_MIN_CONFIRMATIONS}")
        ctx["reason"] = "Deep Rebound BUY non autorizzato: " + "; ".join(missing)

    return ctx


def post_sell_rebound_unlock_context(signal, symbol, setup_type, score, data):
    """
    v31 Deep Sell Rebound Unlock.
    Dopo un SELL già arrivato a TP8/runner e un nuovo low profondo, permette un BUY recovery/dip
    forte anche se la lower-high machine è ancora bearish. È pensato per il rimbalzo rapido stile Max.
    """
    symbol = str(symbol or "XAUUSD").upper()
    signal = normalize_signal(signal)
    setup_type = str(setup_type or "NORMAL").upper()
    data = data or {}
    price = get_price_from_data(data)
    state = get_bear_continuation_state(symbol)

    ctx = {
        "active": False,
        "allow": False,
        "reason": "Post SELL rebound non attivo",
        "setup_type": setup_type,
        "score": int(score or 0),
        "required_score": POST_SELL_REBOUND_MIN_SCORE,
        "recent_sell_tp8_count": 0,
        "impulse_drop": 0,
        "distance_from_low": 999999,
        "price": price,
        "state": state.get("state"),
        "recent_trade": None
    }

    if not POST_SELL_REBOUND_UNLOCK_ENABLED:
        ctx["reason"] = "POST_SELL_REBOUND_UNLOCK_ENABLED = FALSE"
        return ctx
    if signal != "BUY":
        ctx["reason"] = "non è BUY"
        return ctx
    if setup_type not in POST_SELL_REBOUND_ALLOWED_SETUPS:
        ctx["reason"] = "setup BUY non abilitato al rebound"
        return ctx

    recent_sells = get_recent_tp_trades(
        "SELL",
        symbol,
        min_tp=POST_SELL_REBOUND_MIN_SELL_TP,
        lookback_seconds=POST_SELL_REBOUND_LOOKBACK_SECONDS
    )
    recent_runner_sells = [
        t for t in OPEN_TRADES
        if str(t.get("symbol", "")).upper() == symbol
        and normalize_signal(t.get("signal")) == "SELL"
        and bool(t.get("runner"))
        and now_ts() - to_float(t.get("created", 0), 0) <= POST_SELL_REBOUND_LOOKBACK_SECONDS
    ]
    recent_ok = bool(recent_sells or recent_runner_sells)
    recent_trade = (recent_sells or recent_runner_sells or [None])[0]

    impulse_high = to_float(state.get("impulse_high"), 0)
    impulse_low = to_float(state.get("impulse_low"), 0)
    history = recent_bear_history(symbol, BEAR_IMPULSE_LOOKBACK_SECONDS)
    if history:
        if not impulse_high:
            impulse_high = max(to_float(p.get("high"), 0) for p in history)
        if not impulse_low:
            impulse_low = min(to_float(p.get("low"), 999999) for p in history)

    impulse_drop = max(0, impulse_high - impulse_low)
    distance_from_low = abs(price - impulse_low) if price and impulse_low else 999999
    near_low = bool(
        distance_from_low <= POST_SELL_REBOUND_MAX_DISTANCE_FROM_LOW
        or to_bool(data.get("near_day_low"))
        or to_bool(data.get("near_m15_low"))
        or to_bool(data.get("lower_wick_strong"))
        or str(data.get("rejection", "")).upper() == "LOWER_WICK"
    )
    score_ok = int(score or 0) >= POST_SELL_REBOUND_MIN_SCORE
    impulse_ok = impulse_drop >= POST_SELL_REBOUND_MIN_IMPULSE_DROP

    allow = bool(recent_ok and score_ok and impulse_ok and near_low)
    ctx.update({
        "active": recent_ok,
        "allow": allow,
        "reason": (
            "DEEP SELL REBOUND: BUY recovery/dip autorizzato dopo SELL TP6+/runner"
            if allow else "Deep Sell Rebound non autorizzato"
        ),
        "recent_sell_tp8_count": len(recent_sells),
        "recent_runner_sell_count": len(recent_runner_sells),
        "recent_trade": recent_trade,
        "impulse_drop": impulse_drop,
        "distance_from_low": distance_from_low,
        "near_low": near_low,
        "score_ok": score_ok,
        "impulse_ok": impulse_ok,
        "recent_ok": recent_ok,
        "impulse_high": impulse_high,
        "impulse_low": impulse_low
    })

    if not allow:
        missing = []
        if not recent_ok:
            missing.append(f"nessun SELL TP{POST_SELL_REBOUND_MIN_SELL_TP}/runner recente")
        if not score_ok:
            missing.append(f"score {score}/{POST_SELL_REBOUND_MIN_SCORE}")
        if not impulse_ok:
            missing.append(f"drop {round(impulse_drop,2)}/{POST_SELL_REBOUND_MIN_IMPULSE_DROP}")
        if not near_low:
            missing.append(f"troppo lontano dal low {round(distance_from_low,2)}/{POST_SELL_REBOUND_MAX_DISTANCE_FROM_LOW}")
        ctx["reason"] = "Deep Sell Rebound non autorizzato: " + "; ".join(missing)

    return ctx


def post_sell_rebound_unlock_text(ctx):
    ctx = ctx or {}
    trade = ctx.get("recent_trade") or {}
    return (
        f"Active: {ctx.get('active')}\n"
        f"Allow: {ctx.get('allow')}\n"
        f"Reason: {ctx.get('reason')}\n"
        f"Setup: {ctx.get('setup_type')} | Score: {ctx.get('score')}/{ctx.get('required_score')} | ok: {ctx.get('score_ok')}\n"
        f"SELL recenti TP8+: {ctx.get('recent_sell_tp8_count')} | Runner SELL: {ctx.get('recent_runner_sell_count')}\n"
        f"Trade SELL riferimento: {trade.get('id', 'N/D')} | {trade.get('setup_type', 'N/D')} | TP{trade.get('highest_tp', 0)}\n"
        f"Impulse drop: {round(to_float(ctx.get('impulse_drop')), 2)} / {POST_SELL_REBOUND_MIN_IMPULSE_DROP}\n"
        f"Distance from low: {round(to_float(ctx.get('distance_from_low')), 2)} / {POST_SELL_REBOUND_MAX_DISTANCE_FROM_LOW}\n"
        f"Near low: {ctx.get('near_low')} | State: {ctx.get('state')}"
    )


def deep_extension_sell_guard_context(signal, symbol, setup_type, score, data, deep_ctx=None):
    signal = str(signal or "").upper()
    setup_type = str(setup_type or "NORMAL").upper()
    data = data or {}

    if not DEEP_EXTENSION_SELL_GUARD_ENABLED:
        return {"block": False, "reason": "Deep Extension Sell Guard disattivato"}
    if signal != "SELL":
        return {"block": False, "reason": "Non è SELL"}
    if setup_type not in DEEP_EXTENSION_SELL_GUARD_SETUPS:
        return {"block": False, "reason": "Setup esente"}

    deep_ctx = deep_ctx or get_deep_extension_context(symbol, data)
    day_position = to_float(data.get("day_position"), -1)
    low_zone = bool(day_position >= 0 and day_position <= DEEP_EXTENSION_SELL_GUARD_MAX_DAY_POSITION)
    deep_active = bool(deep_ctx.get("active") or to_bool(data.get("deep_extension_local", "false")) or to_bool(data.get("regime_deep_extension_local", "false")))
    score_ok = int(score) >= DEEP_EXTENSION_SELL_GUARD_MIN_SCORE

    block = bool((deep_active or low_zone) and not score_ok)

    return {
        "block": block,
        "reason": (
            "Deep Extension Guard: SELL basso/campaign troppo debole dopo grande drop"
            if block else "Deep Extension Guard ok"
        ),
        "deep_active": deep_active,
        "low_zone": low_zone,
        "score": score,
        "required_score": DEEP_EXTENSION_SELL_GUARD_MIN_SCORE,
        "score_ok": score_ok,
        "day_position": day_position,
        "max_day_position": DEEP_EXTENSION_SELL_GUARD_MAX_DAY_POSITION,
        "deep_extension": deep_ctx
    }


def deep_extension_sell_guard_text(ctx):
    ctx = ctx or {}
    return (
        f"Block: {ctx.get('block')}\n"
        f"Reason: {ctx.get('reason')}\n"
        f"Deep active: {ctx.get('deep_active')} | Low zone: {ctx.get('low_zone')}\n"
        f"Score: {ctx.get('score')}/{ctx.get('required_score')} | ok: {ctx.get('score_ok')}\n"
        f"Day position: {round(to_float(ctx.get('day_position')), 3)} / max {DEEP_EXTENSION_SELL_GUARD_MAX_DAY_POSITION}"
    )

def get_regime_arbiter_state(symbol):
    symbol = str(symbol or "XAUUSD").upper()
    if symbol not in REGIME_ARBITER_STATE:
        REGIME_ARBITER_STATE[symbol] = {
            "mode": "NEUTRAL",
            "reason": "Nessun regime dominante",
            "updated": 0,
            "smart_kill_attempts": 0,
            "smart_kill_window_start": 0,
            "last_smart_kill_trade_id": None,
            "big_move_last_alert_time": 0,
            "big_move_last_signature": None
        }
    return REGIME_ARBITER_STATE[symbol]



# =========================
# MASTER REGIME v34
# =========================

def _recent_price_window(symbol, seconds=7200):
    symbol = str(symbol or "XAUUSD").upper()
    history = recent_bear_history(symbol, seconds)
    if not history:
        return {"high": 0.0, "low": 0.0, "drop": 0.0, "rebound_from_low": 0.0, "count": 0}

    highs = [to_float(p.get("high"), to_float(p.get("price"), 0)) for p in history]
    lows = [to_float(p.get("low"), to_float(p.get("price"), 0)) for p in history]
    last_price = to_float(history[-1].get("price"), 0)
    high = max(highs) if highs else 0.0
    low = min(lows) if lows else 0.0
    return {
        "high": high,
        "low": low,
        "drop": round(high - low, 3) if high and low else 0.0,
        "rebound_from_low": round(last_price - low, 3) if last_price and low else 0.0,
        "count": len(history)
    }


def get_master_regime_context(symbol, data=None):
    symbol = str(symbol or "XAUUSD").upper()
    data = data or {}

    price = get_price_from_data(data) or _latest_price_for_symbol(symbol)
    h1_bias = str(data.get("h1_bias", "NEUTRAL")).upper()
    h4_bias = str(data.get("h4_bias", "NEUTRAL")).upper()
    day_bias = str(data.get("day_bias", "NEUTRAL")).upper()
    structure = str(data.get("structure", "NEUTRAL")).upper()
    candle_dir = str(data.get("candle_dir", "NEUTRAL")).upper()
    ema20_slope = str(data.get("ema20_slope", "FLAT")).upper()
    ema50_slope = str(data.get("ema50_slope", "FLAT")).upper()
    rsi = to_float(data.get("rsi"), 50)
    above_ema200 = to_bool(data.get("close_above_ema200", "false"))
    day_position = to_float(data.get("day_position"), 0.5)
    micro_bos = bool(micro_bos_bear_context(symbol, data).get("micro_bos"))

    active_news_bias, _ = get_auto_news_bias()
    bear_state = get_bear_continuation_state(symbol)
    bear_state_name = str(bear_state.get("state", "IDLE")).upper()
    pre_bear = get_pre_bear_state(symbol)
    pre_bear_status = str(pre_bear.get("status", "IDLE")).upper()
    maturity = bear_trigger_maturity_context(symbol, data)
    recent_window = _recent_price_window(symbol, MASTER_REGIME_BUY_LOCK_LOOKBACK_SECONDS)

    buy_direct_losses = get_recent_direct_losses_custom(
        "BUY", symbol, MASTER_REGIME_BUY_LOCK_LOOKBACK_SECONDS
    )
    sell_direct_losses = get_recent_direct_losses_custom(
        "SELL", symbol, MASTER_REGIME_BUY_LOCK_LOOKBACK_SECONDS
    )
    recent_deep_sells = get_recent_tp_trades(
        "SELL", symbol,
        min_tp=MASTER_REGIME_REBOUND_BUY_MIN_SELL_TP,
        lookback_seconds=MASTER_REGIME_REBOUND_BUY_LOOKBACK_SECONDS
    )
    recent_deep_buys = get_recent_tp_trades(
        "BUY", symbol,
        min_tp=5,
        lookback_seconds=MASTER_REGIME_REBOUND_BUY_LOOKBACK_SECONDS
    )

    bearish_votes = []
    bullish_votes = []

    if h1_bias == "SELL": bearish_votes.append("H1 SELL")
    if h4_bias == "SELL": bearish_votes.append("H4 SELL")
    if day_bias == "SELL": bearish_votes.append("Daily SELL")
    if structure in ["BEARISH", "LH", "LL"]: bearish_votes.append(f"Struttura {structure}")
    if candle_dir == "BEAR": bearish_votes.append("Candela bearish")
    if ema20_slope == "DOWN": bearish_votes.append("EMA20 DOWN")
    if ema50_slope == "DOWN": bearish_votes.append("EMA50 DOWN")
    if not above_ema200: bearish_votes.append("Prezzo sotto EMA200")
    if rsi < 50: bearish_votes.append("RSI sotto 50")
    if micro_bos: bearish_votes.append("Micro BOS bearish")
    if bear_state_name in ["BEAR_IMPULSE", "RELIEF_RALLY", "LOWER_HIGH_ARMED", "SELL_TRIGGERED"]:
        bearish_votes.append(f"Bear state {bear_state_name}")
    if pre_bear_status in ["FAILED_RECOVERY_ARMED", "CONFIRMED", "HANDED_TO_BEAR"]:
        bearish_votes.append(f"Pre-Bear {pre_bear_status}")
    if len(buy_direct_losses) >= MASTER_REGIME_BUY_LOCK_DIRECT_SL:
        bearish_votes.append(f"BUY failure lock {len(buy_direct_losses)} SL")

    if h1_bias == "BUY": bullish_votes.append("H1 BUY")
    if h4_bias == "BUY": bullish_votes.append("H4 BUY")
    if day_bias == "BUY": bullish_votes.append("Daily BUY")
    if structure in ["BULLISH", "HL"]: bullish_votes.append(f"Struttura {structure}")
    if candle_dir == "BULL": bullish_votes.append("Candela bullish")
    if ema20_slope == "UP": bullish_votes.append("EMA20 UP")
    if ema50_slope == "UP": bullish_votes.append("EMA50 UP")
    if above_ema200: bullish_votes.append("Prezzo sopra EMA200")
    if rsi > 50: bullish_votes.append("RSI sopra 50")
    if active_news_bias == "BULLISH_GOLD": bullish_votes.append("News bullish")

    buy_failure_lock = len(buy_direct_losses) >= MASTER_REGIME_BUY_LOCK_DIRECT_SL
    sell_failure_lock = len(sell_direct_losses) >= MASTER_REGIME_MAX_SELL_DIRECT_SL_BEFORE_CHAOS

    price_action_bearish = len(bearish_votes) >= MASTER_REGIME_SELL_CONTROL_BEAR_VOTES
    price_action_bullish = len(bullish_votes) >= MASTER_REGIME_BUY_CONTROL_BULL_VOTES

    recent_sell_paid = len(recent_deep_sells) > 0
    rebound_buy_area = (
        recent_sell_paid
        and recent_window.get("low", 0) > 0
        and price > 0
        and (price - recent_window.get("low", price)) <= MASTER_REGIME_REBOUND_BUY_MAX_DISTANCE_FROM_LOW
        and day_position <= MASTER_REGIME_REBOUND_BUY_MAX_DAY_POSITION
    )

    mode = "MIXED"
    reason = "Regime non ancora dominante"

    if buy_failure_lock and (price_action_bearish or bear_state_name in ["BEAR_IMPULSE", "LOWER_HIGH_ARMED", "SELL_TRIGGERED"]):
        mode = "SELL_CONTROL"
        reason = f"BUY falliti + price action ribassista ({len(bearish_votes)} voti)"
    elif bear_state_name in ["BEAR_IMPULSE", "LOWER_HIGH_ARMED", "SELL_TRIGGERED"] and len(bearish_votes) >= 4:
        mode = "SELL_CONTROL"
        reason = f"Bear state attivo: {bear_state_name}"
    elif pre_bear_status in ["CONFIRMED", "HANDED_TO_BEAR"] and len(bearish_votes) >= 4:
        mode = "SELL_CONTROL"
        reason = f"Pre-Bear passato al ribasso: {pre_bear_status}"
    elif price_action_bearish and not price_action_bullish:
        mode = "SELL_CONTROL"
        reason = f"Price action dominante SELL ({len(bearish_votes)} voti)"
    elif rebound_buy_area and not buy_failure_lock:
        mode = "POST_SELL_REBOUND_BUY"
        reason = f"SELL già pagato TP{MASTER_REGIME_REBOUND_BUY_MIN_SELL_TP}+ e prezzo vicino al low"
    elif price_action_bullish and not price_action_bearish:
        mode = "BUY_CONTROL"
        reason = f"Price action dominante BUY ({len(bullish_votes)} voti)"
    elif buy_failure_lock and sell_failure_lock:
        mode = "CHAOS_CONTROL"
        reason = "SL diretti su entrambe le direzioni: mercato tossico"

    allow_lower_high_sell = (
        mode == "SELL_CONTROL"
        and (maturity.get("mature") or micro_bos or buy_failure_lock or bear_state_name in ["LOWER_HIGH_ARMED", "SELL_TRIGGERED"])
        and len(bearish_votes) >= 4
    )

    allow_rebound_buy = (
        mode == "POST_SELL_REBOUND_BUY"
        or (
            recent_sell_paid
            and rebound_buy_area
            and len(buy_direct_losses) < MASTER_REGIME_BUY_LOCK_DIRECT_SL
            and len(bullish_votes) >= 3
        )
    )

    # v43: la tesi Asia/Londra può correggere SELL_CONTROL troppo meccanico.
    daily_thesis = update_daily_thesis(data) if ASIAN_THESIS_ENABLED else {"preferred": "WAIT", "status": "DISABLED"}
    preferred_thesis = str(daily_thesis.get("preferred", "WAIT")).upper()
    thesis_status = str(daily_thesis.get("status", "")).upper()
    if ASIAN_THESIS_MASTER_OVERRIDE_ENABLED:
        if mode == "SELL_CONTROL" and preferred_thesis == "BUY" and thesis_status in ["REVERSAL_BUY_WATCH", "RANGE_REBOUND_BUY", "ASIA_RANGE_BREAKOUT_BUY"]:
            mode = "POST_ASIA_REVERSAL_BUY"
            reason = "Daily Thesis v43: Asia ha scaricato ma Londra/Europa recupera; non resto SELL_CONTROL cieco"
            bullish_votes.append("Daily Thesis BUY/reversal")
        elif mode == "BUY_CONTROL" and preferred_thesis == "SELL" and thesis_status in ["FADE_SELL_WATCH", "RANGE_FADE_SELL", "ASIA_RANGE_BREAKOUT_SELL"]:
            mode = "POST_ASIA_FADE_SELL"
            reason = "Daily Thesis v43: Asia ha comprato ma zona alta/fade SELL confermata"
            bearish_votes.append("Daily Thesis SELL/fade")

    return {
        "enabled": MASTER_REGIME_ENABLED,
        "mode": mode,
        "reason": reason,
        "price": price,
        "news_bias": active_news_bias,
        "bearish_votes": bearish_votes,
        "bullish_votes": bullish_votes,
        "bearish_vote_count": len(bearish_votes),
        "bullish_vote_count": len(bullish_votes),
        "bear_state": bear_state_name,
        "pre_bear_status": pre_bear_status,
        "maturity": maturity,
        "micro_bos": micro_bos,
        "buy_failure_lock": buy_failure_lock,
        "buy_direct_losses": len(buy_direct_losses),
        "sell_direct_losses": len(sell_direct_losses),
        "recent_deep_sells": len(recent_deep_sells),
        "recent_deep_buys": len(recent_deep_buys),
        "day_position": day_position,
        "recent_window": recent_window,
        "rebound_buy_area": rebound_buy_area,
        "allow_rebound_buy": allow_rebound_buy,
        "allow_lower_high_sell": allow_lower_high_sell,
        "price_action_bearish": price_action_bearish,
        "price_action_bullish": price_action_bullish,
        "daily_thesis": daily_thesis,
    }


def master_regime_status_text(ctx):
    if not ctx:
        return "Master Regime: N/D"
    bearish = ctx.get("bearish_votes", [])[:8]
    bullish = ctx.get("bullish_votes", [])[:8]
    rw = ctx.get("recent_window", {}) or {}
    return (
        f"Mode: {ctx.get('mode')}\n"
        f"Reason: {ctx.get('reason')}\n"
        f"News bias: {ctx.get('news_bias')}\n"
        f"Bear state: {ctx.get('bear_state')} | Pre-Bear: {ctx.get('pre_bear_status')}\n"
        f"Bearish votes: {ctx.get('bearish_vote_count')} -> " + (", ".join(bearish) if bearish else "N/D") + "\n"
        f"Bullish votes: {ctx.get('bullish_vote_count')} -> " + (", ".join(bullish) if bullish else "N/D") + "\n"
        f"BUY direct SL: {ctx.get('buy_direct_losses')} | BUY lock: {ctx.get('buy_failure_lock')}\n"
        f"SELL TP{MASTER_REGIME_REBOUND_BUY_MIN_SELL_TP}+ recenti: {ctx.get('recent_deep_sells')} | Rebound BUY area: {ctx.get('rebound_buy_area')}\n"
        f"Day position: {round(to_float(ctx.get('day_position'), 0), 3)} | Window drop: {rw.get('drop')} | Rebound low: {rw.get('rebound_from_low')}\n"
        f"Allow lower-high SELL: {ctx.get('allow_lower_high_sell')} | Allow rebound BUY: {ctx.get('allow_rebound_buy')}\n"
        f"Daily Thesis: {ctx.get('daily_thesis', {}).get('status')} -> {ctx.get('daily_thesis', {}).get('preferred')}"
    )


def should_block_by_master_regime(signal, symbol, setup_type, score, data):
    ctx = get_master_regime_context(symbol, data)
    if not MASTER_REGIME_ENABLED:
        return False, ctx, "Master Regime disattivato"

    signal = normalize_signal(signal)
    setup_type = str(setup_type or "NORMAL").upper()
    mode = str(ctx.get("mode", "MIXED")).upper()

    if mode == "SELL_CONTROL" and signal == "BUY" and MASTER_REGIME_BLOCK_BUY_IN_SELL_CONTROL:
        pullback_rearm_ctx = max_pullback_rearm_buy_context(signal, symbol, data)
        ctx["pullback_rearm"] = pullback_rearm_ctx
        thesis_ctx = ctx.get("daily_thesis", {}) or {}
        thesis_buy_allowed = bool(
            ASIAN_THESIS_MASTER_OVERRIDE_ENABLED
            and str(thesis_ctx.get("preferred", "")).upper() == "BUY"
            and str(thesis_ctx.get("status", "")).upper() in ["REVERSAL_BUY_WATCH", "RANGE_REBOUND_BUY", "ASIA_RANGE_BREAKOUT_BUY"]
            and setup_type in ASIAN_THESIS_BUY_SETUPS
            and int(score) >= ASIAN_THESIS_REVERSAL_BUY_MIN_SCORE
        )
        buy_allowed = (
            thesis_buy_allowed
            or (
                setup_type in MASTER_REGIME_REBOUND_BUY_SETUPS
                and (
                    ctx.get("allow_rebound_buy")
                    or (
                        setup_type == "MAX_PULLBACK_REARM_BUY"
                        and pullback_rearm_ctx.get("allow")
                        and MAX_PULLBACK_REARM_ALLOW_IN_SELL_CONTROL
                    )
                )
                and int(score) >= min(MASTER_REGIME_REBOUND_BUY_MIN_SCORE, MAX_PULLBACK_REARM_SCORE_FLOOR)
            )
        )
        if not buy_allowed:
            return (
                True,
                ctx,
                "Master Regime SELL_CONTROL: BUY bloccato. Non compro rimbalzi/minimi dentro giornata sell."
            )

    if mode == "POST_ASIA_REVERSAL_BUY" and signal == "SELL":
        if setup_type == "NORMAL" or int(score) < ASIAN_THESIS_COUNTER_FAST_MIN_SCORE:
            return (
                True,
                ctx,
                "Daily Thesis v43: Asia ha già scaricato e Londra recupera; SELL bloccato finché non arriva retest alto/A+."
            )

    if mode == "POST_ASIA_FADE_SELL" and signal == "BUY":
        if setup_type == "NORMAL" or int(score) < ASIAN_THESIS_COUNTER_FAST_MIN_SCORE:
            return (
                True,
                ctx,
                "Daily Thesis v43: Asia ha già comprato e siamo in fade alto; BUY bloccato finché non arriva pullback vero/A+."
            )

    if mode == "BUY_CONTROL" and signal == "SELL" and MASTER_REGIME_BLOCK_COUNTER_SELL_IN_BUY_CONTROL:
        if setup_type == "NORMAL" and int(score) < MASTER_REGIME_BUY_CONTROL_COUNTER_SELL_MIN_SCORE:
            return (
                True,
                ctx,
                "Master Regime BUY_CONTROL: SELL NORMAL debole bloccato contro direzione dominante."
            )

    if mode == "CHAOS_CONTROL":
        return (
            True,
            ctx,
            "Master Regime CHAOS_CONTROL: troppi SL diretti, fermo nuovi ingressi non A+."
        )

    return False, ctx, "Master Regime coerente"



# =========================
# v39 POST SUPER BUY GUARD
# =========================

def get_post_super_buy_guard_context(signal, symbol, setup_type, score, data=None):
    """
    Protegge il caso visto nei log v38:
    il bot prende un SUPER BUY / TP8 e poi non deve aprire una BEAR_CAMPAIGN prematura.
    Il SELL contro quel runner passa solo come EXTREME_SPIKE_FADE_SELL e solo con failed retest alto.
    """
    data = data or {}
    signal = str(signal or "").upper()
    setup_type = str(setup_type or "NORMAL").upper()
    symbol = str(symbol or "XAUUSD").upper()
    score = int(score or 0)

    ctx = {
        "enabled": POST_SUPER_BUY_GUARD_ENABLED,
        "active": False,
        "block": False,
        "allow": False,
        "reason": "Post Super BUY Guard non attivo",
        "setup_type": setup_type,
        "score": score,
        "required_score": POST_SUPER_BUY_GUARD_MIN_SCORE,
        "recent_tp8_buys": 0,
        "best_trade": None,
        "age_seconds": None,
        "event_spike": {},
        "micro_bos": {},
        "bearish_trigger_ok": False,
        "failed_retest_ok": False,
        "micro_ok": False,
    }

    if not POST_SUPER_BUY_GUARD_ENABLED:
        ctx["reason"] = "POST_SUPER_BUY_GUARD_ENABLED = FALSE"
        return ctx

    if signal != "SELL":
        ctx["reason"] = "Non è SELL"
        return ctx

    recent_big_buys = get_recent_tp_trades(
        "BUY",
        symbol,
        min_tp=POST_SUPER_BUY_GUARD_MIN_TP,
        lookback_seconds=POST_SUPER_BUY_GUARD_SECONDS,
    )
    ctx["recent_tp8_buys"] = len(recent_big_buys)

    if not recent_big_buys:
        ctx["reason"] = f"Nessun BUY TP{POST_SUPER_BUY_GUARD_MIN_TP}+ recente da proteggere"
        return ctx

    best = recent_big_buys[0]
    event_time = (
        best.get(f"tp{POST_SUPER_BUY_GUARD_MIN_TP}_time")
        or best.get("last_tp_time")
        or best.get("created")
        or 0
    )
    age = now_ts() - event_time if event_time else None
    ctx["best_trade"] = best
    ctx["age_seconds"] = age
    ctx["active"] = True

    event_ctx = get_event_spike_context(data)
    micro_ctx = micro_bos_bear_context(symbol, data)
    ctx["event_spike"] = event_ctx
    ctx["micro_bos"] = micro_ctx

    candle_dir = str(data.get("candle_dir", "NEUTRAL")).upper()
    rejection = str(data.get("rejection", "NONE")).upper()
    upper_wick = to_bool(data.get("upper_wick_strong"))
    ema20_down = str(data.get("ema20_slope", "FLAT")).upper() == "DOWN"
    ema50_down = str(data.get("ema50_slope", "FLAT")).upper() == "DOWN"
    near_m15_high = to_bool(data.get("near_m15_high"))

    failed_retest_ok = bool(
        event_ctx.get("failed_retest_zone")
        or not POST_SUPER_BUY_GUARD_REQUIRE_FAILED_RETEST
    )
    bearish_trigger_ok = bool(
        candle_dir == "BEAR"
        or rejection == "UPPER_WICK"
        or upper_wick
        or near_m15_high
        or (ema20_down and ema50_down)
        or not POST_SUPER_BUY_GUARD_REQUIRE_BEARISH_CANDLE_OR_REJECTION
    )
    micro_ok = bool(
        micro_ctx.get("confirmed")
        or not POST_SUPER_BUY_GUARD_REQUIRE_MICRO_BOS
    )
    score_ok = score >= POST_SUPER_BUY_GUARD_MIN_SCORE
    setup_allow = setup_type in POST_SUPER_BUY_GUARD_ALLOW_SETUPS

    ctx.update({
        "failed_retest_ok": failed_retest_ok,
        "bearish_trigger_ok": bearish_trigger_ok,
        "micro_ok": micro_ok,
        "score_ok": score_ok,
        "setup_allow": setup_allow,
        "best_trade_id": best.get("id"),
        "best_trade_setup": best.get("setup_type"),
        "best_trade_highest_tp": best.get("highest_tp"),
    })

    if setup_allow and score_ok and failed_retest_ok and bearish_trigger_ok and micro_ok:
        ctx["allow"] = True
        ctx["block"] = False
        ctx["reason"] = "EXTREME_SPIKE_FADE_SELL ammesso: BUY TP8 già pagato + failed retest alto confermato"
        return ctx

    if setup_type in POST_SUPER_BUY_GUARD_BLOCK_SETUPS:
        ctx["block"] = True
        if setup_allow:
            missing = []
            if not score_ok:
                missing.append(f"score {score}/{POST_SUPER_BUY_GUARD_MIN_SCORE}")
            if not failed_retest_ok:
                missing.append("failed retest alto")
            if not bearish_trigger_ok:
                missing.append("candela/rejection bearish")
            if not micro_ok:
                missing.append("micro BOS")
            ctx["reason"] = "Extreme fade non pronto: " + ", ".join(missing)
        else:
            ctx["reason"] = (
                f"SUPER BUY TP{POST_SUPER_BUY_GUARD_MIN_TP}+ ancora fresco: "
                f"blocco {setup_type}. Consentito solo EXTREME_SPIKE_FADE_SELL maturo."
            )
        return ctx

    ctx["reason"] = "Setup SELL non gestito dal Post Super BUY Guard"
    return ctx


def post_super_buy_guard_text(ctx):
    ctx = ctx or {}
    best = ctx.get("best_trade") or {}
    ev = ctx.get("event_spike") or {}
    micro = ctx.get("micro_bos") or {}
    age = ctx.get("age_seconds")
    age_txt = "N/D" if age is None else f"{round(to_float(age), 1)}s"
    return (
        f"Active: {ctx.get('active')} | Block: {ctx.get('block')} | Allow: {ctx.get('allow')}\n"
        f"Reason: {ctx.get('reason')}\n"
        f"BUY protetto: {best.get('id', 'N/D')} | Setup: {best.get('setup_type', 'N/D')} | Highest TP: {best.get('highest_tp', 0)}\n"
        f"Età dal TP8/evento: {age_txt} / {POST_SUPER_BUY_GUARD_SECONDS}s\n"
        f"Setup SELL: {ctx.get('setup_type')} | Score: {ctx.get('score')}/{ctx.get('required_score')} | Score ok: {ctx.get('score_ok')}\n"
        f"Failed retest ok: {ctx.get('failed_retest_ok')} | Bearish trigger ok: {ctx.get('bearish_trigger_ok')} | Micro ok: {ctx.get('micro_ok')}\n"
        f"Spike: top {round(to_float(ev.get('top_position')), 2)} | retrace {round(to_float(ev.get('retrace_from_high')), 2)} | failed retest {ev.get('failed_retest_zone')}\n"
        f"Micro BOS: {micro.get('confirmed')} | source: {micro.get('source')}"
    )

def get_regime_arbiter_context(symbol, data=None):
    symbol = str(symbol or "XAUUSD").upper()
    data = data or {}
    state = get_regime_arbiter_state(symbol)

    recovery_ctx = get_recovery_dominance_context(symbol, data)
    maturity_ctx = bear_trigger_maturity_context(symbol, data)
    deep_ctx = get_deep_extension_context(symbol, data)
    sell_profit_lock_ctx = get_sell_profit_lock_context(symbol, data)
    loss_recovery_ctx = true_max_zone_reentry_context("SELL", symbol, "CONTEXT", 0, data)
    big_move_ctx = get_big_move_thesis_context(symbol, data)
    event_trap_ctx = event_trap_flip_context("CONTEXT", symbol, "CONTEXT", 0, data, special_ctx=recovery_ctx, big_move_ctx=big_move_ctx)
    deep_sell_guard_ctx = deep_extension_sell_guard_context("CONTEXT", symbol, "CONTEXT", 0, data, deep_ctx=deep_ctx)
    pre_bear = get_pre_bear_state(symbol)
    pre_bear_status = str(pre_bear.get("status", "IDLE")).upper()
    bear_state = get_bear_continuation_state(symbol)
    bear_state_name = str(bear_state.get("state", "IDLE")).upper()

    if event_trap_ctx.get("allow"):
        mode, reason = "EVENT_TRAP_FLIP", event_trap_ctx.get("reason")
    elif recovery_ctx.get("active"):
        mode, reason = "RECOVERY_DOMINANT", recovery_ctx.get("reason")
    elif loss_recovery_ctx.get("active"):
        mode, reason = "LOSS_RECOVERY_MAX_ZONE", loss_recovery_ctx.get("reason")
    elif sell_profit_lock_ctx.get("active"):
        mode, reason = "SELL_PROFIT_LOCK", sell_profit_lock_ctx.get("reason")
    elif big_move_ctx.get("active"):
        mode, reason = f"BIG_MOVE_{big_move_ctx.get('status')}", big_move_ctx.get("reason")
    elif deep_ctx.get("active"):
        mode, reason = "DEEP_EXTENSION", "SELL già molto pagato / prezzo vicino low"
    elif maturity_ctx.get("mature"):
        mode, reason = "BEAR_MATURE", "Continuation bearish matura"
    elif pre_bear_status in ["FAILED_RECOVERY_ARMED", "CONFIRMED"]:
        mode, reason = "PRE_BEAR", f"Pre-Bear Thesis {pre_bear_status}"
    elif bear_state_name in ["BEAR_IMPULSE", "RELIEF_RALLY", "LOWER_HIGH_ARMED", "SELL_TRIGGERED"]:
        mode, reason = "BEAR_BUILDING", "Bear state attivo ma trigger non ancora maturo"
    else:
        mode, reason = "NEUTRAL", "Nessun regime dominante"

    state["mode"] = mode
    state["reason"] = reason
    state["updated"] = now_ts()

    return {
        "mode": mode,
        "reason": reason,
        "recovery": recovery_ctx,
        "maturity": maturity_ctx,
        "deep_extension": deep_ctx,
        "sell_profit_lock": sell_profit_lock_ctx,
        "loss_recovery": loss_recovery_ctx,
        "big_move": big_move_ctx,
        "event_trap_flip": event_trap_ctx,
        "deep_extension_sell_guard": deep_sell_guard_ctx,
        "master_regime": get_master_regime_context(symbol, data),
        "pre_bear_status": pre_bear_status,
        "bear_state": bear_state_name
    }


def regime_arbiter_status_text(ctx):
    return (
        f"Mode: {ctx.get('mode')}\n"
        f"Reason: {ctx.get('reason')}\n"
        f"Bear state: {ctx.get('bear_state')}\n"
        f"Pre-Bear: {ctx.get('pre_bear_status')}\n"
        f"Recovery dominant: {ctx.get('recovery', {}).get('active')}\n"
        f"Sell profit lock: {ctx.get('sell_profit_lock', {}).get('active')}\n"
        f"Loss recovery max zone: {ctx.get('loss_recovery', {}).get('active')}\n"
        f"Big move thesis: {ctx.get('big_move', {}).get('status')}\n"
        f"Bear maturity: {ctx.get('maturity', {}).get('mature')}\n"
        f"Deep extension: {ctx.get('deep_extension', {}).get('active')}"
    )


def should_block_by_regime_arbiter(signal, symbol, setup_type, score, data):
    ctx = get_regime_arbiter_context(symbol, data)

    if not REGIME_ARBITER_ENABLED:
        return False, ctx, "Regime Arbiter disattivato"

    signal = str(signal or "").upper()
    setup_type = str(setup_type or "NORMAL").upper()
    master_ctx = ctx.get("master_regime") or get_master_regime_context(symbol, data)
    ctx["master_regime"] = master_ctx
    master_allows_lower_high_sell = (
        MASTER_REGIME_ENABLED
        and signal == "SELL"
        and master_ctx.get("mode") == "SELL_CONTROL"
        and master_ctx.get("allow_lower_high_sell")
        and (
            (setup_type == "NORMAL" and int(score) >= MASTER_REGIME_SELL_CONTROL_NORMAL_MIN_SCORE)
            or (setup_type in MASTER_REGIME_SELL_SPECIAL_SETUPS and int(score) >= MASTER_REGIME_SELL_CONTROL_SPECIAL_MIN_SCORE)
        )
    )

    if signal != "SELL":
        return False, ctx, "Il Regime Arbiter v29 governa qui i conflitti SELL"

    # v26: protezione precoce di qualunque BUY speciale aperto.
    # Serve a evitare: BUY speciale corretto + SELL NORMAL debole subito dopo.
    special_buy_ctx = get_recovery_dominance_context(
        symbol,
        data,
        min_tp=SPECIAL_BUY_NORMAL_SELL_MIN_TP
    )
    ctx["special_buy_protection"] = special_buy_ctx

    event_trap_ctx = event_trap_flip_context(
        signal,
        symbol,
        setup_type,
        score,
        data,
        special_ctx=special_buy_ctx,
        big_move_ctx=ctx.get("big_move")
    )
    ctx["event_trap_flip"] = event_trap_ctx

    flip_window_ctx = special_buy_flip_window_context(
        symbol,
        setup_type,
        score,
        data,
        special_ctx=special_buy_ctx,
        event_trap_ctx=event_trap_ctx
    )
    ctx["special_buy_flip_window"] = flip_window_ctx

    pullback_rearm_ctx = max_pullback_rearm_buy_context("BUY", symbol, data)
    ctx["pullback_rearm"] = pullback_rearm_ctx

    anti_fade_ctx = anti_fade_super_buy_context(
        signal,
        symbol,
        setup_type,
        score,
        data,
        big_move_ctx=ctx.get("big_move"),
        event_trap_ctx=event_trap_ctx,
        flip_window_ctx=flip_window_ctx
    )
    ctx["anti_fade_super_buy"] = anti_fade_ctx

    # v39: priorità assoluta dopo SUPER BUY/TP8.
    # Evita l'errore v38: BEAR_CAMPAIGN_SELL entrato troppo presto contro runner BUY.
    post_super_buy_ctx = get_post_super_buy_guard_context(
        signal,
        symbol,
        setup_type,
        score,
        data
    )
    ctx["post_super_buy_guard"] = post_super_buy_ctx
    if post_super_buy_ctx.get("block"):
        return (
            True,
            ctx,
            post_super_buy_ctx.get("reason")
        )

    if anti_fade_ctx.get("block"):
        return (
            True,
            ctx,
            "Anti-Fade Super BUY: SELL/MAX_FADE bloccato, campagna BUY TP5+ ancora viva e non invalidata"
        )

    if special_buy_ctx.get("active"):
        if setup_type == "NORMAL" and SPECIAL_BUY_BLOCK_NORMAL_SELL:
            return (
                True,
                ctx,
                "Special BUY Protection: SELL NORMAL bloccato contro BUY speciale attivo"
            )

        if event_trap_ctx.get("allow"):
            ctx["counter_sell_override"] = {
                "allow": True,
                "reason": "Bypass Special BUY Dominance via Event Trap Flip"
            }
        elif flip_window_ctx.get("allow"):
            ctx["counter_sell_override"] = {
                "allow": True,
                "reason": "Bypass Special BUY Dominance via Max Flip Window",
                "special_buy": special_buy_ctx,
                "setup_type": setup_type,
                "score": score,
                "required_score": SPECIAL_BUY_FLIP_MIN_SCORE,
                "setup_ok": True,
                "score_ok": True,
                "zone_ok": flip_window_ctx.get("zone_ok"),
                "micro_ok": flip_window_ctx.get("micro_ok"),
                "micro_bos": flip_window_ctx.get("micro_bos"),
                "extreme_info": flip_window_ctx.get("extreme_info")
            }
        else:
            counter_ctx = special_buy_counter_sell_override_context(
                symbol,
                setup_type,
                score,
                data,
                special_ctx=special_buy_ctx
            )
            ctx["counter_sell_override"] = counter_ctx

            if not counter_ctx.get("allow"):
                return (
                    True,
                    ctx,
                    "Special BUY Dominance: SELL contro BUY speciale non abbastanza forte / non in zona Max"
                )

    # v26: SELL NORMAL solo da zona alta/rejection stile Max.
    max_zone_ctx = max_zone_sell_gate_context(
        signal,
        symbol,
        setup_type,
        score,
        data
    )
    ctx["max_zone_gate"] = max_zone_ctx

    if max_zone_ctx.get("block") and not master_allows_lower_high_sell:
        return (
            True,
            ctx,
            "Max Zone Gate: SELL NORMAL bloccato perché non nasce da zona alta valida"
        )

    if max_zone_ctx.get("block") and master_allows_lower_high_sell:
        ctx["max_zone_gate"]["master_override"] = True
        ctx["max_zone_gate"]["reason"] = "Master Regime: SELL_CONTROL autorizza lower-high SELL anche fuori zona alta classica"

    # v27: Trade Compression / Sell Profit Lock.
    profit_lock_ctx = ctx.get("sell_profit_lock") or get_sell_profit_lock_context(symbol, data)
    ctx["sell_profit_lock"] = profit_lock_ctx

    if profit_lock_ctx.get("active"):
        profit_lock_allow_ctx = sell_profit_lock_allow_context(
            symbol,
            setup_type,
            score,
            data,
            lock_ctx=profit_lock_ctx
        )
        ctx["sell_profit_lock_allow"] = profit_lock_allow_ctx

        if not profit_lock_allow_ctx.get("allow"):
            return (
                True,
                ctx,
                "Sell Profit Lock: la view SELL ha già pagato, attendo nuovo rimbalzo/zona Max"
            )

    # v28: dopo SL SELL diretti serve True Max Zone, non primo rimbalzo.
    loss_recovery_ctx = true_max_zone_reentry_context(signal, symbol, setup_type, score, data)
    ctx["loss_recovery"] = loss_recovery_ctx

    if loss_recovery_ctx.get("active") and loss_recovery_ctx.get("block"):
        return (
            True,
            ctx,
            "Loss Recovery / True Max Zone: dopo SL diretti attendo rimbalzo alto vero"
        )

    deep_guard_ctx = deep_extension_sell_guard_context(signal, symbol, setup_type, score, data, deep_ctx=ctx.get("deep_extension"))
    ctx["deep_extension_sell_guard"] = deep_guard_ctx

    if deep_guard_ctx.get("block") and not event_trap_ctx.get("allow") and not master_allows_lower_high_sell:
        return (
            True,
            ctx,
            deep_guard_ctx.get("reason")
        )

    if deep_guard_ctx.get("block") and master_allows_lower_high_sell:
        ctx["deep_extension_sell_guard"]["master_override"] = True
        ctx["deep_extension_sell_guard"]["reason"] = "Master Regime: SELL_CONTROL supera Deep Extension Guard perché lower-high/microBOS è maturo"

    if setup_type in REGIME_MATURITY_REQUIRED_SETUPS:
        recovery_ctx = ctx.get("recovery", {})

        if (
            recovery_ctx.get("active")
            and setup_type in RECOVERY_DOMINANCE_BLOCK_SELL_SETUPS
            and not event_trap_ctx.get("allow")
        ):
            return (
                True,
                ctx,
                "Special BUY Dominance: continuation SELL non può combattere "
                "un BUY speciale TP3+ ancora valido"
            )

        deep_ctx = ctx.get("deep_extension", {})

        if (
            deep_ctx.get("active")
            and to_float(deep_ctx.get("rebound_from_low"), 0)
            < DEEP_EXTENSION_REARM_REBOUND_POINTS
            and not event_trap_ctx.get("allow")
        ):
            return (
                True,
                ctx,
                "Deep Extension: continuation SELL non riarmato; "
                "rimbalzo dal low insufficiente"
            )

        maturity_ctx = ctx.get("maturity", {})

        if not maturity_ctx.get("mature") and not event_trap_ctx.get("allow") and not master_allows_lower_high_sell:
            return (
                True,
                ctx,
                "Trigger Maturity obbligatoria: "
                "SELL continuation/campaign ancora immaturo"
            )

    return False, ctx, "Regime coerente con il setup"


def smart_kill_pre_bear_decision(signal, symbol, setup_type, score, data, extreme_info=None):
    result = {"allow": False, "reason": "", "risk_weight": 0.0, "attempt_number": 0}

    if not SMART_KILL_PRE_BEAR_OVERRIDE_ENABLED:
        result["reason"] = "Smart Kill override disattivato"
        return result
    if str(signal).upper() != "SELL":
        result["reason"] = "Non è SELL"
        return result
    if str(setup_type).upper() != "PRE_BEAR_SELL":
        result["reason"] = "Setup non PRE_BEAR_SELL"
        return result
    if int(score) < SMART_KILL_PRE_BEAR_MIN_SCORE:
        result["reason"] = f"Score {score} sotto {SMART_KILL_PRE_BEAR_MIN_SCORE}"
        return result
    if not is_state_warm(symbol):
        result["reason"] = "Warmup non completato"
        return result

    recovery_ctx = get_recovery_dominance_context(symbol, data)
    if recovery_ctx.get("active"):
        result["reason"] = "Recovery Dominance attiva"
        return result

    if extreme_info is None:
        _, extreme_info = extreme_zone_info("SELL", data)
    if not extreme_info.get("ok"):
        result["reason"] = "Zona estrema SELL non confermata"
        return result

    state = get_regime_arbiter_state(symbol)
    now = now_ts()
    window_start = to_float(state.get("smart_kill_window_start"), 0)
    if not window_start or now - window_start > SMART_KILL_PRE_BEAR_COOLDOWN_SECONDS:
        state["smart_kill_window_start"] = now
        state["smart_kill_attempts"] = 0

    attempts = int(state.get("smart_kill_attempts", 0))
    if attempts >= SMART_KILL_PRE_BEAR_MAX_ATTEMPTS:
        result["reason"] = "Numero massimo tentativi Smart Kill già usato"
        return result

    result.update({
        "allow": True,
        "reason": "PRE_BEAR_SELL forte da zona estrema",
        "risk_weight": SMART_KILL_PRE_BEAR_RISK_WEIGHT,
        "attempt_number": attempts + 1
    })
    return result


def register_smart_kill_pre_bear_override(trade, decision):
    if not decision or not decision.get("allow"):
        return trade

    symbol = str(trade.get("symbol", "XAUUSD")).upper()
    state = get_regime_arbiter_state(symbol)
    state["smart_kill_attempts"] = int(state.get("smart_kill_attempts", 0)) + 1
    state["last_smart_kill_trade_id"] = trade.get("id")
    state["updated"] = now_ts()

    trade["smart_kill_override"] = True
    trade["smart_kill_risk_weight"] = decision.get("risk_weight")
    trade["smart_kill_attempt_number"] = decision.get("attempt_number")

    save_trades()
    save_runtime_state(force=True)
    return trade


# =========================
# PRE-BEAR THESIS + DEEP EXTENSION FLIP v23
# =========================

def _new_pre_bear_state():
    return {
        "status": "IDLE",
        "symbol": "",
        "started": 0,
        "updated": 0,
        "updated_local": "",
        "prior_high": 0,
        "prior_high_time": 0,
        "swing_low": 0,
        "swing_low_time": 0,
        "recovery_peak": 0,
        "recovery_peak_time": 0,
        "prior_drop": 0,
        "recovery_points": 0,
        "retrace": 0,
        "lower_high_gap": 0,
        "macro_votes": 0,
        "invalidation_price": 0,
        "reason": "Nessuna pre-bear thesis attiva"
    }


def get_pre_bear_state(symbol):
    symbol = str(symbol or "XAUUSD").upper()

    if symbol not in PRE_BEAR_STATE:
        PRE_BEAR_STATE[symbol] = _new_pre_bear_state()
        PRE_BEAR_STATE[symbol]["symbol"] = symbol

    return PRE_BEAR_STATE[symbol]


def reset_pre_bear_state(symbol, reason="Reset"):
    symbol = str(symbol or "XAUUSD").upper()
    PRE_BEAR_STATE[symbol] = _new_pre_bear_state()
    PRE_BEAR_STATE[symbol]["symbol"] = symbol
    PRE_BEAR_STATE[symbol]["reason"] = reason
    PRE_BEAR_STATE[symbol]["updated"] = now_ts()
    PRE_BEAR_STATE[symbol]["updated_local"] = local_datetime().strftime("%Y-%m-%d %H:%M:%S")
    return PRE_BEAR_STATE[symbol]


def pre_bear_status_text(symbol):
    state = get_pre_bear_state(symbol)

    return (
        f"Status: {state.get('status')}\n"
        f"Reason: {state.get('reason')}\n"
        f"Prior high: {round(to_float(state.get('prior_high')), 3)}\n"
        f"Swing low: {round(to_float(state.get('swing_low')), 3)}\n"
        f"Recovery peak: {round(to_float(state.get('recovery_peak')), 3)}\n"
        f"Prior drop: {round(to_float(state.get('prior_drop')), 2)}\n"
        f"Recovery: {round(to_float(state.get('recovery_points')), 2)}\n"
        f"Retrace: {round(to_float(state.get('retrace')), 2)}\n"
        f"Lower-high gap: {round(to_float(state.get('lower_high_gap')), 2)}\n"
        f"Macro votes: {state.get('macro_votes', 0)}"
    )


def pre_bear_macro_votes(data):
    votes = 0

    if str(data.get("h1_bias", "")).upper() == "SELL":
        votes += 1
    if str(data.get("h4_bias", "")).upper() == "SELL":
        votes += 1
    if str(data.get("day_bias", "")).upper() == "SELL":
        votes += 1
    if str(data.get("ema20_slope", "")).upper() == "DOWN":
        votes += 1
    if str(data.get("ema50_slope", "")).upper() == "DOWN":
        votes += 1
    if not to_bool(data.get("close_above_ema200", "true")):
        votes += 1
    if to_bool(data.get("pre_bear_sell_candidate", "false")):
        votes += 1

    return votes


def process_pre_bear_thesis(data):
    result = {
        "active": False,
        "confirmed": False,
        "status": "IDLE",
        "reason": ""
    }

    if not PRE_BEAR_THESIS_ENABLED:
        result["reason"] = "Pre-Bear Thesis disattivata"
        return result

    symbol = str(data.get("symbol", "XAUUSD")).upper()
    state = get_pre_bear_state(symbol)
    price = get_price_from_data(data)
    now = now_ts()

    # Se la bear continuation completa è già attiva, la pre-thesis ha fatto il suo lavoro.
    bear_state_name = str(get_bear_continuation_state(symbol).get("state", "IDLE")).upper()
    if bear_state_name in ["BEAR_IMPULSE", "RELIEF_RALLY", "LOWER_HIGH_ARMED", "SELL_TRIGGERED"]:
        if state.get("status") in ["RECOVERY_RALLY", "FAILED_RECOVERY_ARMED", "CONFIRMED"]:
            state["status"] = "HANDED_TO_BEAR"
            state["reason"] = f"Passaggio alla Bear State Machine: {bear_state_name}"
            state["updated"] = now
            state["updated_local"] = local_datetime(now).strftime("%Y-%m-%d %H:%M:%S")

        result.update({
            "active": False,
            "confirmed": False,
            "status": state.get("status"),
            "reason": state.get("reason")
        })
        return result

    # Timeout / invalidation.
    if state.get("status") in ["RECOVERY_RALLY", "FAILED_RECOVERY_ARMED", "CONFIRMED"]:
        if state.get("started", 0) and now - state.get("started", 0) > PRE_BEAR_TIMEOUT_SECONDS:
            state = reset_pre_bear_state(symbol, "Pre-bear scaduta per timeout")

        invalidation = to_float(state.get("invalidation_price"), 0)
        if invalidation and price and price >= invalidation:
            state = reset_pre_bear_state(symbol, "Pre-bear invalidata sopra prior high + buffer")

    history = recent_bear_history(symbol, PRE_BEAR_LOOKBACK_SECONDS)

    if len(history) < 8:
        result.update({
            "status": state.get("status"),
            "reason": "Storico prezzo insufficiente per pre-bear"
        })
        return result

    # Trovo un minimo recente e il massimo che lo precede: è il downswing di riferimento.
    search_points = history[:-1] if len(history) > 1 else history
    low_point = min(search_points, key=lambda p: p.get("low", 999999))
    low_time = low_point.get("time", 0)
    swing_low = to_float(low_point.get("low"), 0)

    preceding = [p for p in history if p.get("time", 0) < low_time]
    if len(preceding) < 3:
        result.update({
            "status": state.get("status"),
            "reason": "Manca prior high prima del swing low"
        })
        return result

    high_point = max(preceding, key=lambda p: p.get("high", 0))
    prior_high = to_float(high_point.get("high"), 0)
    prior_high_time = high_point.get("time", 0)

    after_low = [p for p in history if p.get("time", 0) >= low_time]
    recovery_point = max(after_low, key=lambda p: p.get("high", 0))
    recovery_peak = to_float(recovery_point.get("high"), price)
    recovery_peak_time = recovery_point.get("time", 0)

    prior_drop = max(0, prior_high - swing_low)
    recovery_points = max(0, recovery_peak - swing_low)
    retrace = recovery_points / prior_drop if prior_drop > 0 else 0
    lower_high_gap = max(0, prior_high - recovery_peak)
    macro_votes = pre_bear_macro_votes(data)

    recovery_zone = (
        prior_drop >= PRE_BEAR_MIN_PRIOR_DROP_POINTS
        and recovery_points >= PRE_BEAR_MIN_RECOVERY_POINTS
        and retrace >= PRE_BEAR_MIN_RETRACE
        and retrace <= PRE_BEAR_MAX_RETRACE
        and lower_high_gap >= PRE_BEAR_LOWER_HIGH_GAP
        and macro_votes >= PRE_BEAR_MACRO_VOTES
    )

    if recovery_zone:
        if state.get("status") not in ["FAILED_RECOVERY_ARMED", "CONFIRMED"]:
            state["status"] = "RECOVERY_RALLY"
            state["started"] = state.get("started") or now

        state["prior_high"] = prior_high
        state["prior_high_time"] = prior_high_time
        state["swing_low"] = swing_low
        state["swing_low_time"] = low_time
        state["recovery_peak"] = recovery_peak
        state["recovery_peak_time"] = recovery_peak_time
        state["prior_drop"] = prior_drop
        state["recovery_points"] = recovery_points
        state["retrace"] = retrace
        state["lower_high_gap"] = lower_high_gap
        state["macro_votes"] = macro_votes
        state["invalidation_price"] = prior_high + PRE_BEAR_INVALIDATION_BUFFER
        state["reason"] = (
            f"Failed recovery in preparazione: drop {round(prior_drop, 2)}, "
            f"retrace {round(retrace, 2)}, gap {round(lower_high_gap, 2)}"
        )
        state["updated"] = now
        state["updated_local"] = local_datetime(now).strftime("%Y-%m-%d %H:%M:%S")

        failure_points = max(0, recovery_peak - price) if price else 0
        bearish_confirmation = _bearish_confirmation_from_data(
            data,
            previous_price=to_float(history[-2].get("price"), 0) if len(history) >= 2 else 0
        )
        pine_candidate = to_bool(data.get("pre_bear_sell_candidate", "false"))

        if failure_points >= PRE_BEAR_FAILURE_POINTS or pine_candidate:
            state["status"] = "FAILED_RECOVERY_ARMED"
            state["reason"] = (
                f"Failed recovery armato: failure {round(failure_points, 2)} punti"
            )

        if (
            state.get("status") == "FAILED_RECOVERY_ARMED"
            and bearish_confirmation
            and (failure_points >= PRE_BEAR_FAILURE_POINTS or pine_candidate)
        ):
            state["status"] = "CONFIRMED"
            state["reason"] = (
                f"Pre-Bear confermata: failed recovery {round(failure_points, 2)} punti"
            )

    active = state.get("status") in ["RECOVERY_RALLY", "FAILED_RECOVERY_ARMED", "CONFIRMED"]
    confirmed = state.get("status") == "CONFIRMED"

    result.update({
        "active": active,
        "confirmed": confirmed,
        "status": state.get("status"),
        "reason": state.get("reason")
    })
    return result


def should_block_buy_by_pre_bear(signal, symbol, setup_type, score, data):
    state = get_pre_bear_state(symbol)

    if not PRE_BEAR_THESIS_ENABLED or not PRE_BEAR_BLOCK_BUYS_ENABLED:
        return False, state, "Pre-bear BUY block disattivato"

    if str(signal).upper() != "BUY":
        return False, state, "Non è BUY"

    if state.get("status") not in ["FAILED_RECOVERY_ARMED", "CONFIRMED"]:
        return False, state, "Pre-bear non abbastanza avanzata"

    # Un vero recovery BUY profondo può ancora passare, ma solo dopo deep extension.
    deep_ctx = get_deep_extension_context(symbol, data)
    if (
        str(setup_type).upper() == "MAX_RECOVERY_BUY"
        and deep_ctx.get("active")
        and int(score) >= PRE_BEAR_ALLOW_RECOVERY_BUY_SCORE
    ):
        return False, state, "Recovery BUY profondo ammesso dopo deep extension"

    if str(setup_type).upper() == "MAX_PULLBACK_REARM_BUY":
        rearm_ctx = max_pullback_rearm_buy_context(signal, symbol, data)
        if rearm_ctx.get("allow"):
            return False, state, "Pre-Bear declassata: Max Pullback Re-Arm BUY confermato"

    rebound_ctx = post_sell_rebound_unlock_context(signal, symbol, setup_type, score, data)
    if rebound_ctx.get("allow"):
        return False, state, rebound_ctx.get("reason")

    return True, state, "BUY bloccato: failed recovery / pre-bear thesis attiva"


def get_deep_extension_context(symbol, data):
    symbol = str(symbol or "XAUUSD").upper()
    price = get_price_from_data(data)
    state = get_bear_continuation_state(symbol)

    recent_tp_sells = get_recent_tp_trades(
        "SELL",
        symbol,
        min_tp=DEEP_EXTENSION_TP_LEVEL,
        lookback_seconds=DEEP_EXTENSION_LOOKBACK_SECONDS
    )

    recent_runner_sells = [
        t for t in OPEN_TRADES
        if str(t.get("symbol", "")).upper() == symbol
        and str(t.get("signal", "")).upper() == "SELL"
        and bool(t.get("runner"))
        and now_ts() - (t.get("created") or 0) <= DEEP_EXTENSION_LOOKBACK_SECONDS
    ]

    impulse_high = to_float(state.get("impulse_high"), 0)
    impulse_low = to_float(state.get("impulse_low"), 0)

    # Fallback sulla price history se lo state non è completo.
    history = recent_bear_history(symbol, BEAR_IMPULSE_LOOKBACK_SECONDS)
    if history:
        if not impulse_high:
            impulse_high = max(to_float(p.get("high"), 0) for p in history)
        if not impulse_low:
            impulse_low = min(to_float(p.get("low"), 999999) for p in history)

    impulse_range = max(0, impulse_high - impulse_low)
    position = -1
    distance_to_low = 999999
    rebound_from_low = 0

    if price and impulse_high and impulse_low and impulse_range > 0:
        position = (price - impulse_low) / impulse_range
        position = max(0, min(1, position))
        distance_to_low = max(0, price - impulse_low)
        rebound_from_low = distance_to_low

    impulse_drop = max(
        to_float(state.get("impulse_drop"), 0),
        impulse_range
    )

    near_low = (
        to_bool(data.get("near_m15_low", "false"))
        or to_bool(data.get("near_day_low", "false"))
        or distance_to_low <= DEEP_EXTENSION_NEAR_LOW_POINTS
        or (position >= 0 and position <= DEEP_EXTENSION_LOW_POSITION_MAX)
    )

    paid = (
        len(recent_tp_sells) >= DEEP_EXTENSION_SELL_COUNT
        or len(recent_runner_sells) > 0
        or impulse_drop >= DEEP_EXTENSION_MIN_DROP_POINTS
    )

    active = bool(
        DEEP_EXTENSION_FLIP_ENABLED
        and paid
        and near_low
    )

    return {
        "active": active,
        "paid": paid,
        "near_low": near_low,
        "recent_tp_sells": recent_tp_sells,
        "recent_runner_sells": recent_runner_sells,
        "impulse_high": impulse_high,
        "impulse_low": impulse_low,
        "impulse_drop": impulse_drop,
        "position": position,
        "distance_to_low": distance_to_low,
        "rebound_from_low": rebound_from_low
    }


def deep_extension_status_text(ctx):
    return (
        f"Deep Extension active: {ctx.get('active')}\n"
        f"Recent SELL TP{DEEP_EXTENSION_TP_LEVEL}+: {len(ctx.get('recent_tp_sells', []))}\n"
        f"Runner SELL recenti: {len(ctx.get('recent_runner_sells', []))}\n"
        f"Impulse drop: {round(to_float(ctx.get('impulse_drop')), 2)}\n"
        f"Impulse position: {round(to_float(ctx.get('position')), 2)}\n"
        f"Distance low: {round(to_float(ctx.get('distance_to_low')), 2)}\n"
        f"Rebound low: {round(to_float(ctx.get('rebound_from_low')), 2)}"
    )


def should_block_sell_by_deep_extension(signal, symbol, setup_type, data):
    ctx = get_deep_extension_context(symbol, data)

    if not DEEP_EXTENSION_FLIP_ENABLED or not DEEP_EXTENSION_BLOCK_LOW_SELLS:
        return False, ctx, "Deep Extension block disattivato"

    if str(signal).upper() != "SELL":
        return False, ctx, "Non è SELL"

    if not ctx.get("active"):
        return False, ctx, "Deep Extension non attiva"

    setup_type = str(setup_type or "NORMAL").upper()

    if setup_type in DEEP_EXTENSION_ALWAYS_ALLOW_SELL_SETUPS:
        return False, ctx, f"Setup {setup_type} ammesso anche in deep extension"

    # Una campaign può riarmarsi solo dopo un rimbalzo reale dal minimo.
    if (
        setup_type == "BEAR_CAMPAIGN_SELL"
        and ctx.get("rebound_from_low", 0) >= DEEP_EXTENSION_REARM_REBOUND_POINTS
    ):
        return False, ctx, "Campaign SELL riarmato dopo rimbalzo dal minimo"

    return True, ctx, "SELL basso bloccato: movimento già troppo esteso"


def reconcile_campaign_setup(signal, symbol, setup_type, score, reasons, data, decision):
    """Garantisce coerenza tra nome BEAR_CAMPAIGN_SELL e leg realmente contabilizzata."""
    if str(setup_type).upper() != "BEAR_CAMPAIGN_SELL":
        return setup_type, score, reasons, decision

    if decision and decision.get("allow"):
        return setup_type, score, reasons, decision

    bear_state_name = str(get_bear_continuation_state(symbol).get("state", "IDLE")).upper()
    candle_dir = str(data.get("candle_dir", "")).upper()

    # Rimuove il bonus campaign e ricostruisce il bonus continuation.
    score -= CAMPAIGN_SELL_BASE_BONUS
    if bear_state_name == "LOWER_HIGH_ARMED":
        score -= 4
    if candle_dir == "BEAR":
        score -= 2

    if bear_state_name in ["BEAR_IMPULSE", "RELIEF_RALLY", "LOWER_HIGH_ARMED", "SELL_TRIGGERED"]:
        setup_type = "BEAR_CONTINUATION_SELL"
        score += BEAR_CONTINUATION_BASE_BONUS
        if bear_state_name == "LOWER_HIGH_ARMED":
            score += 4
        if candle_dir == "BEAR":
            score += 2

        reasons.append(
            "Campaign accounting fix: non qualificato come nuova leg; "
            "riclassificato BEAR_CONTINUATION_SELL"
        )
    else:
        setup_type = "NORMAL"
        reasons.append(
            "Campaign accounting fix: setup campaign non contabilizzabile; riclassificato NORMAL"
        )

    decision = evaluate_campaign_leg(
        signal,
        symbol,
        setup_type,
        score,
        data
    )

    return setup_type, score, reasons, decision


# =========================
# CAMPAIGN MANAGER / THESIS PERSISTENCE v22
# =========================

def campaign_leg_weights():
    values = []

    for raw in str(CAMPAIGN_LEG_WEIGHTS_RAW).split(","):
        try:
            value = float(raw.strip())
        except Exception:
            continue

        if value > 0:
            values.append(value)

    if not values:
        values = [0.40, 0.35, 0.25]

    return values


def _new_bear_campaign():
    return {
        "status": "IDLE",
        "direction": "SELL",
        "symbol": "",
        "campaign_id": "",
        "started": 0,
        "started_local": "",
        "updated": 0,
        "updated_local": "",
        "thesis": "",
        "bear_state": "IDLE",
        "impulse_high": 0,
        "impulse_low": 0,
        "rally_peak": 0,
        "invalidation_price": 0,
        "legs": [],
        "total_risk_weight": 0.0,
        "last_leg_price": 0,
        "last_leg_time": 0,
        "last_retest_peak": 0,
        "kill_override_used": False,
        "sl_override_count": 0,
        "trim_notified": False,
        "reason": "Nessuna campagna ribassista attiva"
    }


def get_bear_campaign(symbol):
    symbol = str(symbol or "XAUUSD").upper()

    if symbol not in BEAR_CAMPAIGN_STATE:
        BEAR_CAMPAIGN_STATE[symbol] = _new_bear_campaign()
        BEAR_CAMPAIGN_STATE[symbol]["symbol"] = symbol

    return BEAR_CAMPAIGN_STATE[symbol]


def campaign_is_active(campaign):
    return campaign.get("status") in [
        "THESIS_ACTIVE",
        "SCALING_READY",
        "PAUSED"
    ]


def campaign_status_text(symbol):
    campaign = get_bear_campaign(symbol)

    return (
        f"Campaign ID: {campaign.get('campaign_id') or 'N/D'}\n"
        f"Status: {campaign.get('status')}\n"
        f"Bear state: {campaign.get('bear_state')}\n"
        f"Thesis: {campaign.get('thesis')}\n"
        f"Impulse high: {round(to_float(campaign.get('impulse_high')), 3)}\n"
        f"Impulse low: {round(to_float(campaign.get('impulse_low')), 3)}\n"
        f"Rally peak: {round(to_float(campaign.get('rally_peak')), 3)}\n"
        f"Invalidation: {round(to_float(campaign.get('invalidation_price')), 3)}\n"
        f"Legs: {len(campaign.get('legs', []))}/{CAMPAIGN_MAX_LEGS}\n"
        f"Risk weight usato: {round(to_float(campaign.get('total_risk_weight')), 2)}/{CAMPAIGN_TOTAL_RISK_CAP}"
    )


def start_bear_campaign(symbol, bear_state, reason):
    symbol = str(symbol or "XAUUSD").upper()
    campaign = get_bear_campaign(symbol)

    now = now_ts()
    campaign_id = f"BEAR-{symbol}-{int(now * 1000)}"

    campaign.clear()
    campaign.update(_new_bear_campaign())
    campaign["symbol"] = symbol
    campaign["status"] = "THESIS_ACTIVE"
    campaign["campaign_id"] = campaign_id
    campaign["started"] = now
    campaign["started_local"] = local_datetime(now).strftime("%Y-%m-%d %H:%M:%S")
    campaign["updated"] = now
    campaign["updated_local"] = campaign["started_local"]
    campaign["reason"] = reason
    campaign["thesis"] = "Bear impulse -> relief rally -> lower high -> continuation"
    campaign["bear_state"] = bear_state.get("state", "IDLE")
    campaign["impulse_high"] = to_float(bear_state.get("impulse_high"), 0)
    campaign["impulse_low"] = to_float(bear_state.get("impulse_low"), 0)
    campaign["rally_peak"] = to_float(bear_state.get("rally_peak"), 0)

    if campaign["impulse_high"]:
        campaign["invalidation_price"] = (
            campaign["impulse_high"] + CAMPAIGN_INVALIDATION_BUFFER
        )

    return campaign


def sync_bear_campaign(symbol, data=None):
    symbol = str(symbol or "XAUUSD").upper()

    if not CAMPAIGN_MANAGER_ENABLED:
        return get_bear_campaign(symbol)

    bear_state = get_bear_continuation_state(symbol)
    campaign = get_bear_campaign(symbol)

    bear_state_name = str(bear_state.get("state", "IDLE")).upper()
    active_bear_states = {
        "BEAR_IMPULSE",
        "RELIEF_RALLY",
        "LOWER_HIGH_ARMED",
        "SELL_TRIGGERED"
    }

    price = get_price_from_data(data or {})
    now = now_ts()

    # Invalidation dura: superamento dell'impulse high + buffer.
    if campaign_is_active(campaign):
        invalidation = to_float(campaign.get("invalidation_price"), 0)

        if invalidation and price and price >= invalidation:
            campaign["status"] = "INVALIDATED"
            campaign["reason"] = "Tesi invalidata: prezzo sopra impulse high + buffer"
            campaign["updated"] = now
            campaign["updated_local"] = local_datetime(now).strftime("%Y-%m-%d %H:%M:%S")
            return campaign

        if (
            campaign.get("started", 0)
            and now - campaign.get("started", 0) > CAMPAIGN_TIMEOUT_SECONDS
        ):
            campaign["status"] = "EXPIRED"
            campaign["reason"] = "Campagna scaduta per timeout"
            campaign["updated"] = now
            campaign["updated_local"] = local_datetime(now).strftime("%Y-%m-%d %H:%M:%S")
            return campaign

    # Avvio di una nuova tesi.
    if bear_state_name in active_bear_states:
        if not campaign_is_active(campaign):
            campaign = start_bear_campaign(
                symbol,
                bear_state,
                f"Bear state {bear_state_name} confermato"
            )

        campaign["bear_state"] = bear_state_name
        campaign["impulse_high"] = to_float(
            bear_state.get("impulse_high"),
            campaign.get("impulse_high", 0)
        )
        campaign["impulse_low"] = to_float(
            bear_state.get("impulse_low"),
            campaign.get("impulse_low", 0)
        )

        new_rally_peak = to_float(bear_state.get("rally_peak"), 0)
        if new_rally_peak:
            campaign["rally_peak"] = max(
                to_float(campaign.get("rally_peak"), 0),
                new_rally_peak
            )

        if campaign.get("impulse_high"):
            campaign["invalidation_price"] = (
                campaign["impulse_high"] + CAMPAIGN_INVALIDATION_BUFFER
            )

        if bear_state_name in ["LOWER_HIGH_ARMED", "SELL_TRIGGERED"]:
            campaign["status"] = "SCALING_READY"
            campaign["reason"] = f"Campagna pronta: {bear_state_name}"
        else:
            campaign["status"] = "THESIS_ACTIVE"
            campaign["reason"] = f"Tesi attiva: {bear_state_name}"

        campaign["updated"] = now
        campaign["updated_local"] = local_datetime(now).strftime("%Y-%m-%d %H:%M:%S")

    return campaign


def rebuild_bear_campaigns_from_trades():
    if not CAMPAIGN_MANAGER_ENABLED:
        return

    recent_campaign_trades = [
        t for t in OPEN_TRADES
        if t.get("campaign_id")
        and str(t.get("signal", "")).upper() == "SELL"
        and t.get("status") in ["PENDING", "OPEN", "BE", "WIN"]
        and now_ts() - (t.get("created") or 0) <= CAMPAIGN_TIMEOUT_SECONDS
    ]

    grouped = {}

    for trade in recent_campaign_trades:
        key = (
            str(trade.get("symbol", "XAUUSD")).upper(),
            str(trade.get("campaign_id"))
        )
        grouped.setdefault(key, []).append(trade)

    for (symbol, campaign_id), trades in grouped.items():
        trades = sorted(trades, key=lambda t: t.get("created", 0))
        campaign = get_bear_campaign(symbol)

        campaign["status"] = "THESIS_ACTIVE"
        campaign["campaign_id"] = campaign_id
        campaign["started"] = trades[0].get("created", now_ts())
        campaign["started_local"] = trades[0].get("created_local", "")
        campaign["updated"] = now_ts()
        campaign["updated_local"] = local_datetime().strftime("%Y-%m-%d %H:%M:%S")
        campaign["reason"] = "Ricostruita da trades.json"
        campaign["legs"] = []

        total_weight = 0.0

        for trade in trades:
            weight = to_float(trade.get("campaign_risk_weight"), 0)
            total_weight += weight
            campaign["legs"].append({
                "trade_id": trade.get("id"),
                "price": to_float(trade.get("campaign_leg_price"), 0),
                "score": trade.get("score", 0),
                "setup_type": trade.get("setup_type"),
                "risk_weight": weight,
                "created": trade.get("created", 0)
            })

        campaign["total_risk_weight"] = round(total_weight, 4)

        if campaign["legs"]:
            campaign["last_leg_price"] = campaign["legs"][-1].get("price", 0)
            campaign["last_leg_time"] = campaign["legs"][-1].get("created", 0)


def campaign_setup_is_eligible(setup_type):
    return str(setup_type or "").upper() in CAMPAIGN_ELIGIBLE_SETUPS


def evaluate_campaign_leg(signal, symbol, setup_type, score, data):
    result = {
        "allow": False,
        "reason": "",
        "campaign_id": None,
        "leg_number": None,
        "risk_weight": 0.0,
        "kill_override": False,
        "sl_override": False,
        "better_price": False,
        "new_retest": False
    }

    if not CAMPAIGN_MANAGER_ENABLED:
        result["reason"] = "Campaign Manager disattivato"
        return result

    if str(signal).upper() != "SELL":
        result["reason"] = "La campagna attuale gestisce solo SELL"
        return result

    symbol = str(symbol or "XAUUSD").upper()

    if (
        STATE_WARMUP_ENABLED
        and not is_state_warm(symbol)
    ):
        result["reason"] = "Campaign leg bloccata durante cold-start warmup"
        return result

    maturity_ctx = bear_trigger_maturity_context(symbol, data)
    if not maturity_ctx.get("mature"):
        result["reason"] = "Campaign leg bloccata: Trigger Maturity non confermata"
        return result

    recovery_ctx = get_recovery_dominance_context(symbol, data)
    if recovery_ctx.get("active"):
        result["reason"] = "Campaign leg bloccata: Recovery BUY Dominance attiva"
        return result

    deep_ctx = get_deep_extension_context(symbol, data)
    if deep_ctx.get("active") and to_float(deep_ctx.get("rebound_from_low"), 0) < DEEP_EXTENSION_REARM_REBOUND_POINTS:
        result["reason"] = "Campaign leg bloccata: Deep Extension non riarmata"
        return result

    campaign = sync_bear_campaign(symbol, data)
    bear_state = get_bear_continuation_state(symbol)
    bear_state_name = str(bear_state.get("state", "IDLE")).upper()

    if not campaign_is_active(campaign):
        result["reason"] = f"Campagna non attiva: {campaign.get('status')}"
        return result

    if not campaign_setup_is_eligible(setup_type):
        result["reason"] = f"Setup {setup_type} non ammesso come campaign leg"
        return result

    # Le leg passano solo quando il lower high / continuation è realmente pronto.
    if bear_state_name not in ["LOWER_HIGH_ARMED", "SELL_TRIGGERED"]:
        result["reason"] = f"Bear state non pronto per scaling: {bear_state_name}"
        return result

    legs = campaign.get("legs", [])

    if len(legs) >= CAMPAIGN_MAX_LEGS:
        result["reason"] = "Numero massimo di campaign legs raggiunto"
        return result

    min_score = (
        CAMPAIGN_FIRST_LEG_MIN_SCORE
        if len(legs) == 0
        else CAMPAIGN_REENTRY_MIN_SCORE
    )

    if int(score) < min_score:
        result["reason"] = f"Score {score} sotto soglia campaign {min_score}"
        return result

    price = get_price_from_data(data)

    if not price:
        result["reason"] = "Prezzo non disponibile"
        return result

    now = now_ts()

    if (
        campaign.get("last_leg_time", 0)
        and now - campaign.get("last_leg_time", 0) < CAMPAIGN_LEG_COOLDOWN_SECONDS
    ):
        result["reason"] = "Cooldown tra campaign legs ancora attivo"
        return result

    last_leg_price = to_float(campaign.get("last_leg_price"), 0)
    rally_peak = to_float(bear_state.get("rally_peak"), 0)
    last_retest_peak = to_float(campaign.get("last_retest_peak"), 0)

    better_price = bool(
        last_leg_price
        and price >= last_leg_price + CAMPAIGN_BETTER_PRICE_POINTS
    )

    new_retest = bool(
        rally_peak
        and (
            not last_retest_peak
            or rally_peak >= last_retest_peak + CAMPAIGN_NEW_RETEST_POINTS
        )
    )

    # Prima leg: basta un lower high confermato.
    if len(legs) == 0:
        better_price = True

    # Leg successive: prezzo migliore oppure nuovo retest reale.
    if len(legs) > 0 and not (better_price or new_retest):
        result["reason"] = "Nuova leg non migliora il prezzo e non c'è un nuovo retest"
        return result

    weights = campaign_leg_weights()
    index = min(len(legs), len(weights) - 1)
    risk_weight = weights[index]

    if campaign.get("total_risk_weight", 0) + risk_weight > CAMPAIGN_TOTAL_RISK_CAP + 1e-9:
        result["reason"] = "Risk cap totale campagna superato"
        return result

    # Daily Kill Switch: un solo override molto controllato.
    today_losses = get_today_direct_losses(symbol)
    kill_active = (
        DAILY_KILL_SWITCH_ENABLED
        and len(today_losses) >= DAILY_MAX_DIRECT_SL
    )

    if kill_active:
        if not CAMPAIGN_KILL_SWITCH_OVERRIDE_ENABLED:
            result["reason"] = "Daily Kill Switch attivo e override campaign disattivato"
            return result

        if campaign.get("kill_override_used"):
            result["reason"] = "Override Daily Kill Switch già usato in questa campagna"
            return result

        if int(score) < CAMPAIGN_KILL_SWITCH_MIN_SCORE:
            result["reason"] = (
                f"Kill override richiede score >= {CAMPAIGN_KILL_SWITCH_MIN_SCORE}"
            )
            return result

        result["kill_override"] = True
        risk_weight = min(
            risk_weight,
            CAMPAIGN_KILL_OVERRIDE_RISK_WEIGHT
        )

    result.update({
        "allow": True,
        "reason": "Campaign leg qualificata",
        "campaign_id": campaign.get("campaign_id"),
        "leg_number": len(legs) + 1,
        "risk_weight": round(risk_weight, 4),
        "better_price": better_price,
        "new_retest": new_retest
    })

    return result


def campaign_sl_override_eligible(signal, symbol, setup_type, score, data):
    if not CAMPAIGN_SL_COOLDOWN_OVERRIDE_ENABLED:
        return False, None

    decision = evaluate_campaign_leg(
        signal,
        symbol,
        setup_type,
        score,
        data
    )

    if not decision.get("allow"):
        return False, decision

    campaign = get_bear_campaign(symbol)

    if campaign.get("sl_override_count", 0) >= CAMPAIGN_MAX_SL_OVERRIDES:
        decision["reason"] = "Numero massimo override SL cooldown raggiunto"
        return False, decision

    if int(score) < CAMPAIGN_SL_COOLDOWN_MIN_SCORE:
        decision["reason"] = (
            f"SL override richiede score >= {CAMPAIGN_SL_COOLDOWN_MIN_SCORE}"
        )
        return False, decision

    decision["sl_override"] = True
    return True, decision


def register_campaign_leg(trade, decision):
    if not decision or not decision.get("allow"):
        return trade

    symbol = str(trade.get("symbol", "XAUUSD")).upper()
    campaign = get_bear_campaign(symbol)

    leg_price = (
        to_float(trade.get("entry_low"), 0)
        + to_float(trade.get("entry_high"), 0)
    ) / 2

    if not leg_price:
        leg_price = to_float(trade.get("price"), 0)

    leg = {
        "trade_id": trade.get("id"),
        "price": leg_price,
        "score": trade.get("score", 0),
        "setup_type": trade.get("setup_type"),
        "risk_weight": decision.get("risk_weight", 0),
        "created": trade.get("created", now_ts())
    }

    campaign.setdefault("legs", []).append(leg)
    campaign["total_risk_weight"] = round(
        to_float(campaign.get("total_risk_weight"), 0)
        + to_float(decision.get("risk_weight"), 0),
        4
    )
    campaign["last_leg_price"] = leg_price
    campaign["last_leg_time"] = leg["created"]

    bear_state = get_bear_continuation_state(symbol)
    campaign["last_retest_peak"] = to_float(
        bear_state.get("rally_peak"),
        campaign.get("last_retest_peak", 0)
    )

    if decision.get("kill_override"):
        campaign["kill_override_used"] = True

    if decision.get("sl_override"):
        campaign["sl_override_count"] = (
            int(campaign.get("sl_override_count", 0)) + 1
        )

    campaign["updated"] = now_ts()
    campaign["updated_local"] = local_datetime().strftime("%Y-%m-%d %H:%M:%S")
    campaign["reason"] = (
        f"Campaign leg {decision.get('leg_number')} registrata"
    )

    trade["campaign_id"] = campaign.get("campaign_id")
    trade["campaign_leg"] = decision.get("leg_number")
    trade["campaign_risk_weight"] = decision.get("risk_weight")
    trade["campaign_leg_price"] = leg_price
    trade["campaign_kill_override"] = bool(decision.get("kill_override"))
    trade["campaign_sl_override"] = bool(decision.get("sl_override"))

    save_trades()
    save_runtime_state(force=True)

    return trade


def campaign_trim_message(symbol, price):
    campaign = get_bear_campaign(symbol)
    legs = campaign.get("legs", [])

    if len(legs) < 2:
        return None

    open_leg_trades = []

    for leg in legs:
        trade = next(
            (
                t for t in OPEN_TRADES
                if str(t.get("id")) == str(leg.get("trade_id"))
                and t.get("status") in ["PENDING", "OPEN"]
            ),
            None
        )

        if trade:
            open_leg_trades.append(trade)

    if len(open_leg_trades) < 2:
        return None

    entries = []

    for trade in open_leg_trades:
        midpoint = (
            to_float(trade.get("entry_low"), 0)
            + to_float(trade.get("entry_high"), 0)
        ) / 2
        entries.append((midpoint, trade))

    entries = sorted(entries, key=lambda item: item[0])

    worst_entry = entries[0][0]
    best_entry = entries[-1][0]

    if (
        price <= worst_entry - CAMPAIGN_TRIM_TRIGGER_POINTS
        and not campaign.get("trim_notified")
    ):
        campaign["trim_notified"] = True

        return f"""🧺 BEAR CAMPAIGN MANAGEMENT {VERSION}

Campaign ID: {campaign.get('campaign_id')}
Leg attive: {len(open_leg_trades)}

Prezzo attuale: {round(price, 3)}
Entry più bassa / peggiore: {round(worst_entry, 3)}
Entry più alta / migliore: {round(best_entry, 3)}

Lettura:
La campagna SELL è in profitto sufficiente per proteggere il basket.
Il bot segnala di proteggere/chiudere prima le leg peggiori e lasciare più spazio alle entry migliori.

Risk weight totale: {campaign.get('total_risk_weight')}
"""

    return None


def manage_bear_campaign_on_price_update(data):
    if not CAMPAIGN_MANAGER_ENABLED:
        return []

    symbol = str(data.get("symbol", "XAUUSD")).upper()
    price = get_price_from_data(data)

    campaign = sync_bear_campaign(symbol, data)
    messages = []

    if not campaign_is_active(campaign):
        return messages

    if CAMPAIGN_TRIM_ENABLED and price:
        message = campaign_trim_message(symbol, price)

        if message:
            messages.append(message)

    return messages


def campaign_duplicate_override_allowed(
    signal,
    symbol,
    setup_type,
    score,
    data
):
    decision = evaluate_campaign_leg(
        signal,
        symbol,
        setup_type,
        score,
        data
    )

    return bool(decision.get("allow")), decision



# =========================
# BEARISH CONTINUATION + LOWER HIGH STATE MACHINE v21
# =========================

def _new_bear_state():
    return {
        "state": "IDLE",
        "symbol": "",
        "updated": 0,
        "updated_local": "",
        "started": 0,
        "impulse_high": 0,
        "impulse_high_time": 0,
        "impulse_low": 0,
        "impulse_low_time": 0,
        "impulse_drop": 0,
        "rally_peak": 0,
        "rally_peak_time": 0,
        "relief_retrace": 0,
        "last_price": 0,
        "last_trigger_time": 0,
        "last_trigger_trade_id": None,
        "reason": "Nessuna continuazione bearish attiva"
    }


def get_bear_continuation_state(symbol):
    symbol = str(symbol or "XAUUSD").upper()

    if symbol not in BEAR_CONTINUATION_STATE:
        BEAR_CONTINUATION_STATE[symbol] = _new_bear_state()
        BEAR_CONTINUATION_STATE[symbol]["symbol"] = symbol

    return BEAR_CONTINUATION_STATE[symbol]


def set_bear_continuation_state(symbol, new_state, reason):
    state = get_bear_continuation_state(symbol)
    state["state"] = new_state
    state["reason"] = reason
    state["updated"] = now_ts()
    state["updated_local"] = local_datetime().strftime("%Y-%m-%d %H:%M:%S")

    if not state.get("started") and new_state != "IDLE":
        state["started"] = now_ts()

    return state


def reset_bear_continuation_state(symbol, reason="Reset"):
    symbol = str(symbol or "XAUUSD").upper()
    old = get_bear_continuation_state(symbol)
    last_trigger_time = old.get("last_trigger_time", 0)
    last_trigger_trade_id = old.get("last_trigger_trade_id")

    BEAR_CONTINUATION_STATE[symbol] = _new_bear_state()
    BEAR_CONTINUATION_STATE[symbol]["symbol"] = symbol
    BEAR_CONTINUATION_STATE[symbol]["last_trigger_time"] = last_trigger_time
    BEAR_CONTINUATION_STATE[symbol]["last_trigger_trade_id"] = last_trigger_trade_id
    BEAR_CONTINUATION_STATE[symbol]["reason"] = reason
    BEAR_CONTINUATION_STATE[symbol]["updated"] = now_ts()
    BEAR_CONTINUATION_STATE[symbol]["updated_local"] = local_datetime().strftime("%Y-%m-%d %H:%M:%S")

    return BEAR_CONTINUATION_STATE[symbol]


def bear_state_status_text(symbol):
    state = get_bear_continuation_state(symbol)

    return (
        f"State: {state.get('state')}\n"
        f"Reason: {state.get('reason')}\n"
        f"Impulse high: {round(to_float(state.get('impulse_high')), 3)}\n"
        f"Impulse low: {round(to_float(state.get('impulse_low')), 3)}\n"
        f"Impulse drop: {round(to_float(state.get('impulse_drop')), 2)}\n"
        f"Rally peak: {round(to_float(state.get('rally_peak')), 3)}\n"
        f"Relief retrace: {round(to_float(state.get('relief_retrace')), 2)}"
    )


def record_price_history(data):
    symbol = str(data.get("symbol", "XAUUSD")).upper()
    price = get_price_from_data(data)

    if not price:
        return []

    point = {
        "time": now_ts(),
        "open": to_float(data.get("open"), price),
        "high": to_float(data.get("high"), price),
        "low": to_float(data.get("low"), price),
        "close": to_float(data.get("close"), price),
        "price": price,
        "atr": to_float(data.get("atr"), 0),
        "candle_dir": str(data.get("candle_dir", "")).upper(),
        "rejection": str(data.get("rejection", "")).upper(),
        "upper_wick_strong": to_bool(data.get("upper_wick_strong", "false")),
        "lower_wick_strong": to_bool(data.get("lower_wick_strong", "false")),
        "ema20_slope": str(data.get("ema20_slope", "FLAT")).upper(),
        "ema50_slope": str(data.get("ema50_slope", "FLAT")).upper(),
        "h1_bias": str(data.get("h1_bias", "NEUTRAL")).upper(),
        "h4_bias": str(data.get("h4_bias", "NEUTRAL")).upper(),
        "day_bias": str(data.get("day_bias", "NEUTRAL")).upper(),
        "bear_impulse_local": to_bool(data.get("bear_impulse_local", "false"))
    }

    history = PRICE_HISTORY.setdefault(symbol, [])
    history.append(point)

    cutoff = now_ts() - BEAR_HISTORY_SECONDS
    history[:] = [
        p for p in history
        if p.get("time", 0) >= cutoff
    ][-BEAR_HISTORY_MAX_POINTS:]

    return history


def recent_bear_history(symbol, seconds=None):
    symbol = str(symbol or "XAUUSD").upper()
    history = PRICE_HISTORY.get(symbol, [])

    if seconds is None:
        return history

    cutoff = now_ts() - seconds
    return [p for p in history if p.get("time", 0) >= cutoff]



# =========================
# v43 ASIAN SESSION DAILY THESIS
# =========================

def _thesis_local_dt(ts=None):
    try:
        return datetime.fromtimestamp(ts or now_ts(), ZoneInfo(USER_TIMEZONE))
    except Exception:
        return datetime.fromtimestamp(ts or now_ts(), timezone.utc)


def _thesis_day_key(ts=None):
    return _thesis_local_dt(ts).strftime("%Y-%m-%d")


def _minutes_of_day(dt):
    return dt.hour * 60 + dt.minute


def _asian_start_minute():
    return ASIAN_THESIS_START_HOUR * 60 + ASIAN_THESIS_START_MINUTE


def _asian_end_minute():
    return ASIAN_THESIS_END_HOUR * 60 + ASIAN_THESIS_END_MINUTE


def get_daily_thesis_state(symbol):
    symbol = str(symbol or "XAUUSD").upper()
    day_key = _thesis_day_key()
    state = DAILY_THESIS_STATE.get(symbol)
    if not isinstance(state, dict) or state.get("day_key") != day_key:
        state = {
            "day_key": day_key,
            "symbol": symbol,
            "status": "COLLECTING_ASIA",
            "preferred": "WAIT",
            "direction": "WAIT",
            "reason": "Raccolta dati Asia in corso",
            "asian_open": 0,
            "asian_high": 0,
            "asian_low": 0,
            "asian_close": 0,
            "asian_range": 0,
            "asian_move": 0,
            "asian_direction": "WAIT",
            "session": "ASIA",
            "last_price": 0,
            "last_alert_signature": None,
            "updated": 0,
        }
        DAILY_THESIS_STATE[symbol] = state
    return state


def _asian_points_from_history(symbol):
    history = PRICE_HISTORY.get(str(symbol or "XAUUSD").upper(), []) or []
    day_key = _thesis_day_key()
    start_m = _asian_start_minute()
    end_m = _asian_end_minute()
    points = []
    for p in history:
        ts = to_float(p.get("time"), 0)
        if not ts:
            continue
        dt = _thesis_local_dt(ts)
        if dt.strftime("%Y-%m-%d") != day_key:
            continue
        minute = _minutes_of_day(dt)
        if start_m <= minute <= end_m:
            points.append(p)
    return points


def _current_session_name(ts=None):
    minute = _minutes_of_day(_thesis_local_dt(ts))
    if minute < _asian_start_minute():
        return "PRE_ASIA"
    if minute <= _asian_end_minute():
        return "ASIA"
    if minute < 13 * 60 + 30:
        return "LONDON"
    if minute < 17 * 60 + 30:
        return "NEW_YORK"
    return "LATE_US"


def update_daily_thesis(data, force=False):
    symbol = str(data.get("symbol", "XAUUSD")).upper()
    state = get_daily_thesis_state(symbol)
    price = get_price_from_data(data)
    if not ASIAN_THESIS_ENABLED:
        state.update({"status": "DISABLED", "preferred": "WAIT", "direction": "WAIT", "reason": "ASIAN_THESIS_ENABLED = FALSE"})
        return state

    points = _asian_points_from_history(symbol)
    session = _current_session_name()
    state["session"] = session
    if price:
        state["last_price"] = price

    if points:
        first = points[0]
        last = points[-1]
        asian_open = to_float(first.get("price"), 0)
        asian_close = to_float(last.get("price"), 0)
        asian_high = max(to_float(p.get("high"), to_float(p.get("price"), 0)) for p in points)
        asian_low = min(to_float(p.get("low"), to_float(p.get("price"), 0)) for p in points)
        asian_range = max(0, asian_high - asian_low)
        asian_move = asian_close - asian_open
    else:
        asian_open = asian_close = asian_high = asian_low = asian_range = asian_move = 0

    direction = "RANGE"
    if asian_move >= ASIAN_THESIS_MIN_POINTS:
        direction = "BUY"
    elif asian_move <= -ASIAN_THESIS_MIN_POINTS:
        direction = "SELL"

    preferred = "WAIT"
    status = "COLLECTING_ASIA" if session == "ASIA" else "ASIA_READY"
    reason = "Asia ancora in formazione"
    day_position = to_float(data.get("day_position"), -1)
    recovery_from_low = (price - asian_low) if price and asian_low else 0
    retrace_from_high = (asian_high - price) if price and asian_high else 0
    range_pos = ((price - asian_low) / asian_range) if price and asian_range > 0 else None
    broke_asian_high = bool(price and asian_high and price >= asian_high + ASIAN_THESIS_BREAKOUT_BUFFER)
    broke_asian_low = bool(price and asian_low and price <= asian_low - ASIAN_THESIS_BREAKOUT_BUFFER)
    recovered_mid = bool(price and asian_low and asian_high and price >= asian_low + asian_range * ASIAN_THESIS_RECOVERY_RATIO)
    recovered_open = bool(price and asian_open and price >= asian_open + ASIAN_THESIS_BREAKOUT_BUFFER)
    rejected_high = bool(price and asian_high and retrace_from_high >= ASIAN_THESIS_RECOVERY_POINTS)
    rejected_low = bool(price and asian_low and recovery_from_low >= ASIAN_THESIS_RECOVERY_POINTS)

    if session == "ASIA":
        preferred = "WAIT"
        reason = "00:05-07:30: raccolgo high/low Asia, evito di innamorarmi del primo impulso"
    elif direction == "SELL":
        if recovered_mid or recovered_open:
            preferred = "BUY"
            status = "REVERSAL_BUY_WATCH"
            reason = "Asia ha scaricato, ma Londra/Europa sta recuperando: non inseguo SELL bassi, cerco BUY/reversal da supporto"
        elif broke_asian_low:
            preferred = "SELL"
            status = "ASIA_SELL_CONTINUATION"
            reason = "Asia ribassista confermata sotto il minimo: SELL solo su pullback/retest, non sul minimo se già esteso"
        else:
            preferred = "WAIT"
            status = "POST_ASIA_SELL_BALANCE"
            reason = "Asia ribassista ma recupero non ancora confermato: aspetto rottura o rientro nel range"
    elif direction == "BUY":
        if rejected_high and (range_pos is not None and range_pos >= 0.55):
            preferred = "SELL"
            status = "FADE_SELL_WATCH"
            reason = "Asia rialzista già estesa, prezzo respinto in alto: cerco solo SELL/fade da zona alta confermata"
        elif broke_asian_high:
            preferred = "BUY"
            status = "ASIA_BUY_CONTINUATION"
            reason = "Asia rialzista confermata sopra massimo: BUY solo su pullback/retest, non inseguire spike"
        else:
            preferred = "WAIT"
            status = "POST_ASIA_BUY_BALANCE"
            reason = "Asia rialzista ma non voglio comprare alto senza pullback"
    else:
        if broke_asian_high:
            preferred = "BUY"
            status = "ASIA_RANGE_BREAKOUT_BUY"
            reason = "Asia laterale, rottura sopra massimo: scenario BUY se tiene il retest"
        elif broke_asian_low:
            preferred = "SELL"
            status = "ASIA_RANGE_BREAKOUT_SELL"
            reason = "Asia laterale, rottura sotto minimo: scenario SELL se tiene il retest"
        elif rejected_low:
            preferred = "BUY"
            status = "RANGE_REBOUND_BUY"
            reason = "Asia laterale, reazione dal basso: scalping BUY più pulito"
        elif rejected_high:
            preferred = "SELL"
            status = "RANGE_FADE_SELL"
            reason = "Asia laterale, reazione dall'alto: scalping SELL più pulito"
        else:
            preferred = "RANGE"
            status = "ASIA_RANGE"
            reason = "Asia in range: preferisco FAST piccoli e niente convinzione forte"

    # Protezione Max: dopo TP profondi nella stessa direzione, la tesi diventa gestione.
    if ASIAN_THESIS_AFTER_TP_LOCK_ENABLED and preferred in ["BUY", "SELL"]:
        winners = get_recent_tp_trades(preferred, symbol, min_tp=ASIAN_THESIS_AFTER_TP_LOCK_LEVEL, lookback_seconds=ASIAN_THESIS_AFTER_TP_LOCK_SECONDS)
        if winners:
            best = winners[0]
            state["after_tp_lock"] = True
            state["after_tp_lock_trade"] = best.get("id")
            state["after_tp_lock_tp"] = best.get("highest_tp", 0)
        else:
            state["after_tp_lock"] = False
            state["after_tp_lock_trade"] = None
            state["after_tp_lock_tp"] = 0
    else:
        state["after_tp_lock"] = False
        state["after_tp_lock_trade"] = None
        state["after_tp_lock_tp"] = 0

    state.update({
        "status": status,
        "preferred": preferred,
        "direction": preferred,
        "reason": reason,
        "asian_open": round(asian_open, 3) if asian_open else 0,
        "asian_high": round(asian_high, 3) if asian_high else 0,
        "asian_low": round(asian_low, 3) if asian_low else 0,
        "asian_close": round(asian_close, 3) if asian_close else 0,
        "asian_range": round(asian_range, 3) if asian_range else 0,
        "asian_move": round(asian_move, 3) if asian_move else 0,
        "asian_direction": direction,
        "range_position": round(range_pos, 3) if isinstance(range_pos, (int, float)) else None,
        "recovery_from_low": round(recovery_from_low, 3),
        "retrace_from_high": round(retrace_from_high, 3),
        "broke_asian_high": broke_asian_high,
        "broke_asian_low": broke_asian_low,
        "recovered_mid": recovered_mid,
        "recovered_open": recovered_open,
        "day_position": round(day_position, 3) if day_position >= 0 else day_position,
        "updated": now_ts(),
        "updated_local": local_datetime().strftime("%Y-%m-%d %H:%M:%S"),
    })
    return state


def get_daily_thesis_context(symbol, data=None):
    symbol = str(symbol or "XAUUSD").upper()
    if data is not None:
        return update_daily_thesis(data)
    return get_daily_thesis_state(symbol)


def daily_thesis_signature(ctx):
    if not ctx:
        return None
    return "|".join([
        str(ctx.get("day_key")),
        str(ctx.get("session")),
        str(ctx.get("status")),
        str(ctx.get("preferred")),
        str(ctx.get("asian_direction")),
        str(ctx.get("after_tp_lock")),
    ])


def daily_thesis_text(ctx):
    if not ctx:
        return "Daily Thesis: N/D"
    return (
        f"Status: {ctx.get('status')} | Preferred: {ctx.get('preferred')} | Sessione: {ctx.get('session')}\n"
        f"Reason: {ctx.get('reason')}\n"
        f"Asia {ASIAN_THESIS_START_HOUR:02d}:{ASIAN_THESIS_START_MINUTE:02d}-{ASIAN_THESIS_END_HOUR:02d}:{ASIAN_THESIS_END_MINUTE:02d}: "
        f"Open {ctx.get('asian_open')} | High {ctx.get('asian_high')} | Low {ctx.get('asian_low')} | Close {ctx.get('asian_close')}\n"
        f"Asia dir: {ctx.get('asian_direction')} | Move {ctx.get('asian_move')} | Range {ctx.get('asian_range')} | Range pos {ctx.get('range_position')}\n"
        f"Recovery low: {ctx.get('recovery_from_low')} | Retrace high: {ctx.get('retrace_from_high')}\n"
        f"Break high: {ctx.get('broke_asian_high')} | Break low: {ctx.get('broke_asian_low')} | Recovered mid/open: {ctx.get('recovered_mid')}/{ctx.get('recovered_open')}\n"
        f"After TP lock: {ctx.get('after_tp_lock')} | Trade: {ctx.get('after_tp_lock_trade')} | TP: {ctx.get('after_tp_lock_tp')}"
    )


def maybe_daily_thesis_alert(symbol, data):
    if not ASIAN_THESIS_ALERT_ENABLED:
        return None
    ctx = update_daily_thesis(data)
    if not ctx or ctx.get("status") in ["COLLECTING_ASIA", "DISABLED"]:
        return None
    sig = daily_thesis_signature(ctx)
    if sig and sig == ctx.get("last_alert_signature"):
        return None
    ctx["last_alert_signature"] = sig
    return f"""🧭 DAILY THESIS v43 — NON È ENTRY

Symbol: {symbol}

{daily_thesis_text(ctx)}

Azione pratica:
- I FAST da 2 punti devono rispettare questa tesi.
- Se Asia ha già venduto tanto, non inseguo SELL bassi: cerco recupero BUY o aspetto retest alto.
- Se Asia ha già comprato tanto, non compro spike alto: cerco pullback o fade SELL da zona alta.
- Operazione ufficiale solo quando arriva il messaggio copiabile."""


def daily_thesis_allows_counter(ctx, signal, setup_type, score, data):
    if not ASIAN_THESIS_ENABLED or not ctx:
        return False
    preferred = str(ctx.get("preferred", "WAIT")).upper()
    status = str(ctx.get("status", "")).upper()
    signal = normalize_signal(signal)
    setup = str(setup_type or "NORMAL").upper()
    score = int(score or 0)
    if preferred == signal:
        return True
    if signal == "BUY" and status == "REVERSAL_BUY_WATCH" and setup in ASIAN_THESIS_BUY_SETUPS and score >= ASIAN_THESIS_REVERSAL_BUY_MIN_SCORE:
        return True
    if signal == "SELL" and status in ["FADE_SELL_WATCH", "RANGE_FADE_SELL"] and setup in ASIAN_THESIS_SELL_SETUPS and score >= ASIAN_THESIS_REVERSAL_SELL_MIN_SCORE:
        return True
    return False


def daily_thesis_block_context(signal, symbol, setup_type, score, data, is_fast=False):
    ctx = update_daily_thesis(data)
    signal = normalize_signal(signal)
    setup = str(setup_type or "NORMAL").upper()
    score = int(score or 0)
    preferred = str(ctx.get("preferred", "WAIT")).upper()
    status = str(ctx.get("status", "")).upper()
    day_position = to_float(data.get("day_position"), ctx.get("day_position", -1))
    reasons = []

    if not ASIAN_THESIS_ENABLED:
        return {"block": False, "reason": "Daily thesis disabled", "ctx": ctx, "reasons": []}

    # Asia ha venduto tanto e siamo bassi: non inseguire altri SELL deboli.
    if signal == "SELL" and status in ["REVERSAL_BUY_WATCH", "POST_ASIA_SELL_BALANCE"]:
        if day_position >= 0 and day_position <= ASIAN_THESIS_LOW_POSITION_BLOCK_SELL and score < ASIAN_THESIS_COUNTER_FAST_MIN_SCORE:
            reasons.append("Daily Thesis: Asia già ribassista e prezzo basso; non inseguo SELL, aspetto recupero BUY o retest alto")
        elif preferred == "BUY" and score < ASIAN_THESIS_COUNTER_FAST_MIN_SCORE:
            reasons.append("Daily Thesis preferisce BUY/reversal: SELL ammesso solo A+ o da zona alta")

    # Asia ha comprato tanto e siamo alti: non inseguire BUY deboli.
    if signal == "BUY" and status in ["FADE_SELL_WATCH", "POST_ASIA_BUY_BALANCE"]:
        if day_position >= ASIAN_THESIS_HIGH_POSITION_BLOCK_BUY and score < ASIAN_THESIS_COUNTER_FAST_MIN_SCORE:
            reasons.append("Daily Thesis: Asia già rialzista e prezzo alto; non inseguo BUY, aspetto pullback o fade SELL")
        elif preferred == "SELL" and score < ASIAN_THESIS_COUNTER_FAST_MIN_SCORE:
            reasons.append("Daily Thesis preferisce SELL/fade: BUY ammesso solo A+ o da zona bassa")

    # Se c'è già TP3+ nella direzione della tesi, il bot deve gestire e non moltiplicare entry.
    if ctx.get("after_tp_lock") and preferred == signal and setup == "NORMAL":
        reasons.append(f"Daily Thesis: direzione {signal} già pagata TP{ctx.get('after_tp_lock_tp')}; nuovo NORMAL diventa tesi/gestione")

    # In range asiatico il FAST può lavorare, ma i main NORMAL non devono diventare convinzione forte.
    if not is_fast and preferred == "RANGE" and setup == "NORMAL" and score < MAX_DISCIPLINE_REENTRY_MIN_SCORE:
        reasons.append("Daily Thesis: Asia in range; NORMAL main resta tesi, meglio FAST puliti o aspettare breakout")

    return {
        "block": bool(reasons),
        "reason": reasons[0] if reasons else "Daily Thesis ok",
        "ctx": ctx,
        "reasons": reasons,
    }

def _bearish_context_from_data(data):
    return (
        str(data.get("ema20_slope", "")).upper() == "DOWN"
        or str(data.get("ema50_slope", "")).upper() == "DOWN"
        or str(data.get("candle_dir", "")).upper() == "BEAR"
        or str(data.get("h1_bias", "")).upper() == "SELL"
        or str(data.get("day_bias", "")).upper() == "SELL"
        or to_bool(data.get("bear_impulse_local", "false"))
    )


def _bearish_confirmation_from_data(data, previous_price=0):
    price = get_price_from_data(data)
    bar_open = to_float(data.get("open"), 0)

    return (
        str(data.get("candle_dir", "")).upper() == "BEAR"
        or str(data.get("rejection", "")).upper() == "UPPER_WICK"
        or to_bool(data.get("upper_wick_strong", "false"))
        or str(data.get("ema20_slope", "")).upper() == "DOWN"
        or (bar_open and price < bar_open)
        or (previous_price and price < previous_price)
    )


def bearish_confirmation_details(data, previous_price=0):
    """Conta conferme indipendenti, evitando di contare due volte la stessa candela rossa."""
    price = get_price_from_data(data)
    bar_open = to_float(data.get("open"), 0)

    confirmations = []

    bearish_candle = bool(
        str(data.get("candle_dir", "")).upper() == "BEAR"
        or (bar_open and price < bar_open)
    )
    if bearish_candle:
        confirmations.append("bearish_candle")

    upper_rejection = bool(
        str(data.get("rejection", "")).upper() == "UPPER_WICK"
        or to_bool(data.get("upper_wick_strong", "false"))
    )
    if upper_rejection:
        confirmations.append("upper_rejection")

    if str(data.get("ema20_slope", "")).upper() == "DOWN":
        confirmations.append("ema20_down")

    if previous_price and price < previous_price:
        confirmations.append("lower_close")

    return {
        "count": len(confirmations),
        "items": confirmations
    }


def effective_failure_threshold(
    data,
    legacy_threshold,
    minimum_points,
    atr_mult,
    dynamic_enabled=True
):
    threshold = max(
        to_float(legacy_threshold, 0),
        to_float(minimum_points, 0)
    )

    if dynamic_enabled:
        atr = to_float(data.get("atr"), 0)
        if atr:
            threshold = max(threshold, atr * atr_mult)

    return threshold


def micro_bos_bear_context(symbol, data):
    symbol = str(symbol or "XAUUSD").upper()
    price = get_price_from_data(data)

    pine_confirmed = to_bool(data.get("micro_bos_bear", "false"))
    pine_reference = to_float(data.get("micro_bos_reference_low"), 0)

    if pine_confirmed:
        return {
            "confirmed": True,
            "source": "PINE",
            "reference_low": pine_reference
        }

    history = PRICE_HISTORY.get(symbol, [])
    if not isinstance(history, list):
        history = []

    # Se l'ultimo punto è appena stato registrato con lo stesso close,
    # lo escludo: il BOS deve rompere minimi precedenti.
    prior_history = history
    if history:
        last = history[-1]
        same_close = abs(
            to_float(last.get("close"), 0) - to_float(price, 0)
        ) < 1e-9
        very_recent = now_ts() - to_float(last.get("time"), 0) <= 5

        if same_close and very_recent:
            prior_history = history[:-1]

    prior = prior_history[-MICRO_BOS_LOOKBACK_UPDATES:]

    if not price or len(prior) < max(2, MICRO_BOS_LOOKBACK_UPDATES // 2):
        return {
            "confirmed": False,
            "source": "PYTHON",
            "reference_low": 0
        }

    reference_low = min(
        to_float(p.get("low"), 999999)
        for p in prior
    )

    confirmed = bool(
        reference_low < 999999
        and price <= reference_low - MICRO_BOS_BUFFER_POINTS
    )

    return {
        "confirmed": confirmed,
        "source": "PYTHON",
        "reference_low": reference_low
    }


def detect_recent_bear_impulse(data):
    symbol = str(data.get("symbol", "XAUUSD")).upper()
    history = recent_bear_history(symbol, BEAR_IMPULSE_LOOKBACK_SECONDS)

    if len(history) < 3:
        return None

    current = history[-1]
    current_low = current.get("low", current.get("price", 0))

    # Picco precedente più alto nella finestra.
    peak = max(history[:-1], key=lambda p: p.get("high", 0), default=None)

    if not peak:
        return None

    peak_high = to_float(peak.get("high"), 0)
    peak_time = peak.get("time", 0)

    # Minimo successivo al picco.
    after_peak = [p for p in history if p.get("time", 0) >= peak_time]
    if not after_peak:
        return None

    low_point = min(after_peak, key=lambda p: p.get("low", 999999))
    impulse_low = to_float(low_point.get("low"), current_low)
    impulse_low_time = low_point.get("time", 0)

    drop = peak_high - impulse_low
    atr = to_float(current.get("atr"), 0)
    threshold = max(
        BEAR_IMPULSE_MIN_DROP_POINTS,
        atr * BEAR_IMPULSE_ATR_MULT if atr else 0
    )

    if (
        drop >= threshold
        and _bearish_context_from_data(data)
        and impulse_low_time >= peak_time
    ):
        return {
            "peak_high": peak_high,
            "peak_time": peak_time,
            "impulse_low": impulse_low,
            "impulse_low_time": impulse_low_time,
            "drop": drop,
            "threshold": threshold
        }

    return None


def has_recent_bear_synthetic_sell(symbol):
    symbol = str(symbol).upper()
    now = now_ts()

    for trade in OPEN_TRADES:
        if str(trade.get("symbol", "")).upper() != symbol:
            continue

        if trade.get("setup_type") != "SYNTHETIC_BEAR_CONTINUATION_SELL":
            continue

        created = trade.get("created") or 0

        if trade.get("status") in ["PENDING", "OPEN"]:
            return True, trade

        if now - created <= BEAR_SYNTHETIC_COOLDOWN_SECONDS:
            return True, trade

    return False, None


def build_bear_synthetic_sell_data(data, state):
    price = get_price_from_data(data)

    if not price:
        return None, "Prezzo non disponibile"

    rally_peak = to_float(state.get("rally_peak"), 0)
    entry_low = price - BEAR_SYNTHETIC_ENTRY_HALF_ZONE
    entry_high = price + BEAR_SYNTHETIC_ENTRY_HALF_ZONE

    sl_by_rally = rally_peak + BEAR_SYNTHETIC_RALLY_SL_BUFFER if rally_peak else 0
    sl_by_min_distance = price + BEAR_SYNTHETIC_MIN_SL_DISTANCE
    sl = max(sl_by_rally, sl_by_min_distance)

    risk = sl - price

    if risk <= 0:
        return None, "Rischio SELL non valido"

    if risk > BEAR_SYNTHETIC_MAX_RISK_POINTS:
        return None, (
            f"Rischio troppo largo: {round(risk, 2)} > "
            f"{BEAR_SYNTHETIC_MAX_RISK_POINTS}"
        )

    tp_distances = [
        BEAR_SYNTHETIC_TP1,
        BEAR_SYNTHETIC_TP2,
        BEAR_SYNTHETIC_TP3,
        BEAR_SYNTHETIC_TP4,
        BEAR_SYNTHETIC_TP5,
        BEAR_SYNTHETIC_TP6,
        BEAR_SYNTHETIC_TP7,
        BEAR_SYNTHETIC_TP8
    ]

    out = {
        "signal": "SELL",
        "symbol": data.get("symbol", "XAUUSD"),
        "price": price,
        "tf": data.get("tf", ""),
        "entry_low": round(entry_low, 3),
        "entry_high": round(entry_high, 3),
        "sl": round(sl, 3),
        "synthetic_source": "BEAR_CONTINUATION_STATE_MACHINE"
    }

    for i, dist in enumerate(tp_distances, start=1):
        out[f"tp{i}"] = round(price - dist, 3)

    return out, None


def save_bear_synthetic_sell_trade(data, state):
    synthetic_data, error = build_bear_synthetic_sell_data(data, state)

    if error:
        return None, error

    trade = save_trade(
        synthetic_data,
        "SELL",
        BEAR_SYNTHETIC_SCORE,
        "SYNTHETIC_BEAR_CONTINUATION_SELL"
    )

    trade["status"] = "OPEN"
    trade["entered"] = True
    trade["activated"] = now_ts()
    trade["activated_local"] = local_datetime().strftime("%Y-%m-%d %H:%M:%S")
    trade["synthetic"] = True
    trade["synthetic_source"] = "BEAR_CONTINUATION_STATE_MACHINE"
    trade["impulse_high"] = state.get("impulse_high")
    trade["impulse_low"] = state.get("impulse_low")
    trade["rally_peak"] = state.get("rally_peak")
    trade["relief_retrace"] = state.get("relief_retrace")
    save_trades()

    return trade, None


def bear_synthetic_sell_message(trade, state, data):
    return f"""🐻🔴 GOLD SELL AUTONOMO {VERSION}

🆔 Trade ID: {trade.get('id')}
📌 Setup: SYNTHETIC_BEAR_CONTINUATION_SELL
🧠 Origine: Python Bearish Continuation State Machine
📍 Entry Zone: {trade.get('entry_low')} - {trade.get('entry_high')}
🛑 SL: {trade.get('sl')}
🎯 TP1: {trade.get('tp1')}
🎯 TP2: {trade.get('tp2')}
🎯 TP3: {trade.get('tp3')}
🎯 TP4: {trade.get('tp4')}
🎯 TP5: {trade.get('tp5')}
🎯 TP6: {trade.get('tp6')}
🎯 TP7: {trade.get('tp7')}
🎯 TP8: {trade.get('tp8')}

✅ Pattern:
- Bear impulse confermato
- Relief rally confermato
- Lower high armato
- Continuazione bearish confermata

📊 State Memory:
- Impulse high: {round(to_float(state.get('impulse_high')), 3)}
- Impulse low: {round(to_float(state.get('impulse_low')), 3)}
- Drop: {round(to_float(state.get('impulse_drop')), 2)} punti
- Rally peak: {round(to_float(state.get('rally_peak')), 3)}
- Relief retrace: {round(to_float(state.get('relief_retrace')), 2)}
- Prezzo conferma: {round(get_price_from_data(data), 3)}

⚡ Il SELL è stato generato dal Python senza aspettare un SELL del Pine.
"""


def process_bear_continuation_state_machine(data):
    result = {
        "triggered": False,
        "trade_id": None,
        "state": "IDLE",
        "reason": ""
    }

    if not BEAR_CONTINUATION_ENGINE_ENABLED:
        result["reason"] = "Bear continuation engine disattivato"
        return result

    symbol = str(data.get("symbol", "XAUUSD")).upper()
    history = record_price_history(data)
    state = get_bear_continuation_state(symbol)

    price = get_price_from_data(data)
    bar_high = to_float(data.get("high"), price)
    bar_low = to_float(data.get("low"), price)
    previous_price = to_float(state.get("last_price"), 0)

    if price:
        state["last_price"] = price

    # Timeout dello stato.
    if (
        state.get("state") != "IDLE"
        and state.get("updated", 0)
        and now_ts() - state.get("updated", 0) > BEAR_STATE_TIMEOUT_SECONDS
    ):
        state = reset_bear_continuation_state(symbol, "Timeout bearish state")

    # Nuovo impulso rilevabile in IDLE oppure dopo un vecchio trigger.
    impulse = detect_recent_bear_impulse(data)

    if state.get("state") in ["IDLE", "SELL_TRIGGERED"] and impulse:
        state = set_bear_continuation_state(
            symbol,
            "BEAR_IMPULSE",
            f"Impulso bearish {round(impulse.get('drop', 0), 2)} punti"
        )
        state["impulse_high"] = impulse.get("peak_high")
        state["impulse_high_time"] = impulse.get("peak_time")
        state["impulse_low"] = impulse.get("impulse_low")
        state["impulse_low_time"] = impulse.get("impulse_low_time")
        state["impulse_drop"] = impulse.get("drop")
        state["rally_peak"] = 0
        state["rally_peak_time"] = 0
        state["relief_retrace"] = 0

    # Aggiorna nuovi minimi durante impulso/rally.
    if state.get("state") in ["BEAR_IMPULSE", "RELIEF_RALLY", "LOWER_HIGH_ARMED"]:
        if not state.get("impulse_low") or bar_low < state.get("impulse_low"):
            state["impulse_low"] = bar_low
            state["impulse_low_time"] = now_ts()
            state["impulse_drop"] = max(
                0,
                to_float(state.get("impulse_high")) - bar_low
            )

            # Nuovo minimo dopo un rally = nuova espansione, si riparte da BEAR_IMPULSE.
            if state.get("state") != "BEAR_IMPULSE":
                state = set_bear_continuation_state(
                    symbol,
                    "BEAR_IMPULSE",
                    "Nuovo minimo: continuazione bearish ancora in espansione"
                )
                state["rally_peak"] = 0
                state["rally_peak_time"] = 0
                state["relief_retrace"] = 0

    impulse_high = to_float(state.get("impulse_high"), 0)
    impulse_low = to_float(state.get("impulse_low"), 0)
    impulse_range = max(0, impulse_high - impulse_low)

    # Invalidation: recupero completo sopra il massimo dell'impulso.
    if (
        state.get("state") in ["BEAR_IMPULSE", "RELIEF_RALLY", "LOWER_HIGH_ARMED"]
        and impulse_high
        and price >= impulse_high
    ):
        state = reset_bear_continuation_state(
            symbol,
            "Invalidato: prezzo ha recuperato il massimo impulso"
        )
        result["state"] = state.get("state")
        result["reason"] = state.get("reason")
        return result

    # 1) BEAR_IMPULSE -> RELIEF_RALLY
    if state.get("state") == "BEAR_IMPULSE" and impulse_range > 0:
        bounce = max(0, price - impulse_low)
        retrace = bounce / impulse_range

        if (
            bounce >= BEAR_RELIEF_MIN_POINTS
            and retrace >= BEAR_RELIEF_MIN_RETRACE
            and retrace <= BEAR_RELIEF_MAX_RETRACE
        ):
            state = set_bear_continuation_state(
                symbol,
                "RELIEF_RALLY",
                f"Relief rally {round(bounce, 2)} punti / retrace {round(retrace, 2)}"
            )
            state["rally_peak"] = max(price, bar_high)
            state["rally_peak_time"] = now_ts()
            state["relief_retrace"] = retrace

    # 2) RELIEF_RALLY -> LOWER_HIGH_ARMED
    if state.get("state") == "RELIEF_RALLY" and impulse_range > 0:
        current_peak = max(price, bar_high)

        if current_peak > to_float(state.get("rally_peak"), 0):
            state["rally_peak"] = current_peak
            state["rally_peak_time"] = now_ts()

        rally_peak = to_float(state.get("rally_peak"), 0)
        retrace = (rally_peak - impulse_low) / impulse_range if impulse_range else 0
        lower_high_gap = impulse_high - rally_peak

        state["relief_retrace"] = retrace

        if retrace > BEAR_RELIEF_MAX_RETRACE:
            state = reset_bear_continuation_state(
                symbol,
                f"Relief rally troppo profondo: retrace {round(retrace, 2)}"
            )
        elif (
            retrace >= BEAR_RELIEF_MIN_RETRACE
            and retrace <= BEAR_RELIEF_MAX_RETRACE
            and lower_high_gap >= BEAR_LOWER_HIGH_MIN_GAP
            and now_ts() - state.get("impulse_low_time", 0) >= BEAR_CONTINUATION_MIN_SECONDS
        ):
            state = set_bear_continuation_state(
                symbol,
                "LOWER_HIGH_ARMED",
                (
                    f"Lower high armato: rally peak {round(rally_peak, 2)}, "
                    f"gap {round(lower_high_gap, 2)}"
                )
            )

    # 3) LOWER_HIGH_ARMED -> SELL_TRIGGERED
    if state.get("state") == "LOWER_HIGH_ARMED":
        current_peak = max(price, bar_high)

        # Il rally può migliorare leggermente, purché resti lower high valido.
        if current_peak > to_float(state.get("rally_peak"), 0):
            state["rally_peak"] = current_peak
            state["rally_peak_time"] = now_ts()

        rally_peak = to_float(state.get("rally_peak"), 0)
        lower_high_gap = impulse_high - rally_peak if impulse_high else 0

        if lower_high_gap < BEAR_LOWER_HIGH_MIN_GAP:
            state = reset_bear_continuation_state(
                symbol,
                "Lower high invalidato: rally troppo vicino/sopra impulso high"
            )
        else:
            failure_points = max(0, rally_peak - price)

            stability_age = (
                now_ts() - to_float(state.get("rally_peak_time"), 0)
                if state.get("rally_peak_time")
                else 0
            )
            stability_ok = (
                stability_age >= BEAR_RALLY_PEAK_STABILITY_SECONDS
            )

            failure_threshold = effective_failure_threshold(
                data,
                BEAR_CONTINUATION_FAILURE_POINTS,
                BEAR_CONTINUATION_FAILURE_MIN_POINTS,
                BEAR_CONTINUATION_FAILURE_ATR_MULT,
                BEAR_CONTINUATION_DYNAMIC_FAILURE_ENABLED
            )
            failure_ok = failure_points >= failure_threshold

            confirmation_ctx = bearish_confirmation_details(
                data,
                previous_price=previous_price
            )
            confirmations_ok = (
                confirmation_ctx.get("count", 0)
                >= BEAR_CONTINUATION_MIN_CONFIRMATIONS
            )

            micro_bos_ctx = micro_bos_bear_context(symbol, data)
            micro_bos_ok = (
                micro_bos_ctx.get("confirmed")
                or not BEAR_CONTINUATION_MICRO_BOS_REQUIRED
            )

            warmup_ctx = warmup_status(symbol)
            warmup_ok = (
                warmup_ctx.get("warm")
                or not STATE_WARMUP_BLOCK_AUTONOMOUS
            )

            mature_trigger = (
                stability_ok
                and failure_ok
                and confirmations_ok
                and micro_bos_ok
                and warmup_ok
            )

            if not mature_trigger:
                state["reason"] = (
                    f"Lower high armato ma trigger non maturo | "
                    f"stability {round(stability_age, 1)}/{BEAR_RALLY_PEAK_STABILITY_SECONDS}s | "
                    f"failure {round(failure_points, 2)}/{round(failure_threshold, 2)} | "
                    f"confirm {confirmation_ctx.get('count', 0)}/{BEAR_CONTINUATION_MIN_CONFIRMATIONS} | "
                    f"microBOS {micro_bos_ctx.get('confirmed')} | "
                    f"warm {warmup_ctx.get('warm')}"
                )

            if mature_trigger:
                deep_ctx = get_deep_extension_context(symbol, data)
                if (
                    deep_ctx.get("active")
                    and deep_ctx.get("rebound_from_low", 0) < DEEP_EXTENSION_REARM_REBOUND_POINTS
                ):
                    state["reason"] = (
                        "Synthetic bear SELL bloccato da Deep Extension Flip: "
                        "prezzo troppo vicino al minimo dopo drop già pagato"
                    )
                    result["state"] = state.get("state")
                    result["reason"] = state.get("reason")
                    return result

                duplicate, duplicate_trade = has_recent_bear_synthetic_sell(symbol)

                synthetic_data, risk_error = build_bear_synthetic_sell_data(
                    data,
                    state
                )

                campaign_decision = evaluate_campaign_leg(
                    "SELL",
                    symbol,
                    "SYNTHETIC_BEAR_CONTINUATION_SELL",
                    BEAR_SYNTHETIC_SCORE,
                    synthetic_data or data
                )

                arbiter_block, arbiter_ctx, arbiter_reason = should_block_by_regime_arbiter(
                    "SELL",
                    symbol,
                    "SYNTHETIC_BEAR_CONTINUATION_SELL",
                    BEAR_SYNTHETIC_SCORE,
                    synthetic_data or data
                )
                if arbiter_block:
                    state["reason"] = f"Regime Arbiter blocca synthetic SELL: {arbiter_reason}"
                    result["state"] = state.get("state")
                    result["reason"] = state.get("reason")
                    return result

                if duplicate and not campaign_decision.get("allow"):
                    state["reason"] = (
                        f"Trigger bear già presente: trade {duplicate_trade.get('id')}"
                    )
                elif BEAR_SYNTHETIC_SELL_ENABLED:


                    if risk_error:
                        state["reason"] = (
                            f"Lower high confermato ma trade non creato: {risk_error}"
                        )
                    else:
                        # Safety 1: Kill Switch con override campaign controllato.
                        chaos_ctx = get_chaos_context(symbol, synthetic_data)
                        kill_block = bool(chaos_ctx.get("kill"))

                        if (
                            kill_block
                            and not (
                                campaign_decision.get("allow")
                                and campaign_decision.get("kill_override")
                            )
                        ):
                            state["reason"] = (
                                "Lower high confermato ma Daily Kill Switch attivo"
                            )
                        else:
                            # Safety 2: SELL SL cooldown con massimo un override campaign.
                            block_sl_cooldown, recent_sell_losses = should_block_by_sl_cooldown(
                                "SELL",
                                symbol
                            )

                            sl_override, sl_decision = campaign_sl_override_eligible(
                                "SELL",
                                symbol,
                                "SYNTHETIC_BEAR_CONTINUATION_SELL",
                                BEAR_SYNTHETIC_SCORE,
                                synthetic_data
                            )

                            if block_sl_cooldown and not sl_override:
                                state["reason"] = (
                                    f"Lower high confermato ma SELL SL cooldown attivo "
                                    f"({len(recent_sell_losses)} SL diretti recenti)"
                                )
                            else:
                                if sl_override:
                                    campaign_decision = sl_decision

                                # Safety 3: un SELL recente è ammesso solo come nuova campaign leg qualificata.
                                recent_same_sell = find_recent_same_trade(
                                    "SELL",
                                    symbol
                                )

                                if recent_same_sell and not campaign_decision.get("allow"):
                                    state["reason"] = (
                                        f"Lower high confermato ma SELL recente già attivo "
                                        f"(trade {recent_same_sell.get('id')})"
                                    )
                                else:
                                    trade, error = save_bear_synthetic_sell_trade(
                                        data,
                                        state
                                    )

                                    if error:
                                        state["reason"] = (
                                            f"Errore synthetic bear SELL: {error}"
                                        )
                                    else:
                                        if campaign_decision.get("allow"):
                                            register_campaign_leg(
                                                trade,
                                                campaign_decision
                                            )

                                        state["last_trigger_time"] = now_ts()
                                        state["last_trigger_trade_id"] = trade.get("id")
                                        state = set_bear_continuation_state(
                                            symbol,
                                            "SELL_TRIGGERED",
                                            (
                                                f"Bear continuation matura: "
                                                f"failure {round(failure_points, 2)}/{round(failure_threshold, 2)}, "
                                                f"stability {round(stability_age, 1)}s, "
                                                f"confirm {confirmation_ctx.get('count', 0)}, "
                                                f"microBOS {micro_bos_ctx.get('confirmed')}"
                                            )
                                        )

                                        send_telegram(
                                            bear_synthetic_sell_message(
                                                trade,
                                                state,
                                                data
                                            )
                                        )

                                        result["triggered"] = True
                                        result["trade_id"] = trade.get("id")

    result["state"] = state.get("state")
    result["reason"] = state.get("reason")
    return result


def bear_state_blocks_dip_buy(symbol):
    state = get_bear_continuation_state(symbol)
    return state.get("state") in [
        "BEAR_IMPULSE",
        "RELIEF_RALLY",
        "LOWER_HIGH_ARMED",
        "SELL_TRIGGERED"
    ]


def should_block_buy_by_bear_state(signal, symbol, setup_type, score, data):
    state = get_bear_continuation_state(symbol)

    if not BEAR_CONTINUATION_ENGINE_ENABLED:
        return False, state, "Bear engine disattivato"

    if not BEAR_BLOCK_BUYS_ENABLED:
        return False, state, "Bear BUY block disattivato"

    if str(signal).upper() != "BUY":
        return False, state, "Non è BUY"

    active_states = [
        "BEAR_IMPULSE",
        "RELIEF_RALLY",
        "LOWER_HIGH_ARMED",
        "SELL_TRIGGERED"
    ]

    if state.get("state") not in active_states:
        return False, state, "Bear state non attivo"

    setup_type = str(setup_type).upper()

    # Eccezione molto selettiva: vero recovery BUY da zona bassa con score alto.
    if BEAR_ALLOW_STRONG_RECOVERY_BUY and setup_type == "MAX_RECOVERY_BUY":
        near_day_low = to_bool(data.get("near_day_low", "false"))
        near_m15_low = to_bool(data.get("near_m15_low", "false"))
        candle_bull = str(data.get("candle_dir", "")).upper() == "BULL"
        lower_rejection = (
            str(data.get("rejection", "")).upper() == "LOWER_WICK"
            or to_bool(data.get("lower_wick_strong", "false"))
        )
        reclaimed_ema20 = to_bool(data.get("close_above_ema20", "false"))

        strong_recovery = (
            int(score) >= BEAR_STRONG_RECOVERY_MIN_SCORE
            and (near_day_low or near_m15_low)
            and candle_bull
            and (lower_rejection or reclaimed_ema20)
        )

        if strong_recovery:
            return False, state, "Recovery BUY eccezionale ammesso"

    # v32: se il server ha promosso il BUY a DEEP_REBOUND_BUY, non bloccarlo
    # solo perché la lower-high machine è ancora bearish.
    if setup_type == "DEEP_REBOUND_BUY":
        deep_rebound_ctx = deep_rebound_buy_candidate_context(signal, symbol, data)
        if deep_rebound_ctx.get("allow"):
            return False, state, deep_rebound_ctx.get("reason")

    if setup_type == "MAX_PULLBACK_REARM_BUY":
        rearm_ctx = max_pullback_rearm_buy_context(signal, symbol, data)
        if rearm_ctx.get("allow"):
            return False, state, "Bear state declassato: Max Pullback Re-Arm BUY confermato"

    rebound_ctx = post_sell_rebound_unlock_context(signal, symbol, setup_type, score, data)
    if rebound_ctx.get("allow"):
        return False, state, rebound_ctx.get("reason")

    if setup_type == "MAX_DIP_BUY" and BEAR_BLOCK_MAX_DIP_BUY:
        return True, state, "MAX_DIP_BUY bloccato dentro bearish continuation"

    if setup_type == "REVERSAL_BUY" and BEAR_BLOCK_REVERSAL_BUY:
        return True, state, "REVERSAL_BUY bloccato dentro bearish continuation"

    # Durante LOWER_HIGH_ARMED / SELL_TRIGGERED blocco qualsiasi BUY.
    if state.get("state") in ["LOWER_HIGH_ARMED", "SELL_TRIGGERED"]:
        return True, state, "BUY bloccato: lower high / SELL continuation attivo"

    # Durante impulso/rally blocco anche BUY normali.
    if setup_type == "NORMAL":
        return True, state, "BUY NORMAL bloccato durante bearish impulse/relief rally"

    return False, state, "Setup BUY non bloccato"



# =========================
# EVENT STATE MACHINE + SYNTHETIC SELL v20
# =========================

def _new_event_state():
    return {
        "state": "IDLE",
        "symbol": "",
        "updated": 0,
        "updated_local": "",
        "retest_armed_at": 0,
        "retest_peak": 0,
        "retest_peak_time": 0,
        "last_price": 0,
        "last_trigger_time": 0,
        "last_trigger_trade_id": None,
        "reason": "Nessun pattern evento attivo"
    }


def get_event_state(symbol):
    symbol = str(symbol or "XAUUSD").upper()

    if symbol not in EVENT_STATE_MACHINE:
        EVENT_STATE_MACHINE[symbol] = _new_event_state()
        EVENT_STATE_MACHINE[symbol]["symbol"] = symbol

    return EVENT_STATE_MACHINE[symbol]


def set_event_state(symbol, new_state, reason):
    state = get_event_state(symbol)
    state["state"] = new_state
    state["reason"] = reason
    state["updated"] = now_ts()
    state["updated_local"] = local_datetime().strftime("%Y-%m-%d %H:%M:%S")
    return state


def event_state_status_text(symbol):
    state = get_event_state(symbol)

    return (
        f"State: {state.get('state')}\n"
        f"Reason: {state.get('reason')}\n"
        f"Retest peak: {round(to_float(state.get('retest_peak')), 3)}\n"
        f"Armed at: {state.get('retest_armed_at')}\n"
        f"Last trigger trade: {state.get('last_trigger_trade_id') or 'N/D'}"
    )


def has_recent_synthetic_sell(symbol):
    symbol = str(symbol).upper()
    now = now_ts()

    for trade in OPEN_TRADES:
        if str(trade.get("symbol", "")).upper() != symbol:
            continue

        if trade.get("setup_type") != "SYNTHETIC_FAILED_RETEST_SELL":
            continue

        created = trade.get("created") or 0

        if trade.get("status") in ["PENDING", "OPEN"]:
            return True, trade

        if now - created <= SYNTHETIC_RETEST_COOLDOWN_SECONDS:
            return True, trade

    return False, None


def build_synthetic_sell_data(data, ctx, state):
    price = get_price_from_data(data)

    if not price:
        return None, "Prezzo non disponibile"

    event_high = to_float(ctx.get("high"), 0)
    entry_low = price - SYNTHETIC_RETEST_ENTRY_HALF_ZONE
    entry_high = price + SYNTHETIC_RETEST_ENTRY_HALF_ZONE

    sl_by_high = event_high + SYNTHETIC_RETEST_HIGH_SL_BUFFER if event_high else 0
    sl_by_min_distance = price + SYNTHETIC_RETEST_MIN_SL_DISTANCE
    sl = max(sl_by_high, sl_by_min_distance)

    risk = sl - price

    if risk <= 0:
        return None, "Rischio sintetico non valido"

    if risk > SYNTHETIC_RETEST_MAX_RISK_POINTS:
        return None, (
            f"Rischio troppo largo: {round(risk, 2)} > "
            f"{SYNTHETIC_RETEST_MAX_RISK_POINTS}"
        )

    tp_distances = [
        SYNTHETIC_RETEST_TP1,
        SYNTHETIC_RETEST_TP2,
        SYNTHETIC_RETEST_TP3,
        SYNTHETIC_RETEST_TP4,
        SYNTHETIC_RETEST_TP5,
        SYNTHETIC_RETEST_TP6,
        SYNTHETIC_RETEST_TP7,
        SYNTHETIC_RETEST_TP8
    ]

    out = {
        "signal": "SELL",
        "symbol": data.get("symbol", "XAUUSD"),
        "price": price,
        "tf": data.get("tf", ""),
        "entry_low": round(entry_low, 3),
        "entry_high": round(entry_high, 3),
        "sl": round(sl, 3),
        "synthetic_source": "PRICE_UPDATE_STATE_MACHINE"
    }

    for i, dist in enumerate(tp_distances, start=1):
        out[f"tp{i}"] = round(price - dist, 3)

    return out, None


def save_synthetic_sell_trade(data, ctx, state):
    synthetic_data, error = build_synthetic_sell_data(data, ctx, state)

    if error:
        return None, error

    trade = save_trade(
        synthetic_data,
        "SELL",
        SYNTHETIC_RETEST_SCORE,
        "SYNTHETIC_FAILED_RETEST_SELL"
    )

    # Il pattern è confermato sul close del PRICE_UPDATE:
    # considero il trade attivato al prezzo di conferma, senza attendere un nuovo segnale Pine.
    trade["status"] = "OPEN"
    trade["entered"] = True
    trade["activated"] = now_ts()
    trade["activated_local"] = local_datetime().strftime("%Y-%m-%d %H:%M:%S")
    trade["synthetic"] = True
    trade["synthetic_source"] = "PRICE_UPDATE_STATE_MACHINE"
    trade["event_anchor"] = ctx.get("start_price")
    trade["event_high"] = ctx.get("high")
    trade["event_pullback"] = ctx.get("max_pullback_after_high")
    trade["event_top_position"] = ctx.get("top_position")
    trade["event_retest_peak"] = state.get("retest_peak")
    save_trades()

    return trade, None


def synthetic_sell_message(trade, ctx, state, data):
    return f"""🤖🔴 GOLD SELL AUTONOMO {VERSION}

🆔 Trade ID: {trade.get('id')}
📌 Setup: SYNTHETIC_FAILED_RETEST_SELL
🧠 Origine: Python Event State Machine
📍 Entry Zone: {trade.get('entry_low')} - {trade.get('entry_high')}
🛑 SL: {trade.get('sl')}
🎯 TP1: {trade.get('tp1')}
🎯 TP2: {trade.get('tp2')}
🎯 TP3: {trade.get('tp3')}
🎯 TP4: {trade.get('tp4')}
🎯 TP5: {trade.get('tp5')}
🎯 TP6: {trade.get('tp6')}
🎯 TP7: {trade.get('tp7')}
🎯 TP8: {trade.get('tp8')}

✅ Pattern:
- Spike evento confermato
- Pullback confermato
- Retest alto armato
- Retest fallito con conferma bearish

📊 Event Memory:
- Anchor: {round(to_float(ctx.get('start_price')), 3)}
- High: {round(to_float(ctx.get('high')), 3)}
- Spike up: {round(to_float(ctx.get('up_points')), 2)} punti
- Pullback dopo high: {round(to_float(ctx.get('max_pullback_after_high')), 2)} punti
- Top position: {round(to_float(ctx.get('top_position')), 2)}
- Retest peak: {round(to_float(state.get('retest_peak')), 3)}
- Prezzo conferma: {round(get_price_from_data(data), 3)}

⚡ Il SELL è stato generato dal Python senza aspettare un segnale SELL del Pine.
"""


def process_event_state_machine(data):
    result = {
        "triggered": False,
        "trade_id": None,
        "state": "IDLE",
        "reason": ""
    }

    if not SYNTHETIC_RETEST_ENGINE_ENABLED:
        result["reason"] = "Synthetic engine disattivato"
        return result

    symbol = str(data.get("symbol", "XAUUSD")).upper()
    state = get_event_state(symbol)
    ctx = get_event_spike_context(data)
    price = get_price_from_data(data)
    bar_high = to_float(data.get("high"), price)
    bar_low = to_float(data.get("low"), price)
    bar_open = to_float(data.get("open"), 0)
    candle_dir = str(data.get("candle_dir", "")).upper()
    rejection = str(data.get("rejection", "")).upper()
    upper_wick_strong = to_bool(data.get("upper_wick_strong", "false"))
    previous_price = to_float(state.get("last_price"), 0)

    if price:
        state["last_price"] = price

    # Evento non attivo o spike insufficiente: reset logico.
    spike_ok = (
        ctx.get("active")
        and ctx.get("age", 999999) <= EVENT_SPIKE_LOOKBACK_SECONDS
        and ctx.get("up_points", 0) >= SYNTHETIC_RETEST_SPIKE_MIN_UP_POINTS
    )

    if not spike_ok:
        if state.get("state") != "SELL_TRIGGERED":
            set_event_state(symbol, "IDLE", "Evento/spike non abbastanza forte")
            state["retest_armed_at"] = 0
            state["retest_peak"] = 0
            state["retest_peak_time"] = 0

        result["state"] = state.get("state")
        result["reason"] = state.get("reason")
        return result

    # 1) SPIKE_UP
    if state.get("state") in ["IDLE", "SELL_TRIGGERED"]:
        # Dopo un trigger, un nuovo massimo resetta il ciclo.
        if (
            state.get("state") == "IDLE"
            or ctx.get("high_time", 0) > state.get("last_trigger_time", 0)
        ):
            set_event_state(
                symbol,
                "SPIKE_UP",
                f"Spike up {round(ctx.get('up_points', 0), 2)} punti"
            )
            state["retest_armed_at"] = 0
            state["retest_peak"] = 0
            state["retest_peak_time"] = 0

    # 2) PULLBACK_CONFIRMED
    pullback_ok = ctx.get("max_pullback_after_high", 0) >= SYNTHETIC_RETEST_PULLBACK_POINTS

    if pullback_ok and state.get("state") == "SPIKE_UP":
        set_event_state(
            symbol,
            "PULLBACK_CONFIRMED",
            f"Pullback {round(ctx.get('max_pullback_after_high', 0), 2)} punti"
        )

    # 3) RETEST_ARMED
    retest_zone_ok = (
        pullback_ok
        and ctx.get("top_position", 0) >= SYNTHETIC_RETEST_ARM_POSITION_MIN
        and ctx.get("top_position", 0) <= SYNTHETIC_RETEST_ARM_POSITION_MAX
        and ctx.get("retrace_from_high", 999999) <= SYNTHETIC_RETEST_NEAR_HIGH_DISTANCE
        and ctx.get("seconds_after_high", 0) >= SYNTHETIC_RETEST_MIN_SECONDS_AFTER_HIGH
    )

    if retest_zone_ok and state.get("state") in ["PULLBACK_CONFIRMED", "RETEST_ARMED"]:
        if state.get("state") != "RETEST_ARMED":
            set_event_state(
                symbol,
                "RETEST_ARMED",
                "Prezzo tornato in zona retest alta dopo pullback"
            )
            state["retest_armed_at"] = now_ts()
            state["retest_peak"] = max(price, bar_high)
            state["retest_peak_time"] = now_ts()
        else:
            current_peak = max(price, bar_high)
            if current_peak > to_float(state.get("retest_peak"), 0):
                state["retest_peak"] = current_peak
                state["retest_peak_time"] = now_ts()

    # Se il retest produce un nuovo massimo evento, il ciclo torna SPIKE_UP.
    if (
        state.get("state") == "RETEST_ARMED"
        and ctx.get("high_time", 0) > state.get("retest_armed_at", 0)
        and ctx.get("max_pullback_after_high", 0) < SYNTHETIC_RETEST_PULLBACK_POINTS
    ):
        set_event_state(symbol, "SPIKE_UP", "Nuovo massimo: retest invalidato")
        state["retest_armed_at"] = 0
        state["retest_peak"] = 0
        state["retest_peak_time"] = 0

    # 4) FAILED RETEST CONFIRMATION v24: trigger maturo
    if state.get("state") == "RETEST_ARMED":
        retest_peak = to_float(state.get("retest_peak"), 0)
        failure_points = max(0, retest_peak - price) if retest_peak and price else 0

        stability_age = (
            now_ts() - to_float(state.get("retest_peak_time"), 0)
            if state.get("retest_peak_time")
            else 0
        )
        stability_ok = (
            stability_age >= SYNTHETIC_RETEST_PEAK_STABILITY_SECONDS
        )

        failure_threshold = effective_failure_threshold(
            data,
            SYNTHETIC_RETEST_FAILURE_POINTS,
            SYNTHETIC_RETEST_FAILURE_MIN_POINTS,
            SYNTHETIC_RETEST_FAILURE_ATR_MULT,
            SYNTHETIC_RETEST_DYNAMIC_FAILURE_ENABLED
        )
        failure_ok = failure_points >= failure_threshold

        confirmation_ctx = bearish_confirmation_details(
            data,
            previous_price=previous_price
        )
        confirmations_ok = (
            confirmation_ctx.get("count", 0)
            >= SYNTHETIC_RETEST_MIN_CONFIRMATIONS
        )

        micro_bos_ctx = micro_bos_bear_context(symbol, data)
        micro_bos_ok = (
            micro_bos_ctx.get("confirmed")
            or not SYNTHETIC_RETEST_MICRO_BOS_REQUIRED
        )

        warmup_ctx = warmup_status(symbol)
        warmup_ok = (
            warmup_ctx.get("warm")
            or not STATE_WARMUP_BLOCK_AUTONOMOUS
        )

        mature_trigger = (
            stability_ok
            and failure_ok
            and (
                confirmations_ok
                or not SYNTHETIC_RETEST_REQUIRE_BEAR_CONFIRMATION
            )
            and micro_bos_ok
            and warmup_ok
        )

        if not mature_trigger:
            state["reason"] = (
                f"Retest armato ma trigger non maturo | "
                f"stability {round(stability_age, 1)}/{SYNTHETIC_RETEST_PEAK_STABILITY_SECONDS}s | "
                f"failure {round(failure_points, 2)}/{round(failure_threshold, 2)} | "
                f"confirm {confirmation_ctx.get('count', 0)}/{SYNTHETIC_RETEST_MIN_CONFIRMATIONS} | "
                f"microBOS {micro_bos_ctx.get('confirmed')} | "
                f"warm {warmup_ctx.get('warm')}"
            )

        if mature_trigger:
            duplicate, duplicate_trade = has_recent_synthetic_sell(symbol)

            if duplicate:
                set_event_state(
                    symbol,
                    "SELL_TRIGGERED",
                    f"Trigger già presente: trade {duplicate_trade.get('id')}"
                )
                result["state"] = state.get("state")
                result["reason"] = state.get("reason")
                return result

            synthetic_data, risk_error = build_synthetic_sell_data(data, ctx, state)

            if risk_error:
                state["reason"] = f"Failed retest confermato ma trade non creato: {risk_error}"
                result["state"] = state.get("state")
                result["reason"] = state.get("reason")
                return result

            # Safety 1: Daily Kill Switch resta sempre prioritario.
            chaos_ctx = get_chaos_context(symbol, synthetic_data)
            if chaos_ctx.get("kill"):
                state["reason"] = "Failed retest confermato ma Daily Kill Switch attivo"
                result["state"] = state.get("state")
                result["reason"] = state.get("reason")
                return result

            # Safety 2: rispetta il cooldown dopo SL diretti SELL.
            block_sl_cooldown, recent_sell_losses = should_block_by_sl_cooldown("SELL", symbol)
            if block_sl_cooldown:
                state["reason"] = (
                    f"Failed retest confermato ma SELL SL cooldown attivo "
                    f"({len(recent_sell_losses)} SL diretti recenti)"
                )
                result["state"] = state.get("state")
                result["reason"] = state.get("reason")
                return result

            # Safety 3: evita un secondo SELL se esiste già un SELL recente attivo.
            recent_same_sell = find_recent_same_trade("SELL", symbol)
            if recent_same_sell:
                state["reason"] = (
                    f"Failed retest confermato ma SELL recente già attivo "
                    f"(trade {recent_same_sell.get('id')})"
                )
                result["state"] = state.get("state")
                result["reason"] = state.get("reason")
                return result

            trade, error = save_synthetic_sell_trade(data, ctx, state)

            if error:
                state["reason"] = f"Errore creazione synthetic SELL: {error}"
                result["state"] = state.get("state")
                result["reason"] = state.get("reason")
                return result

            state["last_trigger_time"] = now_ts()
            state["last_trigger_trade_id"] = trade.get("id")
            set_event_state(
                symbol,
                "SELL_TRIGGERED",
                (
                    f"Failed retest maturo: "
                    f"failure {round(failure_points, 2)}/{round(failure_threshold, 2)}, "
                    f"stability {round(stability_age, 1)}s, "
                    f"confirm {confirmation_ctx.get('count', 0)}, "
                    f"microBOS {micro_bos_ctx.get('confirmed')}"
                )
            )

            send_telegram(synthetic_sell_message(trade, ctx, state, data))

            result["triggered"] = True
            result["trade_id"] = trade.get("id")
            result["state"] = state.get("state")
            result["reason"] = state.get("reason")
            return result

    result["state"] = state.get("state")
    result["reason"] = state.get("reason")
    return result


def should_block_buy_by_synthetic_state(signal, symbol):
    if not SYNTHETIC_RETEST_ENGINE_ENABLED:
        return False, get_event_state(symbol)

    if not SYNTHETIC_RETEST_BLOCK_BUYS_WHEN_ARMED:
        return False, get_event_state(symbol)

    if str(signal).upper() != "BUY":
        return False, get_event_state(symbol)

    state = get_event_state(symbol)

    if state.get("state") in ["RETEST_ARMED", "SELL_TRIGGERED"]:
        return True, state

    return False, state



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

        if trade_is_stale_for_lock(trade):
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

        if trade_is_stale_for_lock(trade):
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


def should_block_sell_by_recovery_lock(signal, symbol, setup_type, score, data=None):
    if not RECOVERY_LOCK_ENABLED:
        return False, get_recovery_lock_context(symbol)

    if str(signal).upper() != "SELL":
        return False, get_recovery_lock_context(symbol)

    ctx = get_recovery_lock_context(symbol)

    if not ctx["active"]:
        return False, ctx

    setup_type = str(setup_type).upper()

    # v25: un MAX_RECOVERY_BUY TP3+ ancora valido domina anche sui setup
    # continuation/campaign.
    recovery_dominance = get_recovery_dominance_context(symbol, data or {})
    if recovery_dominance.get("active") and setup_type in RECOVERY_DOMINANCE_BLOCK_SELL_SETUPS:
        ctx["level"] = "RECOVERY_DOMINANT"
        ctx["reason"] = recovery_dominance.get("reason")
        ctx["best_trade"] = recovery_dominance.get("best_trade")
        return True, ctx

    # v38: se il BUY ha già pagato tanto e siamo nel top di uno spike evento,
    # l'Extreme Spike Fade SELL può superare il Recovery Lock. È il flip alto stile Max.
    if setup_type == "EXTREME_SPIKE_FADE_SELL" and int(score) >= EXTREME_SPIKE_FADE_BYPASS_RECOVERY_LOCK_SCORE:
        post_super_buy_ctx = get_post_super_buy_guard_context(
            "SELL",
            symbol,
            setup_type,
            score,
            data or {}
        )
        ctx["post_super_buy_guard"] = post_super_buy_ctx
        if post_super_buy_ctx.get("block"):
            ctx["level"] = "POST_SUPER_BUY_GUARD"
            ctx["reason"] = post_super_buy_ctx.get("reason")
            return True, ctx
        ctx["level"] = "EXTREME_SPIKE_FADE_OVERRIDE"
        ctx["reason"] = "Recovery Lock bypassato: BUY già pagato + top spike evento / failed retest"
        return False, ctx

    # v39: BEAR_CAMPAIGN/CONTINUATION non superano più il lock se il BUY TP8 è ancora fresco.
    post_super_buy_ctx = get_post_super_buy_guard_context(
        "SELL",
        symbol,
        setup_type,
        score,
        data or {}
    )
    ctx["post_super_buy_guard"] = post_super_buy_ctx
    if post_super_buy_ctx.get("block"):
        ctx["level"] = "POST_SUPER_BUY_GUARD"
        ctx["reason"] = post_super_buy_ctx.get("reason")
        return True, ctx

    # v23: failed recovery confermato può superare il Recovery Lock solo con score forte.
    if setup_type == "PRE_BEAR_SELL" and int(score) >= PRE_BEAR_SELL_MIN_SCORE:
        return False, ctx

    # Continuation SELL può superare un vecchio lock solo se non c'è Recovery Dominance.
    if setup_type in [
        "BEAR_CAMPAIGN_SELL",
        "BEAR_CONTINUATION_SELL",
        "SYNTHETIC_BEAR_CONTINUATION_SELL"
    ]:
        return False, ctx

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
# v30 CAMPAIGN LOCK / EXHAUSTION
# =========================

def _trade_age_reference(trade):
    return to_float(trade.get("last_tp_time") or trade.get("activated") or trade.get("created"), 0)


def _is_active_profit_trade(trade, min_tp=1):
    if trade.get("status") not in ["OPEN", "PENDING"]:
        return False
    if not bool(trade.get("be")):
        return False
    if int(trade.get("highest_tp", 0) or 0) < int(min_tp):
        return False
    return True


def campaign_profit_lock_context(signal, symbol, setup_type, score, data):
    """
    Stile Max: dopo TP1 + BE non si apre subito un trade contrario.
    Serve a evitare il caso: SELL TP1 -> immediato REVERSAL_BUY nella stessa zona.
    """
    ctx = {
        "enabled": CAMPAIGN_PROFIT_LOCK_ENABLED,
        "active": False,
        "allow": True,
        "reason": "inactive",
        "trade": None,
        "age_seconds": None,
        "price": get_price_from_data(data),
        "opposite_direction": None,
        "invalidation_level": None,
        "zone_ok": False
    }

    if not CAMPAIGN_PROFIT_LOCK_ENABLED:
        return ctx

    signal = normalize_signal(signal)
    symbol = str(symbol or "XAUUSD").upper()
    opposite = "SELL" if signal == "BUY" else "BUY"
    ctx["opposite_direction"] = opposite

    now = now_ts()
    best = None

    for trade in OPEN_TRADES:
        if str(trade.get("symbol", "")).upper() != symbol:
            continue
        if normalize_signal(trade.get("signal")) != opposite:
            continue
        if not _is_active_profit_trade(trade, CAMPAIGN_PROFIT_LOCK_MIN_TP):
            continue

        ref = _trade_age_reference(trade)
        age = now - ref if ref else 999999
        if age > CAMPAIGN_PROFIT_LOCK_SECONDS:
            continue

        if best is None:
            best = trade
        else:
            if int(trade.get("highest_tp", 0) or 0) > int(best.get("highest_tp", 0) or 0):
                best = trade
            elif ref > _trade_age_reference(best):
                best = trade

    if not best:
        ctx["reason"] = "no active opposite profit trade"
        return ctx

    ctx["active"] = True
    ctx["trade"] = best
    ctx["age_seconds"] = round(now - _trade_age_reference(best), 1)

    price = ctx["price"]
    day_position = to_float(data.get("day_position"), 0.5)
    upper_wick = to_bool(data.get("upper_wick_strong")) or str(data.get("rejection", "")).upper() == "UPPER_WICK"
    lower_wick = to_bool(data.get("lower_wick_strong")) or str(data.get("rejection", "")).upper() == "LOWER_WICK"
    micro_bos_bear = to_bool(data.get("micro_bos_bear"))
    micro_bos_bull = to_bool(data.get("micro_bos_bull")) or to_bool(data.get("micro_bos_buy"))

    if signal == "BUY":
        # BUY contro SELL già in profitto: serve vera invalidazione sopra entry SELL.
        invalidation = to_float(best.get("entry_high"), 0) + CAMPAIGN_PROFIT_LOCK_INVALIDATION_POINTS
        ctx["invalidation_level"] = round(invalidation, 3)
        invalidated = bool(price and price >= invalidation)
        rebound_ctx = post_sell_rebound_unlock_context(signal, symbol, setup_type, score, data)
        ctx["post_sell_rebound"] = rebound_ctx
        exceptional_recovery = (
            setup_type in CAMPAIGN_PROFIT_LOCK_BUY_AFTER_SELL_ALLOW_SETUPS
            and int(score) >= CAMPAIGN_PROFIT_LOCK_ALLOW_SCORE
            and (invalidated or lower_wick or micro_bos_bull)
        )
        if invalidated or exceptional_recovery or rebound_ctx.get("allow"):
            ctx["allow"] = True
            ctx["reason"] = (
                rebound_ctx.get("reason")
                if rebound_ctx.get("allow")
                else "SELL campaign invalidata: BUY eccezionale ammesso"
            )
            return ctx
        ctx["allow"] = False
        ctx["reason"] = "SELL già a TP/BE: blocco BUY contrario immediato"
        return ctx

    if signal == "SELL":
        # SELL contro BUY già in profitto: passa solo da vera zona Max oppure se il BUY è invalidato.
        invalidation = to_float(best.get("entry_low"), 0) - CAMPAIGN_PROFIT_LOCK_INVALIDATION_POINTS
        ctx["invalidation_level"] = round(invalidation, 3)
        invalidated = bool(price and price <= invalidation)
        zone_ok = day_position >= 0.65 or upper_wick or micro_bos_bear
        ctx["zone_ok"] = zone_ok
        special_ctx = get_recovery_dominance_context(symbol, data, min_tp=SPECIAL_BUY_FLIP_MIN_BUY_TP)
        flip_ctx = special_buy_flip_window_context(symbol, setup_type, score, data, special_ctx=special_ctx)
        ctx["special_buy_flip_window"] = flip_ctx
        strong_max_sell = (
            setup_type in CAMPAIGN_PROFIT_LOCK_SELL_AFTER_BUY_ALLOW_SETUPS
            and int(score) >= CAMPAIGN_PROFIT_LOCK_ALLOW_SCORE
            and zone_ok
        )
        if invalidated or strong_max_sell or flip_ctx.get("allow"):
            ctx["allow"] = True
            ctx["reason"] = (
                flip_ctx.get("reason")
                if flip_ctx.get("allow")
                else "BUY campaign stanca/invalidata: SELL Max ammesso"
            )
            return ctx
        ctx["allow"] = False
        ctx["reason"] = "BUY già a TP/BE: blocco SELL contrario non abbastanza Max"
        return ctx

    return ctx


def campaign_profit_lock_text(ctx):
    if not ctx or not ctx.get("active"):
        return "Campaign Profit Lock: non attivo"
    trade = ctx.get("trade") or {}
    return (
        f"Campaign Profit Lock ATTIVO\n"
        f"- Trade protetto: {trade.get('signal')} #{trade.get('id')}\n"
        f"- Setup: {trade.get('setup_type', 'N/D')}\n"
        f"- Highest TP: {trade.get('highest_tp', 0)}\n"
        f"- BE: {trade.get('be', False)}\n"
        f"- Entry: {trade.get('entry_low')} - {trade.get('entry_high')}\n"
        f"- Età dal TP/attivazione: {ctx.get('age_seconds')} sec\n"
        f"- Livello invalidazione: {ctx.get('invalidation_level')}\n"
        f"- Motivo: {ctx.get('reason')}"
    )


def should_block_by_campaign_profit_lock(signal, symbol, setup_type, score, data):
    ctx = campaign_profit_lock_context(signal, symbol, setup_type, score, data)
    return bool(ctx.get("active") and not ctx.get("allow")), ctx


def recent_buy_campaign_winners(symbol):
    symbol = str(symbol or "XAUUSD").upper()
    cutoff = now_ts() - BUY_CAMPAIGN_EXHAUSTION_LOOKBACK_SECONDS
    winners = []
    for trade in OPEN_TRADES:
        if str(trade.get("symbol", "")).upper() != symbol:
            continue
        if normalize_signal(trade.get("signal")) != "BUY":
            continue
        if int(trade.get("highest_tp", 0) or 0) < BUY_CAMPAIGN_EXHAUSTION_MIN_TP:
            continue
        created = to_float(trade.get("created"), 0)
        last_tp = to_float(trade.get("last_tp_time") or created, 0)
        if max(created, last_tp) < cutoff:
            continue
        winners.append(trade)
    return sorted(winners, key=lambda t: int(t.get("highest_tp", 0) or 0), reverse=True)


def max_pullback_rearm_buy_context(signal, symbol, data=None):
    """
    v36:
    BUY re-arm dopo una campagna BUY già pagata.
    Caso reale: il bot aveva BUY vincenti, poi il pullback è stato letto come SELL_CONTROL.
    Qui serve capire se è solo ricarica/pullback e non vero cambio bearish.
    """
    data = data or {}
    symbol = str(symbol or "XAUUSD").upper()
    signal = normalize_signal(signal)

    ctx = {
        "allow": False,
        "active": False,
        "reason": "non valutato",
        "reasons": [],
        "confirmations": 0,
        "required_confirmations": MAX_PULLBACK_REARM_MIN_CONFIRMATIONS,
        "winners": []
    }

    if not MAX_PULLBACK_REARM_ENABLED:
        ctx["reason"] = "MAX_PULLBACK_REARM_ENABLED = FALSE"
        return ctx
    if signal != "BUY":
        ctx["reason"] = "non è BUY"
        return ctx

    winners = [
        t for t in recent_buy_campaign_winners(symbol)
        if int(t.get("highest_tp", 0) or 0) >= MAX_PULLBACK_REARM_MIN_BUY_TP
        and now_ts() - max(to_float(t.get("last_tp_time") or t.get("created"), 0), to_float(t.get("created"), 0)) <= MAX_PULLBACK_REARM_LOOKBACK_SECONDS
    ]
    if not winners:
        ctx["reason"] = f"nessun BUY recente TP{MAX_PULLBACK_REARM_MIN_BUY_TP}+"
        return ctx

    price = get_price_from_data(data) or _latest_price_for_symbol(symbol)
    day_position = to_float(data.get("day_position"), 0.5)
    recent_window = _recent_price_window(symbol, MAX_PULLBACK_REARM_LOOKBACK_SECONDS)
    window_high = to_float(recent_window.get("high"), 0)
    window_low = to_float(recent_window.get("low"), 0)
    pullback_from_high = max(0, window_high - price) if window_high and price else 0
    rebound_from_low = max(0, price - window_low) if window_low and price else 0

    h1 = str(data.get("h1_bias", "NEUTRAL")).upper()
    h4 = str(data.get("h4_bias", "NEUTRAL")).upper()
    day = str(data.get("day_bias", "NEUTRAL")).upper()
    structure = str(data.get("structure", "NEUTRAL")).upper()
    candle = str(data.get("candle_dir", "NEUTRAL")).upper()
    ema20 = str(data.get("ema20_slope", "FLAT")).upper()
    ema50 = str(data.get("ema50_slope", "FLAT")).upper()
    rsi = to_float(data.get("rsi"), 50)
    above_ema200 = to_bool(data.get("close_above_ema200", "false"))
    close_above_ema20 = to_bool(data.get("close_above_ema20", "false"))
    close_above_ema50 = to_bool(data.get("close_above_ema50", "false"))
    near_m15_low = to_bool(data.get("near_m15_low", "false"))
    near_day_low = to_bool(data.get("near_day_low", "false"))
    lower_rejection = str(data.get("rejection", "")).upper() == "LOWER_WICK" or to_bool(data.get("lower_wick_strong", "false"))
    active_news_bias, _ = get_auto_news_bias()

    support_low_candidates = [to_float(t.get("entry_low"), 0) for t in winners if to_float(t.get("entry_low"), 0) > 0]
    support_low = min(support_low_candidates) if support_low_candidates else 0
    invalidation_price = support_low - MAX_PULLBACK_REARM_INVALIDATION_BUFFER if support_low else 0
    support_alive = bool(not invalidation_price or not price or price > invalidation_price)
    pullback_ok = pullback_from_high >= MAX_PULLBACK_REARM_MIN_PULLBACK_POINTS
    not_chasing_top = day_position <= MAX_PULLBACK_REARM_MAX_DAY_POSITION or near_m15_low or near_day_low or lower_rejection

    reasons = []
    confirmations = 0

    if h1 == "BUY":
        confirmations += 1; reasons.append("H1 BUY")
    if h4 == "BUY":
        confirmations += 1; reasons.append("H4 BUY")
    if day == "BUY":
        confirmations += 1; reasons.append("Daily BUY")
    if structure in ["BULLISH", "HL", "LL"]:
        confirmations += 1; reasons.append(f"Struttura {structure}")
    if candle == "BULL":
        confirmations += 1; reasons.append("Candela bullish")
    if ema20 == "UP" or close_above_ema20:
        confirmations += 1; reasons.append("EMA20/close sopra EMA20")
    if ema50 == "UP" or close_above_ema50:
        confirmations += 1; reasons.append("EMA50/close sopra EMA50")
    if above_ema200:
        confirmations += 1; reasons.append("Prezzo sopra EMA200")
    if rsi > 50:
        confirmations += 1; reasons.append("RSI sopra 50")
    if active_news_bias == "BULLISH_GOLD":
        confirmations += 1; reasons.append("News bullish gold")
    if lower_rejection or near_m15_low or near_day_low:
        confirmations += 1; reasons.append("Pullback/rejection su zona bassa")
    if pullback_ok:
        confirmations += 1; reasons.append(f"Pullback dal massimo: {round(pullback_from_high, 2)} punti")
    if support_alive:
        confirmations += 1; reasons.append("Supporto campagna BUY non invalidato")

    allow = bool(
        support_alive
        and pullback_ok
        and not_chasing_top
        and confirmations >= MAX_PULLBACK_REARM_MIN_CONFIRMATIONS
    )

    best = sorted(winners, key=lambda t: (int(t.get("highest_tp", 0) or 0), to_float(t.get("last_tp_time") or t.get("created"), 0)), reverse=True)[0]
    ctx.update({
        "active": bool(winners),
        "allow": allow,
        "reason": (
            "campagna BUY ancora viva: pullback controllato, posso cercare re-entry BUY"
            if allow else
            "campagna BUY viva ma re-arm non confermato"
        ),
        "reasons": reasons,
        "confirmations": confirmations,
        "winners": winners[:5],
        "best_trade": best,
        "highest_tp": int(best.get("highest_tp", 0) or 0),
        "price": price,
        "day_position": day_position,
        "window_high": window_high,
        "window_low": window_low,
        "pullback_from_high": pullback_from_high,
        "rebound_from_low": rebound_from_low,
        "support_low": support_low,
        "invalidation_price": invalidation_price,
        "support_alive": support_alive,
        "pullback_ok": pullback_ok,
        "not_chasing_top": not_chasing_top
    })
    return ctx


def max_pullback_rearm_text(ctx):
    if not ctx or not ctx.get("active"):
        return "Max Pullback Re-Arm: non attivo"
    best = ctx.get("best_trade") or {}
    reasons = "\n".join(f"- {r}" for r in (ctx.get("reasons") or [])[:8]) or "- N/D"
    return (
        f"Active: {ctx.get('active')} | Allow: {ctx.get('allow')}\n"
        f"Reason: {ctx.get('reason')}\n"
        f"Trade base: {best.get('id', 'N/D')} | {best.get('setup_type', 'N/D')} | TP{ctx.get('highest_tp')}\n"
        f"Prezzo: {round(to_float(ctx.get('price')), 3)} | Day position: {round(to_float(ctx.get('day_position')), 2)}\n"
        f"Pullback high: {round(to_float(ctx.get('pullback_from_high')), 2)} | Rebound low: {round(to_float(ctx.get('rebound_from_low')), 2)}\n"
        f"Supporto BUY: {round(to_float(ctx.get('support_low')), 3)} | Invalidation: {round(to_float(ctx.get('invalidation_price')), 3)}\n"
        f"Conferme: {ctx.get('confirmations')}/{MAX_PULLBACK_REARM_MIN_CONFIRMATIONS}\n{reasons}"
    )


def anti_fade_super_buy_context(signal, symbol, setup_type, score, data=None, big_move_ctx=None, event_trap_ctx=None, flip_window_ctx=None):
    """
    v36:
    Anti-fade contro una campagna BUY già pagata.
    Evita MAX_FADE_SELL/NORMAL SELL prematuri quando il BUY ha fatto TP5+ e non è invalidato.
    """
    data = data or {}
    symbol = str(symbol or "XAUUSD").upper()
    signal = normalize_signal(signal)
    setup_type = str(setup_type or "NORMAL").upper()

    ctx = {
        "active": False,
        "block": False,
        "allow": False,
        "reason": "non valutato",
        "bear_confirmations": 0,
        "required_bear_confirmations": ANTI_FADE_SUPER_BUY_MIN_BEAR_CONFIRMATIONS,
        "winners": []
    }

    if not ANTI_FADE_SUPER_BUY_ENABLED:
        ctx["reason"] = "ANTI_FADE_SUPER_BUY_ENABLED = FALSE"
        return ctx
    if signal != "SELL":
        ctx["reason"] = "non è SELL"
        return ctx
    if setup_type not in ANTI_FADE_SUPER_BUY_BLOCK_SETUPS:
        ctx["reason"] = "setup non soggetto ad anti-fade"
        return ctx

    winners = [
        t for t in recent_buy_campaign_winners(symbol)
        if int(t.get("highest_tp", 0) or 0) >= ANTI_FADE_SUPER_BUY_MIN_BUY_TP
        and now_ts() - max(to_float(t.get("last_tp_time") or t.get("created"), 0), to_float(t.get("created"), 0)) <= ANTI_FADE_SUPER_BUY_LOOKBACK_SECONDS
    ]
    if not winners:
        ctx["reason"] = f"nessuna campagna BUY TP{ANTI_FADE_SUPER_BUY_MIN_BUY_TP}+ recente"
        return ctx

    price = get_price_from_data(data) or _latest_price_for_symbol(symbol)
    support_candidates = [to_float(t.get("entry_low"), 0) for t in winners if to_float(t.get("entry_low"), 0) > 0]
    support_low = min(support_candidates) if support_candidates else 0
    invalidation_price = support_low - ANTI_FADE_SUPER_BUY_SUPPORT_BUFFER if support_low else 0
    campaign_invalidated = bool(invalidation_price and price and price <= invalidation_price)

    if campaign_invalidated:
        ctx.update({
            "active": True,
            "allow": True,
            "block": False,
            "reason": "campagna BUY invalidata sotto supporto: SELL non bloccato",
            "winners": winners[:5],
            "price": price,
            "support_low": support_low,
            "invalidation_price": invalidation_price
        })
        return ctx

    day_position = to_float(data.get("day_position"), 0.5)
    near_high = to_bool(data.get("near_m15_high", "false")) or to_bool(data.get("near_day_high", "false"))
    true_high_zone = bool(near_high or day_position >= ANTI_FADE_SUPER_BUY_MIN_DAY_POSITION)
    candle = str(data.get("candle_dir", "NEUTRAL")).upper()
    structure = str(data.get("structure", "NEUTRAL")).upper()
    ema20 = str(data.get("ema20_slope", "FLAT")).upper()
    ema50 = str(data.get("ema50_slope", "FLAT")).upper()
    rsi = to_float(data.get("rsi"), 50)
    above_ema200 = to_bool(data.get("close_above_ema200", "false"))
    upper_rejection = str(data.get("rejection", "")).upper() == "UPPER_WICK" or to_bool(data.get("upper_wick_strong", "false"))
    micro = micro_bos_bear_context(symbol, data)
    micro_ok = bool(micro.get("confirmed") or micro.get("micro_bos"))

    bear_confirmations = 0
    bear_reasons = []
    if candle == "BEAR":
        bear_confirmations += 1; bear_reasons.append("Candela bearish")
    if structure in ["BEARISH", "LH", "HH"]:
        bear_confirmations += 1; bear_reasons.append(f"Struttura {structure}")
    if ema20 == "DOWN":
        bear_confirmations += 1; bear_reasons.append("EMA20 DOWN")
    if ema50 == "DOWN":
        bear_confirmations += 1; bear_reasons.append("EMA50 DOWN")
    if rsi < 50:
        bear_confirmations += 1; bear_reasons.append("RSI sotto 50")
    if not above_ema200:
        bear_confirmations += 1; bear_reasons.append("Prezzo sotto EMA200")
    if upper_rejection:
        bear_confirmations += 1; bear_reasons.append("Upper rejection")
    if micro_ok:
        bear_confirmations += 1; bear_reasons.append("Micro BOS bearish")
    if true_high_zone:
        bear_confirmations += 1; bear_reasons.append("Zona alta vera")

    event_trap_allow = bool((event_trap_ctx or {}).get("allow"))
    flip_window_allow = bool((flip_window_ctx or {}).get("allow"))
    score_ok = int(score or 0) >= ANTI_FADE_SUPER_BUY_ALLOW_SCORE
    micro_rule_ok = micro_ok or not ANTI_FADE_SUPER_BUY_REQUIRE_MICRO_BOS
    zone_rule_ok = true_high_zone or not ANTI_FADE_SUPER_BUY_REQUIRE_TRUE_HIGH_ZONE
    bear_ok = bear_confirmations >= ANTI_FADE_SUPER_BUY_MIN_BEAR_CONFIRMATIONS
    allow = bool(event_trap_allow or (flip_window_allow and score_ok) or (score_ok and micro_rule_ok and zone_rule_ok and bear_ok))
    block = bool(not allow)

    best = sorted(winners, key=lambda t: (int(t.get("highest_tp", 0) or 0), to_float(t.get("last_tp_time") or t.get("created"), 0)), reverse=True)[0]
    ctx.update({
        "active": True,
        "block": block,
        "allow": allow,
        "reason": (
            "SELL autorizzato: invalidazione/flip A+ confermato"
            if allow else
            "SUPER BUY ancora vivo: blocco fade/SELL prematuro contro campagna BUY TP5+"
        ),
        "best_trade": best,
        "highest_tp": int(best.get("highest_tp", 0) or 0),
        "winners": winners[:5],
        "price": price,
        "support_low": support_low,
        "invalidation_price": invalidation_price,
        "campaign_invalidated": campaign_invalidated,
        "score": int(score or 0),
        "required_score": ANTI_FADE_SUPER_BUY_ALLOW_SCORE,
        "true_high_zone": true_high_zone,
        "day_position": day_position,
        "micro_ok": micro_ok,
        "bear_confirmations": bear_confirmations,
        "bear_reasons": bear_reasons,
        "event_trap_allow": event_trap_allow,
        "flip_window_allow": flip_window_allow
    })
    return ctx


def anti_fade_super_buy_text(ctx):
    if not ctx or not ctx.get("active"):
        return "Anti-Fade Super BUY: non attivo"
    best = ctx.get("best_trade") or {}
    bears = "\n".join(f"- {r}" for r in (ctx.get("bear_reasons") or [])[:8]) or "- N/D"
    return (
        f"Active: {ctx.get('active')} | Block: {ctx.get('block')} | Allow: {ctx.get('allow')}\n"
        f"Reason: {ctx.get('reason')}\n"
        f"Trade BUY base: {best.get('id', 'N/D')} | {best.get('setup_type', 'N/D')} | TP{ctx.get('highest_tp')}\n"
        f"Prezzo: {round(to_float(ctx.get('price')), 3)} | Supporto: {round(to_float(ctx.get('support_low')), 3)} | Invalidation: {round(to_float(ctx.get('invalidation_price')), 3)}\n"
        f"Score SELL: {ctx.get('score')}/{ANTI_FADE_SUPER_BUY_ALLOW_SCORE} | Micro BOS: {ctx.get('micro_ok')} | Zona alta vera: {ctx.get('true_high_zone')}\n"
        f"Bear confirmations: {ctx.get('bear_confirmations')}/{ANTI_FADE_SUPER_BUY_MIN_BEAR_CONFIRMATIONS}\n{bears}"
    )


def should_block_by_buy_campaign_exhaustion(signal, symbol, setup_type, score, data):
    if not BUY_CAMPAIGN_EXHAUSTION_ENABLED:
        return False, {"active": False, "reason": "disabled", "winners": []}
    if normalize_signal(signal) != "BUY":
        return False, {"active": False, "reason": "not buy", "winners": []}

    winners = recent_buy_campaign_winners(symbol)
    if not winners:
        return False, {"active": False, "reason": "no recent buy winners", "winners": []}

    day_position = to_float(data.get("day_position"), 0.5)
    setup_type = str(setup_type or "NORMAL")
    score = int(score)
    lower_wick = to_bool(data.get("lower_wick_strong")) or str(data.get("rejection", "")).upper() == "LOWER_WICK"

    ctx = {
        "active": True,
        "winners": winners[:5],
        "day_position": day_position,
        "score": score,
        "setup_type": setup_type,
        "allow": True,
        "reason": "buy campaign still acceptable"
    }

    # Accetto BUY solo se è realmente da pullback basso o score molto forte.
    low_reset = day_position <= BUY_CAMPAIGN_EXHAUSTION_ALLOW_LOW_POSITION or lower_wick
    strong_score = score >= BUY_CAMPAIGN_EXHAUSTION_ALLOW_SCORE
    if day_position >= BUY_CAMPAIGN_EXHAUSTION_MIN_DAY_POSITION and not (low_reset and strong_score):
        ctx["allow"] = False
        ctx["reason"] = "campagna BUY già pagata: non inseguo nuovi BUY alti"
        return True, ctx

    return False, ctx


def buy_campaign_exhaustion_text(ctx):
    if not ctx or not ctx.get("active"):
        return "Buy Campaign Exhaustion: non attivo"
    winners = ctx.get("winners") or []
    rows = []
    for t in winners[:3]:
        rows.append(
            f"- BUY #{t.get('id')} {t.get('setup_type', 'N/D')} TP{t.get('highest_tp', 0)} "
            f"Entry {t.get('entry_low')} - {t.get('entry_high')}"
        )
    return (
        f"Buy Campaign Exhaustion ATTIVO\n"
        f"- Day position: {round(ctx.get('day_position', 0), 2)}\n"
        f"- Setup nuovo: {ctx.get('setup_type')}\n"
        f"- Score nuovo: {ctx.get('score')}\n"
        f"- Motivo: {ctx.get('reason')}\n"
        + "\n".join(rows)
    )


# =========================
# v33 MAX FLIP BUY + VIRTUAL RUNNER
# =========================

def _trade_close_or_update_time(trade):
    return to_float(
        trade.get("closed")
        or trade.get("last_tp_time")
        or trade.get("activated")
        or trade.get("created")
        or 0,
        0
    )


def _trade_mid_entry(trade):
    low = to_float(trade.get("entry_low"), 0)
    high = to_float(trade.get("entry_high"), 0)
    if low and high:
        return (low + high) / 2
    return low or high or 0


def mark_virtual_runner(trade, reason=""):
    if not VIRTUAL_RUNNER_ENABLED or not trade:
        return None

    highest_tp = int(trade.get("highest_tp", 0) or 0)
    if highest_tp < VIRTUAL_RUNNER_MIN_TP:
        return None

    symbol = str(trade.get("symbol", "XAUUSD")).upper()
    state = {
        "active": True,
        "symbol": symbol,
        "trade_id": trade.get("id"),
        "signal": trade.get("signal"),
        "setup_type": trade.get("setup_type"),
        "highest_tp": highest_tp,
        "status": trade.get("status"),
        "entry_low": trade.get("entry_low"),
        "entry_high": trade.get("entry_high"),
        "sl": trade.get("sl"),
        "created": now_ts(),
        "created_local": local_datetime().strftime("%Y-%m-%d %H:%M:%S"),
        "expires": now_ts() + VIRTUAL_RUNNER_LOOKBACK_SECONDS,
        "reason": reason or "Trade chiuso a BE ma tesi ancora valida"
    }
    VIRTUAL_RUNNER_STATE[symbol] = state
    return state


def get_virtual_runner(symbol):
    symbol = str(symbol or "XAUUSD").upper()
    state = VIRTUAL_RUNNER_STATE.get(symbol)
    if not state:
        return {"active": False, "reason": "Nessun runner virtuale"}
    if now_ts() > to_float(state.get("expires"), 0):
        VIRTUAL_RUNNER_STATE.pop(symbol, None)
        return {"active": False, "reason": "Runner virtuale scaduto"}
    return state


def virtual_runner_text(symbol):
    state = get_virtual_runner(symbol)
    if not state.get("active"):
        return f"Active: False\nReason: {state.get('reason')}"
    return (
        f"Active: True\n"
        f"Trade: {state.get('trade_id')} | {state.get('signal')} | {state.get('setup_type')}\n"
        f"Highest TP: {state.get('highest_tp')}\n"
        f"Reason: {state.get('reason')}\n"
        f"Expires: {state.get('expires')}"
    )


def recent_sell_for_max_flip_buy(symbol):
    symbol = str(symbol or "XAUUSD").upper()
    cutoff = now_ts() - MAX_FLIP_BUY_AFTER_SELL_BE_LOOKBACK_SECONDS
    candidates = []

    for trade in OPEN_TRADES:
        if str(trade.get("symbol", "")).upper() != symbol:
            continue
        if str(trade.get("signal", "")).upper() != "SELL":
            continue
        if str(trade.get("setup_type", "NORMAL")).upper() not in MAX_FLIP_BUY_AFTER_SELL_BE_SETUPS_TO_FLIP:
            continue
        if int(trade.get("highest_tp", 0) or 0) < MAX_FLIP_BUY_AFTER_SELL_BE_MIN_SELL_TP:
            continue
        if _trade_close_or_update_time(trade) < cutoff:
            continue
        if trade.get("status") not in ["OPEN", "BE", "WIN"]:
            continue
        candidates.append(trade)

    if not candidates:
        return None

    candidates.sort(
        key=lambda t: (
            int(t.get("highest_tp", 0) or 0),
            _trade_close_or_update_time(t)
        ),
        reverse=True
    )
    return candidates[0]


def has_recent_max_flip_buy(symbol):
    symbol = str(symbol or "XAUUSD").upper()
    cutoff = now_ts() - MAX_FLIP_BUY_AFTER_SELL_BE_COOLDOWN_SECONDS
    for trade in OPEN_TRADES:
        if str(trade.get("symbol", "")).upper() != symbol:
            continue
        if str(trade.get("setup_type", "")).upper() != "MAX_FLIP_BUY":
            continue
        if to_float(trade.get("created", 0), 0) >= cutoff:
            return True, trade
    return False, None


def max_flip_buy_after_sell_be_context(data):
    symbol = str(data.get("symbol", "XAUUSD")).upper()
    price = get_price_from_data(data)
    ctx = {
        "allow": False,
        "reason": "",
        "symbol": symbol,
        "price": price,
        "score": 0,
        "confirmations": 0,
        "sell_trade": None,
        "reasons": []
    }

    if not MAX_FLIP_BUY_AFTER_SELL_BE_ENABLED:
        ctx["reason"] = "MAX_FLIP_BUY_AFTER_SELL_BE_ENABLED = FALSE"
        return ctx

    if not price:
        ctx["reason"] = "Prezzo non disponibile"
        return ctx

    duplicated, old = has_recent_max_flip_buy(symbol)
    if duplicated:
        ctx["reason"] = f"MAX_FLIP_BUY recente già presente #{old.get('id')}"
        return ctx

    # Se c'è già un BUY principale aperto/pending, non sovraccarico.
    for trade in OPEN_TRADES:
        if str(trade.get("symbol", "")).upper() != symbol:
            continue
        if str(trade.get("signal", "")).upper() == "BUY" and trade.get("status") in ["PENDING", "OPEN"]:
            ctx["reason"] = f"BUY già attivo #{trade.get('id')}"
            return ctx

    sell_trade = recent_sell_for_max_flip_buy(symbol)
    virtual = get_virtual_runner(symbol)
    ctx["virtual_runner"] = virtual

    if not sell_trade:
        ctx["reason"] = "Nessun SELL recente TP/BE da flippare"
        return ctx

    ctx["sell_trade"] = sell_trade

    sell_entry_high = to_float(sell_trade.get("entry_high"), 0)
    sell_entry_mid = _trade_mid_entry(sell_trade)
    invalidation_level = sell_entry_high + MAX_FLIP_BUY_AFTER_SELL_BE_INVALIDATION_POINTS if sell_entry_high else 0
    recovered_above_sell = bool(price >= invalidation_level) if invalidation_level else True

    day_position = to_float(data.get("day_position"), -1)
    candle_dir = str(data.get("candle_dir", "")).upper()
    h1 = str(data.get("h1_bias", "")).upper()
    h4 = str(data.get("h4_bias", "")).upper()
    daily = str(data.get("day_bias", data.get("daily_bias", ""))).upper()
    ema20 = str(data.get("ema20_slope", "")).upper()
    ema50 = str(data.get("ema50_slope", "")).upper()
    rsi = to_float(data.get("rsi"), 50)
    close_above_ema20 = to_bool(data.get("close_above_ema20")) or ema20 == "UP"
    close_above_ema50 = to_bool(data.get("close_above_ema50")) or ema50 == "UP"
    lower_wick = to_bool(data.get("lower_wick_strong")) or str(data.get("rejection", "")).upper() == "LOWER_WICK"
    near_low = to_bool(data.get("near_day_low")) or to_bool(data.get("near_m15_low"))
    event_or_news = is_event_or_news_active(data)
    micro_bull = to_bool(data.get("micro_bos_bull")) or to_bool(data.get("breakout_up"))

    reasons = []
    if recovered_above_sell:
        reasons.append(f"recupero sopra zona SELL: {round(price, 3)} >= {round(invalidation_level, 3)}")
    if candle_dir == "BULL":
        reasons.append("candela bullish")
    if h1 == "BUY":
        reasons.append("H1 BUY")
    if h4 == "BUY":
        reasons.append("H4 BUY")
    if daily == "BUY":
        reasons.append("Daily BUY")
    if rsi > 50:
        reasons.append("RSI sopra 50")
    if close_above_ema20:
        reasons.append("recupero/EMA20 UP")
    if close_above_ema50:
        reasons.append("recupero/EMA50 UP")
    if lower_wick or near_low:
        reasons.append("rejection/low difeso")
    if event_or_news:
        reasons.append("evento/news/volatilità attiva")
    if micro_bull:
        reasons.append("micro breakout bullish")

    confirmations = len(reasons)
    score = 10 + confirmations
    if int(sell_trade.get("highest_tp", 0) or 0) >= 3:
        score += 2
    if sell_trade.get("status") == "BE":
        score += 2
    if event_or_news:
        score += 1

    day_position_ok = bool(day_position < 0 or day_position <= MAX_FLIP_BUY_AFTER_SELL_BE_MAX_DAY_POSITION)
    recovery_ok = bool((not MAX_FLIP_BUY_AFTER_SELL_BE_REQUIRE_RECOVERY_ABOVE_SELL) or recovered_above_sell)
    context_ok = bool((not MAX_FLIP_BUY_AFTER_SELL_BE_REQUIRE_BULLISH_CONTEXT) or confirmations >= MAX_FLIP_BUY_AFTER_SELL_BE_MIN_CONFIRMATIONS)
    score_ok = bool(score >= MAX_FLIP_BUY_AFTER_SELL_BE_MIN_SCORE)

    ctx.update({
        "score": score,
        "confirmations": confirmations,
        "reasons": reasons,
        "day_position": day_position,
        "day_position_ok": day_position_ok,
        "recovery_ok": recovery_ok,
        "context_ok": context_ok,
        "score_ok": score_ok,
        "sell_entry_high": sell_entry_high,
        "sell_entry_mid": sell_entry_mid,
        "invalidation_level": invalidation_level,
        "recovered_above_sell": recovered_above_sell,
        "sell_highest_tp": int(sell_trade.get("highest_tp", 0) or 0),
        "sell_status": sell_trade.get("status"),
        "sell_setup": sell_trade.get("setup_type")
    })

    if recovery_ok and context_ok and score_ok and day_position_ok:
        ctx["allow"] = True
        ctx["reason"] = "SELL pagato/BE invalidato: flip BUY stile Max autorizzato"
    else:
        missing = []
        if not recovery_ok:
            missing.append(f"manca recupero sopra SELL {round(price, 3)}/{round(invalidation_level, 3)}")
        if not context_ok:
            missing.append(f"conferme bullish {confirmations}/{MAX_FLIP_BUY_AFTER_SELL_BE_MIN_CONFIRMATIONS}")
        if not score_ok:
            missing.append(f"score {score}/{MAX_FLIP_BUY_AFTER_SELL_BE_MIN_SCORE}")
        if not day_position_ok:
            missing.append(f"day position alta {round(day_position, 2)}/{MAX_FLIP_BUY_AFTER_SELL_BE_MAX_DAY_POSITION}")
        ctx["reason"] = "; ".join(missing) if missing else "condizioni non complete"

    return ctx


def build_max_flip_buy_data(data, ctx):
    price = get_price_from_data(data)
    if not price:
        return None, "Prezzo non disponibile"

    entry_high = round(price, 3)
    entry_low = round(price - MAX_FLIP_BUY_AFTER_SELL_BE_ENTRY_HALF_ZONE, 3)
    sl = round(entry_low - MAX_FLIP_BUY_AFTER_SELL_BE_SL_POINTS, 3)

    out = {
        "signal": "BUY",
        "symbol": data.get("symbol", "XAUUSD"),
        "price": price,
        "tf": data.get("tf", "1"),
        "entry_low": entry_low,
        "entry_high": entry_high,
        "sl": sl,
        "synthetic_source": "MAX_FLIP_BUY_AFTER_SELL_BE",
        "day_position": data.get("day_position")
    }

    for i, dist in enumerate(MAX_FLIP_BUY_AFTER_SELL_BE_TP_DISTANCES, start=1):
        out[f"tp{i}"] = round(entry_low + float(dist), 3)

    return out, None


def save_max_flip_buy_trade(data, ctx):
    synthetic_data, error = build_max_flip_buy_data(data, ctx)
    if error:
        return None, error

    trade = save_trade(
        synthetic_data,
        "BUY",
        int(ctx.get("score", MAX_FLIP_BUY_AFTER_SELL_BE_MIN_SCORE)),
        "MAX_FLIP_BUY"
    )
    trade["status"] = "OPEN"
    trade["entered"] = True
    trade["activated"] = now_ts()
    trade["activated_local"] = local_datetime().strftime("%Y-%m-%d %H:%M:%S")
    trade["synthetic"] = True
    trade["synthetic_source"] = "MAX_FLIP_BUY_AFTER_SELL_BE"
    sell_trade = ctx.get("sell_trade") or {}
    trade["flip_from_sell_id"] = sell_trade.get("id")
    trade["flip_from_sell_setup"] = sell_trade.get("setup_type")
    trade["flip_from_sell_highest_tp"] = sell_trade.get("highest_tp")
    trade["flip_reason"] = ctx.get("reason")
    save_trades()
    return trade, None


def max_flip_buy_message(trade, ctx):
    reason_text = "\n".join([f"- {r}" for r in ctx.get("reasons", [])]) or "- recupero bullish post SELL"
    sell_trade = ctx.get("sell_trade") or {}
    return f"""🟢🔄 GOLD BUY AUTONOMO {VERSION}

🆔 Trade ID: {trade.get('id')}
📌 Setup: MAX_FLIP_BUY
🧠 Origine: Python Max Flip BUY dopo SELL TP/BE
📍 Entry Zone: {trade.get('entry_low')} - {trade.get('entry_high')}
🛑 SL: {trade.get('sl')}
🎯 TP1: {trade.get('tp1')}
🎯 TP2: {trade.get('tp2')}
🎯 TP3: {trade.get('tp3')}
🎯 TP4: {trade.get('tp4')}
🎯 TP5: {trade.get('tp5')}
🎯 TP6: {trade.get('tp6')}
🎯 TP7: {trade.get('tp7')}
🎯 TP8: {trade.get('tp8')}

🧠 Score flip: {ctx.get('score')}

SELL flippato:
- ID: {sell_trade.get('id', 'N/D')}
- Setup: {sell_trade.get('setup_type', 'N/D')}
- Status: {sell_trade.get('status', 'N/D')}
- Highest TP: {sell_trade.get('highest_tp', 0)}
- Zona SELL: {sell_trade.get('entry_low', 'N/D')} - {sell_trade.get('entry_high', 'N/D')}

Conferme:
{reason_text}

Virtual Runner:
{virtual_runner_text(trade.get('symbol', 'XAUUSD'))}

Azione:
Il bot considera il SELL precedente pagato/invalido e prova il recupero BUY stile Max.
"""


def process_max_flip_buy_after_sell_be(data):
    result = {
        "triggered": False,
        "trade_id": None,
        "reason": ""
    }
    ctx = max_flip_buy_after_sell_be_context(data)
    result["reason"] = ctx.get("reason")
    result["ctx"] = ctx
    if not ctx.get("allow"):
        return result

    trade, error = save_max_flip_buy_trade(data, ctx)
    if error:
        result["reason"] = error
        return result

    send_telegram(max_flip_buy_message(trade, ctx))
    result["triggered"] = True
    result["trade_id"] = trade.get("id")
    return result


def fast_pause_status(symbol=None):
    symbol = str(symbol or "XAUUSD").upper()
    consecutive = fast_consecutive_sl_count(symbol)
    if consecutive < FAST_MAX_CONSECUTIVE_SL:
        return {"active": False, "consecutive_sl": consecutive, "remaining_seconds": 0}
    last_loss = fast_last_loss_ts(symbol)
    remaining = max(0, FAST_STOP_AFTER_CONSECUTIVE_SL_SECONDS - (now_ts() - last_loss))
    return {"active": remaining > 0, "consecutive_sl": consecutive, "remaining_seconds": remaining}


def maybe_fast_pause_message(symbol):
    if not FAST_PAUSE_ALERT_ENABLED:
        return None
    symbol = str(symbol or "XAUUSD").upper()
    status = fast_pause_status(symbol)
    if not status.get("active"):
        return None
    last_notified = to_float(FAST_PAUSE_NOTIFIED.get(symbol), 0)
    if now_ts() - last_notified < FAST_PAUSE_ALERT_COOLDOWN_SECONDS:
        return None
    FAST_PAUSE_NOTIFIED[symbol] = now_ts()
    mins = int(math.ceil(status.get("remaining_seconds", 0) / 60.0))
    return (
        f"⏸ FAST SCALPER IN PAUSA\n\n"
        f"Symbol: {symbol}\n"
        f"Motivo: {status.get('consecutive_sl')} SL fast consecutivi\n"
        f"Pausa residua circa: {mins} minuti\n\n"
        f"Azione:\n"
        f"Il motore veloce non è rotto: si ferma per evitare overtrading dopo SL ravvicinati.\n"
        f"La strategia principale continua normalmente."
    )

# =========================
# FAST SCALPER PARALLELO
# =========================

def fmt_price(value):
    return f"{to_float(value):.2f}"


def html_code(value):
    return f"<code>{html.escape(str(value))}</code>"


def load_fast_trades():
    global FAST_TRADES

    if not os.path.exists(FAST_TRADES_FILE):
        FAST_TRADES = []
        return

    try:
        with open(FAST_TRADES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        FAST_TRADES = data if isinstance(data, list) else []

    except Exception as e:
        print(f"Errore caricamento fast trades: {e}")
        FAST_TRADES = []


def save_fast_trades():
    try:
        with open(FAST_TRADES_FILE, "w", encoding="utf-8") as f:
            json.dump(FAST_TRADES, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Errore salvataggio fast trades: {e}")


def fast_trade_day(trade):
    created_local = str(trade.get("created_local", ""))
    if created_local:
        return created_local[:10]
    created = to_float(trade.get("created"), 0)
    if created:
        return datetime.fromtimestamp(created, LOCAL_TZ).strftime("%Y-%m-%d")
    return ""


def fast_today_trades(symbol=None):
    today = today_key()
    out = []
    for trade in FAST_TRADES:
        if fast_trade_day(trade) != today:
            continue
        if symbol and str(trade.get("symbol", "")).upper() != str(symbol).upper():
            continue
        out.append(trade)
    return out


def fast_active_trades(symbol=None):
    out = []
    for trade in FAST_TRADES:
        if trade.get("status") not in ["PENDING", "OPEN"]:
            continue
        if symbol and str(trade.get("symbol", "")).upper() != str(symbol).upper():
            continue
        out.append(trade)
    return out


def fast_consecutive_sl_count(symbol=None):
    today = fast_today_trades(symbol)
    closed = [
        t for t in today
        if t.get("status") in ["WIN", "LOSS", "BE", "CANCELLED"]
    ]
    closed.sort(key=lambda x: to_float(x.get("closed", x.get("created", 0)), 0), reverse=True)

    count = 0
    for trade in closed:
        if trade.get("status") == "LOSS":
            count += 1
        elif trade.get("status") == "WIN":
            break
        elif trade.get("status") == "BE":
            break
    return count


def fast_direct_sl_today(symbol=None):
    return [
        t for t in fast_today_trades(symbol)
        if t.get("status") == "LOSS"
    ]


def fast_last_loss_ts(symbol=None):
    losses = fast_direct_sl_today(symbol)
    if not losses:
        return 0
    return max(to_float(t.get("closed", 0), 0) for t in losses)


def get_main_big_move_direction(symbol):
    """
    Legge solo lo stato informativo dei trade v29.
    Non cambia la logica del bot principale.
    Se un trade v29 ha già TP5+/runner recente, il fast evita di andargli contro.
    """
    if not FAST_BLOCK_COUNTER_BIG_MOVE:
        return None

    symbol = str(symbol or "XAUUSD").upper()
    cutoff = now_ts() - FAST_MAIN_DOMINANCE_LOOKBACK_SECONDS
    best = None

    for trade in OPEN_TRADES:
        if str(trade.get("symbol", "")).upper() != symbol:
            continue

        created = to_float(trade.get("created"), 0)
        if created and created < cutoff:
            continue

        highest_tp = int(trade.get("highest_tp", 0) or 0)
        is_runner = bool(trade.get("runner"))
        status = trade.get("status")

        if status not in ["OPEN", "PENDING", "BE"] and not is_runner:
            continue

        if highest_tp < FAST_MAIN_DOMINANCE_TP_LEVEL and not is_runner:
            continue

        if best is None or highest_tp > int(best.get("highest_tp", 0) or 0):
            best = trade

    if not best:
        return None

    return {
        "direction": best.get("signal"),
        "trade_id": best.get("id"),
        "setup": best.get("setup_type"),
        "highest_tp": int(best.get("highest_tp", 0) or 0),
        "runner": bool(best.get("runner")),
        "status": best.get("status")
    }


def fast_direction_score(data, signal):
    score = 0
    reasons = []
    signal = normalize_signal(signal)

    h1_bias = str(data.get("h1_bias", "")).upper()
    h4_bias = str(data.get("h4_bias", "")).upper()
    day_bias = str(data.get("day_bias", "")).upper()
    candle_dir = str(data.get("candle_dir", "")).upper()
    ema20_slope = str(data.get("ema20_slope", "")).upper()
    ema50_slope = str(data.get("ema50_slope", "")).upper()
    rejection = str(data.get("rejection", "")).upper()
    rsi = to_float(data.get("rsi"), 50)
    close_above_ema200 = to_bool(data.get("close_above_ema200"))
    event_mode = to_bool(data.get("event_mode")) or to_bool(data.get("auto_event_pine"))
    volume_spike = to_bool(data.get("volume_spike"))
    near_m15_low = to_bool(data.get("near_m15_low"))
    near_m15_high = to_bool(data.get("near_m15_high"))
    lower_wick_strong = to_bool(data.get("lower_wick_strong"))
    upper_wick_strong = to_bool(data.get("upper_wick_strong"))

    if h1_bias == signal:
        score += 1
        reasons.append("H1 allineato")
    if h4_bias == signal:
        score += 1
        reasons.append("H4 allineato")
    if day_bias == signal:
        score += 1
        reasons.append("Daily allineato")

    if signal == "BUY":
        if candle_dir == "BULL":
            score += 1
            reasons.append("candela bullish")
        if rsi >= 50:
            score += 1
            reasons.append("RSI sopra 50")
        if ema20_slope == "UP":
            score += 1
            reasons.append("EMA20 UP")
        if ema50_slope == "UP":
            score += 1
            reasons.append("EMA50 UP")
        if close_above_ema200:
            score += 1
            reasons.append("prezzo sopra EMA200")
        if near_m15_low or lower_wick_strong or rejection == "LOWER_WICK":
            score += 1
            reasons.append("pullback/rejection basso")
    else:
        if candle_dir == "BEAR":
            score += 1
            reasons.append("candela bearish")
        if rsi <= 50:
            score += 1
            reasons.append("RSI sotto 50")
        if ema20_slope == "DOWN":
            score += 1
            reasons.append("EMA20 DOWN")
        if ema50_slope == "DOWN":
            score += 1
            reasons.append("EMA50 DOWN")
        if not close_above_ema200:
            score += 1
            reasons.append("prezzo sotto EMA200")
        if near_m15_high or upper_wick_strong or rejection == "UPPER_WICK":
            score += 1
            reasons.append("rimbalzo/rejection alto")

    if event_mode:
        score += 1
        reasons.append("volatilità/event mode")
    if volume_spike:
        score += 1
        reasons.append("volume spike")

    return score, reasons


def dynamic_fast_sl_points(data):
    """
    v35: SL fast adattivo.
    TP resta veloce (2 punti), ma lo stop non resta più microscopico quando Gold M1 spika.
    """
    data = data or {}
    base = max(to_float(FAST_SL_POINTS, 3.5), to_float(FAST_MIN_SL_POINTS, 3.5))

    if FAST_USE_DYNAMIC_SL:
        atr_candidates = [
            data.get("atr"), data.get("atr14"), data.get("atr_14"),
            data.get("m1_atr"), data.get("atr_m1"), data.get("range_atr")
        ]
        atr_values = [to_float(v, 0) for v in atr_candidates]
        atr_values = [v for v in atr_values if v and v > 0]
        if atr_values:
            base = max(base, max(atr_values) * FAST_ATR_SL_MULT)

        event_active = bool(
            to_bool(data.get("event_mode"))
            or to_bool(data.get("auto_event_pine"))
            or to_float(data.get("m15_range_atr"), 0) >= BIG_MOVE_BREAKOUT_M15_ATR
            or to_float(data.get("range_atr"), 0) >= 2.2
            or to_bool(data.get("volume_spike"))
        )
        if event_active:
            base = max(base, FAST_EVENT_SL_POINTS)

    base = max(base, FAST_MIN_SL_POINTS)
    base = min(base, FAST_MAX_SL_POINTS)
    return round(base, 2)



# =========================
# v39 FAST CAMPAIGN GUARD
# =========================

def get_fast_opposite_main_campaign_context(symbol, signal):
    symbol = str(symbol or "XAUUSD").upper()
    signal = normalize_signal(signal)
    opposite = "SELL" if signal == "BUY" else "BUY"

    ctx = {
        "enabled": FAST_BLOCK_OPPOSITE_MAIN_CAMPAIGN,
        "active": False,
        "block": False,
        "reason": "Nessuna campagna principale opposta viva",
        "opposite_trade": None,
        "opposite_signal": opposite,
    }

    if not FAST_BLOCK_OPPOSITE_MAIN_CAMPAIGN:
        ctx["reason"] = "FAST_BLOCK_OPPOSITE_MAIN_CAMPAIGN = FALSE"
        return ctx

    candidates = []
    for trade in OPEN_TRADES:
        if str(trade.get("symbol", "")).upper() != symbol:
            continue
        if str(trade.get("signal", "")).upper() != opposite:
            continue
        if trade.get("status") not in ["OPEN", "PENDING"]:
            continue
        setup = str(trade.get("setup_type", "NORMAL")).upper()
        if setup not in FAST_BLOCK_OPPOSITE_MAIN_SETUPS:
            continue
        age = now_ts() - to_float(trade.get("created"), 0)
        if age > FAST_BLOCK_OPPOSITE_MAIN_SECONDS:
            continue
        highest_tp = int(trade.get("highest_tp", 0) or 0)
        if highest_tp < FAST_BLOCK_OPPOSITE_MAIN_MIN_TP:
            continue
        candidates.append(trade)

    if not candidates:
        return ctx

    best = sorted(
        candidates,
        key=lambda x: (int(x.get("highest_tp", 0) or 0), x.get("last_tp_time") or x.get("created") or 0),
        reverse=True,
    )[0]

    ctx.update({
        "active": True,
        "block": True,
        "opposite_trade": best,
        "reason": (
            f"FAST {signal} bloccato: trade principale {opposite} ancora vivo "
            f"({best.get('setup_type')} #{best.get('id')}, TP{best.get('highest_tp', 0)})"
        ),
    })
    return ctx

def fast_should_block(data, signal, entry, score=None, score_reasons=None):
    symbol = str(data.get("symbol", "XAUUSD")).upper()
    tf = str(data.get("tf", "")).strip()
    reasons = []
    score = to_int(score, 0)
    score_reasons = score_reasons or []

    if not FAST_ENGINE_ENABLED:
        return True, ["FAST_ENGINE_ENABLED = FALSE"]

    if tf and tf not in FAST_ALLOWED_TFS:
        return True, [f"TF {tf} non adatto al fast scalper"]

    if len(fast_active_trades(symbol)) >= FAST_MAX_ACTIVE_TRADES:
        return True, [f"troppi fast trade attivi sul simbolo ({FAST_MAX_ACTIVE_TRADES})"]

    if ASIAN_THESIS_FAST_BLOCK_ENABLED:
        dt_block = daily_thesis_block_context(signal, symbol, "FAST", score, data, is_fast=True)
        if dt_block.get("block"):
            return True, [dt_block.get("reason", "Daily Thesis fast block")]

    today = fast_today_trades(symbol)
    if len(today) >= FAST_MAX_TRADES_PER_DAY:
        return True, [f"limite trade fast giornaliero raggiunto ({FAST_MAX_TRADES_PER_DAY})"]

    if FAST_DISCIPLINE_ENABLED:
        recent_fast_same = recent_fast_trades(symbol, signal, FAST_DISCIPLINE_WINDOW_SECONDS)
        if len(recent_fast_same) >= FAST_MAX_PER_DIRECTION_WINDOW:
            return True, [
                f"FAST v42: già mandato {len(recent_fast_same)} FAST {signal} negli ultimi {int(FAST_DISCIPLINE_WINDOW_SECONDS // 60)} min"
            ]

        if FAST_REQUIRE_MAIN_CONTEXT:
            main_ok, main_trade = has_main_context_for_fast(symbol, signal)
            if not main_ok and score < FAST_DISCIPLINE_A_PLUS_SCORE:
                return True, [
                    f"FAST v42: manca contesto principale {signal} già valido/TP{FAST_MAIN_CONTEXT_MIN_TP}; score {score}/{FAST_DISCIPLINE_A_PLUS_SCORE}"
                ]

    direct_sl = fast_direct_sl_today(symbol)
    if len(direct_sl) >= FAST_MAX_DIRECT_SL_PER_DAY:
        return True, [f"limite SL fast giornaliero raggiunto ({FAST_MAX_DIRECT_SL_PER_DAY})"]

    consecutive_sl = fast_consecutive_sl_count(symbol)
    if consecutive_sl >= FAST_MAX_CONSECUTIVE_SL:
        last_loss = fast_last_loss_ts(symbol)
        remaining = FAST_STOP_AFTER_CONSECUTIVE_SL_SECONDS - (now_ts() - last_loss)
        if remaining > 0:
            return True, [
                f"{consecutive_sl} SL fast consecutivi: pausa ancora {int(remaining // 60)} min"
            ]

    # v35: Master Gate del FAST.
    # Il FAST resta parallelo, ma non può più fare BUY quando il Master Regime
    # sta dicendo SELL_CONTROL, né SELL in BUY_CONTROL. Questo risolve il caso
    # in cui il main bot blocca un BUY ma il FAST lo manda comunque e prende SL.
    if FAST_MASTER_GATE_ENABLED and MASTER_REGIME_ENABLED:
        master_ctx = get_master_regime_context(symbol, data)
        master_mode = str(master_ctx.get("mode", "MIXED")).upper()

        if master_mode == "SELL_CONTROL" and signal == "BUY" and FAST_BLOCK_BUY_IN_SELL_CONTROL:
            return True, [
                "FAST bloccato da Master Regime SELL_CONTROL: niente BUY veloci contro giornata sell",
                master_ctx.get("reason", "")
            ]

        if master_mode == "BUY_CONTROL" and signal == "SELL" and FAST_BLOCK_SELL_IN_BUY_CONTROL:
            return True, [
                "FAST bloccato da Master Regime BUY_CONTROL: niente SELL veloci contro giornata buy",
                master_ctx.get("reason", "")
            ]

        if master_mode == "CHAOS_CONTROL" and FAST_BLOCK_CHAOS_CONTROL:
            return True, [
                "FAST bloccato da Master Regime CHAOS_CONTROL: mercato tossico / troppi SL diretti",
                master_ctx.get("reason", "")
            ]

        if signal == "SELL" and master_mode == "SELL_CONTROL" and score < FAST_SELL_CONTROL_MIN_SCORE:
            return True, [
                f"FAST SELL in SELL_CONTROL ma score basso {score}/{FAST_SELL_CONTROL_MIN_SCORE}"
            ]

        if signal == "BUY" and master_mode == "BUY_CONTROL" and score < FAST_BUY_CONTROL_MIN_SCORE:
            return True, [
                f"FAST BUY in BUY_CONTROL ma score basso {score}/{FAST_BUY_CONTROL_MIN_SCORE}"
            ]

    # v39: blocca il FAST contro una campagna/trade principale viva.
    # Evita che il motore veloce apra il contrario mentre la v29/v38 sta ancora gestendo la view principale.
    fast_campaign_ctx = get_fast_opposite_main_campaign_context(symbol, signal)
    if fast_campaign_ctx.get("block"):
        return True, [fast_campaign_ctx.get("reason")]

    # v35: se Big Move Watch/Confirmed è attivo da TP3+, il FAST non fa contromano.
    if FAST_BLOCK_COUNTER_BIG_MOVE_THESIS:
        big_move_ctx = get_big_move_thesis_context(symbol, data)
        big_direction = str(big_move_ctx.get("signal", "")).upper()
        big_status = str(big_move_ctx.get("status", "")).upper()
        big_tp = int(big_move_ctx.get("highest_tp", 0) or 0)
        if (
            big_move_ctx.get("active")
            and big_direction in ["BUY", "SELL"]
            and big_status in ["WATCH", "CONFIRMED"]
            and big_tp >= FAST_BIG_MOVE_BLOCK_FROM_TP
            and big_direction != signal
        ):
            return True, [
                f"FAST bloccato: Big Move {big_direction} {big_status} già a TP{big_tp}; niente contromano",
                big_move_ctx.get("reason", "")
            ]

    for trade in FAST_TRADES:
        if trade.get("status") not in ["PENDING", "OPEN"]:
            continue
        if str(trade.get("symbol", "")).upper() != symbol:
            continue
        if trade.get("signal") != signal:
            continue
        age = now_ts() - to_float(trade.get("created"), 0)
        old_entry = to_float(trade.get("entry"), 0)
        if age <= FAST_DUPLICATE_SECONDS and abs(old_entry - entry) <= FAST_DUPLICATE_PRICE_DISTANCE:
            return True, ["duplicato fast sullo stesso movimento"]

    main_direction = get_main_big_move_direction(symbol)
    if main_direction and main_direction.get("direction") and main_direction.get("direction") != signal:
        rebound_ctx = post_sell_rebound_unlock_context(signal, symbol, str(data.get("setup") or data.get("setup_type") or "NORMAL"), to_int(data.get("score"), 0), data)
        if FAST_ALLOW_DEEP_REBOUND_COUNTER and signal == "BUY" and rebound_ctx.get("allow"):
            reasons.append("FAST BUY rebound autorizzato contro SELL TP8/runner già pagato")
        else:
            return True, [
                f"fast contro big move v29 {main_direction.get('direction')} "
                f"TP{main_direction.get('highest_tp')} / runner={main_direction.get('runner')}"
            ]

    day_position = to_float(data.get("day_position"), 0.5)
    lower_wick = to_bool(data.get("lower_wick_strong"))
    upper_wick = to_bool(data.get("upper_wick_strong"))
    candle_dir = str(data.get("candle_dir", "NEUTRAL")).upper()
    ema20_slope = str(data.get("ema20_slope", "FLAT")).upper()
    ema50_slope = str(data.get("ema50_slope", "FLAT")).upper()
    near_m15_high = to_bool(data.get("near_m15_high"))
    near_m15_low = to_bool(data.get("near_m15_low"))

    if FAST_QUALITY_GATE_ENABLED:
        if len(score_reasons) < FAST_MIN_REASON_COUNT:
            return True, [
                f"fast quality gate: poche confluenze {len(score_reasons)}/{FAST_MIN_REASON_COUNT}"
            ]

        if FAST_REQUIRE_MOMENTUM_OR_REJECTION:
            if signal == "BUY":
                momentum_or_rejection = bool(
                    candle_dir == "BULL"
                    or ema20_slope == "UP"
                    or ema50_slope == "UP"
                    or near_m15_low
                    or lower_wick
                )
                if not momentum_or_rejection:
                    return True, ["BUY fast bloccato: manca momentum o rejection bassa"]
            else:
                momentum_or_rejection = bool(
                    candle_dir == "BEAR"
                    or ema20_slope == "DOWN"
                    or ema50_slope == "DOWN"
                    or near_m15_high
                    or upper_wick
                )
                if not momentum_or_rejection:
                    return True, ["SELL fast bloccato: manca momentum o rejection alta"]

        if FAST_BLOCK_MIDDLE_WITHOUT_BIG_MOVE and not main_direction:
            if FAST_MIDDLE_LOW <= day_position <= FAST_MIDDLE_HIGH and score < FAST_MIDDLE_A_PLUS_SCORE:
                return True, [
                    f"fast bloccato nel mezzo del range ({round(day_position, 2)}): serve big move/zona estrema oppure score A+ {score}/{FAST_MIDDLE_A_PLUS_SCORE}"
                ]

    if FAST_BLOCK_HIGH_SPIKE_BUY and signal == "BUY" and day_position >= FAST_HIGH_POSITION_BLOCK and not lower_wick:
        return True, [
            f"BUY fast bloccato: prezzo troppo alto nel range giornaliero ({round(day_position, 2)})"
        ]

    if FAST_BLOCK_LOW_SPIKE_SELL and signal == "SELL" and day_position <= FAST_LOW_POSITION_BLOCK and not upper_wick:
        return True, [
            f"SELL fast bloccato: prezzo troppo basso nel range giornaliero ({round(day_position, 2)})"
        ]

    return False, reasons


def build_fast_trade(data, signal):
    symbol = str(data.get("symbol", "XAUUSD")).upper()
    signal = normalize_signal(signal)

    price = get_price_from_data(data)
    if not price:
        price = to_float(data.get("close"), 0)

    if not price:
        raise ValueError("prezzo mancante")

    # Entry mercato/copia rapida. L'offset resta a 0 per non cambiare il comportamento.
    # v37: SL fast dinamico davvero usato. In v36 il valore sl_points poteva restare non definito.
    sl_points = dynamic_fast_sl_points(data)

    if signal == "BUY":
        entry = price + FAST_ENTRY_OFFSET
        tp = entry + FAST_TP_POINTS
        sl = entry - sl_points
    else:
        entry = price - FAST_ENTRY_OFFSET
        tp = entry - FAST_TP_POINTS
        sl = entry + sl_points

    score, reasons = fast_direction_score(data, signal)
    blocked, block_reasons = fast_should_block(data, signal, entry, score, reasons)

    if score < FAST_MIN_SCORE:
        blocked = True
        block_reasons.append(f"score fast basso {score}/{FAST_MIN_SCORE}")

    trade = {
        "id": str(int(time.time() * 1000)),
        "symbol": symbol,
        "signal": signal,
        "entry": round(entry, 2),
        "sl": round(sl, 2),
        "tp": round(tp, 2),
        "tp_points": round(FAST_TP_POINTS, 2),
        "sl_points": round(sl_points, 2),
        "score": score,
        "status": "PENDING",
        "created": now_ts(),
        "created_local": local_datetime().strftime("%Y-%m-%d %H:%M:%S"),
        "activated": None,
        "activated_local": None,
        "closed": None,
        "closed_local": None,
        "reasons": reasons,
        "source_version": VERSION,
        "fast_version": FAST_VERSION
    }

    return trade, blocked, block_reasons, reasons


def fast_message(trade):
    symbol = trade.get("symbol", "XAUUSD")
    signal = trade.get("signal", "BUY")
    entry = fmt_price(trade.get("entry"))
    sl = fmt_price(trade.get("sl"))
    tp = fmt_price(trade.get("tp"))
    score = trade.get("score", 0)
    tp_points = trade.get("tp_points", FAST_TP_POINTS)
    sl_points = trade.get("sl_points", FAST_SL_POINTS)
    reasons = trade.get("reasons") or []
    reason_text = "\n".join([f"- {r}" for r in reasons]) if reasons else "- conferme base fast"

    if FAST_USE_HTML_COPY_FORMAT:
        return f"""⚡ {html.escape(FAST_VERSION)}

FAST 2 PUNTI — OPERAZIONE UFFICIALE 🚀
{html_code(symbol + ' ' + signal)}

Entry: {html_code(entry)}
SL: {html_code(sl)}
TP1: {html_code(tp)}

📋 COPIA RAPIDA MT4
Symbol: {html_code(symbol)}
Type: {html_code(signal)}
Entry: {html_code(entry)}
SL: {html_code(sl)}
TP: {html_code(tp)}

🎯 Obiettivo veloce: {html_code(str(tp_points) + ' punti')}
🛑 Stop smart: {html_code(str(sl_points) + ' punti')}
🧠 Score fast: {html_code(str(score))}

Lettura:
{html.escape(reason_text)}

Nota: tocca/tieni premuto sui valori grigi per copiarli dal telefono."""

    return f"""⚡ {FAST_VERSION}

FAST 2 PUNTI — OPERAZIONE UFFICIALE 🚀
{symbol} {signal}

Entry: {entry}
SL: {sl}
TP1: {tp}

📋 COPIA RAPIDA MT4
{entry}
{sl}
{tp}

Score fast: {score}
SL smart: {sl_points} punti
"""


def fast_block_message(data, signal, trade, block_reasons):
    symbol = str(data.get("symbol", "XAUUSD")).upper()
    price = fmt_price(get_price_from_data(data))
    score = trade.get("score") if trade else "N/D"
    reason_text = "\n".join([f"- {r}" for r in block_reasons]) if block_reasons else "- filtro fast"

    return f"""⚡🚫 FAST SCALP BLOCCATO

Symbol: {symbol}
Segnale: {signal}
Prezzo: {price}
Score fast: {score}

Motivi:
{reason_text}

Azione:
Il motore veloce cerca più segnali da 2 punti, ma questo è stato filtrato perché il contesto non è abbastanza pulito."""


def save_fast_trade(trade):
    FAST_TRADES.append(trade)
    save_fast_trades()
    return trade


def close_fast_trade(trade, status):
    trade["status"] = status
    trade["closed"] = now_ts()
    trade["closed_local"] = local_datetime().strftime("%Y-%m-%d %H:%M:%S")


def handle_fast_price_update(data):
    high = to_float(data.get("high"), 0)
    low = to_float(data.get("low"), 0)
    symbol = str(data.get("symbol", "XAUUSD")).upper()

    if not high or not low:
        price = get_price_from_data(data)
        high = high or price
        low = low or price

    updates = []
    changed = False

    for trade in FAST_TRADES:
        if str(trade.get("symbol", "")).upper() != symbol:
            continue
        if trade.get("status") not in ["PENDING", "OPEN"]:
            continue

        signal = trade.get("signal")
        entry = to_float(trade.get("entry"), 0)
        sl = to_float(trade.get("sl"), 0)
        tp = to_float(trade.get("tp"), 0)
        trade_id = trade.get("id")

        if trade.get("status") == "PENDING":
            if signal == "BUY" and high >= entry:
                trade["status"] = "OPEN"
                trade["activated"] = now_ts()
                trade["activated_local"] = local_datetime().strftime("%Y-%m-%d %H:%M:%S")
                changed = True
                updates.append(f"⚡ FAST #{trade_id} BUY ATTIVATO\nEntry: {fmt_price(entry)}")
            elif signal == "SELL" and low <= entry:
                trade["status"] = "OPEN"
                trade["activated"] = now_ts()
                trade["activated_local"] = local_datetime().strftime("%Y-%m-%d %H:%M:%S")
                changed = True
                updates.append(f"⚡ FAST #{trade_id} SELL ATTIVATO\nEntry: {fmt_price(entry)}")
            else:
                continue

        if signal == "BUY":
            if low <= sl:
                close_fast_trade(trade, "LOSS")
                changed = True
                updates.append(
                    f"❌ FAST #{trade_id} BUY SL\n"
                    f"SL: {fmt_price(sl)}\n"
                    f"Consecutivi oggi: {fast_consecutive_sl_count(symbol)}"
                )
                pause_msg = maybe_fast_pause_message(symbol)
                if pause_msg:
                    updates.append(pause_msg)
                continue

            if high >= tp:
                close_fast_trade(trade, "WIN")
                changed = True
                updates.append(
                    f"✅ FAST #{trade_id} BUY TP PRESO\n"
                    f"Entry: {fmt_price(entry)}\n"
                    f"TP: {fmt_price(tp)}\n"
                    f"+{fmt_price(FAST_TP_POINTS)} punti"
                )
                continue

        if signal == "SELL":
            if high >= sl:
                close_fast_trade(trade, "LOSS")
                changed = True
                updates.append(
                    f"❌ FAST #{trade_id} SELL SL\n"
                    f"SL: {fmt_price(sl)}\n"
                    f"Consecutivi oggi: {fast_consecutive_sl_count(symbol)}"
                )
                pause_msg = maybe_fast_pause_message(symbol)
                if pause_msg:
                    updates.append(pause_msg)
                continue

            if low <= tp:
                close_fast_trade(trade, "WIN")
                changed = True
                updates.append(
                    f"✅ FAST #{trade_id} SELL TP PRESO\n"
                    f"Entry: {fmt_price(entry)}\n"
                    f"TP: {fmt_price(tp)}\n"
                    f"+{fmt_price(FAST_TP_POINTS)} punti"
                )
                continue

    if changed:
        save_fast_trades()

    for msg in updates:
        send_telegram(msg)

    return updates


# =========================
# v41 MAX DISCIPLINE / ONE CAMPAIGN MODE
# =========================

def trade_entry_mid(trade):
    low = to_float(trade.get("entry_low"), 0)
    high = to_float(trade.get("entry_high"), 0)
    if low and high:
        return (low + high) / 2.0
    return low or high or to_float(trade.get("entry"), 0)


def data_entry_mid(data):
    low = to_float(data.get("entry_low"), 0)
    high = to_float(data.get("entry_high"), 0)
    price = get_price_from_data(data) if "get_price_from_data" in globals() else to_float(data.get("price"), 0)
    if low and high:
        return (low + high) / 2.0
    return low or high or price


def trade_is_recent(trade, window_seconds):
    created = to_float(trade.get("created"), 0)
    if not created:
        return False
    return now_ts() - created <= window_seconds


def is_a_plus_setup(setup_type, score=0):
    setup = str(setup_type or "NORMAL").upper()
    return setup in MAX_DISCIPLINE_A_PLUS_SETUPS or int(score or 0) >= MAX_DISCIPLINE_REENTRY_MIN_SCORE


def recent_main_trades(symbol, signal=None, window_seconds=None):
    symbol = str(symbol or "XAUUSD").upper()
    signal = normalize_signal(signal) if signal else None
    window_seconds = window_seconds or MAX_DISCIPLINE_WINDOW_SECONDS
    out = []
    for trade in OPEN_TRADES:
        if str(trade.get("symbol", "")).upper() != symbol:
            continue
        if signal and str(trade.get("signal", "")).upper() != signal:
            continue
        if not trade_is_recent(trade, window_seconds):
            continue
        if trade.get("status") in ["CANCELLED", "EXPIRED"]:
            continue
        out.append(trade)
    return sorted(out, key=lambda x: to_float(x.get("created"), 0), reverse=True)


def same_direction_winners(symbol, signal, min_tp=1, window_seconds=None):
    winners = []
    for trade in recent_main_trades(symbol, signal, window_seconds):
        if int(trade.get("highest_tp", 0) or 0) >= int(min_tp):
            winners.append(trade)
    return winners


def max_discipline_context(signal, symbol, setup_type, score, data):
    signal = normalize_signal(signal)
    symbol = str(symbol or "XAUUSD").upper()
    setup = str(setup_type or "NORMAL").upper()
    score = int(score or 0)
    price = get_price_from_data(data) if "get_price_from_data" in globals() else to_float(data.get("price"), 0)
    entry_mid = data_entry_mid(data)
    day_position = to_float(data.get("day_position"), -1)
    event_active = bool(
        to_bool(data.get("event_mode"))
        or to_bool(data.get("auto_event_pine"))
        or to_bool(data.get("volume_spike"))
        or to_float(data.get("m15_range_atr"), 0) >= to_float(globals().get("BIG_MOVE_BREAKOUT_M15_ATR", 2.0), 2.0)
        or to_float(data.get("range_atr"), 0) >= 2.2
    )
    extreme_ok, extreme_info = extreme_zone_info(signal, data)
    recent_same = recent_main_trades(symbol, signal, MAX_DISCIPLINE_WINDOW_SECONDS)
    recent_normal_same = [t for t in recent_same if str(t.get("setup_type", "NORMAL")).upper() == "NORMAL"]
    winners_tp1 = same_direction_winners(symbol, signal, 1, MAX_DISCIPLINE_WINDOW_SECONDS)
    winners_tp3 = same_direction_winners(symbol, signal, MAX_DISCIPLINE_SPECIAL_TP_LOCK_LEVEL, MAX_DISCIPLINE_WINDOW_SECONDS)
    direct_losses_recent = get_recent_direct_losses_total(symbol, MAX_DISCIPLINE_DIRECT_SL_LOOKBACK_SECONDS)
    direct_losses_today = get_today_direct_losses(symbol)

    nearest_distance = None
    if entry_mid:
        distances = []
        for trade in recent_same:
            old_mid = trade_entry_mid(trade)
            if old_mid:
                distances.append(abs(entry_mid - old_mid))
        if distances:
            nearest_distance = min(distances)

    ctx = {
        "enabled": MAX_DISCIPLINE_ENABLED,
        "block": False,
        "reason": "Disciplina Max: OK",
        "reasons": [],
        "symbol": symbol,
        "signal": signal,
        "setup": setup,
        "score": score,
        "price": price,
        "entry_mid": entry_mid,
        "day_position": day_position,
        "event_active": event_active,
        "extreme_ok": extreme_ok,
        "extreme_info": extreme_info,
        "recent_same": recent_same,
        "recent_normal_same": recent_normal_same,
        "winners_tp1": winners_tp1,
        "winners_tp3": winners_tp3,
        "direct_losses_recent": direct_losses_recent,
        "direct_losses_today": direct_losses_today,
        "nearest_distance": nearest_distance,
    }

    if not MAX_DISCIPLINE_ENABLED:
        ctx["reason"] = "MAX_DISCIPLINE_ENABLED = FALSE"
        return ctx

    def add(reason):
        ctx["reasons"].append(reason)

    # v43) Daily Thesis sopra la disciplina: prima capisco il film della giornata.
    if ASIAN_THESIS_MAIN_BLOCK_ENABLED:
        daily_block = daily_thesis_block_context(signal, symbol, setup, score, data, is_fast=False)
        ctx["daily_thesis"] = daily_block.get("ctx")
        if daily_block.get("block"):
            for r in daily_block.get("reasons", []):
                add(r)

    # 1) Dopo 2 SL diretti il bot diventa subito più prudente: niente NORMAL,
    # niente entry basse/medie, passa solo A+ da zona Max.
    if MAX_DISCIPLINE_EARLY_DAILY_GUARD:
        sl_count = max(len(direct_losses_recent), len(direct_losses_today))
        if sl_count >= MAX_DISCIPLINE_DIRECT_SL_LIMIT:
            if setup == "NORMAL":
                add(f"Early guard: {sl_count} SL diretti; NORMAL bloccato")
            elif score < MAX_DISCIPLINE_REENTRY_MIN_SCORE and not extreme_ok:
                add(
                    f"Early guard: {sl_count} SL diretti; serve A+ score {MAX_DISCIPLINE_REENTRY_MIN_SCORE}+ o zona estrema"
                )

    # 2) News/event mode: se c'è spike/news, i NORMAL non devono diventare operazioni ufficiali.
    # Devono restare tesi finché non c'è setup speciale o score davvero alto.
    if MAX_DISCIPLINE_BLOCK_NORMAL_IN_EVENT and event_active and setup == "NORMAL" and score <= MAX_DISCIPLINE_EVENT_MAX_NORMAL_SCORE:
        add(f"Evento/news attivo: NORMAL con score {score}/{MAX_DISCIPLINE_EVENT_MAX_NORMAL_SCORE} declassato a tesi")

    # 3) Una volta che la direzione ha già pagato TP1/TP2, non si continua a mandare NORMAL.
    if MAX_DISCIPLINE_NORMAL_AFTER_TP_BLOCK and setup == "NORMAL" and winners_tp1:
        best = winners_tp1[0]
        add(
            f"Direzione {signal} già pagata: trade #{best.get('id')} a TP{best.get('highest_tp', 0)}; nuovo NORMAL diventa gestione/tesi"
        )

    # 4) Se una campagna speciale ha già TP3+, i nuovi speciali stessa direzione passano solo se c'è prezzo molto migliore.
    if MAX_DISCIPLINE_SPECIAL_AFTER_TP_BLOCK and setup != "NORMAL" and winners_tp3:
        if nearest_distance is not None and nearest_distance < MAX_DISCIPLINE_MIN_NEW_ENTRY_DISTANCE and score < MAX_DISCIPLINE_REENTRY_MIN_SCORE:
            best = winners_tp3[0]
            add(
                f"Campagna {signal} già viva a TP{best.get('highest_tp', 0)}; nuova entry troppo vicina ({round(nearest_distance, 2)} punti)"
            )

    # 5) Limite ufficiali nella stessa direzione: il bot può continuare a leggere la tesi,
    # ma non deve mandare 5-6 operazioni copiabili nello stesso movimento.
    if len(recent_same) >= MAX_DISCIPLINE_MAX_OFFICIAL_PER_DIRECTION:
        if not (is_a_plus_setup(setup, score) and extreme_ok and (nearest_distance is None or nearest_distance >= MAX_DISCIPLINE_MIN_NEW_ENTRY_DISTANCE)):
            add(
                f"Troppe operazioni ufficiali {signal} nella finestra: {len(recent_same)}/{MAX_DISCIPLINE_MAX_OFFICIAL_PER_DIRECTION}"
            )

    if setup == "NORMAL" and len(recent_normal_same) >= MAX_DISCIPLINE_MAX_NORMAL_PER_DIRECTION:
        add(
            f"NORMAL {signal} già usato nella finestra: {len(recent_normal_same)}/{MAX_DISCIPLINE_MAX_NORMAL_PER_DIRECTION}"
        )

    # 6) Continuation/campaign SELL non deve inseguire il prezzo basso: serve retest alto o score A+.
    continuation_setups = {
        "BEAR_CONTINUATION_SELL",
        "SYNTHETIC_BEAR_CONTINUATION_SELL",
        "BEAR_CAMPAIGN_SELL",
        "SYNTHETIC_FAILED_RETEST_SELL",
        "MAX_FAILED_RETEST_SELL",
    }
    if (
        MAX_DISCIPLINE_CONTINUATION_NEEDS_RETEST
        and signal == "SELL"
        and setup in continuation_setups
        and day_position >= 0
        and day_position <= MAX_DISCIPLINE_CONTINUATION_LOW_POSITION
        and not extreme_ok
        and score < MAX_DISCIPLINE_REENTRY_MIN_SCORE
    ):
        add(
            f"SELL continuation troppo basso nel range ({round(day_position, 2)}): serve retest alto/zona Max o score {MAX_DISCIPLINE_REENTRY_MIN_SCORE}+"
        )

    if ctx["reasons"]:
        ctx["block"] = True
        ctx["reason"] = ctx["reasons"][0]

    return ctx


def should_block_by_max_discipline(signal, symbol, setup_type, score, data):
    ctx = max_discipline_context(signal, symbol, setup_type, score, data)
    return bool(ctx.get("block")), ctx


def max_discipline_text(ctx):
    recent_same = ctx.get("recent_same", []) or []
    winners_tp1 = ctx.get("winners_tp1", []) or []
    winners_tp3 = ctx.get("winners_tp3", []) or []
    direct_recent = ctx.get("direct_losses_recent", []) or []
    direct_today = ctx.get("direct_losses_today", []) or []
    reasons = ctx.get("reasons", []) or [ctx.get("reason", "Disciplina Max")]
    lines = [
        f"Motivo principale: {ctx.get('reason')}",
        f"Ufficiali stessa direzione nella finestra: {len(recent_same)} / {MAX_DISCIPLINE_MAX_OFFICIAL_PER_DIRECTION}",
        f"Trade stessa direzione già a TP1+: {len(winners_tp1)}",
        f"Trade stessa direzione già a TP{MAX_DISCIPLINE_SPECIAL_TP_LOCK_LEVEL}+: {len(winners_tp3)}",
        f"SL diretti recenti: {len(direct_recent)} / guard {MAX_DISCIPLINE_DIRECT_SL_LIMIT}",
        f"SL diretti oggi: {len(direct_today)} / guard {MAX_DISCIPLINE_DIRECT_SL_LIMIT}",
        f"Day position: {round(ctx.get('day_position', -1), 3) if isinstance(ctx.get('day_position', -1), (int, float)) else ctx.get('day_position')}",
        f"Evento/news attivo: {ctx.get('event_active')}",
        f"Zona estrema OK: {ctx.get('extreme_ok')}",
        f"Distanza da entry recente più vicina: {round(ctx.get('nearest_distance'), 2) if isinstance(ctx.get('nearest_distance'), (int, float)) else 'N/D'}",
        "",
        "Daily Thesis:",
        daily_thesis_text(ctx.get("daily_thesis", {})),
        "",
        "Regole scattate:",
    ]
    lines.extend([f"- {r}" for r in reasons])
    return "\n".join(lines)


def recent_fast_trades(symbol, signal=None, window_seconds=None):
    symbol = str(symbol or "XAUUSD").upper()
    signal = normalize_signal(signal) if signal else None
    window_seconds = window_seconds or FAST_DISCIPLINE_WINDOW_SECONDS
    out = []
    for trade in FAST_TRADES:
        if str(trade.get("symbol", "")).upper() != symbol:
            continue
        if signal and str(trade.get("signal", "")).upper() != signal:
            continue
        created = to_float(trade.get("created"), 0)
        if created and now_ts() - created <= window_seconds:
            out.append(trade)
    return sorted(out, key=lambda x: to_float(x.get("created"), 0), reverse=True)


def has_main_context_for_fast(symbol, signal):
    signal = normalize_signal(signal)
    for trade in recent_main_trades(symbol, signal, MAX_DISCIPLINE_WINDOW_SECONDS):
        if int(trade.get("highest_tp", 0) or 0) >= FAST_MAIN_CONTEXT_MIN_TP:
            return True, trade
        if trade.get("status") in ["PENDING", "OPEN"] and str(trade.get("setup_type", "NORMAL")).upper() != "NORMAL":
            return True, trade
    return False, None

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

    # v33: se un trade aveva già pagato TP2/TP3+ e chiude a BE,
    # non cancelliamo mentalmente la tesi: resta un runner virtuale per re-entry/flip.
    if status == "BE":
        mark_virtual_runner(trade, f"{trade.get('signal')} chiuso a BE dopo TP{trade.get('highest_tp', 0)}")


def runner_message(trade, tp_level, tp_value):
    signal = trade.get("signal")
    trade_id = trade.get("id")
    setup = trade.get("setup_type", "NORMAL")

    return (
        f"🚀 RUNNER MODE ATTIVO\n\n"
        f"Trade #{trade_id} {signal}\n"
        f"Setup: {setup}\n"
        f"TP{tp_level} raggiunto: {tp_value}\n\n"
        f"Lettura v28:\n"
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


@app.route("/webhook_fast", methods=["POST"])
def webhook_fast():
    """
    Motore parallelo TP piccoli.
    Usa lo stesso JSON del Pine v47/v29, ma non entra nella pipeline v29.

    TradingView:
    - webhook principale: https://TUO-SERVIZIO.onrender.com/webhook
    - webhook fast:       https://TUO-SERVIZIO.onrender.com/webhook_fast
    """
    data = request.get_json(silent=True) or {}

    if str(data.get("type", "")).upper() == "PRICE_UPDATE":
        updates = handle_fast_price_update(data)
        return jsonify({
            "status": "fast_price_checked",
            "updates": len(updates),
            "fast_active_trades": len(fast_active_trades(data.get("symbol", "XAUUSD"))),
            "fast_total_trades": len(FAST_TRADES)
        })

    signal = normalize_signal(data.get("fast_signal") or data.get("signal"))
    if signal not in ["BUY", "SELL"]:
        return jsonify({
            "status": "ignored_fast_no_signal",
            "reason": "missing BUY/SELL signal"
        }), 400

    try:
        trade, blocked, block_reasons, reasons = build_fast_trade(data, signal)
    except Exception as e:
        return jsonify({
            "status": "error_fast_build_trade",
            "error": str(e)
        }), 400

    if blocked:
        # Per non intasare Telegram, mando i blocchi fast solo quando l'alert aveva score quasi valido.
        if to_int(trade.get("score"), 0) >= max(FAST_MIN_SCORE - 1, 1):
            send_telegram(fast_block_message(data, signal, trade, block_reasons))
        return jsonify({
            "status": "blocked_fast",
            "signal": signal,
            "score": trade.get("score"),
            "reasons": block_reasons
        })

    save_fast_trade(trade)

    message = fast_message(trade)
    telegram_sent = send_telegram(
        message,
        parse_mode="HTML" if FAST_USE_HTML_COPY_FORMAT else None
    )

    return jsonify({
        "status": "fast_sent",
        "signal": signal,
        "trade_id": trade.get("id"),
        "entry": trade.get("entry"),
        "sl": trade.get("sl"),
        "tp": trade.get("tp"),
        "score": trade.get("score"),
        "telegram_sent": telegram_sent
    })


@app.route("/fast_trades")
def fast_trades():
    return jsonify({
        "version": FAST_VERSION,
        "enabled": FAST_ENGINE_ENABLED,
        "count": len(FAST_TRADES),
        "active": len(fast_active_trades()),
        "today": len(fast_today_trades()),
        "tp_points": FAST_TP_POINTS,
        "sl_points": FAST_SL_POINTS,
        "min_sl_points": FAST_MIN_SL_POINTS,
        "event_sl_points": FAST_EVENT_SL_POINTS,
        "master_gate_enabled": FAST_MASTER_GATE_ENABLED,
        "trades": FAST_TRADES[-100:]
    })


@app.route("/fast_status")
def fast_status():
    symbol = request.args.get("symbol", "XAUUSD")
    return jsonify({
        "version": FAST_VERSION,
        "main_version": VERSION,
        "symbol": str(symbol).upper(),
        "pause": fast_pause_status(symbol),
        "fast_active_trades": len(fast_active_trades(symbol)),
        "fast_today_trades": len(fast_today_trades(symbol)),
        "fast_consecutive_sl": fast_consecutive_sl_count(symbol),
        "virtual_runner": get_virtual_runner(symbol),
        "master_regime": get_master_regime_context(symbol, {}),
        "max_flip_buy_enabled": MAX_FLIP_BUY_AFTER_SELL_BE_ENABLED
    })


@app.route("/test_fast")
def test_fast():
    fake = {
        "symbol": "XAUUSD",
        "signal": "BUY",
        "price": "4140.00",
        "tf": "1",
        "h1_bias": "BUY",
        "h4_bias": "BUY",
        "day_bias": "BUY",
        "candle_dir": "BULL",
        "rsi": "55",
        "ema20_slope": "UP",
        "ema50_slope": "UP",
        "close_above_ema200": "true",
        "day_position": "0.25"
    }
    trade, blocked, block_reasons, reasons = build_fast_trade(fake, "BUY")
    if blocked:
        ok = send_telegram(fast_block_message(fake, "BUY", trade, block_reasons))
        return jsonify({"status": "fast_test_blocked", "sent": ok, "reasons": block_reasons})
    ok = send_telegram(fast_message(trade), parse_mode="HTML")
    return jsonify({"status": "fast_test_sent", "sent": ok, "trade": trade})



def maybe_send_fast_from_main_webhook(data, signal, main_trade=None, main_setup_type=None, source="main_webhook"):
    """
    v31: alimenta il motore FAST anche dal webhook principale.
    Così non serve per forza creare un secondo alert TradingView.
    La v29/v30 principale resta indipendente: se FAST si blocca, il trade principale non cambia.
    """
    result = {
        "enabled": FAST_ENGINE_ENABLED,
        "auto_from_main": FAST_AUTO_FROM_MAIN_WEBHOOK,
        "status": "skipped",
        "sent": False,
        "trade_id": None,
        "reasons": []
    }

    if not FAST_ENGINE_ENABLED:
        result["status"] = "disabled"
        result["reasons"] = ["FAST_ENGINE_ENABLED = FALSE"]
        return result

    if not FAST_AUTO_FROM_MAIN_WEBHOOK:
        result["status"] = "auto_from_main_disabled"
        result["reasons"] = ["FAST_AUTO_FROM_MAIN_WEBHOOK = FALSE"]
        return result

    setup = str(main_setup_type or data.get("setup") or data.get("setup_type") or "NORMAL")
    if setup not in FAST_MAIN_ALLOWED_SETUPS:
        result["status"] = "main_setup_not_allowed"
        result["reasons"] = [f"setup principale non abilitato al FAST: {setup}"]
        return result

    try:
        fast_trade, blocked, block_reasons, _ = build_fast_trade(data, signal)
    except Exception as e:
        result["status"] = "error"
        result["reasons"] = [str(e)]
        return result

    fast_trade["source"] = source
    if main_trade:
        fast_trade["main_trade_id"] = main_trade.get("id")
        fast_trade["main_setup_type"] = main_trade.get("setup_type")

    if blocked:
        result["status"] = "blocked"
        result["reasons"] = block_reasons
        if FAST_SEND_BLOCKED_FROM_MAIN:
            send_telegram(fast_block_message(data, signal, fast_trade, block_reasons))
        return result

    save_fast_trade(fast_trade)
    sent = send_telegram(
        fast_message(fast_trade),
        parse_mode="HTML" if FAST_USE_HTML_COPY_FORMAT else None
    )

    result.update({
        "status": "sent",
        "sent": sent,
        "trade_id": fast_trade.get("id"),
        "entry": fast_trade.get("entry"),
        "sl": fast_trade.get("sl"),
        "tp": fast_trade.get("tp")
    })
    return result


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(silent=True) or {}

    if str(data.get("type", "")).upper() == "PRICE_UPDATE":
        # v24: ogni update alimenta il warmup prima di valutare trigger autonomi.
        note_price_update_for_warmup(data)

        # v20:
        # 1) aggiorna Auto Event + memoria spike;
        # 2) gestisce i trade già esistenti;
        # 3) fa avanzare la macchina a stati;
        # 4) se il failed retest è confermato, Python può creare un SELL autonomo.
        detect_auto_event_from_data(data)
        updates = handle_price_update(data)

        # Motore parallelo FAST: usa gli stessi PRICE_UPDATE solo per gestire TP/SL fast.
        # Non modifica la logica decisionale v29.
        fast_updates = handle_fast_price_update(data)

        # v20 state machine: event spike -> failed retest.
        synthetic_result = process_event_state_machine(data)

        # v21 state machine: bear impulse -> relief rally -> lower high -> continuation SELL.
        bear_result = process_bear_continuation_state_machine(data)

        # v43: aggiorna e notifica la tesi giornaliera Asia/Londra/NY.
        daily_thesis_ctx = update_daily_thesis(data)
        daily_thesis_alert = maybe_daily_thesis_alert(data.get("symbol", "XAUUSD"), data)
        if daily_thesis_alert:
            send_telegram(daily_thesis_alert)

        # v23: failed recovery prima del bear impulse completo.
        pre_bear_result = process_pre_bear_thesis(data)
        deep_extension_ctx = get_deep_extension_context(
            data.get("symbol", "XAUUSD"),
            data
        )

        # v22: persiste la tesi e gestisce il basket/campaign.
        campaign = sync_bear_campaign(
            data.get("symbol", "XAUUSD"),
            data
        )

        campaign_messages = manage_bear_campaign_on_price_update(data)
        for campaign_message in campaign_messages:
            send_telegram(campaign_message)

        # v33: se un SELL già pagato/BE viene invalidato da recupero forte,
        # genera un BUY autonomo stile Max senza aspettare un nuovo alert Pine.
        max_flip_buy_result = process_max_flip_buy_after_sell_be(data)

        # v25/v28: aggiorna l'arbitro centrale sul nuovo prezzo e valuta Big Move Thesis.
        regime_ctx = get_regime_arbiter_context(data.get("symbol", "XAUUSD"), data)
        big_move_ctx = regime_ctx.get("big_move") or get_big_move_thesis_context(data.get("symbol", "XAUUSD"), data)
        big_move_alert = maybe_big_move_thesis_alert(data.get("symbol", "XAUUSD"), data, big_move_ctx)
        if big_move_alert:
            send_telegram(big_move_alert)

        # v24: snapshot periodico della memoria runtime.
        save_runtime_state(force=False)
        warmup_ctx = warmup_status(data.get("symbol", "XAUUSD"))

        return jsonify({
            "status": "price_checked",
            "updates": len(updates),
            "fast_updates": len(fast_updates),
            "fast_active_trades": len(fast_active_trades(data.get("symbol", "XAUUSD"))),
            "synthetic_triggered": synthetic_result.get("triggered"),
            "synthetic_trade_id": synthetic_result.get("trade_id"),
            "event_state": synthetic_result.get("state"),
            "event_reason": synthetic_result.get("reason"),
            "bear_triggered": bear_result.get("triggered"),
            "bear_trade_id": bear_result.get("trade_id"),
            "bear_state": bear_result.get("state"),
            "bear_reason": bear_result.get("reason"),
            "daily_thesis_status": daily_thesis_ctx.get("status"),
            "daily_thesis_preferred": daily_thesis_ctx.get("preferred"),
            "daily_thesis_reason": daily_thesis_ctx.get("reason"),
            "max_flip_buy_triggered": max_flip_buy_result.get("triggered"),
            "max_flip_buy_trade_id": max_flip_buy_result.get("trade_id"),
            "max_flip_buy_reason": max_flip_buy_result.get("reason"),
            "pre_bear_status": pre_bear_result.get("status"),
            "pre_bear_confirmed": pre_bear_result.get("confirmed"),
            "pre_bear_reason": pre_bear_result.get("reason"),
            "deep_extension_active": deep_extension_ctx.get("active"),
            "deep_extension_position": deep_extension_ctx.get("position"),
            "deep_extension_rebound": deep_extension_ctx.get("rebound_from_low"),
            "state_warm": warmup_ctx.get("warm"),
            "warmup_elapsed_seconds": warmup_ctx.get("elapsed_seconds"),
            "warmup_update_count": warmup_ctx.get("update_count"),
            "runtime_state_restored": RUNTIME_STATE_RESTORED,
            "regime_mode": regime_ctx.get("mode"),
            "regime_reason": regime_ctx.get("reason"),
            "recovery_dominance_active": regime_ctx.get("recovery", {}).get("active"),
            "sell_profit_lock_active": regime_ctx.get("sell_profit_lock", {}).get("active"),
            "sell_profit_lock_reason": regime_ctx.get("sell_profit_lock", {}).get("reason"),
            "loss_recovery_active": regime_ctx.get("loss_recovery", {}).get("active"),
            "loss_recovery_reason": regime_ctx.get("loss_recovery", {}).get("reason"),
            "big_move_active": big_move_ctx.get("active"),
            "big_move_status": big_move_ctx.get("status"),
            "big_move_reason": big_move_ctx.get("reason"),
            "big_move_targets": big_move_ctx.get("target_levels"),
            "bear_trigger_mature": regime_ctx.get("maturity", {}).get("mature"),
            "campaign_id": campaign.get("campaign_id"),
            "campaign_status": campaign.get("status"),
            "campaign_legs": len(campaign.get("legs", [])),
            "campaign_risk_weight": campaign.get("total_risk_weight"),
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

    # v22: valuta una eventuale nuova leg della campagna.
    campaign_decision = evaluate_campaign_leg(
        signal,
        symbol,
        setup_type,
        score,
        data
    )

    # v23: se si chiama BEAR_CAMPAIGN_SELL deve essere davvero una leg contabilizzata.
    setup_type, score, reasons, campaign_decision = reconcile_campaign_setup(
        signal,
        symbol,
        setup_type,
        score,
        reasons,
        data,
        campaign_decision
    )

    # v25: decisione Smart Kill PRE_BEAR calcolata una sola volta.
    _, precomputed_extreme_info = extreme_zone_info(signal, data)
    smart_kill_decision = smart_kill_pre_bear_decision(
        signal, symbol, setup_type, score, data,
        extreme_info=precomputed_extreme_info
    )

    # v35: FAST parallelo ma non cieco.
    # Di default NON lo provo prima dei blocchi principali: prima decide il Master Regime.
    # Se vuoi tornare al comportamento aggressivo, metti FAST_AUTO_BEFORE_MAIN_BLOCKS=TRUE.
    fast_pre_result = {"status": "skipped"}
    if FAST_AUTO_BEFORE_MAIN_BLOCKS:
        fast_pre_result = maybe_send_fast_from_main_webhook(
            data,
            signal,
            main_trade=None,
            main_setup_type=setup_type,
            source="pre_main_blocks"
        )

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
            "setup_type": setup_type,
            "fast_pre": fast_pre_result
        })

    # =========================
    # POST SL QUARANTINE BLOCK v37
    # =========================

    block_post_sl, post_sl_ctx = post_sl_quarantine_context(
        signal,
        symbol,
        setup_type,
        score,
        data
    )

    if block_post_sl:
        text = f"""🧊🚫 SEGNALE BLOCCATO {VERSION}

Motivo: Anti Whipsaw / Post SL Quarantine

Segnale: {signal}
Symbol: {symbol}
Prezzo: {price}
Setup: {setup_type}
Score finale: {score}

{post_sl_quarantine_text(post_sl_ctx)}

Azione:
Dopo uno SL diretto il bot non flippa subito BUY ↔ SELL.
Aspetta retest, micro BOS e zona migliore stile Max.
"""
        send_telegram(text)

        return jsonify({
            "status": "blocked_post_sl_quarantine",
            "score": score,
            "setup_type": setup_type,
            "last_loss_signal": post_sl_ctx.get("last_loss_signal"),
            "last_loss_setup": post_sl_ctx.get("last_loss_setup"),
            "remaining_seconds": post_sl_ctx.get("remaining_seconds"),
            "confirmation_ok": post_sl_ctx.get("confirmation_ok"),
            "fast_pre": fast_pre_result
        })

    # =========================
    # MASTER REGIME BLOCK v34
    # =========================

    block_master, master_ctx, master_reason = should_block_by_master_regime(
        signal, symbol, setup_type, score, data
    )

    if block_master:
        text = f"""🧠🚫 SEGNALE BLOCCATO {VERSION}

Motivo: Master Regime / One Direction Control

Segnale: {signal}
Symbol: {symbol}
Prezzo: {price}
Setup: {setup_type}
Score finale: {score}

{master_regime_status_text(master_ctx)}

Dettaglio:
{master_reason}

Azione:
Il bot sceglie una tesi dominante prima del singolo segnale.
- In SELL_CONTROL non compra ogni rimbalzo o nuovo minimo.
- Le news bullish vengono declassate se il prezzo conferma bear impulse/lower-high.
- Il FAST segue la direzione dominante e non va contro regime.
- Il BUY di rimbalzo passa solo dopo SELL già pagato e zona bassa vera.
"""
        send_telegram(text)
        return jsonify({
            "status": "blocked_master_regime",
            "score": score,
            "setup_type": setup_type,
            "master_mode": master_ctx.get("mode"),
            "master_reason": master_reason,
            "fast_pre": fast_pre_result
        })

    # =========================
    # COLD START WARMUP BLOCK v24
    # =========================

    warmup_ctx = warmup_status(symbol)

    if (
        STATE_WARMUP_ENABLED
        and not warmup_ctx.get("warm")
        and signal == "SELL"
        and setup_type == "NORMAL"
        and int(score) < STATE_WARMUP_NORMAL_SELL_MIN_SCORE
    ):
        text = f"""🧊⏳ SELL BLOCCATO {VERSION}

Motivo: Cold Start Warmup

Segnale: {signal}
Symbol: {symbol}
Prezzo: {price}
Setup: {setup_type}
Score finale: {score}
Score minimo temporaneo NORMAL SELL: {STATE_WARMUP_NORMAL_SELL_MIN_SCORE}

Warmup:
- Update ricevuti: {warmup_ctx.get('update_count')}/{STATE_WARMUP_MIN_PRICE_UPDATES}
- Secondi osservati: {round(warmup_ctx.get('elapsed_seconds', 0), 1)}/{STATE_WARMUP_SECONDS}
- Storico runtime: {warmup_ctx.get('history_count')}
- Runtime ripristinato: {RUNTIME_STATE_RESTORED}

Azione:
Durante il cold start il bot non apre NORMAL SELL deboli senza memoria sufficiente.
"""
        send_telegram(text)

        return jsonify({
            "status": "blocked_cold_start_warmup",
            "score": score,
            "setup_type": setup_type,
            "warmup": warmup_ctx
        })

    # =========================
    # REGIME ARBITER BLOCK v25
    # =========================

    block_regime, regime_ctx, regime_reason = should_block_by_regime_arbiter(
        signal, symbol, setup_type, score, data
    )

    if block_regime:
        maturity_ctx = regime_ctx.get("maturity", {})
        recovery_ctx = regime_ctx.get("recovery", {})

        text = f"""🧭🚫 SEGNALE BLOCCATO {VERSION}

Motivo: Regime Arbiter

Segnale: {signal}
Symbol: {symbol}
Prezzo: {price}
Setup: {setup_type}
Score finale: {score}

{regime_arbiter_status_text(regime_ctx)}

Master Regime:
{master_regime_status_text(regime_ctx.get('master_regime', {}))}

Dettaglio:
{regime_reason}

Trigger Maturity:
{bear_trigger_maturity_text(maturity_ctx)}

Special BUY Dominance:
{recovery_dominance_text(recovery_ctx)}

Special BUY Protection:
{special_buy_counter_sell_text(regime_ctx.get('counter_sell_override', {}))}

Max Flip Window v31:
{special_buy_flip_window_text(regime_ctx.get('special_buy_flip_window', {}))}

Max Zone Gate:
{max_zone_sell_gate_text(regime_ctx.get('max_zone_gate', {}))}

Sell Profit Lock:
{sell_profit_lock_status_text(regime_ctx.get('sell_profit_lock', {}))}

Profit Lock Allow:
{sell_profit_lock_allow_text(regime_ctx.get('sell_profit_lock_allow', {}))}

Loss Recovery / True Max Zone:
{true_max_zone_reentry_text(regime_ctx.get('loss_recovery', {}))}

Big Move Thesis:
{big_move_thesis_text(regime_ctx.get('big_move', {}))}

Max Pullback Re-Arm v36:
{max_pullback_rearm_text(regime_ctx.get('pullback_rearm', {}))}

Anti-Fade Super BUY v36:
{anti_fade_super_buy_text(regime_ctx.get('anti_fade_super_buy', {}))}

Post Super BUY Guard v39:
{post_super_buy_guard_text(regime_ctx.get('post_super_buy_guard', {}))}

Event Trap Flip:
{event_trap_flip_text(regime_ctx.get('event_trap_flip', {}))}

Deep Extension Sell Guard:
{deep_extension_sell_guard_text(regime_ctx.get('deep_extension_sell_guard', {}))}

Azione:
Il bot usa una sola tesi dominante.
- SELL NORMAL bloccati contro BUY speciale attivo
- continuation/campaign SELL solo con trigger maturo
- nessun continuation SELL contro BUY speciale TP3+ ancora valido
- SELL contro BUY forte solo se speciale, in zona Max, score alto e micro-BOS
- se il SELL ha già preso TP8/Runner, comprimo nuove entrate simili
- dopo 2 SL SELL, accetto solo vera zona Max alta
- se un trade è TP3+ e protetto, attivo Big Move Watch/Confirmed
- v36: dopo BUY TP5+ non vendo pullback non invalidati con MAX_FADE prematuro
- v36: se il pullback tiene supporto, il BUY può riarmarsi anche se prima c'era SELL_CONTROL
- v39: dopo SUPER BUY/TP8 non apro BEAR_CAMPAIGN prematura; passa solo Extreme Spike Fade maturo
- Event Trap Flip può ribaltare SUPER BUY in SUPER SELL da zona alta evento
- Deep Extension deve essere realmente riarmata
"""
        send_telegram(text)
        return jsonify({
            "status": "blocked_regime_arbiter",
            "score": score,
            "setup_type": setup_type,
            "regime_mode": regime_ctx.get("mode"),
            "regime_reason": regime_reason
        })

    if signal == "SELL" and regime_ctx.get("event_trap_flip", {}).get("allow"):
        reasons.append("EVENT TRAP FLIP: SELL A+ autorizzato contro BUY recovery / Big Move BUY")

    if signal == "SELL" and regime_ctx.get("special_buy_flip_window", {}).get("allow"):
        reasons.append("MAX FLIP WINDOW v31: flip SELL autorizzato contro BUY già pagato")

    # =========================
    # PRE-BEAR BUY BLOCK v23
    # =========================

    block_pre_bear_buy, pre_bear_state, pre_bear_block_reason = should_block_buy_by_pre_bear(
        signal,
        symbol,
        setup_type,
        score,
        data
    )

    if block_pre_bear_buy:
        text = f"""🐻🟠 BUY BLOCCATO {VERSION}

Motivo: Pre-Bear Thesis / Failed Recovery

Segnale: {signal}
Symbol: {symbol}
Prezzo: {price}
Setup: {setup_type}
Score finale: {score}

{pre_bear_status_text(symbol)}

Dettaglio:
{pre_bear_block_reason}

Azione:
Il bot non compra il rimbalzo quando il recupero sta fallendo prima del bear impulse completo.
"""
        send_telegram(text)

        return jsonify({
            "status": "blocked_pre_bear_thesis",
            "score": score,
            "setup_type": setup_type,
            "pre_bear_status": pre_bear_state.get("status"),
            "pre_bear_reason": pre_bear_block_reason
        })

    # =========================
    # BEARISH CONTINUATION BUY BLOCK v21
    # =========================

    block_bear_buy, bear_state, bear_block_reason = should_block_buy_by_bear_state(
        signal,
        symbol,
        setup_type,
        score,
        data
    )

    if block_bear_buy:
        text = f"""🐻🔒 BUY BLOCCATO {VERSION}

Motivo: Bearish Continuation / Lower High State

Segnale: {signal}
Symbol: {symbol}
Prezzo: {price}
Setup: {setup_type}
Score finale: {score}

{bear_state_status_text(symbol)}

Dettaglio:
{bear_block_reason}

Azione:
Il bot non compra ogni nuovo minimo/rimbalzo dentro una gamba ribassista.
Aspetta invalidazione reale oppure recovery BUY eccezionale.
"""
        send_telegram(text)

        return jsonify({
            "status": "blocked_bear_continuation_state",
            "score": score,
            "setup_type": setup_type,
            "bear_state": bear_state.get("state"),
            "bear_reason": bear_block_reason
        })

    # =========================
    # SYNTHETIC EVENT STATE BUY BLOCK v20
    # =========================

    block_state_buy, synthetic_state = should_block_buy_by_synthetic_state(
        signal,
        symbol
    )

    if block_state_buy:
        text = f"""🧠🔒 BUY BLOCCATO {VERSION}

Motivo: Event State Machine

Segnale: {signal}
Symbol: {symbol}
Prezzo: {price}
Setup: {setup_type}
Score finale: {score}

{event_state_status_text(symbol)}

Azione:
Il Python ha già armato un retest alto post-evento.
Non compro il rimbalzo mentre il pattern SELL è in preparazione/conferma.
"""
        send_telegram(text)

        return jsonify({
            "status": "blocked_synthetic_event_state",
            "score": score,
            "setup_type": setup_type,
            "event_state": synthetic_state.get("state"),
            "event_reason": synthetic_state.get("reason")
        })

    # =========================
    # SL COOLDOWN BLOCK
    # =========================

    block_sl_cooldown, recent_losses = should_block_by_sl_cooldown(signal, symbol)

    campaign_sl_override, campaign_sl_decision = campaign_sl_override_eligible(
        signal,
        symbol,
        setup_type,
        score,
        data
    )

    if block_sl_cooldown and not campaign_sl_override:
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

    if block_sl_cooldown and campaign_sl_override:
        campaign_decision = campaign_sl_decision
        reasons.append(
            "Campaign override controllato del SELL SL cooldown"
        )

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
    # DEEP EXTENSION FLIP BLOCK v23
    # =========================

    block_deep_sell, deep_ctx, deep_reason = should_block_sell_by_deep_extension(
        signal,
        symbol,
        setup_type,
        data
    )

    if block_deep_sell:
        text = f"""🧯🔄 SELL BLOCCATO {VERSION}

Motivo: Deep Extension Flip

Segnale: {signal}
Symbol: {symbol}
Prezzo: {price}
Setup: {setup_type}
Score finale: {score}

{deep_extension_status_text(deep_ctx)}

Dettaglio:
{deep_reason}

Azione:
Dopo TP profondi / drop enorme il bot non vende il minimo.
Aspetta un vero rimbalzo per riarmare SELL oppure favorisce MAX_RECOVERY_BUY.
"""
        send_telegram(text)

        return jsonify({
            "status": "blocked_deep_extension_sell",
            "score": score,
            "setup_type": setup_type,
            "deep_extension_active": deep_ctx.get("active"),
            "deep_extension_position": deep_ctx.get("position"),
            "deep_extension_rebound": deep_ctx.get("rebound_from_low")
        })

    # =========================
    # CHAOS DAY / EXTREME ZONE BLOCK v15
    # =========================

    block_chaos, chaos_ctx, extreme_info, chaos_reason = should_block_by_chaos_mode(
        signal,
        symbol,
        setup_type,
        score,
        data,
        smart_kill_decision=smart_kill_decision
    )

    if block_chaos:
        text = f"""🌪️ SEGNALE BLOCCATO {VERSION}

Motivo: Chaos Day / Extreme Zone Filter

Segnale: {signal}
Symbol: {symbol}
Prezzo: {price}
Setup: {setup_type}
Score finale: {score}

{chaos_status_text(chaos_ctx, extreme_info, chaos_reason)}

Azione:
Giornata tossica o troppi SL diretti.
Il bot non prende segnali nel mezzo.
In Chaos Mode passa solo:
- SELL da zona alta estrema
- BUY da zona bassa estrema
- setup speciale e score sufficiente
"""
        send_telegram(text)

        return jsonify({
            "status": "blocked_chaos_mode",
            "score": score,
            "setup_type": setup_type,
            "chaos_reason": chaos_reason,
            "extreme_ok": extreme_info.get("ok"),
            "direct_losses_recent": len(chaos_ctx.get("recent_losses", [])),
            "direct_losses_today": len(chaos_ctx.get("today_losses", []))
        })



    # =========================
    # BUY FATIGUE BLOCK v14/v15
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
    # v30 BUY CAMPAIGN EXHAUSTION
    # =========================

    block_buy_campaign, buy_campaign_ctx = should_block_by_buy_campaign_exhaustion(
        signal,
        symbol,
        setup_type,
        score,
        data
    )

    if block_buy_campaign:
        text = f"""🟢🧯 BUY BLOCCATO {VERSION}

Motivo: Buy Campaign Exhaustion / non inseguire onda già pagata

Segnale: {signal}
Symbol: {symbol}
Prezzo: {price}
Setup: {setup_type}
Score finale: {score}

{buy_campaign_exhaustion_text(buy_campaign_ctx)}

Azione:
La campagna BUY ha già pagato TP profondi.
Il bot non apre nuovi BUY alti: aspetta pullback basso vero oppure score molto forte.
"""
        send_telegram(text)

        return jsonify({
            "status": "blocked_buy_campaign_exhaustion",
            "score": score,
            "setup_type": setup_type,
            "day_position": buy_campaign_ctx.get("day_position"),
            "recent_buy_winners": len(buy_campaign_ctx.get("winners", []))
        })

    # =========================
    # v30 CAMPAIGN PROFIT LOCK
    # =========================

    block_campaign_lock, campaign_lock_ctx = should_block_by_campaign_profit_lock(
        signal,
        symbol,
        setup_type,
        score,
        data
    )

    if block_campaign_lock:
        text = f"""🔒 SEGNALE BLOCCATO {VERSION}

Motivo: Campaign Profit Lock stile Max

Segnale: {signal}
Symbol: {symbol}
Prezzo: {price}
Setup: {setup_type}
Score finale: {score}

{campaign_profit_lock_text(campaign_lock_ctx)}

Azione:
Dopo TP1 + BE il bot gestisce la campagna invece di aprire subito il contrario.
Il contrario passa solo se c'è vera invalidazione o setup A+ da zona Max.
"""
        send_telegram(text)

        return jsonify({
            "status": "blocked_campaign_profit_lock",
            "score": score,
            "setup_type": setup_type,
            "lock_reason": campaign_lock_ctx.get("reason"),
            "protected_trade_id": (campaign_lock_ctx.get("trade") or {}).get("id"),
            "protected_direction": (campaign_lock_ctx.get("trade") or {}).get("signal")
        })

    # =========================
    # CONFLICT RESOLVER BLOCK v14/v15
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

    block_recovery_lock, recovery_ctx = should_block_sell_by_recovery_lock(signal, symbol, setup_type, score, data)

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
EXTREME_SPIKE_FADE_SELL può passare se BUY già pagato e spike evento è in failed retest alto.
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
    # v41 MAX DISCIPLINE / ONE CAMPAIGN MODE
    # =========================

    block_max_discipline, max_discipline_ctx = should_block_by_max_discipline(
        signal,
        symbol,
        setup_type,
        score,
        data
    )

    if block_max_discipline:
        text = f"""🧭 SEGNALE BLOCCATO {VERSION}

Motivo: Max Discipline / One Campaign Mode

Segnale: {signal}
Symbol: {symbol}
Prezzo: {price}
Setup: {setup_type}
Score finale: {score}

{max_discipline_text(max_discipline_ctx)}

Azione:
La lettura può essere utile come TESI, ma non diventa una nuova operazione ufficiale.
Il bot evita layering eccessivo: dopo una direzione già pagata gestisce, protegge e aspetta nuova zona Max.
"""
        send_telegram(text)

        return jsonify({
            "status": "blocked_max_discipline",
            "score": score,
            "setup_type": setup_type,
            "max_discipline_reason": max_discipline_ctx.get("reason"),
            "recent_same_direction": len(max_discipline_ctx.get("recent_same", [])),
            "winners_tp1": len(max_discipline_ctx.get("winners_tp1", [])),
            "winners_tp3": len(max_discipline_ctx.get("winners_tp3", [])),
            "direct_losses_recent": len(max_discipline_ctx.get("direct_losses_recent", [])),
            "direct_losses_today": len(max_discipline_ctx.get("direct_losses_today", []))
        })


    # =========================
    # DUPLICATE BLOCK
    # =========================

    block_duplicate, recent = should_block_duplicate(signal, symbol, score)

    duplicate_campaign_override, duplicate_campaign_decision = campaign_duplicate_override_allowed(
        signal,
        symbol,
        setup_type,
        score,
        data
    )

    if block_duplicate and not duplicate_campaign_override:
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

    if block_duplicate and duplicate_campaign_override:
        campaign_decision = duplicate_campaign_decision
        reasons.append(
            "Nuovo retest/prezzo migliore: duplicato trasformato in campaign leg"
        )

    # =========================
    # SAVE TRADE
    # =========================

    trade = save_trade(data, signal, score, setup_type)

    if campaign_decision.get("allow"):
        register_campaign_leg(
            trade,
            campaign_decision
        )

    if smart_kill_decision.get("allow"):
        register_smart_kill_pre_bear_override(trade, smart_kill_decision)

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

    if trade.get("campaign_id"):
        lines.extend([
            f"🧠 Campaign ID: {trade.get('campaign_id')}",
            f"🪜 Campaign Leg: {trade.get('campaign_leg')}/{CAMPAIGN_MAX_LEGS}",
            f"⚖️ Risk Weight Leg: {trade.get('campaign_risk_weight')}",
            f"📦 Risk Weight Totale: {get_bear_campaign(symbol).get('total_risk_weight')}/{CAMPAIGN_TOTAL_RISK_CAP}"
        ])

    if trade.get("smart_kill_override"):
        lines.extend([
            "🛡 Smart Kill Override: PRE_BEAR",
            f"⚖️ Risk Weight Informativo: {trade.get('smart_kill_risk_weight')}",
            f"🎟 Tentativo Override: {trade.get('smart_kill_attempt_number')}/{SMART_KILL_PRE_BEAR_MAX_ATTEMPTS}"
        ])

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

    entry_copy = f"{entry_low} - {entry_high}" if entry_low and entry_high else str(price)
    tp1_copy = data.get("tp1", "")
    lines.extend([
        "",
        "📋 COPIA RAPIDA MT4",
        f"Symbol: {symbol}",
        f"Type: {signal}",
        f"Entry: {entry_copy}",
        f"SL: {sl}",
        f"TP: {tp1_copy}",
        "",
        "Nota: copia solo se il messaggio sopra è OPERAZIONE UFFICIALE.",
        "I messaggi BLOCCATI/TESI non sono entry.",
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

    # v30: FAST scalper parallelo alimentato anche dal webhook principale.
    # Se FAST viene bloccato o va in errore, il trade principale rimane comunque valido.
    if FAST_AUTO_BEFORE_MAIN_BLOCKS and fast_pre_result.get("status") == "sent":
        fast_auto_result = fast_pre_result
        fast_auto_result["linked_main_trade_id"] = trade.get("id")
    else:
        fast_auto_result = maybe_send_fast_from_main_webhook(
            data,
            signal,
            main_trade=trade,
            main_setup_type=setup_type,
            source="after_main_sent"
        )

    return jsonify({
        "status": "sent",
        "signal": signal,
        "score": score,
        "setup_type": setup_type,
        "trade_id": trade["id"],
        "campaign_id": trade.get("campaign_id"),
        "campaign_leg": trade.get("campaign_leg"),
        "campaign_risk_weight": trade.get("campaign_risk_weight"),
        "smart_kill_override": trade.get("smart_kill_override", False),
        "smart_kill_risk_weight": trade.get("smart_kill_risk_weight"),
        "telegram_sent": telegram_sent,
        "fast_auto": fast_auto_result
    })


# =========================
# STARTUP
# =========================

load_runtime_state()
load_trades()
load_fast_trades()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
