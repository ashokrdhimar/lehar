"""
generate_data.py — Lehar live data generator.

Scans Nifty 100, computes setups + market breadth + sector strength +
index regime, and writes data.json for the HTML dashboard to read.

Standalone (NO Streamlit) — runs headless in GitHub Actions every 15 min.
Reuses pure-logic modules: indicators, scanner, options_analyzer, stock_universe.
"""
import json
from datetime import datetime, timezone, timedelta

import yfinance as yf
import pandas as pd

from utils.indicators import add_indicators, find_support_resistance
from utils.scanner import evaluate_setup
from utils.options_analyzer import detect_regime, expected_move, suggest_strikes
from utils.stock_universe import get_universe

IST = timezone(timedelta(hours=5, minutes=30))

# Sector mapping for Nifty 100 (static; rarely changes)
SECTOR_MAP = {
    # Banking
    "HDFCBANK":"Banking","ICICIBANK":"Banking","SBIN":"Banking","AXISBANK":"Banking",
    "KOTAKBANK":"Banking","INDUSINDBK":"Banking","BANKBARODA":"Banking","PNB":"Banking",
    "FEDERALBNK":"Banking","IDFCFIRSTB":"Banking","AUBANK":"Banking","CANBK":"Banking",
    # Auto
    "MARUTI":"Auto","TATAMOTORS":"Auto","M&M":"Auto","BAJAJ-AUTO":"Auto",
    "EICHERMOT":"Auto","HEROMOTOCO":"Auto","TVSMOTOR":"Auto","BOSCHLTD":"Auto",
    # IT
    "TCS":"IT","INFY":"IT","WIPRO":"IT","HCLTECH":"IT","TECHM":"IT","LTIM":"IT",
    # Pharma / Healthcare
    "SUNPHARMA":"Pharma","DRREDDY":"Pharma","CIPLA":"Pharma","DIVISLAB":"Pharma",
    "TORNTPHARM":"Pharma","ZYDUSLIFE":"Pharma","APOLLOHOSP":"Healthcare",
    # FMCG
    "HINDUNILVR":"FMCG","ITC":"FMCG","NESTLEIND":"FMCG","BRITANNIA":"FMCG",
    "TATACONSUM":"FMCG","DABUR":"FMCG","GODREJCP":"FMCG","MARICO":"FMCG",
    "VBL":"FMCG","UNITDSPR":"FMCG",
    # Metal
    "TATASTEEL":"Metal","JSWSTEEL":"Metal","HINDALCO":"Metal","VEDL":"Metal",
    "JINDALSTEL":"Metal","NMDC":"Metal",
    # Energy / Power
    "RELIANCE":"Energy","ONGC":"Energy","BPCL":"Energy","IOC":"Energy","GAIL":"Energy",
    "NTPC":"Power","POWERGRID":"Power","COALINDIA":"Power","TATAPOWER":"Power",
    "ADANIGREEN":"Power","ADANIPOWER":"Power","PFC":"Finance","RECLTD":"Finance",
    # Finance / NBFC / Insurance
    "BAJFINANCE":"Finance","BAJAJFINSV":"Finance","SHRIRAMFIN":"Finance","CHOLAFIN":"Finance",
    "SBICARD":"Finance","HDFCAMC":"Finance","ICICIGI":"Insurance","ICICIPRULI":"Insurance",
    "SBILIFE":"Insurance","HDFCLIFE":"Insurance","LICI":"Insurance","JIOFIN":"Finance",
    # Cement
    "ULTRACEMCO":"Cement","GRASIM":"Cement","AMBUJACEM":"Cement","SHREECEM":"Cement",
    # Consumer / Retail / Paints
    "TITAN":"Consumer","TRENT":"Consumer","DMART":"Consumer","ASIANPAINT":"Paints",
    "BERGEPAINT":"Paints","PIDILITIND":"Chemicals","HAVELLS":"Consumer Durables",
    # Infra / Capital goods
    "LT":"Infra","SIEMENS":"Capital Goods","ABB":"Capital Goods","BEL":"Defence",
    "HAL":"Defence","POWERINDIA":"Capital Goods",
    # Telecom / Others
    "BHARTIARTL":"Telecom","INDIGO":"Aviation","IRCTC":"Travel","ETERNAL":"Internet",
    "ZOMATO":"Internet","NAUKRI":"Internet","DLF":"Realty","LODHA":"Realty",
    "ADANIENT":"Conglomerate","ADANIPORTS":"Logistics","INDHOTEL":"Hospitality",
    "BAJAJHLDNG":"Finance",
}


