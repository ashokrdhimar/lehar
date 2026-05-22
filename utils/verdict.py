"""
Verdict generator — combines technical signal + fundamentals into a
plain-Hindi verdict with clear "what to do next" guidance.

Philosophy: English technical terms (trend, support, RSI, PE) are kept
as-is, but the reasoning and advice flow in simple Hindi so the user
immediately understands the action to take.

This is rule-based (not AI). Output is educational, never financial advice.
"""


def _technical_summary(signal: dict, sr: dict) -> str:
    """Hindi explanation of the technical picture."""
    if not signal:
        return "अभी कोई clear technical setup नहीं है — stock sideways या undecided है।"

    direction = signal["direction"]
    setup = signal["setup"]
    rsi = signal.get("rsi", 0)
    adx = signal.get("adx", 0)

    parts = []

    if direction == "LONG":
        parts.append(f"Stock एक <b>bullish setup</b> ({setup}) में है — मतलब ऊपर जाने के संकेत हैं।")
    else:
        parts.append(f"Stock एक <b>bearish setup</b> ({setup}) में है — मतलब नीचे जाने के संकेत हैं।")

    # ADX (trend strength)
    if adx >= 28:
        parts.append(f"ADX {adx} है — trend <b>मज़बूत</b> है, यानी move टिकने की संभावना ज़्यादा।")
    elif adx >= 20:
        parts.append(f"ADX {adx} है — trend ठीक-ठाक है।")
    else:
        parts.append(f"ADX {adx} है — trend अभी <b>कमज़ोर</b> है, सावधानी रखें।")

    # RSI
    if rsi > 70:
        parts.append(f"RSI {rsi} — stock overbought है (बहुत तेज़ चढ़ चुका, थोड़ा रुक सकता है)।")
    elif rsi < 30:
        parts.append(f"RSI {rsi} — stock oversold है (बहुत गिर चुका, bounce आ सकता है)।")
    else:
        parts.append(f"RSI {rsi} — healthy zone में है।")

    if sr.get("support"):
        parts.append(f"नज़दीकी support: ₹{sr['support'][0]:,.0f}।")
    if sr.get("resistance"):
        parts.append(f"नज़दीकी resistance: ₹{sr['resistance'][0]:,.0f}।")

    return " ".join(parts)


def _fundamental_summary(fund: dict) -> tuple:
    """Hindi explanation + a fundamental health score (0-100)."""
    if not fund:
        return ("Fundamental data उपलब्ध नहीं है।", 50)

    parts = []
    score = 50  # neutral baseline

    pe = fund.get("pe")
    roe = fund.get("roe")
    de = fund.get("debt_to_equity")
    margin = fund.get("profit_margin")
    growth = fund.get("earnings_growth")

    # Valuation (PE)
    if pe:
        if pe < 15:
            parts.append(f"PE {pe:.1f} — stock <b>सस्ता</b> दिख रहा है (valuation आकर्षक)।")
            score += 12
        elif pe < 30:
            parts.append(f"PE {pe:.1f} — valuation <b>उचित</b> है।")
            score += 5
        elif pe < 50:
            parts.append(f"PE {pe:.1f} — stock थोड़ा <b>महंगा</b> है।")
            score -= 5
        else:
            parts.append(f"PE {pe:.1f} — stock <b>बहुत महंगा</b> है, सावधानी।")
            score -= 12

    # Profitability (ROE)
    if roe is not None:
        if roe > 20:
            parts.append(f"ROE {roe:.0f}% — company <b>बहुत अच्छा</b> return दे रही है।")
            score += 12
        elif roe > 12:
            parts.append(f"ROE {roe:.0f}% — return ठीक है।")
            score += 6
        elif roe > 0:
            parts.append(f"ROE {roe:.0f}% — return कमज़ोर है।")
            score -= 5
        else:
            parts.append(f"ROE {roe:.0f}% — company घाटे में या कमज़ोर।")
            score -= 12

    # Debt
    if de is not None:
        de_ratio = de / 100 if de > 5 else de  # yfinance sometimes gives % form
        if de_ratio < 0.5:
            parts.append(f"Debt कम है (D/E {de_ratio:.2f}) — <b>safe</b>।")
            score += 8
        elif de_ratio < 1:
            parts.append(f"Debt moderate है (D/E {de_ratio:.2f})।")
        else:
            parts.append(f"Debt <b>ज़्यादा</b> है (D/E {de_ratio:.2f}) — risk बढ़ता है।")
            score -= 8

    # Growth
    if growth is not None:
        if growth > 15:
            parts.append(f"Earnings {growth:.0f}% बढ़ी हैं — <b>तेज़ growth</b>।")
            score += 8
        elif growth > 0:
            parts.append(f"Earnings {growth:.0f}% बढ़ी हैं।")
            score += 3
        else:
            parts.append(f"Earnings {growth:.0f}% — growth नहीं/गिरावट।")
            score -= 6

    if not parts:
        return ("Fundamental data सीमित है।", 50)

    return (" ".join(parts), max(0, min(100, score)))


