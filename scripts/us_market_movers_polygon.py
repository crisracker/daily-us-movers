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
def is_us_market_open_or_premarket():
    us_tz = pytz.timezone("US/Eastern")
    now = datetime.now(us_tz)

    pre_market_open = now.replace(hour=4, minute=0, second=0, microsecond=0)
    market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)

    return pre_market_open <= now < market_open

# =========================
# Main logic
# =========================
def main():
    if not is_us_market_open_or_premarket():
        send_telegram_message("⏳ US pre-market is not open.")
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

    gainers_list = gainers_resp.get("tickers", [])
    losers_list = losers_resp.get("tickers", [])

    # =========================
    # Handle empty pre-market (NORMAL on free tier)
    # =========================
    if not gainers_list and not losers_list:
        send_telegram_message(
            "ℹ️ *US Pre-Market Movers*\n"
            "_Polygon.io · 🆓 FREE tier · ~15 min delayed_\n\n"
            "Pre-market is open, but no significant movers yet.\n"
            "This is normal before ~08:00 ET."
        )
        return

    # =========================
    # Build Telegram message
    # =========================
    message = "📊 *US Pre-Market Movers*\n"
    message += "_Polygon.io · 🆓 FREE tier · ~15 min delayed_\n\n"

    message += "*🚀 Top Gainers*\n"
    for t in gainers_list[:6]:
        symbol = t.get("ticker", "N/A")
        pct = round(t.get("todaysChangePerc", 0), 2)
        price = round(t.get("lastTrade", {}).get("p", 0), 2)
        message += f"`{symbol}`  {pct}% (${price})\n"

    message += "\n*🔻 Top Losers*\n"
    for t in losers_list[:6]:
        symbol = t.get("ticker", "N/A")
        pct = round(t.get("todaysChangePerc", 0), 2)
        price = round(t.get("lastTrade", {}).get("p", 0), 2)
        message += f"`{symbol}`  {pct}% (${price})\n"

    send_telegram_message(message)

# =========================
# Entry point
# =========================
if __name__ == "__main__":
    main()
