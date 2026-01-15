import pandas as pd
import numpy as np

def calculate_rsi(data, window=14):
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_macd(data, short=12, long=26, signal=9):
    short_ema = data.ewm(span=short, adjust=False).mean()
    long_ema = data.ewm(span=long, adjust=False).mean()
    macd = short_ema - long_ema
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    return macd, signal_line

def calculate_atr(data, window=14):
    high, low, close = data['High'], data['Low'], data['Close']
    tr = pd.concat([high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()], axis=1).max(axis=1)
    return tr.rolling(window=window).mean()

def calculate_stochastic(data, n=14, m=3, t=3):
    low_min = data['Low'].rolling(n).min()
    high_max = data['High'].rolling(n).max()
    fast_k = ((data['Close'] - low_min) / (high_max - low_min)) * 100
    slow_k = fast_k.rolling(m).mean()
    return slow_k, slow_k.rolling(t).mean()

def round_to_tick(price):
    if price < 2000: return int(round(price, -1))
    elif price < 20000: return int(round(price, -1))
    elif price < 200000: return int(round(price, -2))
    else: return int(round(price, -3))
