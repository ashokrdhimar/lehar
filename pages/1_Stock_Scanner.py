"""
Stock Swing Scanner page.
Scans selected universe and presents ranked setups with entry/SL/target.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from utils.market_data import fetch_multiple, fetch_ohlcv
from utils.indicators import add_indicators, find_support_resistance
from utils.scanner import scan
from utils.stock_universe import get_universe, to_yf_symbol


st.set_page_config(page_title="Lehar · Stock Scanner", page_icon="📈", layout="wide")

st.title("📈 Stock Swing Scanner")
st.caption("Scans the selected universe for strong swing-trading setups on the daily timeframe.")

# --- Controls ---
control_col1, control_col2, control_col3, control_col4 = st.columns([2, 1, 1, 1])

with control_col1:
    universe_name = st.selectbox(
        "Universe",
        ["Nifty 50", "Nifty Next 50", "Nifty 100", "Bank Nifty"],
        index=0,
    )

with control_col2:
    timeframe = st.selectbox(
        "Timeframe",
        ["Daily", "Weekly"],
        index=0,
        help="Daily for active swing (days–weeks). Weekly for positional swing (weeks–months).",
    )

with control_col3:
    min_score = st.slider("Min Score", 0, 100, 50, step=5)

with control_col4:
    direction_filter = st.selectbox("Direction", ["All", "LONG only", "SHORT only"])


run_scan = st.button("🔍 Run Scan", type="primary", use_container_width=True)


# --- Scan execution ---
if run_scan:
    symbols = get_universe(universe_name)
    period = "1y" if timeframe == "Daily" else "5y"
    interval = "1d" if timeframe == "Daily" else "1wk"

    with st.spinner(f"Fetching data for {len(symbols)} stocks..."):
        data = fetch_multiple(symbols, period=period, interval=interval)

    if not data:
        st.error("❌ Could not fetch market data. Check internet / try again later.")
        st.stop()

    st.success(f"✅ Fetched data for {len(data)} stocks. Running scan...")

    with st.spinner("Evaluating setups..."):
        results = scan(data, add_indicators, min_score=min_score)

    if results.empty:
        st.warning(f"No setups found with score ≥ {min_score}. Try lowering the threshold.")
        st.stop()

    # Apply direction filter
    if direction_filter == "LONG only":
        results = results[results['direction'] == 'LONG']
    elif direction_filter == "SHORT only":
        results = results[results['direction'] == 'SHORT']

    st.session_state['scan_results'] = results
    st.session_state['scan_data'] = data
    st.session_state['scan_timeframe'] = timeframe


# --- Results display ---
if 'scan_results' in st.session_state and not st.session_state['scan_results'].empty:
    results = st.session_state['scan_results']
    data = st.session_state['scan_data']

    st.divider()

    # Summary metrics
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Signals", len(results))
    m2.metric("LONG Setups", len(results[results['direction'] == 'LONG']))
    m3.metric("SHORT Setups", len(results[results['direction'] == 'SHORT']))
    m4.metric("High Confidence", len(results[results['confidence'] == 'high']))

    st.divider()

    # Results as clean cards (stock name prominent, readable on mobile)
    st.subheader(f"🎯 Top Setups ({st.session_state.get('scan_timeframe', 'Daily')})")

    def hindi_hint(direction, score):
        if direction == 'SHORT':
            return "🔴 गिरावट का setup — short करें या दूर रहें"
        if score >= 75:
            return "🟢 मज़बूत मौका — खरीदने लायक"
        if score >= 60:
            return "🟢 अच्छा setup — confirmation पर खरीदें"
        return "🟡 ठीक setup — नज़र रखें, जल्दबाज़ी न करें"

    for _, row in results.iterrows():
        dir_color = "#0b6e3f" if row['direction'] == 'LONG' else "#6e1b1b"
        dir_emoji = "🟢" if row['direction'] == 'LONG' else "🔴"
        st.markdown(f"""
        <div style="border:1px solid rgba(255,255,255,0.1); border-left:5px solid {dir_color};
                    border-radius:12px; padding:14px 18px; margin:8px 0; background:rgba(255,255,255,0.02);">
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <span style="font-size:1.25rem; font-weight:700;">{dir_emoji} {row['symbol']}</span>
            <span style="font-size:0.95rem; color:#FFB700; font-weight:600;">{row['direction']} · Score {row['score']}/100</span>
          </div>
          <div style="color:#bbb; margin:4px 0 8px 0;">{row['setup']}</div>
          <div style="font-size:0.95rem;">
            Entry <b>₹{row['entry']:,.2f}</b> &nbsp;·&nbsp;
            SL <b style="color:#ff6666;">₹{row['stop_loss']:,.2f}</b> &nbsp;·&nbsp;
            T1 <b style="color:#66cc88;">₹{row['target1']:,.2f}</b> &nbsp;·&nbsp;
            T2 <b style="color:#66cc88;">₹{row['target2']:,.2f}</b>
          </div>
          <div style="font-size:0.85rem; color:#999; margin-top:4px;">
            R:R 1:{row['rr_ratio']} &nbsp;·&nbsp; RSI {row['rsi']} &nbsp;·&nbsp; ADX {row['adx']} &nbsp;·&nbsp; Vol {row['vol_ratio']}×
          </div>
          <div style="margin-top:8px; font-size:0.92rem;">{hindi_hint(row['direction'], row['score'])}</div>
        </div>
        """, unsafe_allow_html=True)

    st.caption("💡 Score जितना ज़्यादा, setup उतना मज़बूत। पूरे technical + fundamental + news analysis के लिए "
               "**Stock Analysis** page पर stock का नाम डालें।")

    # --- Drill down into one stock ---
    st.divider()
    st.subheader("🔬 Detailed View")

    chosen_symbol = st.selectbox(
        "Select stock for detailed analysis",
        options=results['symbol'].tolist(),
    )

    if chosen_symbol:
        full_symbol = to_yf_symbol(chosen_symbol)
        df = data.get(full_symbol)
        if df is None:
            df = fetch_ohlcv(full_symbol, period="1y", interval="1d")

        if df is not None:
            df = add_indicators(df)
            signal = results[results['symbol'] == chosen_symbol].iloc[0].to_dict()

            # Signal card
            sig_col1, sig_col2, sig_col3 = st.columns(3)
            with sig_col1:
                st.metric("Setup", signal['setup'])
                st.metric("Direction", signal['direction'])
                st.metric("Strength Score", f"{signal['score']}/100")
            with sig_col2:
                st.metric("CMP", f"₹{signal['cmp']:,.2f}")
                st.metric("Entry", f"₹{signal['entry']:,.2f}")
                st.metric("Stop Loss", f"₹{signal['stop_loss']:,.2f}")
            with sig_col3:
                st.metric("Target 1", f"₹{signal['target1']:,.2f}")
                st.metric("Target 2", f"₹{signal['target2']:,.2f}")
                st.metric("Risk:Reward", f"1:{signal['rr_ratio']}")

            # Support/Resistance
            sr = find_support_resistance(df)
            sr_col1, sr_col2 = st.columns(2)
            with sr_col1:
                if sr['support']:
                    st.write(f"**Support levels:** {', '.join([f'₹{s:,.2f}' for s in sr['support']])}")
            with sr_col2:
                if sr['resistance']:
                    st.write(f"**Resistance levels:** {', '.join([f'₹{r:,.2f}' for r in sr['resistance']])}")

            # Chart with indicators
            last_n = df.tail(120)
            fig = make_subplots(
                rows=3, cols=1,
                shared_xaxes=True,
                row_heights=[0.55, 0.2, 0.25],
                vertical_spacing=0.03,
                subplot_titles=("Price + EMAs", "Volume", "RSI / MACD Hist"),
            )

            # Price
            fig.add_trace(go.Candlestick(
                x=last_n.index, open=last_n['Open'], high=last_n['High'],
                low=last_n['Low'], close=last_n['Close'], name='Price',
            ), row=1, col=1)
            fig.add_trace(go.Scatter(
                x=last_n.index, y=last_n['EMA_20'],
                line=dict(color='#FFB700', width=1.5), name='EMA 20',
            ), row=1, col=1)
            fig.add_trace(go.Scatter(
                x=last_n.index, y=last_n['EMA_50'],
                line=dict(color='#4A90E2', width=1.5), name='EMA 50',
            ), row=1, col=1)

            # Entry/SL/Target lines
            for level, color, name in [
                (signal['entry'], '#FFFFFF', 'Entry'),
                (signal['stop_loss'], '#FF4D4D', 'SL'),
                (signal['target1'], '#00CC88', 'T1'),
                (signal['target2'], '#00CC88', 'T2'),
            ]:
                fig.add_hline(y=level, line_dash="dash", line_color=color,
                              annotation_text=name, annotation_position="right", row=1, col=1)

            # Volume bars
            colors = ['#00CC88' if c >= o else '#FF4D4D'
                      for c, o in zip(last_n['Close'], last_n['Open'])]
            fig.add_trace(go.Bar(
                x=last_n.index, y=last_n['Volume'], marker_color=colors,
                name='Volume', showlegend=False,
            ), row=2, col=1)

            # RSI
            fig.add_trace(go.Scatter(
                x=last_n.index, y=last_n['RSI'],
                line=dict(color='#BB86FC'), name='RSI',
            ), row=3, col=1)
            fig.add_hline(y=70, line_dash="dot", line_color="#888", row=3, col=1)
            fig.add_hline(y=30, line_dash="dot", line_color="#888", row=3, col=1)

            fig.update_layout(
                height=750, template='plotly_dark',
                xaxis_rangeslider_visible=False,
                showlegend=True,
                margin=dict(l=10, r=10, t=40, b=10),
            )

            st.plotly_chart(fig, use_container_width=True)

else:
    st.info(
        "👆 Configure the scan parameters above and click **Run Scan**. "
        "Default settings (Nifty 50, Daily, Score ≥ 50) usually return 5–15 setups."
    )

    with st.expander("📚 Setup Definitions"):
        st.markdown("""
        **Bullish Pullback to EMA20** — Price above EMA50, EMA20 above EMA50, recent pullback brings price within ~2% of EMA20, RSI 40–62, MACD momentum turning up. *Best buy-on-dip setup in an uptrend.*

        **Bullish Breakout (Volume)** — Close above 20-day high with volume > 1.5× average, price above EMA50, RSI > 55. *Momentum-driven breakout.*

        **EMA 20/50 Bullish Cross** — Fresh cross of EMA20 above EMA50 with price above. *Early trend-change signal.*

        **Bullish RSI Reversal** — RSI bouncing from oversold (<35) into 35–50 zone with MACD turning up. *Bottom-fishing in pullbacks.*

        **Bearish setups** are the mirror — pullback to EMA20 in downtrend, breakdown below 20-day low with volume, EMA bearish cross.

        **Score (0–100)** combines:
        - Trend strength via ADX (30 pts)
        - Momentum via RSI + MACD (25 pts)
        - Volume vs 20-day average (20 pts)
        - Moving-average alignment (15 pts)
        - Bollinger position quality (10 pts)
        """)
