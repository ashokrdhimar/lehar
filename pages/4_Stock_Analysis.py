"""
Stock Analysis — the heart of Lehar.

For any chosen stock, shows:
  - A bold, color-coded VERDICT card with plain-Hindi guidance ("आगे क्या करें")
  - Technical analysis (chart + indicators + setup)
  - Fundamental analysis (PE, ROE, debt, growth as cards)
  - Recent News headlines

Technical terms stay in English; explanations and advice are in simple Hindi.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from utils.market_data import fetch_ohlcv
from utils.indicators import add_indicators, find_support_resistance
from utils.scanner import evaluate_setup
from utils.fundamentals import get_fundamentals, get_news, fmt_market_cap
from utils.verdict import generate_verdict
from utils.stock_universe import get_universe, to_yf_symbol


st.set_page_config(page_title="Lehar · Stock Analysis", page_icon="🔍", layout="wide")

# ---------- Custom styling for a polished look ----------
st.markdown("""
<style>
.verdict-card {
    border-radius: 16px;
    padding: 22px 26px;
    margin: 8px 0 18px 0;
    border: 1px solid rgba(255,255,255,0.08);
}
.verdict-strong { background: linear-gradient(135deg, #0b6e3f, #14543a); }
.verdict-buy    { background: linear-gradient(135deg, #15633f, #1a3d2e); }
.verdict-watch  { background: linear-gradient(135deg, #6e5a0b, #3d3414); }
.verdict-avoid  { background: linear-gradient(135deg, #2a2f3a, #1a1d24); }
.verdict-short  { background: linear-gradient(135deg, #6e1b1b, #3d1414); }
.verdict-title { font-size: 1.5rem; font-weight: 700; margin-bottom: 6px; }
.verdict-action { font-size: 1.02rem; line-height: 1.65; }
.section-label {
    font-size: 0.78rem; letter-spacing: 0.06em; text-transform: uppercase;
    color: #FFB700; font-weight: 600; margin: 4px 0;
}
.fund-pill {
    display:inline-block; background: rgba(255,255,255,0.05);
    border-radius: 10px; padding: 4px 10px; margin: 3px; font-size: 0.85rem;
}
</style>
""", unsafe_allow_html=True)

st.title("🔍 Stock Analysis")
st.caption("किसी भी stock का पूरा picture — Technical + Fundamental + News + साफ़ Hindi राय।")

# ---------- Stock selector ----------
col1, col2 = st.columns([2, 1])
with col1:
    universe = get_universe("Nifty 100")
    clean_names = [s.replace(".NS", "") for s in universe]
    chosen = st.selectbox("Stock चुनें (Nifty 100)", clean_names, index=clean_names.index("RELIANCE") if "RELIANCE" in clean_names else 0)
with col2:
    custom = st.text_input("या कोई और NSE symbol लिखें", placeholder="जैसे: IRCTC, ZOMATO")

symbol_input = custom.strip().upper() if custom.strip() else chosen
yf_symbol = to_yf_symbol(symbol_input)

analyze = st.button("🔍 Analyze करें", type="primary", use_container_width=True)

if analyze or "last_analyzed" in st.session_state:
    if analyze:
        st.session_state["last_analyzed"] = yf_symbol
    target_symbol = st.session_state.get("last_analyzed", yf_symbol)

    with st.spinner(f"{symbol_input} का analysis हो रहा है..."):
        df = fetch_ohlcv(target_symbol, period="1y", interval="1d")

    if df is None or df.empty:
        st.error(f"❌ {symbol_input} का data नहीं मिला। Symbol सही है क्या? (NSE symbol होना चाहिए)")
        st.stop()

    df = add_indicators(df)
    signal = evaluate_setup(df)
    sr = find_support_resistance(df)
    fund = get_fundamentals(target_symbol)
    news = get_news(target_symbol)

    last = df.iloc[-1]
    prev = df.iloc[-2]
    cmp = last["Close"]
    change = cmp - prev["Close"]
    pct = (change / prev["Close"]) * 100 if prev["Close"] else 0

    # ---------- VERDICT CARD (top, most important) ----------
    verdict = generate_verdict(signal, fund, sr)
    card_class = {
        "STRONG_BUY": "verdict-strong",
        "BUY": "verdict-buy",
        "WATCH": "verdict-watch",
        "AVOID": "verdict-avoid",
        "SHORT_SETUP": "verdict-short",
    }.get(verdict["rating"], "verdict-avoid")

    st.markdown(f"""
    <div class="verdict-card {card_class}">
        <div class="verdict-title">{verdict['rating_hi']}</div>
        <div class="verdict-action">✅ <b>आगे क्या करें:</b><br>{verdict['action_text']}</div>
    </div>
    """, unsafe_allow_html=True)

    # ---------- Quick header metrics ----------
    name = fund.get("name", symbol_input)
    sector = fund.get("sector", "N/A")
    st.markdown(f"### {name}")
    st.caption(f"Sector: {sector} · Industry: {fund.get('industry', 'N/A')}")

    h1, h2, h3, h4 = st.columns(4)
    h1.metric("CMP", f"₹{cmp:,.2f}", f"{change:+,.2f} ({pct:+.2f}%)")
    h2.metric("Market Cap", fmt_market_cap(fund.get("market_cap")))
    if fund.get("high_52w") and fund.get("low_52w"):
        pos = (cmp - fund["low_52w"]) / (fund["high_52w"] - fund["low_52w"]) * 100 if (fund["high_52w"] - fund["low_52w"]) else 0
        h3.metric("52W Range", f"₹{fund['low_52w']:,.0f}–{fund['high_52w']:,.0f}", f"{pos:.0f}% तक")
    else:
        h3.metric("52W Range", "N/A")
    tech_lbl = signal["direction"] if signal else "—"
    h4.metric("Technical Setup", tech_lbl, f"Score {signal['score']}" if signal else "No setup")

    # ---------- Tabs: Technical / Fundamental / News ----------
    tab1, tab2, tab3 = st.tabs(["📈 Technical", "📊 Fundamental", "📰 News"])

    # ===== TECHNICAL TAB =====
    with tab1:
        st.markdown('<div class="section-label">Technical समझ (Hindi)</div>', unsafe_allow_html=True)
        st.markdown(verdict["tech_text"], unsafe_allow_html=True)
        st.write("")

        if signal:
            c1, c2, c3 = st.columns(3)
            c1.metric("Setup", signal["setup"])
            c1.metric("Direction", signal["direction"])
            c2.metric("Entry", f"₹{signal['entry']:,.2f}")
            c2.metric("Stop Loss", f"₹{signal['stop_loss']:,.2f}")
            c3.metric("Target 1", f"₹{signal['target1']:,.2f}")
            c3.metric("Risk:Reward", f"1:{signal['rr_ratio']}")

        # Support / Resistance
        sc1, sc2 = st.columns(2)
        if sr.get("support"):
            sc1.success("**Support:** " + ", ".join(f"₹{s:,.0f}" for s in sr["support"]))
        if sr.get("resistance"):
            sc2.error("**Resistance:** " + ", ".join(f"₹{r:,.0f}" for r in sr["resistance"]))

        # Chart
        last_n = df.tail(120)
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3],
                            vertical_spacing=0.04, subplot_titles=("Price + EMAs", "RSI"))
        fig.add_trace(go.Candlestick(x=last_n.index, open=last_n["Open"], high=last_n["High"],
                                     low=last_n["Low"], close=last_n["Close"], name="Price"), row=1, col=1)
        fig.add_trace(go.Scatter(x=last_n.index, y=last_n["EMA_20"], line=dict(color="#FFB700", width=1.5), name="EMA 20"), row=1, col=1)
        fig.add_trace(go.Scatter(x=last_n.index, y=last_n["EMA_50"], line=dict(color="#4A90E2", width=1.5), name="EMA 50"), row=1, col=1)
        if signal:
            for lvl, color, nm in [(signal["entry"], "#FFFFFF", "Entry"),
                                   (signal["stop_loss"], "#FF4D4D", "SL"),
                                   (signal["target1"], "#00CC88", "T1")]:
                fig.add_hline(y=lvl, line_dash="dash", line_color=color, annotation_text=nm, row=1, col=1)
        fig.add_trace(go.Scatter(x=last_n.index, y=last_n["RSI"], line=dict(color="#BB86FC"), name="RSI"), row=2, col=1)
        fig.add_hline(y=70, line_dash="dot", line_color="#888", row=2, col=1)
        fig.add_hline(y=30, line_dash="dot", line_color="#888", row=2, col=1)
        fig.update_layout(height=560, template="plotly_dark", xaxis_rangeslider_visible=False,
                          margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(fig, use_container_width=True)

    # ===== FUNDAMENTAL TAB =====
    with tab2:
        st.markdown('<div class="section-label">Fundamental समझ (Hindi)</div>', unsafe_allow_html=True)
        st.markdown(verdict["fund_text"], unsafe_allow_html=True)
        st.write("")

        if fund:
            f1, f2, f3, f4 = st.columns(4)
            f1.metric("PE Ratio", f"{fund['pe']:.1f}" if fund.get("pe") else "N/A")
            f2.metric("PB Ratio", f"{fund['pb']:.1f}" if fund.get("pb") else "N/A")
            f3.metric("ROE", f"{fund['roe']:.0f}%" if fund.get("roe") is not None else "N/A")
            f4.metric("Profit Margin", f"{fund['profit_margin']:.0f}%" if fund.get("profit_margin") is not None else "N/A")

            g1, g2, g3, g4 = st.columns(4)
            de = fund.get("debt_to_equity")
            de_disp = f"{(de/100 if de and de > 5 else de):.2f}" if de is not None else "N/A"
            g1.metric("Debt/Equity", de_disp)
            g2.metric("Earnings Growth", f"{fund['earnings_growth']:.0f}%" if fund.get("earnings_growth") is not None else "N/A")
            g3.metric("Dividend Yield", f"{fund['dividend_yield']:.2f}%" if fund.get("dividend_yield") is not None else "N/A")
            g4.metric("Beta", f"{fund['beta']:.2f}" if fund.get("beta") else "N/A")

            st.caption("💡 PE = कितना महंगा/सस्ता · ROE = company कितना return देती है · "
                       "D/E = कर्ज़ कितना · Beta = market से कितना volatile (1 से ज़्यादा = ज़्यादा झटके)।")
        else:
            st.warning("इस stock का fundamental data यफ़ाइनेंस से नहीं मिला (कुछ stocks पर सीमित होता है)।")

    # ===== NEWS TAB =====
    with tab3:
        st.markdown('<div class="section-label">हाल की खबरें</div>', unsafe_allow_html=True)
        if news:
            for n in news:
                meta = " · ".join(filter(None, [n.get("publisher"), n.get("time")]))
                if n.get("link"):
                    st.markdown(f"**[{n['title']}]({n['link']})**")
                else:
                    st.markdown(f"**{n['title']}**")
                if meta:
                    st.caption(meta)
                st.divider()
            st.caption("💡 खबरें खुद पढ़कर समझें — कोई बड़ी news (results, order, scam) signal को बदल सकती है।")
        else:
            st.info("इस stock की recent news नहीं मिली। (yfinance पर Indian stocks की news सीमित होती है — "
                    "Google News या MoneyControl पर direct check कर सकते हैं।)")

else:
    st.info("👆 ऊपर से stock चुनें या symbol लिखें, फिर **Analyze करें** दबाएँ — पूरा technical + fundamental + news picture एक साथ मिलेगा, साथ में Hindi में साफ़ राय।")