def sector_of(sym):
    return SECTOR_MAP.get(sym.replace(".NS", ""), "Other")


def fmt_mcap(mc):
    if not mc:
        return "—"
    cr = mc / 1e7
    if cr >= 100000:
        return f"{cr/100000:.1f}L Cr"
    return f"{cr:,.0f} Cr"


def fetch_indices():
    """Market pulse quotes + dataframes for Nifty/BankNifty regime."""
    syms = {"NIFTY 50":"^NSEI","BANK NIFTY":"^NSEBANK","SENSEX":"^BSESN","INDIA VIX":"^INDIAVIX"}
    market, frames = {}, {}
    for name, sym in syms.items():
        try:
            df = yf.Ticker(sym).history(period="6mo", interval="1d")
            df = df.rename(columns={c: c.capitalize() for c in df.columns})
            df = df.dropna(subset=["Close"])
            last, prev = df["Close"].iloc[-1], df["Close"].iloc[-2]
            market[name] = {"price": round(float(last), 2),
                            "change": round(float(last - prev), 2),
                            "pct": round(float((last - prev) / prev * 100), 2)}
            frames[name] = df
        except Exception as e:
            print(f"Index fetch failed {name}: {e}")
            market[name] = {"price": 0, "change": 0, "pct": 0}
    return market, frames


def fetch_all(symbols):
    """Batch fetch daily OHLCV for the universe."""
    data = {}
    try:
        raw = yf.download(tickers=" ".join(symbols), period="1y", interval="1d",
                          group_by="ticker", auto_adjust=False, progress=False, threads=True)
        for sym in symbols:
            try:
                df = raw[sym].copy()
                df.columns = [c.capitalize() if isinstance(c, str) else c for c in df.columns]
                df = df.dropna(subset=["Open", "High", "Low", "Close"])
                if not df.empty:
                    data[sym] = df
            except (KeyError, AttributeError):
                continue
    except Exception as e:
        print(f"Batch fetch error: {e}")
    return data


def quick_fundamentals(symbol):
    """Best-effort PE/ROE/MarketCap. Returns dict with '—' fallbacks."""
    out = {"pe": "—", "roe": "—", "mcap": "—"}
    try:
        info = yf.Ticker(symbol).info
        pe = info.get("trailingPE")
        roe = info.get("returnOnEquity")
        mc = info.get("marketCap")
        if pe: out["pe"] = round(pe, 1)
        if roe is not None: out["roe"] = round(roe * 100)
        if mc: out["mcap"] = fmt_mcap(mc)
    except Exception:
        pass
    return out


def rating_of(direction, score):
    if direction == "SHORT":
        return "SHORT_SETUP"
    if score >= 75:
        return "STRONG_BUY"
    if score >= 60:
        return "BUY"
    return "WATCH"


# ---------- Hindi reasoning generators ----------
def why_hindi(setup, direction, rsi, adx, vol):
    trend_txt = ("trend दमदार है" if adx >= 28 else "trend ठीक-ठाक है" if adx >= 20 else "trend अभी कमज़ोर है")
    vol_txt = (f"Volume average से {vol}× ज़्यादा — खरीदारों का दम।" if vol >= 1.5 else "Volume सामान्य है।")
    if direction == "SHORT":
        return (f"{setup} — बिकवाली का दबाव दिख रहा है। ADX {adx} ({trend_txt} नीचे की तरफ़), "
                f"RSI {rsi} कमज़ोरी दिखा रहा है। {vol_txt}")
    if "Pullback" in setup:
        return (f"Stock uptrend में है और support के पास pullback आया है — सस्ते में खरीदने का मौका। "
                f"ADX {adx} ({trend_txt}), RSI {rsi} healthy। {vol_txt}")
    if "Breakout" in setup:
        return (f"20-दिन high के ऊपर breakout हुआ है। ADX {adx} ({trend_txt}), RSI {rsi}। {vol_txt} "
                f"यानी असली खरीदारी, fake नहीं।")
    if "Cross" in setup:
        return (f"EMA20 ने EMA50 को ऊपर cross किया — trend बदलने का early संकेत। ADX {adx} ({trend_txt})। "
                f"{vol_txt} Confirmation का थोड़ा इंतज़ार बेहतर।")
    return (f"{setup}। ADX {adx} ({trend_txt}), RSI {rsi}। {vol_txt}")


