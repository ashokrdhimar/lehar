# 🌊 Lehar
### *Market की लहरों पर सवारी*

Swing trading signals + index option-selling analysis for Indian markets (NSE/BSE).

**Phase 1:** Signals only (analysis & alerts)
**Phase 2 (planned):** Dhan API execution

---

## 🎯 क्या-क्या मिलता है (Features)

### 1. Stock Swing Scanner (`pages/1_📈_Stock_Scanner.py`)
- Nifty 50 / Next 50 / 100 / Bank Nifty को scan करता है
- Daily और Weekly दोनों timeframes
- 7 setups detect करता है (Pullback, Breakout, MA Cross, RSI Reversal — both bullish/bearish)
- हर signal के साथ: Entry, Stop Loss, Target 1, Target 2, Risk:Reward, Strength Score (0–100)
- Click करके detailed chart with EMAs, Volume, RSI

### 2. Options Selling Dashboard (`pages/2_📊_Options_Dashboard.py`)
- Nifty / Bank Nifty / Fin Nifty
- Market regime detection (Trending vs Range-bound) ADX के through
- India VIX status
- Expected move calculation (ATR + IV based)
- **CE और PE sell करने के लिए suggested strikes** with safe distance
- Support/Resistance levels
- Option chain analysis (PCR, Max Pain, OI distribution) — NSE से fetch
- Visual chart with all levels marked

### 3. Settings (`pages/3_⚙️_Settings.py`)
- Dhan API setup instructions (Phase 2 के लिए)
- Cache control
- App preferences

---

## 🛠️ Local Setup (PC पर — Windows/Mac/Linux)

### Step 1: Python install करें
- Download from https://www.python.org/downloads/ (version 3.10 या ऊपर)
- Installation में **"Add Python to PATH"** का checkbox ज़रूर tick करें (Windows)

### Step 2: Code को एक folder में रखें
```
lehar/
├── app.py
├── requirements.txt
├── README.md
├── .streamlit/
├── pages/
└── utils/
```

### Step 3: Terminal/Command Prompt खोलें और इस folder में जाएँ
```bash
cd path/to/lehar
```

### Step 4: Dependencies install करें
```bash
pip install -r requirements.txt
```
(2–3 minutes लगेंगे, ~150 MB download होगा)

### Step 5: App चलाएँ
```bash
streamlit run app.py
```

Browser में अपने आप http://localhost:8501 खुलेगा। 🎉

---

## ☁️ Cloud Deploy — GitHub + Streamlit Cloud (Free, Mobile-friendly)

### Step 1: GitHub account बनाएँ
- https://github.com/signup → email से free account बनाएँ

### Step 2: नया Repository बनाएँ
- Top-right **"+" → New repository**
- Name: `lehar` (URL में आएगा यह)
- **Public** select करें (Streamlit Cloud free tier के लिए ज़रूरी)
- **Add a README** tick करें → **Create**

### Step 3: Code upload करें
- नए repo में **"Add file → Upload files"** click करें
- ZIP extract करके **सारे files** drag-and-drop करें (folder नहीं — directly contents: `app.py`, `requirements.txt`, `pages/`, `utils/`, `.streamlit/`)
- नीचे **Commit changes** click करें

### Step 4: Streamlit Cloud पर deploy करें
- https://share.streamlit.io पर जाएँ
- **Sign in with GitHub**
- **New app** click करें
- Repository: `<your-username>/lehar`, Branch: `main`, Main file path: `app.py`
- **Deploy!**

2–3 minutes में URL मिल जाएगा (कुछ ऐसा: `https://lehar-<random>.streamlit.app`)

### Step 5: Mobile पर install करें (PWA-style)
- अपने Android phone में Chrome से वह URL खोलें
- ⋮ (3-dot menu) → **Add to Home screen**
- Home screen पर 🌊 Lehar का icon आ जाएगा — PLI Manager जैसे ही app की तरह।

### बाद में code update करना हो तो:
- GitHub पर file पर click → ✏️ (pencil/edit icon) → changes save → **Commit changes**
- Streamlit app अपने आप redeploy हो जाएगी (1–2 minutes)

