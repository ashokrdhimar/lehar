"""
Settings page - app preferences and Dhan API setup (Phase 2 prep).
"""
import streamlit as st


st.set_page_config(page_title="Lehar · Settings", page_icon="⚙️", layout="wide")

st.title("⚙️ Settings & Dhan API")
st.caption("App preferences and broker integration setup for Phase 2 (order execution).")


# --- Phase 2 readiness ---
st.subheader("🔌 Dhan API Integration (Phase 2)")

st.info(
    "Phase 2 will use Dhan's free API for live data and order execution. "
    "Setup is a one-time activity, listed below."
)

with st.expander("Step-by-step: Get Dhan API Access", expanded=True):
    st.markdown("""
    1. **Open Dhan account** at https://dhan.co (if not already done). KYC takes 1–2 days.
    2. Log in to Dhan web (https://web.dhan.co), go to **Profile → DhanHQ APIs**.
    3. Click **Generate Access Token** (valid for 24 hours; can be regenerated). For a long-term token you'll need to register an app.
    4. Note down:
       - **Client ID** (your Dhan login ID)
       - **Access Token**
    5. Save these in `.env` file (next to `app.py`):
       ```
       DHAN_CLIENT_ID=your_client_id
       DHAN_ACCESS_TOKEN=your_token
       ```
    6. Install the SDK: `pip install dhanhq`
    7. In Phase 2 we'll add a connection module that:
       - Replaces yfinance with Dhan's market quote API (real-time, no 15-min delay)
       - Pulls the option chain reliably (NSE direct often blocks)
       - Places **bracket orders** with SL + Target from the scanner directly
    """)

# --- Manual token entry (placeholder for future) ---
st.divider()
st.markdown("**Manual Token Entry (for testing — once Dhan is set up):**")

with st.form("dhan_credentials"):
    client_id = st.text_input("Dhan Client ID", value=st.session_state.get('dhan_client_id', ''))
    access_token = st.text_input(
        "Dhan Access Token",
        value=st.session_state.get('dhan_token', ''),
        type='password',
    )
    submitted = st.form_submit_button("Save (session only)")
    if submitted:
        st.session_state['dhan_client_id'] = client_id
        st.session_state['dhan_token'] = access_token
        st.success("Saved for this browser session. Restart clears it. For permanent storage use .env file.")

st.warning(
    "⚠️ For Phase 1 (signals only), these credentials are not used. "
    "We'll wire them up when execution is built."
)


# --- App preferences ---
st.divider()
st.subheader("🎨 App Preferences")

pref_col1, pref_col2 = st.columns(2)

with pref_col1:
    st.markdown("**Scanner Defaults**")
    default_universe = st.selectbox(
        "Default Universe",
        ["Nifty 50", "Nifty Next 50", "Nifty 100", "Bank Nifty"],
        index=0,
    )
    default_min_score = st.slider("Default Min Score", 0, 100, 50, step=5)

with pref_col2:
    st.markdown("**Cache Behavior**")
    st.write("Market data is cached for 5 minutes to avoid hitting API limits.")
    if st.button("🔄 Clear Cache Now"):
        st.cache_data.clear()
        st.success("Cache cleared. Next scan will fetch fresh data.")


# --- About ---
st.divider()
st.subheader("ℹ️ About")
st.markdown("""
**🌊 Lehar — Market की लहरों पर सवारी**

Swing trading signals + index option-selling analysis for Indian markets.

- **Phase 1 (current):** Analysis & signals (stocks swing + index option selling)
- **Phase 2 (planned):** Dhan API execution layer — place orders directly from the scanner
- **Phase 3 (future):** Backtesting engine, alert notifications (WhatsApp/email), portfolio tracking

**Tech Stack:**
- Streamlit (UI framework)
- yfinance (market data, free)
- ta library (indicators)
- Plotly (charts)
- Dhan API (Phase 2 execution)

**Data Sources:**
- Yahoo Finance (OHLCV, indices, VIX) — 15-min delayed during market hours
- NSE direct (option chain) — sometimes blocked; Dhan API more reliable

**Educational Use Only:** All signals are analytical outputs, not trading advice. Always use your own judgement and respect risk management.

Built for **Ashok Ram Sajivan Dhimar**
SPM, Bemetara S.O., Durg Division, Chhattisgarh
""")
