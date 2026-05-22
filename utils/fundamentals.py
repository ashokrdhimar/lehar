"""
Fundamentals + News fetcher for the Stock Analysis page.
Uses yfinance .info and .news. All wrapped in try/except because
yfinance fundamental data can be flaky for some symbols.
"""
import streamlit as st
import yfinance as yf
from datetime import datetime


@st.cache_data(ttl=3600, show_spinner=False)  # cache 1 hour - fundamentals change slowly
def get_fundamentals(symbol: str) -> dict:
    """Return a dict of fundamental metrics. Missing values are None."""
    try:
        info = yf.Ticker(symbol).info
    except Exception:
        info = {}

    if not info:
        return {}

    def pct(v):
        return round(v * 100, 2) if isinstance(v, (int, float)) else None

    return {
        "name": info.get("longName") or info.get("shortName") or symbol,
        "sector": info.get("sector", "N/A"),
        "industry": info.get("industry", "N/A"),
        "market_cap": info.get("marketCap"),
        "pe": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "pb": info.get("priceToBook"),
        "roe": pct(info.get("returnOnEquity")),
        "debt_to_equity": info.get("debtToEquity"),
        "profit_margin": pct(info.get("profitMargins")),
        "revenue_growth": pct(info.get("revenueGrowth")),
        "earnings_growth": pct(info.get("earningsQuarterlyGrowth")),
        "dividend_yield": pct(info.get("dividendYield")),
        "beta": info.get("beta"),
        "high_52w": info.get("fiftyTwoWeekHigh"),
        "low_52w": info.get("fiftyTwoWeekLow"),
        "current_price": info.get("currentPrice") or info.get("regularMarketPrice"),
        "book_value": info.get("bookValue"),
        "eps": info.get("trailingEps"),
    }


@st.cache_data(ttl=1800, show_spinner=False)  # cache 30 min
def get_news(symbol: str, limit: int = 6) -> list:
    """Return recent news headlines. Handles old & new yfinance structures."""
    try:
        raw = yf.Ticker(symbol).news or []
    except Exception:
        return []

    items = []
    for n in raw[:limit]:
        try:
            # New yfinance nests data under 'content'
            content = n.get("content", n)

            title = content.get("title") or n.get("title", "")
            if not title:
                continue

            # Publisher
            provider = content.get("provider")
            if isinstance(provider, dict):
                publisher = provider.get("displayName", "")
            else:
                publisher = n.get("publisher", "")

            # Link
            link = ""
            if isinstance(content.get("canonicalUrl"), dict):
                link = content["canonicalUrl"].get("url", "")
            elif content.get("clickThroughUrl"):
                link = content["clickThroughUrl"].get("url", "") if isinstance(content["clickThroughUrl"], dict) else ""
            else:
                link = n.get("link", "")

            # Time
            pub_time = ""
            ts = content.get("pubDate") or n.get("providerPublishTime")
            if isinstance(ts, (int, float)):
                pub_time = datetime.fromtimestamp(ts).strftime("%d %b %Y")
            elif isinstance(ts, str):
                pub_time = ts[:10]

            items.append({
                "title": title,
                "publisher": publisher,
                "link": link,
                "time": pub_time,
            })
        except Exception:
            continue

    return items


def fmt_market_cap(mc) -> str:
    """Format market cap in Indian crore notation."""
    if not mc:
        return "N/A"
    cr = mc / 1e7  # 1 crore = 10 million
    if cr >= 100000:
        return f"₹{cr/100000:,.2f} L Cr"  # lakh crore
    return f"₹{cr:,.0f} Cr"