def watch_hindi(direction, sl, resistance, support):
    if direction == "SHORT":
        return f"यह गिरावट का setup है। short करें तो SL ₹{sl:,.0f} (इसके ऊपर गया तो निकलें)।"
    res_txt = f" ₹{resistance[0]:,.0f} resistance है, वहाँ रुक सकता है।" if resistance else ""
    return f"₹{sl:,.0f} (SL) के नीचे बंद हुआ तो setup टूटा — तुरंत निकलें।{res_txt}"


def exit_hindi(direction, sl, t1, t2):
    if direction == "SHORT":
        return f"short नहीं करते तो इसे खरीदने की गलती न करें — अभी इस stock से दूर रहें।"
    return (f"T1 ₹{t1:,.0f} पर आधा profit book करें, बाकी T2 ₹{t2:,.0f} के लिए रखें। "
            f"SL ₹{sl:,.0f} trailing करते रहें।")


def breadth_summary(bull, neut, bear, total):
    if total == 0:
        return "Data उपलब्ध नहीं।"
    ratio = bull / total
    if ratio > 0.55:
        mood = "<b>तेज़ी (bullish)</b> की तरफ़"
        tail = "माहौल खरीदारी के पक्ष में, पर SL ज़रूर रखें।"
    elif ratio > 0.40:
        mood = "<b>मिला-जुला (neutral)</b>"
        tail = "साफ़ दिशा नहीं — चुनिंदा strong setups पर ही दांव लगाएँ।"
    else:
        mood = "<b>कमज़ोरी (bearish)</b> की तरफ़"
        tail = "सावधानी रखें — long trades में जल्दबाज़ी न करें, SL सख़्त रखें।"
    return (f"बाज़ार आज {mood} है — {total} में से {bull} stocks में खरीदारी का रुझान। {tail}")