def generate_verdict(signal: dict, fund: dict, sr: dict) -> dict:
    """Combine technical + fundamental into an overall verdict.

    Returns dict with:
      - rating: 'STRONG_BUY' / 'BUY' / 'WATCH' / 'AVOID' / 'SHORT_SETUP'
      - rating_hi: Hindi label
      - tech_text, fund_text: Hindi explanations
      - action_text: what to do next (Hindi)
      - tech_score, fund_score
    """
    tech_text = _technical_summary(signal, sr)
    fund_text, fund_score = _fundamental_summary(fund)

    tech_score = signal["score"] if signal else 0
    direction = signal["direction"] if signal else None

    # Combined logic
    if direction == "SHORT":
        rating = "SHORT_SETUP"
        rating_hi = "🔴 Bearish / गिरावट का setup"
        action = (
            "यह एक <b>short / बिकवाली</b> का setup है। अगर आप short trade करते हैं तो "
            f"Entry ₹{signal['entry']:,.2f}, Stop Loss ₹{signal['stop_loss']:,.2f}, "
            f"Target ₹{signal['target1']:,.2f} रख सकते हैं। "
            "अगर short नहीं करते — तो इस stock से <b>अभी दूर रहें</b>, खरीदने का समय नहीं है।"
        )
    elif direction == "LONG":
        combined = (tech_score * 0.6) + (fund_score * 0.4)
        if combined >= 70 and fund_score >= 55:
            rating = "STRONG_BUY"
            rating_hi = "🟢🟢 मज़बूत मौका (Strong)"
            action = (
                "Technical और fundamental <b>दोनों मज़बूत</b> हैं — यह अच्छा swing मौका है। "
                f"Entry ₹{signal['entry']:,.2f} के आसपास, Stop Loss ₹{signal['stop_loss']:,.2f} "
                f"(इससे नीचे गया तो निकल जाएँ), Target 1 ₹{signal['target1']:,.2f}, "
                f"Target 2 ₹{signal['target2']:,.2f}। "
                "Position size ऐसा रखें कि SL hit हो तो capital का सिर्फ 1-2% जाए।"
            )
        elif combined >= 55:
            rating = "BUY"
            rating_hi = "🟢 खरीदने लायक (Buy)"
            action = (
                "अच्छा setup है पर थोड़ा confirmation का इंतज़ार कर सकते हैं। "
                f"अगर entry लें तो ₹{signal['entry']:,.2f} पर, Stop Loss ₹{signal['stop_loss']:,.2f}, "
                f"Target ₹{signal['target1']:,.2f}। छोटी position से शुरू करें।"
            )
        else:
            rating = "WATCH"
            rating_hi = "🟡 नज़र रखें (Watch)"
            action = (
                "Technical setup तो है पर overall picture mixed है "
                "(या तो trend कमज़ोर है या fundamentals उतने अच्छे नहीं)। "
                "<b>अभी जल्दबाज़ी न करें</b> — watchlist में डालें और एक-दो दिन देखें कि "
                f"₹{signal['entry']:,.2f} के ऊपर टिकता है या नहीं।"
            )
    else:
        rating = "AVOID"
        rating_hi = "⚪ कोई setup नहीं (Wait)"
        action = (
            "अभी इस stock में कोई clear trading setup नहीं है। "
            "<b>इंतज़ार करें</b> — जब तक saaf trend या breakout न दिखे, पैसा न लगाएँ। "
            "Watchlist में रखकर scanner से नज़र रखें।"
        )

    return {
        "rating": rating,
        "rating_hi": rating_hi,
        "tech_text": tech_text,
        "fund_text": fund_text,
        "action_text": action,
        "tech_score": tech_score,
        "fund_score": fund_score,
    }
