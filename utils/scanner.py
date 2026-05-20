"""
Stock swing scanner. Evaluates each stock against a set of swing-trading
setups and returns scored signals.

Setups detected:
  Long:
    - Bullish Pullback to EMA20 (in uptrend)
    - Bullish Breakout (20-day high + volume)
    - EMA 20/50 Bullish Cross
    - RSI Bullish Reversal from oversold
  Short:
    - Bearish Pullback to EMA20 (in downtrend)
    - Bearish Breakdown (20-day low + volume)
    - EMA 20/50 Bearish Cross

Strength score (0-100) combines trend strength, momentum, volume, MA alignment,
and risk/reward potential.
"""
import pandas as pd
import numpy as np


def evaluate_setup(df: pd.DataFrame) -> dict:
    """Evaluate the latest bar for a swing setup.

    Returns dict with setup info, or None if no qualifying setup.
    Expects df to already have indicators added (use indicators.add_indicators).
    """
    if df is None or len(df) < 50:
        return None
    if 'EMA_50' not in df.columns or pd.isna(df['EMA_50'].iloc[-1]):
        return None

    last = df.iloc[-1]
    prev = df.iloc[-2]

    setups = []

    # --- BULLISH SETUPS ---

    # 1. Pullback to EMA20 in established uptrend
    if (last['Close'] > last['EMA_50']
        and last['EMA_20'] > last['EMA_50']
        and abs(last['Close'] - last['EMA_20']) / last['EMA_20'] < 0.025
        and 40 < last['RSI'] < 62
        and last['MACD_Hist'] > prev['MACD_Hist']):  # momentum turning up
        setups.append(('Bullish Pullback to EMA20', 'LONG', 'high'))

    # 2. Breakout above 20-day high with volume
    if (last['Close'] > prev['High_20']
        and last['Vol_ratio'] > 1.5
        and last['Close'] > last['EMA_50']
        and last['RSI'] > 55):
        setups.append(('Bullish Breakout (Volume)', 'LONG', 'high'))

    # 3. EMA 20/50 bullish cross (early trend signal)
    if (last['EMA_20'] > last['EMA_50']
        and prev['EMA_20'] <= prev['EMA_50']
        and last['Close'] > last['EMA_20']):
        setups.append(('EMA 20/50 Bullish Cross', 'LONG', 'medium'))

    # 4. RSI bullish reversal from oversold + MACD turning up
    if (last['RSI'] > 35 and last['RSI'] < 50
        and df['RSI'].iloc[-3:].min() < 35
        and last['MACD_Hist'] > prev['MACD_Hist']
        and last['Close'] > last['EMA_50'] * 0.95):  # not in deep downtrend
        setups.append(('Bullish RSI Reversal', 'LONG', 'medium'))

    # --- BEARISH SETUPS ---

    # 5. Pullback to EMA20 in established downtrend
    if (last['Close'] < last['EMA_50']
        and last['EMA_20'] < last['EMA_50']
        and abs(last['Close'] - last['EMA_20']) / last['EMA_20'] < 0.025
        and 38 < last['RSI'] < 58
        and last['MACD_Hist'] < prev['MACD_Hist']):
        setups.append(('Bearish Pullback to EMA20', 'SHORT', 'high'))

    # 6. Breakdown below 20-day low with volume
    if (last['Close'] < prev['Low_20']
        and last['Vol_ratio'] > 1.5
        and last['Close'] < last['EMA_50']
        and last['RSI'] < 45):
        setups.append(('Bearish Breakdown (Volume)', 'SHORT', 'high'))

    # 7. EMA 20/50 bearish cross
    if (last['EMA_20'] < last['EMA_50']
        and prev['EMA_20'] >= prev['EMA_50']
        and last['Close'] < last['EMA_20']):
        setups.append(('EMA 20/50 Bearish Cross', 'SHORT', 'medium'))

    if not setups:
        return None

    # Prefer high-confidence setups
    setups.sort(key=lambda x: 0 if x[2] == 'high' else 1)
    setup_name, direction, confidence = setups[0]

    # Score and trade levels
    score = calculate_score(df, direction)
    atr = last['ATR']
    cmp = last['Close']

    if direction == 'LONG':
        entry = cmp
        stop_loss = round(cmp - 1.5 * atr, 2)
        target1 = round(cmp + 2 * atr, 2)
        target2 = round(cmp + 3.5 * atr, 2)
    else:
        entry = cmp
        stop_loss = round(cmp + 1.5 * atr, 2)
        target1 = round(cmp - 2 * atr, 2)
        target2 = round(cmp - 3.5 * atr, 2)

    risk = abs(entry - stop_loss)
    reward1 = abs(target1 - entry)
    rr = round(reward1 / risk, 2) if risk > 0 else 0

    return {
        'setup': setup_name,
        'direction': direction,
        'confidence': confidence,
        'score': score,
        'cmp': round(cmp, 2),
        'entry': round(entry, 2),
        'stop_loss': stop_loss,
        'target1': target1,
        'target2': target2,
        'rr_ratio': rr,
        'rsi': round(last['RSI'], 1),
        'adx': round(last['ADX'], 1) if not pd.isna(last['ADX']) else 0,
        'vol_ratio': round(last['Vol_ratio'], 2),
        'atr_pct': round(atr / cmp * 100, 2),
        'pct_5d': round(last['Return_5'] * 100, 2) if not pd.isna(last['Return_5']) else 0,
    }


