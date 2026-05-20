"""
Stock universe definitions for scanning.
Symbols use yfinance format: SYMBOL.NS for NSE.
Update these lists periodically as index composition changes.
"""

# Nifty 50 (as of 2025-2026 - rebalanced semi-annually by NSE)
NIFTY_50 = [
    "ADANIENT", "ADANIPORTS", "APOLLOHOSP", "ASIANPAINT", "AXISBANK",
    "BAJAJ-AUTO", "BAJAJFINSV", "BAJFINANCE", "BEL", "BHARTIARTL",
    "CIPLA", "COALINDIA", "DRREDDY", "EICHERMOT", "ETERNAL",
    "GRASIM", "HCLTECH", "HDFCBANK", "HDFCLIFE", "HEROMOTOCO",
    "HINDALCO", "HINDUNILVR", "ICICIBANK", "INDUSINDBK", "INFY",
    "ITC", "JIOFIN", "JSWSTEEL", "KOTAKBANK", "LT",
    "M&M", "MARUTI", "NESTLEIND", "NTPC", "ONGC",
    "POWERGRID", "RELIANCE", "SBILIFE", "SBIN", "SHRIRAMFIN",
    "SUNPHARMA", "TATACONSUM", "TATAMOTORS", "TATASTEEL", "TCS",
    "TECHM", "TITAN", "TRENT", "ULTRACEMCO", "WIPRO",
]

# Nifty Next 50 (large caps just outside Nifty 50)
NIFTY_NEXT_50 = [
    "ABB", "ADANIGREEN", "ADANIPOWER", "AMBUJACEM", "BAJAJHLDNG",
    "BANKBARODA", "BERGEPAINT", "BOSCHLTD", "BPCL", "BRITANNIA",
    "CANBK", "CHOLAFIN", "DABUR", "DIVISLAB", "DLF",
    "DMART", "GAIL", "GODREJCP", "HAL", "HAVELLS",
    "HDFCAMC", "ICICIGI", "ICICIPRULI", "INDIGO", "IOC",
    "IRCTC", "JINDALSTEL", "LICI", "LODHA", "LTIM",
    "MARICO", "NAUKRI", "NMDC", "PFC", "PIDILITIND",
    "PNB", "POWERINDIA", "RECLTD", "SBICARD", "SHREECEM",
    "SIEMENS", "TATAPOWER", "TORNTPHARM", "TVSMOTOR", "UNITDSPR",
    "VBL", "VEDL", "ZOMATO", "ZYDUSLIFE", "INDHOTEL",
]

# Banking & Financial Services (high-beta swing candidates)
BANK_NIFTY_STOCKS = [
    "HDFCBANK", "ICICIBANK", "SBIN", "AXISBANK", "KOTAKBANK",
    "INDUSINDBK", "BANKBARODA", "PNB", "FEDERALBNK", "IDFCFIRSTB",
    "AUBANK", "IDFC",
]

# Indices for the Options Dashboard
INDICES = {
    "NIFTY 50": "^NSEI",
    "BANK NIFTY": "^NSEBANK",
    "FIN NIFTY": "NIFTY_FIN_SERVICE.NS",
    "SENSEX": "^BSESN",
    "INDIA VIX": "^INDIAVIX",
}


def to_yf_symbol(symbol: str) -> str:
    """Convert NSE symbol to yfinance format."""
    if symbol.startswith("^") or symbol.endswith(".NS") or symbol.endswith(".BO"):
        return symbol
    return f"{symbol}.NS"


def get_universe(name: str) -> list:
    """Return symbol list (in yfinance format) for the named universe."""
    universes = {
        "Nifty 50": NIFTY_50,
        "Nifty Next 50": NIFTY_NEXT_50,
        "Nifty 100": NIFTY_50 + NIFTY_NEXT_50,
        "Bank Nifty": BANK_NIFTY_STOCKS,
    }
    symbols = universes.get(name, NIFTY_50)
    return [to_yf_symbol(s) for s in symbols]
