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

    # Results table
    st.subheader(f"🎯 Top Setups ({st.session_state.get('scan_timeframe', 'Daily')})")

    display_df = results.copy()
    display_df['CMP'] = display_df['cmp'].apply(lambda x: f"₹{x:,.2f}")
    display_df['Entry'] = display_df['entry'].apply(lambda x: f"₹{x:,.2f}")
    display_df['SL'] = display_df['stop_loss'].apply(lambda x: f"₹{x:,.2f}")
    display_df['T1'] = display_df['target1'].apply(lambda x: f"₹{x:,.2f}")
    display_df['T2'] = display_df['target2'].apply(lambda x: f"₹{x:,.2f}")
    display_df['R:R'] = display_df['rr_ratio'].apply(lambda x: f"1:{x}")
    display_df['Score'] = display_df['score']
    display_df['Direction'] = display_df['direction'].apply(
        lambda x: f"🟢 {x}" if x == 'LONG' else f"🔴 {x}"
    )

    show_cols = ['symbol', 'Direction', 'setup', 'Score', 'CMP', 'Entry', 'SL', 'T1', 'T2', 'R:R',
                 'rsi', 'adx', 'vol_ratio']
    display_df = display_df[show_cols].rename(columns={
        'symbol': 'Stock',
        'setup': 'Setup',
        'rsi': 'RSI',
        'adx': 'ADX',
        'vol_ratio': 'Vol×',
    })

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Score": st.column_config.ProgressColumn(
                "Score", min_value=0, max_value=100, format="%d",
            ),
        },
    )

    st.caption("💡 Sorted by Score (strength). Higher score = stronger confluence of trend, momentum, and volume.")

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