def calculate_score(df: pd.DataFrame, direction: str) -> int:
    """Strength score 0-100. Higher = stronger setup."""
    last = df.iloc[-1]
    score = 0

    # Trend strength (30 points) - ADX
    if not pd.isna(last['ADX']):
        if last['ADX'] > 28:
            score += 30
        elif last['ADX'] > 22:
            score += 22
        elif last['ADX'] > 18:
            score += 12

    # Momentum quality (25 points)
    if direction == 'LONG':
        if 52 < last['RSI'] < 68:
            score += 15
        elif 45 <= last['RSI'] <= 52:
            score += 10
        if last['MACD_Hist'] > 0:
            score += 10
    else:
        if 32 < last['RSI'] < 48:
            score += 15
        elif 48 <= last['RSI'] <= 55:
            score += 10
        if last['MACD_Hist'] < 0:
            score += 10

    # Volume confirmation (20 points)
    if last['Vol_ratio'] > 2:
        score += 20
    elif last['Vol_ratio'] > 1.5:
        score += 15
    elif last['Vol_ratio'] > 1:
        score += 8

    # MA alignment (15 points)
    if direction == 'LONG':
        if last['Close'] > last['EMA_20'] > last['EMA_50']:
            score += 15
        elif last['Close'] > last['EMA_50']:
            score += 8
    else:
        if last['Close'] < last['EMA_20'] < last['EMA_50']:
            score += 15
        elif last['Close'] < last['EMA_50']:
            score += 8

    # Position in Bollinger (10 points) - prefer middle for swing entries
    if not pd.isna(last['BB_upper']) and not pd.isna(last['BB_lower']):
        bb_range = last['BB_upper'] - last['BB_lower']
        if bb_range > 0:
            bb_pos = (last['Close'] - last['BB_lower']) / bb_range
            if 0.25 < bb_pos < 0.75:
                score += 10
            elif 0.15 < bb_pos < 0.85:
                score += 5

    return min(100, max(0, score))


def scan(data_dict: dict, indicators_fn, min_score: int = 0) -> pd.DataFrame:
    """Run scanner over a dict of {symbol: ohlcv_df}.

    Args:
        data_dict: {symbol: DataFrame with OHLCV}
        indicators_fn: function that adds indicators (e.g. indicators.add_indicators)
        min_score: minimum strength score to include in results

    Returns DataFrame of signals sorted by score (highest first).
    """
    results = []
    for symbol, df in data_dict.items():
        if df is None or df.empty:
            continue
        df = indicators_fn(df)
        signal = evaluate_setup(df)
        if signal and signal['score'] >= min_score:
            signal['symbol'] = symbol.replace('.NS', '').replace('^', '')
            results.append(signal)

    if not results:
        return pd.DataFrame()

    df_out = pd.DataFrame(results)
    # Sort: score descending, then high confidence first
    df_out['conf_rank'] = df_out['confidence'].map({'high': 0, 'medium': 1, 'low': 2})
    df_out = df_out.sort_values(by=['score', 'conf_rank'], ascending=[False, True])
    df_out = df_out.drop(columns=['conf_rank'])
    return df_out.reset_index(drop=True)
