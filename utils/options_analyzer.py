"""
Index Options Selling Analyzer.

Core idea: For option SELLERS, trend is the enemy. Range-bound markets
with stable/falling IV are favorable. This module:
  - Detects market regime (trending vs range-bound) using ADX
  - Reads volatility status from India VIX
  - Calculates expected move using ATR and IV
  - Suggests safer strike distances based on volatility + support/resistance
  - Processes NSE option chain to compute PCR and Max Pain (when available)
"""
import pandas as pd
import numpy as np
from typing import Optional


def detect_regime(df: pd.DataFrame) -> dict:
    """Classify market regime on the last bar.

    Returns dict with:
      - regime: 'STRONG_TREND_UP', 'TREND_UP', 'RANGE', 'TREND_DOWN', 'STRONG_TREND_DOWN'
      - adx: current ADX value
      - bb_width: Bollinger width (volatility expansion indicator)
      - verdict: 'FAVORABLE' / 'CAUTION' / 'AVOID' for option selling
      - reason: short explanation
    """
    if df is None or len(df) < 50 or 'ADX' not in df.columns:
        return {'regime': 'UNKNOWN', 'verdict': 'UNKNOWN', 'reason': 'Insufficient data'}

    last = df.iloc[-1]
    adx = last['ADX'] if not pd.isna(last['ADX']) else 0
    di_plus = last['DI_pos'] if not pd.isna(last['DI_pos']) else 0
    di_minus = last['DI_neg'] if not pd.isna(last['DI_neg']) else 0
    bb_width = last['BB_width'] if not pd.isna(last['BB_width']) else 0

    # ADX-based regime classification
    if adx >= 30:
        regime = 'STRONG_TREND_UP' if di_plus > di_minus else 'STRONG_TREND_DOWN'
    elif adx >= 22:
        regime = 'TREND_UP' if di_plus > di_minus else 'TREND_DOWN'
    else:
        regime = 'RANGE'

    # Verdict for option selling
    if regime == 'RANGE' and bb_width < 0.10:
        verdict = 'FAVORABLE'
        reason = f"Range-bound market (ADX {adx:.1f}), low volatility. Good environment for selling."
    elif regime == 'RANGE':
        verdict = 'FAVORABLE'
        reason = f"Range-bound (ADX {adx:.1f}). Watch for breakouts."
    elif regime in ('TREND_UP', 'TREND_DOWN'):
        verdict = 'CAUTION'
        reason = f"Moderate trend (ADX {adx:.1f}). Sell strikes well away from price, on opposite side of trend if possible."
    else:  # STRONG TREND
        verdict = 'AVOID'
        reason = f"Strong trend (ADX {adx:.1f}). Avoid selling on the trend side - high gap/breakout risk."

    return {
        'regime': regime,
        'adx': round(adx, 1),
        'di_plus': round(di_plus, 1),
        'di_minus': round(di_minus, 1),
        'bb_width': round(bb_width * 100, 2),
        'verdict': verdict,
        'reason': reason,
    }


def expected_move(spot: float, atr: float, vix: Optional[float] = None, days: int = 7) -> dict:
    """Calculate expected price move over N days.

    Two estimates:
      - ATR-based: typical daily range * sqrt(days)
      - IV-based (if VIX available): spot * (VIX/100) * sqrt(days/365)
    """
    atr_move = atr * np.sqrt(days)

    iv_move = None
    if vix and vix > 0:
        iv_move = spot * (vix / 100) * np.sqrt(days / 365)

    # Use larger of the two as conservative estimate
    conservative = max(atr_move, iv_move) if iv_move else atr_move

    return {
        'atr_move': round(atr_move, 2),
        'iv_move': round(iv_move, 2) if iv_move else None,
        'conservative_move': round(conservative, 2),
        'upper_band': round(spot + conservative, 2),
        'lower_band': round(spot - conservative, 2),
        'days': days,
    }


def suggest_strikes(spot: float, expected: dict, regime: dict,
                    strike_step: int = 50, sr_levels: dict = None) -> dict:
    """Suggest CE (call sell) and PE (put sell) strike levels.

    Logic:
      - Base: 1 expected-move away from spot
      - Adjust based on regime: trending market -> sell further on opposite side
      - Snap to nearest valid strike (50 for Nifty, 100 for BankNifty)
      - Respect major support/resistance if available
    """
    move = expected['conservative_move']
    regime_label = regime.get('regime', 'RANGE')

    # Adjustment based on trend direction
    ce_adjust = 0  # extra distance for CE (calls) to be safer
    pe_adjust = 0  # extra distance for PE (puts) to be safer

    if regime_label in ('TREND_UP', 'STRONG_TREND_UP'):
        ce_adjust = move * 0.5  # uptrend -> sell calls further away
    elif regime_label in ('TREND_DOWN', 'STRONG_TREND_DOWN'):
        pe_adjust = move * 0.5  # downtrend -> sell puts further away

    # Raw target strikes
    ce_raw = spot + move + ce_adjust
    pe_raw = spot - move - pe_adjust

    # Snap to nearest strike
    ce_strike = round(ce_raw / strike_step) * strike_step
    pe_strike = round(pe_raw / strike_step) * strike_step

    # Ensure strikes are outside the expected range
    if ce_strike < spot + move:
        ce_strike += strike_step
    if pe_strike > spot - move:
        pe_strike -= strike_step

    # Distance from spot in percentage
    ce_pct = round((ce_strike - spot) / spot * 100, 2)
    pe_pct = round((spot - pe_strike) / spot * 100, 2)

    result = {
        'spot': round(spot, 2),
        'ce_strike': int(ce_strike),
        'pe_strike': int(pe_strike),
        'ce_distance_pct': ce_pct,
        'pe_distance_pct': pe_pct,
        'expected_upper': expected['upper_band'],
        'expected_lower': expected['lower_band'],
    }

    # Add notes about S/R proximity
    notes = []
    if sr_levels:
        for r in sr_levels.get('resistance', []):
            if ce_strike < r < ce_strike + 2 * strike_step:
                notes.append(f"CE {ce_strike} is below resistance {r} - consider {r + strike_step}+ instead")
        for s in sr_levels.get('support', []):
            if pe_strike - 2 * strike_step < s < pe_strike:
                notes.append(f"PE {pe_strike} is above support {s} - consider {s - strike_step}- instead")
    result['notes'] = notes

    return result


