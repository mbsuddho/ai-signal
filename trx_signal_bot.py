import time
import requests
import ccxt
import pandas as pd
from flask import Flask
import threading

# --- 1. TELEGRAM CONFIGURATION ---
TELEGRAM_BOT_TOKEN = "8943651714:AAHOlFMDZODtTjcW-4fws7vu5_Sm_YHIea0"
TELEGRAM_CHAT_ID = "@suddhosignal"

# --- 2. MULTI-COIN CONFIGURATION ---
WATCH_SYMBOLS = ['TRX/USDT', 'DOGE/USDT', 'XRP/USDT', 'ADA/USDT']
TIMEFRAME = '15m'

# Track active live trades to monitor TP/SL and prevent double trades
active_trades = {symbol: None for symbol in WATCH_SYMBOLS} 

# --- 3. INDICATOR MATH ---
def calculate_indicators(candles):
    df = pd.DataFrame(candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['close'] = df['close'].astype(float)
    
    # 200 EMA
    df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()
    
    # 14 RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-10)
    df['rsi'] = 100 - (100 / (1 + rs))
    
    return df

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"})
    except Exception as e:
        print(f"Telegram error: {e}")

# --- 4. THE LIVE CORE ENGINE ---
def run_signal_engine():
    print("Connecting to Binance Futures...")
    exchange = ccxt.binance({
        'options': {'defaultType': 'future'},
        'enableRateLimit': True
    })
    
    print("Market-Ready Engine is active and scanning...")
    while True:
        for symbol in WATCH_SYMBOLS:
            try:
                # --- SUB-ENGINE 1: LIVE POSITION TRACKER ---
                if active_trades[symbol] is not None:
                    trade = active_trades[symbol]
                    ticker = exchange.fetch_ticker(symbol)
                    live_price = float(ticker['last'])
                    
                    if trade['side'] == 'LONG':
                        if live_price >= trade['tp']:
                            send_telegram_message(f"✅ **{symbol} TAKE PROFIT HIT!** 💰\nTarget ${trade['tp']} reached from entry ${trade['entry']}.")
                            active_trades[symbol] = None  # Trade over, unlock scanner
                        elif live_price <= trade['sl']:
                            send_telegram_message(f"❌ **{symbol} STOP LOSS HIT.** 🛡️\nSafety level ${trade['sl']} touched.")
                            active_trades[symbol] = None  # Trade over, unlock scanner
                            
                    elif trade['side'] == 'SHORT':
                        if live_price <= trade['tp']:
                            send_telegram_message(f"✅ **{symbol} SHORT TAKE PROFIT HIT!** 💰\nTarget ${trade['tp']} reached from entry ${trade['entry']}.")
                            active_trades[symbol] = None
                        elif live_price >= trade['sl']:
                            send_telegram_message(f"❌ **{symbol} SHORT STOP LOSS HIT.** 🛡️\nSafety level ${trade['sl']} touched.")
                            active_trades[symbol] = None
                    
                    continue  # Freeze scanner for this coin while a trade is running
                
                # --- SUB-ENGINE 2: MARKET-READY SCANNER ---
                candles = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=250)
                if len(candles) < 200:
                    continue
                    
                df = calculate_indicators(candles)
                
                # Get the last two completed candles to check for a crossover hook
                previous_row = df.iloc[-3]  # The candle before last
                latest_closed_row = df.iloc[-2]  # The most recently finished candle
                
                current_price = float(latest_closed_row['close'])
                current_ema = latest_closed_row['ema200']
                
                rsi_prev = previous_row['rsi']
                rsi_now = latest_closed_row['rsi']
                
                # 🛑 STRATEGY CROSSOVER RULES:
                
                # Rule 1: LONG (Price is above 200 EMA, RSI was oversold but has now hooked back up above 35)
                if current_price > current_ema and rsi_prev < 35 and rsi_now >= 35:
                    tp_target = current_price * 1.01
                    sl_target = current_price * 0.995
                    
                    msg = (
                        f"🟢 **AI AGENT: {symbol} MARKET READY (LONG)** 🚀\n\n"
                        f"📊 **Trend Filter:** Safely Above 200 EMA\n"
                        f"🔄 **Momentum Hook:** RSI crossed back UP from {round(rsi_prev,1)} to {round(rsi_now,1)}\n"
                        f"----------------------------------------\n"
                        f"📥 **Entry Price:** ${current_price}\n"
                        f"🎯 **Take Profit (1.0%):** ${round(tp_target, 5)}\n"
                        f"🛡️ **Stop Loss (-0.5%):** ${round(sl_target, 5)}"
                    )
                    send_telegram_message(msg)
                    active_trades[symbol] = {'side': 'LONG', 'entry': current_price, 'tp': tp_target, 'sl': sl_target}
                    
                # Rule 2: SHORT (Price is below 200 EMA, RSI was overbought but has now hooked back down below 65)
                elif current_price < current_ema and rsi_prev > 65 and rsi_now <= 65:
                    tp_target = current_price * 0.99
                    sl_target = current_price * 1.005
                    
                    msg = (
                        f"🔴 **AI AGENT: {symbol} MARKET READY (SHORT)** 💥\n\n"
                        f"📊 **Trend Filter:** Safely Below 200 EMA\n"
                        f"🔄 **Momentum Hook:** RSI crossed back DOWN from {round(rsi_prev,1)} to {round(rsi_now,1)}\n"
                        f"----------------------------------------\n"
                        f"📥 **Entry Price:** ${current_price}\n"
                        f"🎯 **Take Profit (1.0%):** ${round(tp_target, 5)}\n"
                        f"🛡️ **Stop Loss (-0.5%):** ${round(sl_target, 5)}"
                    )
                    send_telegram_message(msg)
                    active_trades[symbol] = {'side': 'SHORT', 'entry': current_price, 'tp': tp_target, 'sl': sl_target}
                    
            except Exception as e:
                print(f"Error looping {symbol}: {e}")
                
        time.sleep(5)  # Constantly check prices every 5 seconds

# --- 5. RENDER SYSTEM PORT HOOK ---
app = Flask('')

@app.route('/')
def home():
    return "Multi-Coin Reversal Core is Online!"

def run_web_server():
    app.run(host='0.0.0.0', port=10000)

if __name__ == "__main__":
    t = threading.Thread(target=run_signal_engine)
    t.daemon = True
    t.start()
    
    run_web_server()
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
    
