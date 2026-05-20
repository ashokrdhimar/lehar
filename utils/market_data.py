"""
Market data fetcher. Uses yfinance for OHLCV (free, no auth).
NSE direct fetch is provided as fallback / for option chain.
Streamlit caching applied here to avoid repeated API calls.
"""
import streamlit as st
import pandas as pd
import yfinance as yf
import requests
from datetime import datetime, timedelta
from typing import Optional


# Headers that NSE accepts for direct requests (rotate user-agent if blocked)
NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
}


@st.cache_data(ttl=300, show_spinner=False)  # 5-minute cache
def fetch_ohlcv(symbol: str, period: str = "6mo", interval: str = "1d") -> Optional[pd.DataFrame]:
    """Fetch OHLCV data for a single symbol.

    Args:
        symbol: yfinance symbol (e.g. 'RELIANCE.NS', '^NSEI')
        period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, ytd, max
        interval: 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo

    Returns DataFrame or None on failure.
    """
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=interval, auto_adjust=False)
        if df is None or df.empty:
            return None
        # Standardize column names
        df = df.rename(columns={c: c.capitalize() for c in df.columns})
        # Drop any rows with NaN in essential columns
        df = df.dropna(subset=['Open', 'High', 'Low', 'Close'])
        return df
    except Exception as e:
        # Silent fail - scanner will skip this symbol
        return None


@st.cache_data(ttl=300, show_spinner=False)
def fetch_multiple(symbols: list, period: str = "6mo", interval: str = "1d") -> dict:
    """Batch fetch using yfinance download. Faster than per-symbol calls.

    Returns dict of {symbol: DataFrame}.
    """
    if not symbols:
        return {}
    try:
        # yfinance handles batch download efficiently
        data = yf.download(
            tickers=" ".join(symbols),
            period=period,
            interval=interval,
            group_by='ticker',
            auto_adjust=False,
            progress=False,
            threads=True,
        )
        result = {}
        if len(symbols) == 1:
            df = data.copy()
            df.columns = [c.capitalize() if isinstance(c, str) else c for c in df.columns]
            result[symbols[0]] = df.dropna(subset=['Open', 'High', 'Low', 'Close']) if 'Close' in df else None
        else:
            for sym in symbols:
                try:
                    df = data[sym].copy()
                    df.columns = [c.capitalize() if isinstance(c, str) else c for c in df.columns]
                    df = df.dropna(subset=['Open', 'High', 'Low', 'Close'])
                    if not df.empty:
                        result[sym] = df
                except (KeyError, AttributeError):
                    continue
        return result
    except Exception:
        # Fallback to per-symbol fetch
        result = {}
        for sym in symbols:
            df = fetch_ohlcv(sym, period, interval)
            if df is not None and not df.empty:
                result[sym] = df
        return result


@st.cache_data(ttl=60, show_spinner=False)
def get_quote(symbol: str) -> Optional[dict]:
    """Latest quote summary for one symbol."""
    df = fetch_ohlcv(symbol, period="5d", interval="1d")
    if df is None or df.empty:
        return None
    last = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else last
    change = last['Close'] - prev['Close']
    pct = (change / prev['Close']) * 100 if prev['Close'] else 0
    return {
        'symbol': symbol,
        'price': round(last['Close'], 2),
        'change': round(change, 2),
        'pct_change': round(pct, 2),
        'volume': int(last['Volume']) if not pd.isna(last['Volume']) else 0,
        'date': df.index[-1].strftime('%Y-%m-%d'),
    }


@st.cache_data(ttl=300, show_spinner=False)
def fetch_option_chain_nse(symbol: str = "NIFTY") -> Optional[dict]:
    """Try to fetch NSE option chain directly. May fail due to NSE anti-bot.
    When Dhan API is set up later, replace this with Dhan's option chain endpoint.

    Args:
        symbol: 'NIFTY', 'BANKNIFTY', 'FINNIFTY', or any F&O underlying
    """
    try:
        url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"
        session = requests.Session()
        # First hit homepage to get cookies
        session.get("https://www.nseindia.com/", headers=NSE_HEADERS, timeout=10)
        resp = session.get(url, headers=NSE_HEADERS, timeout=10)
        if resp.status_code != 200:
            return None
        return resp.json()
    except Exception:
        return None
