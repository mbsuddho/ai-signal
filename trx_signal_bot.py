import ccxt
import requests
import time
from datetime import datetime
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- 1. LIVE WEB SERVER TRICK FOR RENDER ---
class SimpleWebServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"Bot is alive and scanning TRX/USDT!")

def run_web_server():
    # Render automatically looks for port 10000 on web services
    server = HTTPServer(('0.0.0.0', 10000), SimpleWebServer)
    print("🌍 Web Server running on port 10000 (Keeping Render Awake)")
    server.serve_forever()

# --- 2. CONFIGURATION ---
exchange = ccxt.binance({'enableRateLimit': True})
TELEGRAM_BOT_TOKEN = '8943651714:AAHOlFMDZODtTjcW-4fws7vu5_Sm_YHIea0'
TELEGRAM_CHAT_ID = '@suddhosignal'
SYMBOL = 'TRX/USDT'
SIGNAL_THRESHOLD_PERCENT = 0.5
TAKE_PROFIT_PERCENT = 1.0       
STOP_LOSS_PERCENT = 0.5         
CHECK_INTERVAL_SECONDS = 5      

# --- 3. TELEGRAM SIGNAL CARDS ---
def send_telegram_signal(symbol, entry_price, direction):
    time_str = datetime.utcnow().strftime('%H:%M (UTC)')
    if direction == "LONG":
        action_title = "🚀 AI AGENT: TRX/USDT LONG SIGNAL 🚀"
        tp_price = entry_price * (1 + (TAKE_PROFIT_PERCENT / 100))
        sl_price = entry_price * (1 - (STOP_LOSS_PERCENT / 100))
    else:
        action_title = "💥 AI AGENT: TRX/USDT SHORT SIGNAL 💥"
        tp_price = entry_price * (1 - (TAKE_PROFIT_PERCENT / 100))
        sl_price = entry_price * (1 + (STOP_LOSS_PERCENT / 100))

    message = (
        f"{action_title}\n\n"
        f"💱 **Trading Pair:** {symbol}\n"
        f"📥 **Entry Price:** ${entry_price:.5f}\n"
        f"🎯 **Take Profit Target:** ${tp_price:.5f} (+1.0%)\n"
        f"🛡️ **Stop Loss Safety:** ${sl_price:.5f} (-0.5%)\n"
    )
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"})
        return tp_price, sl_price
    except Exception as e:
        print(f"⚠️ Telegram error: {e}")
        return None, None

# --- 4. ENGINE CORE ---
def run_signal_engine():
    print(f"📡 Scanning {SYMBOL} order books...")
    ticker = exchange.fetch_ticker(SYMBOL)
    last_anchor_price = ticker['last']
    active_tp, active_sl, active_direction = None, None, None

    while True:
        try:
            ticker = exchange.fetch_ticker(SYMBOL)
            current_price = ticker['last']
            
            if active_tp is not None:
                if active_direction == "LONG":
                    if current_price >= active_tp:
                        requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", json={"chat_id": TELEGRAM_CHAT_ID, "text": "✅ **TRX/USDT TAKE PROFIT HIT!** 💰"})
                        active_tp, active_sl, active_direction = None, None, None
                    elif current_price <= active_sl:
                        requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", json={"chat_id": TELEGRAM_CHAT_ID, "text": "❌ **TRX/USDT STOP LOSS HIT.** 🛡️"})
                        active_tp, active_sl, active_direction = None, None, None
            else:
                price_change = ((current_price - last_anchor_price) / last_anchor_price) * 100
                if price_change <= -SIGNAL_THRESHOLD_PERCENT:
                    active_tp, active_sl = send_telegram_signal(SYMBOL, current_price, "LONG")
                    active_direction = "LONG"
                    last_anchor_price = current_price
                elif price_change >= SIGNAL_THRESHOLD_PERCENT:
                    active_tp, active_sl = send_telegram_signal(SYMBOL, current_price, "SHORT")
                    active_direction = "SHORT"
                    last_anchor_price = current_price

            time.sleep(CHECK_INTERVAL_SECONDS)
        except Exception as e:
            time.sleep(10)

if __name__ == "__main__":
    # Start the web server thread so Render stays happy
    threading.Thread(target=run_web_server, daemon=True).start()
    # Start the crypto scanning engine
    run_signal_engine()
