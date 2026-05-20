"""
Index Options Selling Dashboard.

For Nifty/BankNifty option sellers — analyzes whether the market regime
and volatility favor option selling, and suggests safer strikes.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from utils.market_data import fetch_ohlcv, get_quote, fetch_option_chain_nse
from utils.indicators import add_indicators, find_support_resistance
from utils.options_analyzer import (
    detect_regime, expected_move, suggest_strikes,
    parse_option_chain, interpret_pcr,
)


st.set_page_config(page_title="Lehar · Options Dashboard", page_icon="📊", layout="wide")

st.title("📊 Index Options Selling Dashboard")
st.caption("Regime detection + volatility + suggested strikes — built for option SELLERS, not buyers.")

# --- Index selector ---
INDEX_CONFIG = {
    "Nifty 50": {"symbol": "^NSEI", "nse_symbol": "NIFTY", "strike_step": 50},
    "Bank Nifty": {"symbol": "^NSEBANK", "nse_symbol": "BANKNIFTY", "strike_step": 100},
    "Fin Nifty": {"symbol": "NIFTY_FIN_SERVICE.NS", "nse_symbol": "FINNIFTY", "strike_step": 50},
}

col_a, col_b, col_c = st.columns([1, 1, 2])
with col_a:
    chosen_index = st.selectbox("Index", list(INDEX_CONFIG.keys()), index=0)
with col_b:
    horizon_days = st.selectbox(
        "Horizon (days to expiry)", [3, 5, 7, 14, 21, 30], index=2,
        help="Days you plan to hold the short position. Affects expected-move calculation.",
    )
with col_c:
    st.markdown("&nbsp;")

config = INDEX_CONFIG[chosen_index]

# --- Fetch data ---
with st.spinner(f"Loading {chosen_index} data..."):
    df = fetch_ohlcv(config['symbol'], period="6mo", interval="1d")
    vix_quote = get_quote("^INDIAVIX")

if df is None or df.empty:
    st.error(f"❌ Could not fetch data for {chosen_index}.")
    st.stop()

df = add_indicators(df)
last = df.iloc[-1]
spot = float(last['Close'])
atr = float(last['ATR']) if not pd.isna(last['ATR']) else spot * 0.01
vix = vix_quote['price'] if vix_quote else None

# --- Top metrics ---
st.divider()
m1, m2, m3, m4 = st.columns(4)
m1.metric("Spot", f"{spot:,.2f}", f"{last['Close'] - df.iloc[-2]['Close']:+,.2f}")
m2.metric("India VIX", f"{vix:.2f}" if vix else "—",
          help="< 14: low vol, good for selling. > 20: high vol, premium rich but risky.")
m3.metric("Daily ATR", f"{atr:,.2f}", help="Average daily range — directly used for expected move.")
m4.metric("BB Width", f"{last['BB_width']*100:.2f}%", help="< 8% = consolidation, often precedes breakout.")


# --- Regime detection ---
st.divider()
st.subheader("🎯 Market Regime")

regime = detect_regime(df)
verdict_color = {
    'FAVORABLE': '🟢',
    'CAUTION': '🟡',
    'AVOID': '🔴',
    'UNKNOWN': '⚪',
}.get(regime['verdict'], '⚪')

reg_col1, reg_col2 = st.columns([1, 2])
with reg_col1:
    st.markdown(f"### {verdict_color} {regime['verdict']}")
    st.markdown(f"**Regime:** {regime['regime'].replace('_', ' ').title()}")
    st.markdown(f"**ADX:** {regime['adx']}")
    st.markdown(f"**+DI:** {regime['di_plus']}  |  **−DI:** {regime['di_minus']}")
with reg_col2:
    if regime['verdict'] == 'FAVORABLE':
        st.success(regime['reason'])
    elif regime['verdict'] == 'CAUTION':
        st.warning(regime['reason'])
    else:
        st.error(regime['reason'])

    st.markdown("""
    **Rule of thumb for option sellers:**
    - ADX < 20 → range-bound → 🟢 favorable
    - ADX 20–28 → moderate trend → 🟡 caution, sell wider
    - ADX > 28 → strong trend → 🔴 avoid selling on trend side
    """)


# --- Expected Move & Strike Suggestions ---
st.divider()
st.subheader(f"📐 Expected Move ({horizon_days} days) & Suggested Strikes")

exp = expected_move(spot, atr, vix, horizon_days)
sr = find_support_resistance(df)
suggestion = suggest_strikes(spot, exp, regime, strike_step=config['strike_step'], sr_levels=sr)

em_col1, em_col2 = st.columns(2)
with em_col1:
    st.markdown("**Expected Move:**")
    st.write(f"• ATR-based: ±{exp['atr_move']:.0f}")
    if exp['iv_move']:
        st.write(f"• IV (VIX) based: ±{exp['iv_move']:.0f}")
    st.write(f"• **Conservative band:** {exp['lower_band']:,.0f} – {exp['upper_band']:,.0f}")

with em_col2:
    st.markdown("**Suggested Strike Distances:**")
    st.write(f"• Sell **CE @ {suggestion['ce_strike']}** ({suggestion['ce_distance_pct']}% above spot)")
    st.write(f"• Sell **PE @ {suggestion['pe_strike']}** ({suggestion['pe_distance_pct']}% below spot)")
    if suggestion['notes']:
        for n in suggestion['notes']:
            st.warning(n)

# Visualize spot, expected band, and strikes
st.markdown("**Levels Visualization:**")
levels_fig = go.Figure()
last_n = df.tail(60)
levels_fig.add_trace(go.Scatter(
    x=last_n.index, y=last_n['Close'],
    line=dict(color='#FFB700', width=2), name='Spot',
))
levels_fig.add_hline(y=exp['upper_band'], line_dash="dash", line_color="#888",
                    annotation_text=f"Expected Upper {exp['upper_band']:.0f}")
levels_fig.add_hline(y=exp['lower_band'], line_dash="dash", line_color="#888",
                    annotation_text=f"Expected Lower {exp['lower_band']:.0f}")
levels_fig.add_hline(y=suggestion['ce_strike'], line_dash="dot", line_color="#FF6666",
                    annotation_text=f"CE Sell {suggestion['ce_strike']}")
levels_fig.add_hline(y=suggestion['pe_strike'], line_dash="dot", line_color="#66CC66",
                    annotation_text=f"PE Sell {suggestion['pe_strike']}")
for r in sr['resistance'][:2]:
    levels_fig.add_hline(y=r, line_dash="dashdot", line_color="#FFAA66", opacity=0.5,
                        annotation_text=f"R: {r}")
for s in sr['support'][:2]:
    levels_fig.add_hline(y=s, line_dash="dashdot", line_color="#66AAFF", opacity=0.5,
                        annotation_text=f"S: {s}")
levels_fig.update_layout(
    height=400, template='plotly_dark',
    margin=dict(l=10, r=10, t=20, b=10),
    showlegend=False,
)
st.plotly_chart(levels_fig, use_container_width=True)


# --- Option Chain (NSE direct) ---
st.divider()
st.subheader("⛓️ Option Chain Analysis")

with st.spinner("Fetching NSE option chain..."):
    chain_raw = fetch_option_chain_nse(config['nse_symbol'])

if chain_raw:
    chain = parse_option_chain(chain_raw)
    if chain:
        oc_col1, oc_col2, oc_col3, oc_col4 = st.columns(4)
        oc_col1.metric("Expiry", chain['expiry'])
        oc_col2.metric("PCR", f"{chain['pcr']:.2f}", help=interpret_pcr(chain['pcr']))
        oc_col3.metric("Max Pain", f"{chain['max_pain']:,}")
        oc_col4.metric("Underlying", f"{chain['underlying']:,.2f}")

        st.write(f"**Top Call OI (Resistance zones):** {', '.join(str(x) for x in chain['top_ce_oi_strikes'])}")
        st.write(f"**Top Put OI (Support zones):** {', '.join(str(x) for x in chain['top_pe_oi_strikes'])}")
        st.write(f"**PCR Interpretation:** {interpret_pcr(chain['pcr'])}")

        # Bar chart of OI by strike (top 20 around spot)
        strikes_df = pd.DataFrame(chain['strikes_data'])
        nearby = strikes_df[
            (strikes_df['strike'] >= spot - 10 * config['strike_step']) &
            (strikes_df['strike'] <= spot + 10 * config['strike_step'])
        ].sort_values('strike')

        if not nearby.empty:
            oi_fig = go.Figure()
            oi_fig.add_trace(go.Bar(
                x=nearby['strike'], y=nearby['ce_oi'],
                name='Call OI', marker_color='#FF6666',
            ))
            oi_fig.add_trace(go.Bar(
                x=nearby['strike'], y=-nearby['pe_oi'],
                name='Put OI', marker_color='#66CC66',
            ))
            oi_fig.add_vline(x=spot, line_dash="dash", line_color="#FFB700",
                            annotation_text=f"Spot {spot:.0f}")
            oi_fig.update_layout(
                title="Open Interest by Strike (Calls vs Puts)",
                height=400, template='plotly_dark',
                barmode='relative',
                margin=dict(l=10, r=10, t=40, b=10),
            )
            st.plotly_chart(oi_fig, use_container_width=True)
    else:
        st.info("Option chain data fetched but couldn't be parsed.")
else:
    st.warning(
        "⚠️ NSE option chain not accessible right now (NSE often blocks direct API calls). "
        "When Dhan API is set up via Settings, option chain will load from there reliably."
    )


# --- Educational footer ---
st.divider()
with st.expander("📚 How to Use This Dashboard"):
    st.markdown("""
    **For weekly Nifty/BankNifty option selling, this is the typical workflow:**

    1. **Check Market Regime first.** If 🔴 AVOID — stand aside for the day, or sell only on the side opposite to the strong trend.
    2. **Check VIX.** Very low VIX (< 12) means thin premium — not worth the risk. Moderate VIX (14–18) is the sweet spot for sellers. Spiking VIX (> 22) = big move likely, deeper distance needed.
    3. **Use Expected Move.** Your strikes should be outside the expected upper/lower bands. The dashboard already does this.
    4. **Cross-check with Option Chain:** Max Pain often acts as a magnet near expiry. High Call OI strikes act as resistance; high Put OI strikes act as support.
    5. **Honor Support/Resistance.** If a suggested CE strike is right below a major resistance, move it one step higher.
    6. **Always plan adjustment / SL** before entering. Common rules: exit if spot crosses sold strike, or if premium doubles.

    **Remember:** Option selling has limited reward and (theoretically) unlimited risk. Position sizing matters more than the strike choice.
    """)