---

## 🔌 Phase 2: Dhan API Integration (बाद में)

Phase 1 stable होने के बाद Phase 2 में हम जोड़ेंगे:

1. **Real-time data** (15-min delay हटेगा)
2. **Option chain Dhan से** — NSE block करने की समस्या ख़त्म
3. **Order execution** — scanner से directly bracket order with SL + Target
4. **Position tracking** — open positions, P&L, exit alerts

Dhan API setup के steps Settings page में detail से दिए हैं।

---

## ⚙️ Stock List update करना

जब NSE Nifty 50 / Next 50 की composition बदले (साल में 2 बार होता है), edit करें:

`utils/stock_universe.py` → `NIFTY_50` और `NIFTY_NEXT_50` list।

Symbol format: सिर्फ NSE का base symbol (जैसे `RELIANCE`, `TCS`), `.NS` अपने आप जुड़ जाएगा।

---

## ❓ Common Issues

**"Module not found" error:**
`pip install -r requirements.txt` फिर से चलाएँ। अगर अलग-अलग Python versions हैं तो `pip3` try करें।

**"Could not fetch data" — Stock Scanner:**
- Internet check करें
- Market hours में Yahoo Finance कभी-कभी throttle करता है — 1-2 minute बाद retry करें
- Settings page से Cache clear करें

**Option chain नहीं आ रहा:**
- NSE अक्सर direct API call block करता है (anti-bot)
- Phase 2 में Dhan API से reliably मिल जाएगा
- तब तक regime, expected move, और suggested strikes काम करते रहेंगे — option chain optional है

**Streamlit Cloud पर deploy fail:**
- `requirements.txt` ठीक से upload हुई है क्या check करें
- App logs में exact error देखें (Cloud dashboard में)

---

## 📊 Setup Definitions (Strategy Reference)

### Bullish (LONG) Setups
| Setup | Trigger Conditions |
|---|---|
| **Pullback to EMA20** | Price > EMA50, EMA20 > EMA50, Price within 2.5% of EMA20, RSI 40–62, MACD turning up |
| **Breakout (Volume)** | Close > prev 20-day high, Volume > 1.5× avg, Price > EMA50, RSI > 55 |
| **EMA 20/50 Cross** | EMA20 freshly crosses above EMA50, Price > EMA20 |
| **RSI Reversal** | RSI bouncing from <35 into 35–50 zone, MACD turning up |

### Bearish (SHORT) Setups — mirror logic
| Setup | Trigger Conditions |
|---|---|
| **Pullback to EMA20** | Price < EMA50, EMA20 < EMA50, Price within 2.5% of EMA20, RSI 38–58, MACD turning down |
| **Breakdown (Volume)** | Close < prev 20-day low, Volume > 1.5× avg, Price < EMA50, RSI < 45 |
| **EMA 20/50 Cross** | EMA20 freshly crosses below EMA50, Price < EMA20 |

### Strength Score (0–100)
| Component | Weight | Logic |
|---|---|---|
| Trend Strength (ADX) | 30 | Higher ADX = stronger trend = better |
| Momentum (RSI + MACD) | 25 | Direction-appropriate momentum |
| Volume Confirmation | 20 | Volume × 20-day average |
| MA Alignment | 15 | Clean stacking of Price/EMA20/EMA50 |
| Bollinger Position | 10 | Avoid extremes; mid-range is healthy |

### Trade Levels (Auto-calculated)
- **Stop Loss** = Entry ± 1.5 × ATR
- **Target 1** = Entry ± 2 × ATR (1.33 R:R)
- **Target 2** = Entry ± 3.5 × ATR (2.33 R:R)

---

## 📜 Disclaimer

यह educational analysis tool है, investment advice नहीं। सभी trading decisions और risk management आपके हैं। Past performance future returns की guarantee नहीं देता। Markets unpredictable हैं।

---

**🌊 Lehar** · Built for **Ashok Ram Sajivan Dhimar**
SPM, Bemetara S.O., Durg Division, Chhattisgarh
Phase 1 (Signals)
