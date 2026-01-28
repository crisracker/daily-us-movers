import os
import yfinance as yf
import pandas as pd
import requests
import pytz
from datetime import datetime

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
# Market session check
# =========================
def is_us_premarket():
    us_tz = pytz.timezone("US/Eastern")
    now = datetime.now(us_tz)

    pre_market_open = now.replace(hour=4, minute=0, second=0, microsecond=0)
    market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)

    return pre_market_open <= now < market_open

# =========================
# Ticker groups
# =========================

# Watching stocks
WATCHLIST = ["MA", "V", "WM", "PL", "UNG"]

# Crypto-related stocks
CRYPTO_STOCKS = ["BMNR", "NU", "SUIG", "RIOT"]

# Broad liquid universe (REPLACED AS REQUESTED)
BASE_TICKERS = [
    # Mega-cap tech
    "AAPL","MSFT","NVDA","AMZN","META","GOOGL","GOOG","TSLA",
    "AMD","NFLX","AVGO","INTC","QCOM","MU","TXN","AMAT","LRCX","KLAC",

    # Financials
    "JPM","BAC","WFC","GS","MS","C","SCHW","BLK","AXP","USB","PNC",

    # Energy
    "XOM","CVX","COP","SLB","OXY","MPC","VLO","PSX",

    # Healthcare
    "JNJ","PFE","MRK","LLY","UNH","ABBV","TMO","ABT","DHR","MDT",

    # Consumer discretionary
    "AMZN","TSLA","HD","LOW","NKE","MCD","SBUX","BKNG","TJX",

    # Consumer staples
    "WMT","COST","PG","KO","PEP","PM","MO","CL",

    # Industrials
    "BA","CAT","GE","RTX","DE","UPS","FDX","MMM","HON","ETN",

    # Communication
    "META","NFLX","DIS","CMCSA","VZ","T","TMUS",

    # Materials
    "LIN","APD","ECL","SHW","FCX","NEM"
]

# Merge & deduplicate all tickers
ALL_TICKERS = sorted(set(BASE_TICKERS + WATCHLIST + CRYPTO_STOCKS))

# =========================
# Main logic
# =========================
def main():
    if not is_us_premarket():
        send_telegram_message("⏳ US pre-market is not open.")
        return

    movers = []

    for ticker in ALL_TICKERS:
        try:
            stock = yf.Ticker(ticker)
            info = stock.fast_info

            prev_close = info.get("previous_close")
            last_price = info.get("last_price")

            if prev_close is None or last_price is None:
                continue

            pct_change = ((last_price - prev_close) / prev_close) * 100

            movers.append({
                "ticker": ticker,
                "price": round(last_price, 2),
                "pct_change": round(pct_change, 2)
            })

        except Exception:
            continue

    if not movers:
        send_telegram_message(
            "ℹ️ *US Pre-Market Movers (Yahoo)*\n\n"
            "Pre-market is open, but no significant movement yet."
        )
        return

    df = pd.DataFrame(movers)

    # =========================
    # Top movers
    # =========================
    top_gainers = df.sort_values("pct_change", ascending=False).head(6)
    top_losers = df.sort_values("pct_change").head(6)

    # =========================
    # Watchlist & crypto views
    # =========================
    watch_df = df[df["ticker"].isin(WATCHLIST)]
    crypto_df = df[df["ticker"].isin(CRYPTO_STOCKS)]

    # =========================
    # Build Telegram message
    # =========================
    message = "📊 *US Pre-Market Movers*\n"
    message += "_Yahoo Finance · FREE_\n\n"

    message += "*🚀 Top Gainers*\n"
    for _, r in top_gainers.iterrows():
        message += f"`{r.ticker}`  {r.pct_change}% (${r.price})\n"

    message += "\n*🔻 Top Losers*\n"
    for _, r in top_losers.iterrows():
        message += f"`{r.ticker}`  {r.pct_change}% (${r.price})\n"

    if not watch_df.empty:
        message += "\n*👀 Watching Stocks*\n"
        for _, r in watch_df.iterrows():
            message += f"`{r.ticker}`  {r.pct_change}% (${r.price})\n"

    if not crypto_df.empty:
        message += "\n*₿ Crypto-Related Stocks*\n"
        for _, r in crypto_df.iterrows():
            message += f"`{r.ticker}`  {r.pct_change}% (${r.price})\n"

    send_telegram_message(message)

# =========================
# Entry point
# =========================
if __name__ == "__main__":
    main()
