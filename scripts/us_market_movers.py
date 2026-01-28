import os
import yfinance as yf
import pandas as pd
import requests
import pytz
from datetime import datetime

# Load secrets from GitHub Actions
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    raise RuntimeError("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID")

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    requests.post(url, json=payload, timeout=10)

def is_us_market_open_or_premarket():
    us_tz = pytz.timezone("US/Eastern")
    now = datetime.now(us_tz)

    pre_market_open = now.replace(hour=4, minute=0, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)

    return pre_market_open <= now <= market_close

def main():
    if not is_us_market_open_or_premarket():
        send_telegram_message("⏳ US market is currently closed.")
        return

    # Pull S&P 500 components
    tickers = yf.Tickers("^GSPC").symbols[:200]  # limit to reduce rate limits
    movers = []

    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            info = stock.fast_info

            prev_close = info.get("previous_close")
            last_price = info.get("last_price")

            if prev_close and last_price:
                pct_change = ((last_price - prev_close) / prev_close) * 100
                movers.append({
                    "ticker": ticker,
                    "price": round(last_price, 2),
                    "pct_change": round(pct_change, 2)
                })
        except Exception:
            continue

    df = pd.DataFrame(movers)

    if df.empty:
        send_telegram_message("⚠️ No market data available.")
        return

    top_gainers = df.sort_values("pct_change", ascending=False).head(6)
    top_losers = df.sort_values("pct_change").head(6)

    message = "📊 *CT US Market Movers (Pre-Market / Open)*\n\n"

    message += "*🚀 Top Gainers*\n"
    for _, r in top_gainers.iterrows():
        message += f"`{r.ticker}`  {r.pct_change}% (${r.price})\n"

    message += "\n*🔻 Top Losers*\n"
    for _, r in top_losers.iterrows():
        message += f"`{r.ticker}`  {r.pct_change}% (${r.price})\n"

    send_telegram_message(message)

if __name__ == "__main__":
    main()
