"""
Technical indicators - thin wrapper around `ta` library.
All functions take a DataFrame with columns: Open, High, Low, Close, Volume.
"""
import pandas as pd
import numpy as np
from ta.trend import EMAIndicator, MACD, ADXIndicator
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands, AverageTrueRange


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add all swing-trading indicators to a price dataframe.

    Returns the same df with new columns added. Safely handles
    short dataframes (< 50 bars) by returning as-is.
    """
    if df is None or len(df) < 50:
        return df

    df = df.copy()

    # Moving Averages (EMA preferred over SMA for swing trading)
    df['EMA_20'] = EMAIndicator(close=df['Close'], window=20).ema_indicator()
    df['EMA_50'] = EMAIndicator(close=df['Close'], window=50).ema_indicator()
    if len(df) >= 200:
        df['EMA_200'] = EMAIndicator(close=df['Close'], window=200).ema_indicator()
    else:
        df['EMA_200'] = np.nan

    # RSI - momentum
    df['RSI'] = RSIIndicator(close=df['Close'], window=14).rsi()

    # MACD - trend & momentum
    macd = MACD(close=df['Close'])
    df['MACD'] = macd.macd()
    df['MACD_Signal'] = macd.macd_signal()
    df['MACD_Hist'] = macd.macd_diff()

    # ADX - trend strength (crucial for distinguishing trending vs ranging)
    adx_ind = ADXIndicator(high=df['High'], low=df['Low'], close=df['Close'], window=14)
    df['ADX'] = adx_ind.adx()
    df['DI_pos'] = adx_ind.adx_pos()
    df['DI_neg'] = adx_ind.adx_neg()

    # Bollinger Bands - volatility & mean reversion
    bb = BollingerBands(close=df['Close'], window=20, window_dev=2)
    df['BB_upper'] = bb.bollinger_hband()
    df['BB_lower'] = bb.bollinger_lband()
    df['BB_mid'] = bb.bollinger_mavg()
    df['BB_width'] = (df['BB_upper'] - df['BB_lower']) / df['BB_mid']

    # ATR - position sizing & stop-loss distance
    atr = AverageTrueRange(high=df['High'], low=df['Low'], close=df['Close'], window=14)
    df['ATR'] = atr.average_true_range()

    # Volume analysis
    df['Vol_avg_20'] = df['Volume'].rolling(20).mean()
    df['Vol_ratio'] = df['Volume'] / df['Vol_avg_20']

    # Range tracking
    df['High_20'] = df['High'].rolling(20).max()
    df['Low_20'] = df['Low'].rolling(20).min()
    df['High_50'] = df['High'].rolling(50).max()
    df['Low_50'] = df['Low'].rolling(50).min()

    # Returns for divergence detection
    df['Return_5'] = df['Close'].pct_change(5)

    return df


def find_support_resistance(df: pd.DataFrame, lookback: int = 60, n_levels: int = 3) -> dict:
    """Identify key support and resistance levels using swing highs/lows.

    Returns dict with 'support' and 'resistance' lists (most recent first).
    """
    if df is None or len(df) < lookback:
        return {'support': [], 'resistance': []}

    recent = df.tail(lookback)
    cmp = recent['Close'].iloc[-1]

    # Swing pivots: local maxima/minima over 5-bar window
    highs = []
    lows = []
    window = 5
    for i in range(window, len(recent) - window):
        bar_high = recent['High'].iloc[i]
        bar_low = recent['Low'].iloc[i]
        if bar_high == recent['High'].iloc[i - window:i + window + 1].max():
            highs.append(bar_high)
        if bar_low == recent['Low'].iloc[i - window:i + window + 1].min():
            lows.append(bar_low)

    # Resistance = swing highs above CMP, Support = swing lows below CMP
    resistance = sorted([h for h in highs if h > cmp])[:n_levels]
    support = sorted([l for l in lows if l < cmp], reverse=True)[:n_levels]

    return {
        'support': [round(s, 2) for s in support],
        'resistance': [round(r, 2) for r in resistance],
    }
