import time
import requests
import ccxt
import pandas as pd
from flask import Flask
import threading

# --- 1. TELEGRAM CONFIGURATION ---
TELEGRAM_BOT_TOKEN = "8943651714:AAHOlFMDZODtTjcW-4fws7vu5_Sm_YHIea0"
TELEGRAM_CHAT_ID = "@suddhosignal"

# --- 2. EXPANDED HIGH-VOLUME COIN CONFIGURATION ---
WATCH_SYMBOLS = [
    'TRX/USDT', 'DOGE/USDT', 'XRP/USDT', 'ADA/USDT',
    'SOL/USDT', 'MATIC/USDT', 'LINK/USDT', 'OP/USDT', 
    'NEAR/USDT', 'AVAX/USDT', 'APT/USDT', 'SUI/USDT'
]
TIMEFRAME = '15m'  # Dropped to 5 minutes for faster indicators and quicker entries

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
    
    print("High-Frequency Reversal Engine is active and scanning...")
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
                previous_row = df.iloc[-3]  
                latest_closed_row = df.iloc[-2]  
                
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
                        f"🔄 **Momentum Hook:** 5m RSI crossed UP from {round(rsi_prev,1)} to {round(rsi_now,1)}\n"
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
                        f"🔄 **Momentum Hook:** 5m RSI crossed back DOWN from {round(rsi_prev,1)} to {round(rsi_now,1)}\n"
                        f"----------------------------------------\n"
                        f"📥 **Entry Price:** ${current_price}\n"
                        f"🎯 **Take Profit (1.0%):** ${round(tp_target, 5)}\n"
                        f"🛡️ **Stop Loss (-0.5%):** ${round(sl_target, 5)}"
                    )
                    send_telegram_message(msg)
                    active_trades[symbol] = {'side': 'SHORT', 'entry': current_price, 'tp': tp_target, 'sl': sl_target}
                    
            except Exception as e:
                print(f"Error looping {symbol}: {e}")
                
        time.sleep(3)  # Loop faster (every 3 seconds) since we have more coins to cover

# --- 5. RENDER SYSTEM PORT HOOK ---
app = Flask('')

@app.route('/')
def home():
    return "Multi-Coin High-Frequency Core is Online!"

def run_web_server():
    app.run(host='0.0.0.0', port=10000)

if __name__ == "__main__":
    t = threading.Thread(target=run_signal_engine)
    t.daemon = True
    t.start()
    
    run_web_server()