def main():
    now = datetime.now(IST)
    print(f"[{now}] Generating Lehar data...")

    # 1. Indices + regime
    market, frames = fetch_indices()
    nifty_df = frames.get("NIFTY 50")
    vix = market.get("INDIA VIX", {}).get("price")

    regime_out = {"index": "Nifty 50", "verdict": "UNKNOWN", "regime": "—", "adx": 0,
                  "reason_hi": "Data उपलब्ध नहीं।", "ce_strike": 0, "pe_strike": 0, "expected": "—"}
    if nifty_df is not None and len(nifty_df) >= 50:
        ndf = add_indicators(nifty_df)
        reg = detect_regime(ndf)
        last = ndf.iloc[-1]
        spot = float(last["Close"]); atr = float(last["ATR"])
        sr = find_support_resistance(ndf)
        exp = expected_move(spot, atr, vix, 7)
        strikes = suggest_strikes(spot, exp, reg, strike_step=50, sr_levels=sr)
        regime_out = {
            "index": "Nifty 50", "verdict": reg["verdict"], "regime": reg["regime"].replace("_", " ").title(),
            "adx": reg["adx"],
            "reason_hi": reg["reason"].replace("Range-bound market", "Range-bound market")  # keep as-is
                if reg["verdict"] != "UNKNOWN" else "Data N/A",
            "ce_strike": strikes["ce_strike"], "pe_strike": strikes["pe_strike"],
            "expected": f"{exp['lower_band']:,.0f} – {exp['upper_band']:,.0f}",
        }

    # 2. Scan universe
    symbols = get_universe("Nifty 100")
    symbols = list(dict.fromkeys(symbols))   # dedupe, preserve order
    print(f"Fetching {len(symbols)} stocks...")
    all_data = fetch_all(symbols)
    print(f"Got {len(all_data)} stocks. Analyzing...")

    setups = []
    bull = neut = bear = 0
    sector_stats = {}  # sector -> [bullish_count, total]

    for sym, df in all_data.items():
        df = add_indicators(df)
        if df is None or len(df) < 50 or pd.isna(df["EMA_50"].iloc[-1]):
            continue
        last = df.iloc[-1]
        sec = sector_of(sym)
        sector_stats.setdefault(sec, [0, 0])
        sector_stats[sec][1] += 1

        # breadth + sector classification
        is_bull = last["Close"] > last["EMA_50"] and last["EMA_20"] > last["EMA_50"]
        is_bear = last["Close"] < last["EMA_50"] and last["EMA_20"] < last["EMA_50"]
        if is_bull:
            bull += 1; sector_stats[sec][0] += 1
        elif is_bear:
            bear += 1
        else:
            neut += 1

        # setup detection
        sig = evaluate_setup(df)
        if sig:
            setups.append((sym, df, sig))

    # 3. Select best setups: dedupe by symbol (keep highest score), quality filter
    setups.sort(key=lambda x: x[2]["score"], reverse=True)
    seen, unique = set(), []
    for sym, df, sig in setups:
        key = sym.replace(".NS", "")
        if key in seen:
            continue
        seen.add(key)
        unique.append((sym, df, sig))
    # Prefer strong setups (score >= 55); if too few, show top 8 so list is never empty
    strong = [s for s in unique if s[2]["score"] >= 55]
    setups = strong[:10] if len(strong) >= 4 else unique[:8]

    setup_cards = []
    for sym, df, sig in setups:
        clean = sym.replace(".NS", "")
        last = df.iloc[-1]
        sr = find_support_resistance(df)
        fund = quick_fundamentals(sym)
        spark = [round(float(c), 2) for c in df["Close"].tail(12).tolist()]
        rating = rating_of(sig["direction"], sig["score"])
        setup_cards.append({
            "symbol": clean, "sector": sector_of(sym),
            "direction": sig["direction"], "rating": rating, "setup": sig["setup"],
            "score": sig["score"], "cmp": round(sig["cmp"]),
            "entry": round(sig["entry"]), "sl": round(sig["stop_loss"]),
            "t1": round(sig["target1"]), "t2": round(sig["target2"]), "rr": sig["rr_ratio"],
            "rsi": sig["rsi"], "adx": sig["adx"], "vol": sig["vol_ratio"],
            "pe": fund["pe"], "roe": fund["roe"], "mcap": fund["mcap"],
            "support": [round(s) for s in sr["support"][:2]] or [round(sig["stop_loss"])],
            "resistance": [round(r) for r in sr["resistance"][:2]] or [round(sig["target1"])],
            "spark": spark,
            "why_hi": why_hindi(sig["setup"], sig["direction"], sig["rsi"], sig["adx"], sig["vol_ratio"]),
            "watch_hi": watch_hindi(sig["direction"], sig["stop_loss"],
                                    [round(r) for r in sr["resistance"][:1]],
                                    [round(s) for s in sr["support"][:1]]),
            "exit_hi": exit_hindi(sig["direction"], round(sig["stop_loss"]),
                                  round(sig["target1"]), round(sig["target2"])),
        })

    # 4. Sectors strength
    sectors = []
    for sec, (b, t) in sorted(sector_stats.items(), key=lambda x: -(x[1][0]/x[1][1] if x[1][1] else 0)):
        if t < 2:
            continue
        r = b / t
        strength = "strong" if r > 0.6 else "weak" if r < 0.3 else "neutral"
        sectors.append({"name": sec, "strength": strength})
    sectors = sectors[:8]

    total = bull + neut + bear
    data = {
        "updated_at": now.strftime("%d %b %Y, %-I:%M %p"),
        "is_demo": False,
        "market": market,
        "breadth": {"bullish": bull, "neutral": neut, "bearish": bear,
                    "summary_hi": breadth_summary(bull, neut, bear, total)},
        "sectors": sectors,
        "regime": regime_out,
        "setups": setup_cards,
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"data.json written: {len(setup_cards)} setups, breadth {bull}/{neut}/{bear}")


if __name__ == "__main__":
    main()
