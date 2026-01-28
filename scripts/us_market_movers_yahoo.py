import os
import json
import yfinance as yf
import pandas as pd
import requests
import pytz
from datetime import datetime

# =========================
# CONFIG
# =========================
PREMARKET_THRESHOLD = 1.0   # %
MARKET_THRESHOLD = 2.0      # %
VOLUME_MULTIPLIER = 1.5     # volume spike
STATE_FILE = "alerted.json"

# =========================
# Load Telegram secrets
# =========================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    raise RuntimeError("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID")

# =========================
# Telegram sender
# =========================
def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    requests.post(url, json=payload, timeout=10)

# =========================
# Market session helpers
# =========================
def market_state():
    us_tz = pytz.timezone("US/Eastern")
    now = datetime.now(us_tz)

    pre = now.replace(hour=4, minute=0, second=0, microsecond=0)
    open_ = now.replace(hour=9, minute=30, second=0, microsecond=0)
    close = now.replace(hour=16, minute=0, second=0, microsecond=0)

    if pre <= now < open_:
        return "PREMARKET"
    if open_ <= now <= close:
        return "MARKET"
    return "CLOSED"

# =========================
# Load / save alerted state
# =========================
def load_alerted():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_alerted(alerted):
    with open(STATE_FILE, "w") as f:
        json.dump(list(alerted), f)

# =========================
# Tickers
# =========================
WATCHLIST = ["MA", "V", "WM", "PL", "UNG"]
CRYPTO_STOCKS = ["BMNR", "NU", "SUIG", "RIOT"]

BASE_TICKERS = [
    "AAPL","MSFT","NVDA","AMZN","META","GOOGL","GOOG","TSLA",
    "AMD","NFLX","AVGO","INTC","QCOM","MU","TXN","AMAT","LRCX","KLAC",
    "JPM","BAC","WFC","GS","MS","C","SCHW","BLK","AXP","USB","PNC",
    "XOM","CVX","COP","SLB","OXY","MPC","VLO","PSX",
    "JNJ","PFE","MRK","LLY","UNH","ABBV","TMO","ABT","DHR","MDT",
    "HD","LOW","NKE","MCD","SBUX","BKNG","TJX",
    "WMT","COST","PG","KO","PEP","PM","MO","CL",
    "BA","CAT","GE","RTX","DE","UPS","FDX","MMM","HON","ETN",
    "DIS","CMCSA","VZ","T","TMUS",
    "LIN","APD","ECL","SHW","FCX","NEM"
]

ALL_TICKERS = sorted(set(BASE_TICKERS + WATCHLIST + CRYPTO_STOCKS))

# =========================
# Emoji strength
# =========================
def strength_emoji(pct):
    pct = abs(pct)
    if pct >= 5:
        return "🚨"
    if pct >= 3:
        return "🔥"
    return ""

# =========================
# Main
# =========================
def main():
    state = market_state()
    if state == "CLOSED":
        send_telegram_message("⏳ US market is closed.")
        return

    threshold = PREMARKET_THRESHOLD if state == "PREMARKET" else MARKET_THRESHOLD
    alerted = load_alerted()
    movers = []

    for ticker in ALL_TICKERS:
        try:
            t = yf.Ticker(ticker)
            info = t.fast_info

            prev_close = info.get("previous_close")
            price = info.get("last_price")
            volume = info.get("last_volume")
            avg_volume = info.get("ten_day_average_volume")

            if not all([prev_close, price, volume, avg_volume]):
                continue

            pct = ((price - prev_close) / prev_close) * 100

            if abs(pct) < threshold:
                continue

            if volume < avg_volume * VOLUME_MULTIPLIER:
                continue

            if ticker in alerted:
                continue

            movers.append({
                "ticker": ticker,
                "pct": round(pct, 2),
                "price": round(price, 2),
                "emoji": strength_emoji(pct)
            })

        except Exception:
            continue

    if not movers:
        send_telegram_message(
            f"ℹ️ *US {state} Movers*\n\n"
            f"No stocks moving more than ±{threshold}% with volume yet."
        )
        return

    df = pd.DataFrame(movers)
    gainers = df.sort_values("pct", ascending=False).head(6)
    losers = df.sort_values("pct").head(6)

    message = f"📊 *US {state} Movers*\n"
    message += "_Yahoo Finance · FREE_\n\n"

    message += "*🚀 Top Gainers*\n"
    for _, r in gainers.iterrows():
        message += f"{r.emoji} `{r.ticker}` {r.pct}% (${r.price})\n"
        alerted.add(r.ticker)

    message += "\n*🔻 Top Losers*\n"
    for _, r in losers.iterrows():
        message += f"{r.emoji} `{r.ticker}` {r.pct}% (${r.price})\n"
        alerted.add(r.ticker)

    send_telegram_message(message)
    save_alerted(alerted)

if __name__ == "__main__":
    main()
