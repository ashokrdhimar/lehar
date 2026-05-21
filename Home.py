"""
Lehar (लहर) — Market की लहरों पर सवारी
Main landing page with market overview.

Author: Built for Ashok R. Dhimar
Phase 1: Signals only (analysis & alerts)
Phase 2 (planned): Dhan API execution integration
"""
import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.graph_objects as go

from utils.market_data import fetch_ohlcv, get_quote
from utils.indicators import add_indicators
from utils.options_analyzer import detect_regime
from utils.stock_universe import INDICES


st.set_page_config(
    page_title="Lehar 🌊",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Header ---
col_a, col_b = st.columns([3, 1])
with col_a:
    st.title("🌊 Lehar")
    st.markdown("##### *Market की लहरों पर सवारी* — Swing trading signals & index option-selling analysis")
    st.caption("Educational tool — signals are not buy/sell advice.")
with col_b:
    st.markdown(f"**🕐 {datetime.now().strftime('%d %b %Y, %H:%M')}**")
    st.markdown("Market: NSE / BSE")


st.divider()

# --- Market Overview ---
st.subheader("Market Overview")

# Display in rows of 3 — prevents number truncation in narrow columns.
items = list(INDICES.items())
for row_start in range(0, len(items), 3):
    row_items = items[row_start:row_start + 3]
    cols = st.columns(3)  # always 3 columns; last row may have an empty slot
    for i, (name, symbol) in enumerate(row_items):
        with cols[i]:
            q = get_quote(symbol)
            if q is None:
                st.metric(label=name, value="—", delta="No data")
                continue
            delta_str = f"{q['change']:+.2f} ({q['pct_change']:+.2f}%)"
            st.metric(label=name, value=f"{q['price']:,.2f}", delta=delta_str)


st.divider()

# --- Quick Regime Check ---
st.subheader("📍 Quick Regime Check — Nifty 50 & Bank Nifty")
st.caption("Trending or range-bound? Critical for option sellers.")

regime_cols = st.columns(2)

for idx, (label, sym) in enumerate([("Nifty 50", "^NSEI"), ("Bank Nifty", "^NSEBANK")]):
    with regime_cols[idx]:
        st.markdown(f"### {label}")
        with st.spinner(f"Analyzing {label}..."):
            df = fetch_ohlcv(sym, period="6mo", interval="1d")
            if df is None or df.empty:
                st.warning("Data not available")
                continue
            df = add_indicators(df)
            regime = detect_regime(df)

            verdict_color = {
                'FAVORABLE': '🟢',
                'CAUTION': '🟡',
                'AVOID': '🔴',
                'UNKNOWN': '⚪',
            }.get(regime['verdict'], '⚪')

            st.markdown(f"**Regime:** {regime['regime'].replace('_', ' ').title()}")
            st.markdown(f"**Option Selling:** {verdict_color} {regime['verdict']}")
            st.markdown(f"**ADX:** {regime['adx']}  &nbsp;&nbsp; **BB Width:** {regime['bb_width']}%")
            st.info(regime['reason'])

            # Mini price chart with EMAs
            last_n = df.tail(60)
            fig = go.Figure()
            fig.add_trace(go.Candlestick(
                x=last_n.index,
                open=last_n['Open'], high=last_n['High'],
                low=last_n['Low'], close=last_n['Close'],
                name='Price', showlegend=False,
            ))
            fig.add_trace(go.Scatter(
                x=last_n.index, y=last_n['EMA_20'],
                line=dict(color='#FFB700', width=1.5), name='EMA 20',
            ))
            fig.add_trace(go.Scatter(
                x=last_n.index, y=last_n['EMA_50'],
                line=dict(color='#4A90E2', width=1.5), name='EMA 50',
            ))
            fig.update_layout(
                height=300, xaxis_rangeslider_visible=False,
                margin=dict(l=10, r=10, t=10, b=10),
                showlegend=True, legend=dict(orientation='h', y=1.1),
                template='plotly_dark',
            )
            st.plotly_chart(fig, use_container_width=True)


st.divider()

# --- Navigation hint ---
st.markdown("""
### 🧭 Use the sidebar to explore:

- **📈 Stock Scanner** — scan Nifty 50 / Next 50 / Bank stocks for swing setups
- **📊 Options Dashboard** — index option-selling analysis with strike suggestions
- **⚙️ Settings** — Dhan API integration (for Phase 2 execution)
""")

with st.expander("ℹ️ Disclaimer & Notes"):
    st.markdown("""
- This is an **educational analysis tool**, not investment advice.
- Signals are derived from technical indicators; markets remain unpredictable.
- All trading decisions and risk management are yours.
- Past performance of any indicator/setup does not guarantee future results.
- Data source: Yahoo Finance (free, 15-min delayed during market hours).
- For real-time data, integrate broker API (planned: Dhan) via Settings page.
""")

st.caption("🌊 Lehar · Built for Ashok R. Dhimar · SPM Bemetara S.O. · Phase 1 (Signals)")
