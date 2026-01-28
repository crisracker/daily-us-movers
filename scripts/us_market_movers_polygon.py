import os
import requests
import pytz
from datetime import datetime

# =========================
# Load secrets
# =========================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")

if not all([TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, POLYGON_API_KEY]):
    raise RuntimeError("Missing required environment variables")

# =========================
# Telegram
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
def is_us_market_open_or_premarket():
    us_tz = pytz.timezone("US/Eastern")
    now = datetime.now(us_tz)

    pre_market_open = now.replace(hour=4, minute=0, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)

    return pre_market_open <= now <= market_close

# =========================
# Main logic
# =========================
def main():
    if not is_us_market_open_or_premarket():
        send_telegram_message("⏳ US market is currently closed.")
        return

    gainers_url = (
        "https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/gainers"
        f"?apiKey={POLYGON_API_KEY}"
    )
    losers_url = (
        "https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/losers"
        f"?apiKey={POLYGON_API_KEY}"
    )

    gainers_resp = requests.get(gainers_url, timeout=15).json()
    losers_resp = requests.get(losers_url, timeout=15).json()

    if "tickers" not in gainers_resp or "tickers" not in losers_resp:
        send_telegram_message("⚠️ Polygon API returned no data (free-tier delay or limit).")
        return

    message = "📊 *US Market Top Movers (Pre-Market / Open)*\n"
    message += "_Polygon.io · ~15 min delayed_\n\n"

    message += "*🚀 Top Gainers*\n"
    for t in gainers_resp["tickers"][:6]:
        symbol = t["ticker"]
        pct = round(t.get("todaysChangePerc", 0), 2)
        price = round(t.get("lastTrade", {}).get("p", 0), 2)
        message += f"`{symbol}`  {pct}% (${price})\n"

    message += "\n*🔻 Top Losers*\n"
    for t in losers_resp["tickers"][:6]:
        symbol = t["ticker"]
        pct = round(t.get("todaysChangePerc", 0), 2)
        price = round(t.get("lastTrade", {}).get("p", 0), 2)
        message += f"`{symbol}`  {pct}% (${price})\n"

    send_telegram_message(message)

# =========================
# Entry point
# =========================
if __name__ == "__main__":
    main()