def parse_option_chain(chain_data: dict, expiry: str = None) -> dict:
    """Parse NSE option chain JSON into useful metrics.

    Returns dict with PCR, Max Pain, total OI, max-OI strikes, etc.
    Returns empty dict if data is malformed.
    """
    if not chain_data or 'records' not in chain_data:
        return {}

    records = chain_data['records']
    all_data = records.get('data', [])
    expiries = records.get('expiryDates', [])
    underlying = records.get('underlyingValue', 0)

    if expiry is None and expiries:
        expiry = expiries[0]  # nearest expiry

    rows = [r for r in all_data if r.get('expiryDate') == expiry]
    if not rows:
        return {}

    ce_oi_total = 0
    pe_oi_total = 0
    ce_volume_total = 0
    pe_volume_total = 0
    strikes_data = []

    for r in rows:
        strike = r.get('strikePrice', 0)
        ce = r.get('CE', {}) or {}
        pe = r.get('PE', {}) or {}

        ce_oi = ce.get('openInterest', 0)
        pe_oi = pe.get('openInterest', 0)
        ce_vol = ce.get('totalTradedVolume', 0)
        pe_vol = pe.get('totalTradedVolume', 0)

        ce_oi_total += ce_oi
        pe_oi_total += pe_oi
        ce_volume_total += ce_vol
        pe_volume_total += pe_vol

        strikes_data.append({
            'strike': strike,
            'ce_oi': ce_oi,
            'pe_oi': pe_oi,
            'ce_volume': ce_vol,
            'pe_volume': pe_vol,
            'ce_iv': ce.get('impliedVolatility', 0),
            'pe_iv': pe.get('impliedVolatility', 0),
        })

    # PCR = Put OI / Call OI
    pcr = round(pe_oi_total / ce_oi_total, 3) if ce_oi_total > 0 else 0

    # Max Pain - strike where total option-buyer pain is maximum
    max_pain_strike, max_pain_value = compute_max_pain(strikes_data)

    # Top OI strikes (resistance/support from options)
    by_ce_oi = sorted(strikes_data, key=lambda x: x['ce_oi'], reverse=True)[:3]
    by_pe_oi = sorted(strikes_data, key=lambda x: x['pe_oi'], reverse=True)[:3]

    return {
        'expiry': expiry,
        'underlying': underlying,
        'pcr': pcr,
        'total_ce_oi': ce_oi_total,
        'total_pe_oi': pe_oi_total,
        'max_pain': max_pain_strike,
        'top_ce_oi_strikes': [s['strike'] for s in by_ce_oi],
        'top_pe_oi_strikes': [s['strike'] for s in by_pe_oi],
        'strikes_data': strikes_data,
    }


def compute_max_pain(strikes_data: list) -> tuple:
    """Compute Max Pain strike - where option writers' payout is minimum
    (equivalent to option buyers' loss being maximum)."""
    if not strikes_data:
        return 0, 0

    strikes = sorted([s['strike'] for s in strikes_data])
    pain_by_strike = {}

    for expiry_strike in strikes:
        total_pain = 0
        for s in strikes_data:
            # CE pain: if expiry above strike, CE buyer loses (writer gains payout = max(expiry - strike, 0) * OI for each strike's CE OI; flip to writer perspective)
            ce_intrinsic = max(expiry_strike - s['strike'], 0) * s['ce_oi']
            pe_intrinsic = max(s['strike'] - expiry_strike, 0) * s['pe_oi']
            total_pain += ce_intrinsic + pe_intrinsic
        pain_by_strike[expiry_strike] = total_pain

    max_pain = min(pain_by_strike, key=pain_by_strike.get)
    return max_pain, pain_by_strike[max_pain]


def interpret_pcr(pcr: float) -> str:
    """Quick text interpretation of PCR for the dashboard."""
    if pcr == 0:
        return "N/A"
    if pcr > 1.3:
        return "🟢 Bullish (excess put writing)"
    if pcr > 0.9:
        return "🟡 Neutral"
    if pcr > 0.6:
        return "🟠 Slightly bearish"
    return "🔴 Bearish (excess call writing)"
