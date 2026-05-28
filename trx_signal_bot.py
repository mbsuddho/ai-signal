import time
import requests
import ccxt
import pandas as pd
from flask import Flask
import threading

# --- 1. TELEGRAM CONFIGURATION ---
TELEGRAM_BOT_TOKEN = "8943651714:AAHOlFMDZODtTjcW-4fws7vu5_Sm_YHIea0"  # Keep your real token here
TELEGRAM_CHAT_ID = "@suddhosignal"      # Keep your real chat ID here

# --- 2. MULTI-COIN SETUP ---
WATCH_SYMBOLS = ['TRX/USDT', 'DOGE/USDT', 'XRP/USDT', 'ADA/USDT']
TIMEFRAME = '15m'  # 15-minute candles offer stable indicators

# --- 3. INDICATOR MATH FUNCTIONS ---
def calculate_indicators(candles):
    """Converts raw candle data into a dataframe with 200 EMA and RSI."""
    df = pd.DataFrame(candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['close'] = df['close'].astype(float)
    
    # Calculate 200 EMA
    df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()
    
    # Calculate 14-period RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-10)  # Avoid division by zero
    df['rsi'] = 100 - (100 / (1 + rs))
    
    return df

def send_telegram_signal(symbol, side, entry, tp, sl, rsi, ema):
    """Sends a formatted indicator confirmation card to Telegram."""
    emoji = "🟢 LONG" if side == "LONG" else "🔴 SHORT"
    rocket = "🚀" if side == "LONG" else "💥"
    
    message = (
        f"{rocket} **AI AGENT: {symbol} {emoji} SIGNAL** {rocket}\n\n"
        f"📊 **Trend Filter:** Price {'Above' if entry > ema else 'Below'} 200 EMA\n"
        f"⏱️ **RSI Level:** {round(rsi, 2)}\n"
        f"----------------------------------------\n"
        f"💸 **Entry Price:** ${entry}\n"
        f"🎯 **Take Profit Target (1.0%):** ${round(tp, 5)}\n"
        f"🛡️ **Stop Loss Safety (0.5%):** ${round(sl, 5)}\n"
    )
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"})
    except Exception as e:
        print(f"Telegram network glitch: {e}")

# --- 4. THE LIVE CORE ENGINE ---
def run_signal_engine():
    print("Initializing Binance Futures Connection...")
    exchange = ccxt.binance({
        'options': {'defaultType': 'future'},
        'enableRateLimit': True
    })
    
    # Track states to avoid spamming multiple signals on the exact same candle
    last_signal_time = {symbol: 0 for symbol in WATCH_SYMBOLS}
    
    print("Multi-Coin Indicator Engine is active and scanning...")
    while True:
        for symbol in WATCH_SYMBOLS:
            try:
                # Fetch recent historical charts
                candles = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=250)
                if len(candles) < 200:
                    continue
                    
                df = calculate_indicators(candles)
                
                # Get the latest completed data state
                latest_row = df.iloc[-2]
                current_price = latest_row['close']
                current_rsi = latest_row['rsi']
                current_ema = latest_row['ema200']
                timestamp = latest_row['timestamp']
                
                # Check if we already handled this specific candle
                if timestamp == last_signal_time[symbol]:
                    continue
                
                # 🛑 STRATEGY RULES:
                # 1. LONG Rule: Price must be in macro uptrend (Price > EMA) and micro oversold (RSI < 35)
                if current_price > current_ema and current_rsi < 35:
                    tp = current_price * 1.01
                    sl = current_price * 0.995
                    send_telegram_signal(symbol, "LONG", current_price, tp, sl, current_rsi, current_ema)
                    last_signal_time[symbol] = timestamp
                    
                # 2. SHORT Rule: Price must be in macro downtrend (Price < EMA) and micro overbought (RSI > 65)
                elif current_price < current_ema and current_rsi > 65:
                    tp = current_price * 0.99
                    sl = current_price * 1.005
                    send_telegram_signal(symbol, "SHORT", current_price, tp, sl, current_rsi, current_ema)
                    last_signal_time[symbol] = timestamp
                    
            except Exception as e:
                print(f"Error checking {symbol}: {e}")
                
        time.sleep(15)  # Check the group of tickers every 15 seconds safely

# --- 5. RENDER WEB SERVER HOOK ---
app = Flask('')

@app.route('/')
def home():
    return "Multi-Coin RSI/EMA Intelligence Core is Alive!"

def run_web_server():
    app.run(host='0.0.0.0', port=10000)

if __name__ == "__main__":
    # Fire up the background scanner thread
    t = threading.Thread(target=run_signal_engine)
    t.daemon = True
    t.start()
    
    # Fire up the main web server thread for Render/Cron-job
    run_web_server()
    
