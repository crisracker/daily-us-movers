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
PREMARKET_THRESHOLD = 1.0
MARKET_THRESHOLD = 2.0
VOLUME_MULTIPLIER = 1.5
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
# Market state
# =========================
def market_state():
    us_tz = pytz.timezone("US/Eastern")
    now = datetime.now(us_tz)

    pre = now.replace(hour=4, minute=0, second=0, microsecond=0)
    open_ = now.replace(hour=9, minute=30, second=0, microsecond=0)
    close = now.replace(hour=16, minute=0, second=0, microsecond=0)

    if pre <= now < open_:
        return "PRE-MARKET"
    if open_ <= now <= close:
        return "MARKET"
    return "CLOSED"

# =========================
# Alert state persistence
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
# Direction icon (🟢 🔴 ⚪)
# =========================
def direction_icon(pct):
    if pct > 0:
        return "🟢"
    if pct < 0:
        return "🔴"
    return "⚪"

# =========================
# MARKET SECTORS (ALWAYS SHOWN)
# =========================
SECTOR_TICKERS = [
    "CQQQ","VWRA","SPY","CSPX","XLB","XLC","XLE","XLF","XLG","XLI",
    "XLK","XLP","XLU","XLV","XLY"
]

def get_sector_snapshot():
    rows = []
    for ticker in SECTOR_TICKERS:
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="2d")
            name = t.info.get("shortName", ticker)

            if len(hist) >= 2:
                prev = hist["Close"].iloc[-2]
                last = hist["Close"].iloc[-1]
                pct = ((last - prev) / prev) * 100
            elif len(hist) == 1:
                last = hist["Close"].iloc[-1]
                pct = 0.0
            else:
                last = None
                pct = 0.0

            rows.append({
                "ticker": ticker,
                "name": name,
                "price": f"{last:.2f}" if isinstance(last, float) else "N/A",
                "pct": f"{pct:.2f}%",
                "icon": direction_icon(pct)
            })

        except Exception:
            rows.append({
                "ticker": ticker,
                "name": ticker,
                "price": "N/A",
                "pct": "N/A",
                "icon": "⚪"
            })

    return rows

# =========================
# Emoji strength for movers
# =========================
def strength_emoji(pct):
    pct = abs(pct)
    if pct >= 5:
        return "🚨"
    if pct >= 3:
        return "🔥"
    return ""

# =========================
# Stock universe
# =========================
WATCHLIST = ["MA", "V", "WM", "PL", "UNG", "CHA", "FTNT", "UNH"]
CRYPTO_STOCKS = ["IBIT", "BMNR", "NU", "SUIG", "RIOT"]

BASE_TICKERS = [
    "AAPL","MSFT","NVDA","AMZN","META","GOOGL","TSLA", "PLTR",
    "AMD","NFLX","AVGO","INTC","QCOM","MU","TXN","AMAT","LRCX","KLAC",
    "JPM","BAC","WFC","GS","MS","C","SCHW","BLK","AXP","USB","PNC",
    "XOM","CVX","COP","SLB","OXY","MPC","VLO","PSX",
    "JNJ","PFE","MRK","LLY","UNH","ABBV","TMO","ABT","DHR","MDT",
    "HD","LOW","NKE","MCD","SBUX","BKNG","TJX",
    "WMT","COST","PG","KO","PEP","PM","MO","CL",
    "BA","CAT","GE","RTX","DE","UPS","FDX","MMM","HON","ETN",
    "DIS","CMCSA","VZ","T","TMUS", "SOFI",
    "LIN","APD","ECL","SHW","FCX","NEM",
    "BXSL", "PBDC"
]

ALL_TICKERS = sorted(set(BASE_TICKERS + WATCHLIST + CRYPTO_STOCKS))

# =========================
# Main
# =========================
def main():
    state = market_state()
    threshold = PREMARKET_THRESHOLD if state == "PRE-MARKET" else MARKET_THRESHOLD
    alerted = load_alerted()

    # -------------------------
    # Market Sectors (ALWAYS)
    # -------------------------
    sectors = get_sector_snapshot()

    message = f"📊 *US Market Snapshot* ({state})\n"
    message += "_Market Sectors_\n\n"

    message += "*📈 Market Sectors*\n"
    for s in sectors:
        message += f"`{s['ticker']}` {s['name']} — ${s['price']} ({s['pct']}) {s['icon']}\n"

    if state == "CLOSED":
        send_telegram_message(message)
        return

    movers = []

    for ticker in ALL_TICKERS:
        try:
            t = yf.Ticker(ticker)
            info = t.fast_info

            prev = info.get("previous_close")
            price = info.get("last_price")
            vol = info.get("last_volume")
            avg_vol = info.get("ten_day_average_volume")

            if not all([prev, price, vol, avg_vol]):
                continue

            pct = ((price - prev) / prev) * 100

            if abs(pct) < threshold:
                continue
            if vol < avg_vol * VOLUME_MULTIPLIER:
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

    if movers:
        df = pd.DataFrame(movers)
        gainers = df.sort_values("pct", ascending=False).head(6)
        losers = df.sort_values("pct").head(6)

        message += "\n*🚀 Top Gainers*\n"
        for _, r in gainers.iterrows():
            message += f"{r.emoji} `{r.ticker}` {r.pct}% (${r.price})\n"
            alerted.add(r.ticker)

        message += "\n*🔻 Top Losers*\n"
        for _, r in losers.iterrows():
            message += f"{r.emoji} `{r.ticker}` {r.pct}% (${r.price})\n"
            alerted.add(r.ticker)
    else:
        message += f"\nℹ️ No stocks moving more than ±{threshold}% with volume yet."

    send_telegram_message(message)
    save_alerted(alerted)

if __name__ == "__main__":
    main()
