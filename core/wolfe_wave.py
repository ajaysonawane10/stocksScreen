"""
Wolfe Wave Detection Engine
Identifies bullish and bearish Wolfe Wave patterns on NSE stocks.

Wolfe Wave Rules (Bullish):
  Point 1: A significant low
  Point 2: A significant high after Point 1
  Point 3: A new low, lower than Point 1
  Point 4: A rally high, stays between Point 1 and Point 2
  Point 5: A final decline that touches or slightly overshoots the 1-3 trendline ("sweet zone")
  Target (EPA): Line from Point 1 through Point 4, projected to the vertical time of Point 5

Wolfe Wave Rules (Bearish):
  Point 1: A significant high
  Point 2: A significant low after Point 1
  Point 3: A new high, higher than Point 1
  Point 4: A decline low, stays between Point 1 and Point 2
  Point 5: A final rally that touches or slightly overshoots the 1-3 trendline ("sweet zone")
  Target (EPA): Line from Point 1 through Point 4, projected to the vertical time of Point 5
"""

import bisect
import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view
from core.indicators import (
    calculate_rsi, calculate_macd, calculate_fibonacci_levels,
    volume_analysis, detect_rsi_divergence, detect_macd_crossover,
    is_above_key_emas, calculate_atr
)


def find_swing_points(high: pd.Series, low: pd.Series, close: pd.Series, order: int = 5):
    """
    Find swing highs and swing lows using vectorized NumPy comparisons.
    order: number of bars on each side to confirm a swing point.
    Returns list of (index, price, type) tuples.
    """
    h = high.values
    l = low.values
    n = len(h)

    if n < 2 * order + 1:
        return []

    win = 2 * order + 1

    # sliding_window_view gives shape (n - win + 1, win)
    h_windows = sliding_window_view(h, win)
    l_windows = sliding_window_view(l, win)

    center = order  # the center column is the candidate bar
    h_center = h_windows[:, center]
    l_center = l_windows[:, center]

    h_max = h_windows.max(axis=1)
    l_min = l_windows.min(axis=1)

    # Strict inequality: center must be strictly the max/min of its window
    is_swing_high = h_center == h_max
    is_swing_low = l_center == l_min

    # Map window index back to original series index (offset by `order`)
    swings = []
    offsets = np.where(is_swing_high)[0]
    for w_idx in offsets:
        orig_idx = w_idx + order
        swings.append((orig_idx, float(h[orig_idx]), 'high'))

    offsets = np.where(is_swing_low)[0]
    for w_idx in offsets:
        orig_idx = w_idx + order
        swings.append((orig_idx, float(l[orig_idx]), 'low'))

    swings.sort(key=lambda x: x[0])
    return swings


def line_value_at(x1, y1, x2, y2, x_target):
    """Calculate Y value on a line defined by two points at a given X."""
    if x2 == x1:
        return y1
    slope = (y2 - y1) / (x2 - x1)
    return y1 + slope * (x_target - x1)


def line_slope(x1, y1, x2, y2):
    """Calculate slope of line between two points."""
    if x2 == x1:
        return 0
    return (y2 - y1) / (x2 - x1)


def detect_bullish_wolfe(df: pd.DataFrame, max_lookback: int = 150,
                         precomputed: dict = None):
    """
    Detect bullish Wolfe Wave patterns.

    Bullish pattern (buy at point 5):
      P1 (low) -> P2 (high) -> P3 (low < P1) -> P4 (high, P1 < P4 < P2) -> P5 (low, near 1-3 line)

    The 1-3 and 2-4 lines should converge (forming a falling wedge).
    Point 5 is the entry — it should be at or slightly below the 1-3 trendline.
    Target is the 1-4 line extended to the time of P5.

    precomputed: dict with pre-computed indicators (rsi, macd_hist, vol_avg20, vol_series)
                 to avoid redundant calculation inside scoring.

    Returns list of detected patterns with scores.
    """
    if len(df) < max_lookback:
        return []

    recent = df.iloc[-max_lookback:].copy().reset_index(drop=True)
    high = recent['High']
    low = recent['Low']
    close = recent['Close']
    n = len(recent)

    patterns = []

    for swing_order in [3, 5, 7]:
        swings = find_swing_points(high, low, close, order=swing_order)

        if len(swings) < 5:
            continue

        swing_lows  = [(idx, price) for idx, price, typ in swings if typ == 'low']
        swing_highs = [(idx, price) for idx, price, typ in swings if typ == 'high']

        # Pre-extract index arrays for bisect-based search
        low_indices  = [s[0] for s in swing_lows]
        high_indices = [s[0] for s in swing_highs]

        current_price = float(close.iloc[-1])

        for i_p1, p1 in enumerate(swing_lows):
            # P2: first high strictly after P1
            p2_start = bisect.bisect_right(high_indices, p1[0])
            for i_p2 in range(p2_start, len(swing_highs)):
                p2 = swing_highs[i_p2]

                # P3: first low strictly after P2, must be lower than P1
                p3_start = bisect.bisect_right(low_indices, p2[0])
                for i_p3 in range(p3_start, len(swing_lows)):
                    p3 = swing_lows[i_p3]
                    if p3[1] >= p1[1]:          # RULE: P3 < P1
                        continue

                    # P4: first high strictly after P3
                    p4_start = bisect.bisect_right(high_indices, p3[0])
                    for i_p4 in range(p4_start, len(swing_highs)):
                        p4 = swing_highs[i_p4]
                        if p4[1] >= p2[1]:          # P4 must be below P2
                            continue
                        if p4[1] < p1[1] * 0.97:   # P4 should be near/above P1
                            continue

                        # P5: first low strictly after P4
                        p5_start = bisect.bisect_right(low_indices, p4[0])
                        for i_p5 in range(p5_start, len(swing_lows)):
                            p5 = swing_lows[i_p5]

                            # P5 must be recent (within last 25 bars)
                            bars_since_p5 = n - 1 - p5[0]
                            if bars_since_p5 > 25:
                                continue

                            # --- Sweet Zone Check ---
                            line_13_at_p5 = line_value_at(p1[0], p1[1], p3[0], p3[1], p5[0])
                            p5_deviation = (p5[1] - line_13_at_p5) / line_13_at_p5 * 100
                            if p5_deviation > 3.0:   # Too far above
                                continue
                            if p5_deviation < -8.0:  # Excessive overshoot
                                continue

                            # --- Convergence Check ---
                            slope_13 = line_slope(p1[0], p1[1], p3[0], p3[1])
                            slope_24 = line_slope(p2[0], p2[1], p4[0], p4[1])
                            if slope_24 >= slope_13:  # Lines diverging — not Wolfe
                                continue

                            # RULE: P5 should be at or below P3 level
                            if p5[1] > p3[1] * 1.02:
                                continue

                            # --- EPA (Estimated Price at Arrival) ---
                            epa = line_value_at(p1[0], p1[1], p4[0], p4[1], p5[0])
                            if epa <= p5[1] * 1.03:   # EPA not profitable
                                continue
                            if current_price >= epa * 0.95:  # Target already reached
                                continue

                            score = _score_bullish_wolfe(
                                p1, p2, p3, p4, p5, epa,
                                line_13_at_p5, p5_deviation,
                                slope_13, slope_24,
                                bars_since_p5, current_price,
                                precomputed
                            )

                            patterns.append({
                                'type': 'Bullish',
                                'p1': {'idx': p1[0], 'price': p1[1]},
                                'p2': {'idx': p2[0], 'price': p2[1]},
                                'p3': {'idx': p3[0], 'price': p3[1]},
                                'p4': {'idx': p4[0], 'price': p4[1]},
                                'p5': {'idx': p5[0], 'price': p5[1]},
                                'epa': epa,
                                'line_13_at_p5': line_13_at_p5,
                                'p5_deviation': p5_deviation,
                                'convergence': slope_13 - slope_24,
                                'score': score,
                                'bars_since_p5': bars_since_p5,
                                'current_price': current_price,
                                'swing_order': swing_order,
                            })

    patterns = _deduplicate_patterns(patterns)
    return patterns


def detect_bearish_wolfe(df: pd.DataFrame, max_lookback: int = 150,
                         precomputed: dict = None):
    """
    Detect bearish Wolfe Wave patterns.

    Bearish pattern (sell at point 5):
      P1 (high) -> P2 (low) -> P3 (high > P1) -> P4 (low, P1 > P4 > P2) -> P5 (high, near 1-3 line)

    The 1-3 and 2-4 lines should converge (forming a rising wedge).
    Point 5 is the entry — it should be at or slightly above the 1-3 trendline.
    Target is the 1-4 line extended to the time of P5.
    """
    if len(df) < max_lookback:
        return []

    recent = df.iloc[-max_lookback:].copy().reset_index(drop=True)
    high = recent['High']
    low = recent['Low']
    close = recent['Close']
    n = len(recent)

    patterns = []

    for swing_order in [3, 5, 7]:
        swings = find_swing_points(high, low, close, order=swing_order)

        if len(swings) < 5:
            continue

        swing_lows  = [(idx, price) for idx, price, typ in swings if typ == 'low']
        swing_highs = [(idx, price) for idx, price, typ in swings if typ == 'high']

        low_indices  = [s[0] for s in swing_lows]
        high_indices = [s[0] for s in swing_highs]

        current_price = float(close.iloc[-1])

        for i_p1, p1 in enumerate(swing_highs):
            # P2: first low strictly after P1
            p2_start = bisect.bisect_right(low_indices, p1[0])
            for i_p2 in range(p2_start, len(swing_lows)):
                p2 = swing_lows[i_p2]

                # P3: first high strictly after P2, must be higher than P1
                p3_start = bisect.bisect_right(high_indices, p2[0])
                for i_p3 in range(p3_start, len(swing_highs)):
                    p3 = swing_highs[i_p3]
                    if p3[1] <= p1[1]:           # RULE: P3 > P1
                        continue

                    # P4: first low strictly after P3
                    p4_start = bisect.bisect_right(low_indices, p3[0])
                    for i_p4 in range(p4_start, len(swing_lows)):
                        p4 = swing_lows[i_p4]
                        if p4[1] <= p2[1]:           # P4 must be above P2
                            continue
                        if p4[1] > p1[1] * 1.03:    # P4 must stay below P1
                            continue

                        # P5: first high strictly after P4
                        p5_start = bisect.bisect_right(high_indices, p4[0])
                        for i_p5 in range(p5_start, len(swing_highs)):
                            p5 = swing_highs[i_p5]

                            bars_since_p5 = n - 1 - p5[0]
                            if bars_since_p5 > 25:
                                continue

                            # --- Sweet Zone Check ---
                            line_13_at_p5 = line_value_at(p1[0], p1[1], p3[0], p3[1], p5[0])
                            p5_deviation = (p5[1] - line_13_at_p5) / line_13_at_p5 * 100
                            if p5_deviation < -3.0:   # Too far below line
                                continue
                            if p5_deviation > 8.0:    # Excessive overshoot
                                continue

                            # --- Convergence Check ---
                            slope_13 = line_slope(p1[0], p1[1], p3[0], p3[1])
                            slope_24 = line_slope(p2[0], p2[1], p4[0], p4[1])
                            if slope_24 <= slope_13:  # Lines diverging
                                continue

                            # P5 should be at or above P3 level
                            if p5[1] < p3[1] * 0.98:
                                continue

                            # --- EPA Target ---
                            epa = line_value_at(p1[0], p1[1], p4[0], p4[1], p5[0])
                            if epa >= p5[1] * 0.97:    # EPA not profitable
                                continue
                            if current_price <= epa * 1.05:  # Target already reached
                                continue

                            score = _score_bearish_wolfe(
                                p1, p2, p3, p4, p5, epa,
                                line_13_at_p5, p5_deviation,
                                slope_13, slope_24,
                                bars_since_p5, current_price,
                                precomputed
                            )

                            patterns.append({
                                'type': 'Bearish',
                                'p1': {'idx': p1[0], 'price': p1[1]},
                                'p2': {'idx': p2[0], 'price': p2[1]},
                                'p3': {'idx': p3[0], 'price': p3[1]},
                                'p4': {'idx': p4[0], 'price': p4[1]},
                                'p5': {'idx': p5[0], 'price': p5[1]},
                                'epa': epa,
                                'line_13_at_p5': line_13_at_p5,
                                'p5_deviation': p5_deviation,
                                'convergence': slope_24 - slope_13,
                                'score': score,
                                'bars_since_p5': bars_since_p5,
                                'current_price': current_price,
                                'swing_order': swing_order,
                            })

    patterns = _deduplicate_patterns(patterns)
    return patterns


def _score_bullish_wolfe(p1, p2, p3, p4, p5, epa,
                          line_13_at_p5, p5_deviation,
                          slope_13, slope_24,
                          bars_since_p5, current_price,
                          precomputed):
    """
    Score a bullish Wolfe Wave pattern (0-100).
    Uses pre-computed indicators from `precomputed` dict to avoid redundant calculation.
    """
    score = 0

    # --- Pattern Geometry (40 points max) ---

    # Sweet zone precision: P5 close to 1-3 line (15 points)
    abs_dev = abs(p5_deviation)
    if abs_dev <= 1.0:
        score += 15
    elif abs_dev <= 2.0:
        score += 12
    elif abs_dev <= 3.0:
        score += 8
    elif abs_dev <= 5.0:
        score += 5
    else:
        score += 2

    # Convergence quality (10 points)
    convergence = slope_13 - slope_24
    if convergence > 0.5:
        score += 10
    elif convergence > 0.2:
        score += 7
    elif convergence > 0.05:
        score += 4
    else:
        score += 2

    # Symmetry: time between waves should be roughly proportional (10 points)
    wave12_bars = p2[0] - p1[0]
    wave23_bars = p3[0] - p2[0]
    wave34_bars = p4[0] - p3[0]
    wave45_bars = p5[0] - p4[0]

    if wave12_bars > 0 and wave34_bars > 0:
        time_ratio_1 = wave23_bars / wave12_bars
        time_ratio_2 = wave45_bars / wave34_bars
        if 0.5 <= time_ratio_1 <= 2.0 and 0.5 <= time_ratio_2 <= 2.0:
            score += 10
        elif 0.3 <= time_ratio_1 <= 3.0 and 0.3 <= time_ratio_2 <= 3.0:
            score += 6
        else:
            score += 2

    # EPA quality: target should be meaningful (5 points)
    potential_pct = (epa - p5[1]) / p5[1] * 100
    if potential_pct >= 15:
        score += 5
    elif potential_pct >= 10:
        score += 4
    elif potential_pct >= 5:
        score += 3
    else:
        score += 1

    # --- Recency (15 points max) ---
    if bars_since_p5 <= 3:
        score += 15
    elif bars_since_p5 <= 7:
        score += 12
    elif bars_since_p5 <= 12:
        score += 8
    elif bars_since_p5 <= 20:
        score += 5
    else:
        score += 2

    # --- Price action confirmation (15 points max) ---
    if current_price > p5[1]:
        bounce_pct = (current_price - p5[1]) / p5[1] * 100
        if 0 < bounce_pct <= 3:
            score += 15
        elif 3 < bounce_pct <= 6:
            score += 12
        elif 6 < bounce_pct <= 10:
            score += 8
        else:
            score += 4
    else:
        score += 2

    # --- Volume/Momentum (15 points max) — use pre-computed values ---
    if precomputed:
        current_rsi = precomputed.get('current_rsi', 50)
        vol_avg = precomputed.get('vol_avg20', 0)
        vol_series = precomputed.get('volume')
        macd_hist = precomputed.get('macd_hist')
    else:
        current_rsi = 50
        vol_avg = 0
        vol_series = None
        macd_hist = None

    # RSI scoring
    if 30 <= current_rsi <= 50:
        score += 5
    elif 50 < current_rsi <= 60:
        score += 4
    elif current_rsi < 30:
        score += 3
    else:
        score += 1

    # Volume declining into P5 (classic for Wolfe completion)
    if vol_series is not None and len(vol_series) >= 10 and vol_avg > 0:
        p5_idx = p5[0]
        vol_at_p5 = vol_series.iloc[max(0, p5_idx - 2):p5_idx + 3].mean() if p5_idx < len(vol_series) else 0
        if vol_at_p5 < vol_avg * 0.8:
            score += 5
        elif vol_at_p5 < vol_avg:
            score += 3
        else:
            score += 1

    # MACD momentum
    if macd_hist is not None and len(macd_hist) >= 2:
        if macd_hist.iloc[-1] > macd_hist.iloc[-2]:
            score += 5
        elif len(macd_hist) >= 3 and macd_hist.iloc[-1] > macd_hist.iloc[-3]:
            score += 3
        else:
            score += 1

    return min(100, score)


def _score_bearish_wolfe(p1, p2, p3, p4, p5, epa,
                          line_13_at_p5, p5_deviation,
                          slope_13, slope_24,
                          bars_since_p5, current_price,
                          precomputed):
    """
    Score a bearish Wolfe Wave pattern (0-100).
    Uses pre-computed indicators from `precomputed` dict to avoid redundant calculation.
    """
    score = 0

    # --- Pattern Geometry (40 points max) ---
    abs_dev = abs(p5_deviation)
    if abs_dev <= 1.0:
        score += 15
    elif abs_dev <= 2.0:
        score += 12
    elif abs_dev <= 3.0:
        score += 8
    elif abs_dev <= 5.0:
        score += 5
    else:
        score += 2

    convergence = slope_24 - slope_13
    if convergence > 0.5:
        score += 10
    elif convergence > 0.2:
        score += 7
    elif convergence > 0.05:
        score += 4
    else:
        score += 2

    wave12_bars = p2[0] - p1[0]
    wave23_bars = p3[0] - p2[0]
    wave34_bars = p4[0] - p3[0]
    wave45_bars = p5[0] - p4[0]

    if wave12_bars > 0 and wave34_bars > 0:
        time_ratio_1 = wave23_bars / wave12_bars
        time_ratio_2 = wave45_bars / wave34_bars
        if 0.5 <= time_ratio_1 <= 2.0 and 0.5 <= time_ratio_2 <= 2.0:
            score += 10
        elif 0.3 <= time_ratio_1 <= 3.0 and 0.3 <= time_ratio_2 <= 3.0:
            score += 6
        else:
            score += 2

    potential_pct = (p5[1] - epa) / p5[1] * 100
    if potential_pct >= 15:
        score += 5
    elif potential_pct >= 10:
        score += 4
    elif potential_pct >= 5:
        score += 3
    else:
        score += 1

    # --- Recency (15 points) ---
    if bars_since_p5 <= 3:
        score += 15
    elif bars_since_p5 <= 7:
        score += 12
    elif bars_since_p5 <= 12:
        score += 8
    elif bars_since_p5 <= 20:
        score += 5
    else:
        score += 2

    # --- Price action (15 points) ---
    if current_price < p5[1]:
        drop_pct = (p5[1] - current_price) / p5[1] * 100
        if 0 < drop_pct <= 3:
            score += 15
        elif 3 < drop_pct <= 6:
            score += 12
        elif 6 < drop_pct <= 10:
            score += 8
        else:
            score += 4
    else:
        score += 2

    # --- Volume/Momentum (15 points) — use pre-computed values ---
    if precomputed:
        current_rsi = precomputed.get('current_rsi', 50)
        vol_avg = precomputed.get('vol_avg20', 0)
        vol_series = precomputed.get('volume')
        macd_hist = precomputed.get('macd_hist')
    else:
        current_rsi = 50
        vol_avg = 0
        vol_series = None
        macd_hist = None

    # RSI scoring
    if 60 <= current_rsi <= 80:
        score += 5
    elif 50 < current_rsi < 60:
        score += 4
    elif current_rsi > 80:
        score += 3
    else:
        score += 1

    # Volume declining into P5
    if vol_series is not None and len(vol_series) >= 10 and vol_avg > 0:
        p5_idx = p5[0]
        vol_at_p5 = vol_series.iloc[max(0, p5_idx - 2):p5_idx + 3].mean() if p5_idx < len(vol_series) else 0
        if vol_at_p5 < vol_avg * 0.8:
            score += 5
        elif vol_at_p5 < vol_avg:
            score += 3
        else:
            score += 1

    # MACD momentum
    if macd_hist is not None and len(macd_hist) >= 2:
        if macd_hist.iloc[-1] < macd_hist.iloc[-2]:
            score += 5
        elif len(macd_hist) >= 3 and macd_hist.iloc[-1] < macd_hist.iloc[-3]:
            score += 3
        else:
            score += 1

    return min(100, score)


def _deduplicate_patterns(patterns, price_threshold=0.03):
    """Remove near-duplicate patterns, keeping the highest scoring one."""
    if not patterns:
        return patterns

    patterns.sort(key=lambda x: x['score'], reverse=True)

    unique = []
    for pat in patterns:
        is_dup = False
        for existing in unique:
            p5_diff = abs(pat['p5']['price'] - existing['p5']['price']) / existing['p5']['price']
            p1_diff = abs(pat['p1']['price'] - existing['p1']['price']) / existing['p1']['price']
            if p5_diff < price_threshold and p1_diff < price_threshold:
                is_dup = True
                break
        if not is_dup:
            unique.append(pat)

    return unique


def analyze_wolfe_wave(df: pd.DataFrame, symbol: str):
    """
    Complete Wolfe Wave analysis for a single stock.
    Returns analysis dict or None if no valid setup found.
    """
    if df is None or len(df) < 150:
        return None

    try:
        close = df['Close']
        high = df['High']
        low = df['Low']
        volume = df['Volume']

        # --- Pre-compute all indicators ONCE ---
        rsi_series = calculate_rsi(close)
        current_rsi = float(rsi_series.iloc[-1])

        macd_line, signal_line, histogram = calculate_macd(close)
        current_macd = float(macd_line.iloc[-1])
        current_signal = float(signal_line.iloc[-1])
        has_macd_crossover = detect_macd_crossover(macd_line, signal_line)

        vol_avg20_series = volume.rolling(20).mean()
        vol_avg20 = float(vol_avg20_series.iloc[-1]) if not vol_avg20_series.empty else 0

        # Bundle pre-computed values to pass into scoring functions
        precomputed = {
            'current_rsi': current_rsi,
            'vol_avg20': vol_avg20,
            'volume': volume,          # full series (sliced inside scorer)
            'macd_hist': histogram,
        }

        # Detect both bullish and bearish patterns — pass pre-computed indicators
        bullish_patterns = detect_bullish_wolfe(df, precomputed=precomputed)
        bearish_patterns = detect_bearish_wolfe(df, precomputed=precomputed)

        all_patterns = bullish_patterns + bearish_patterns

        if not all_patterns:
            return None

        # Pick the highest-scoring pattern
        best = max(all_patterns, key=lambda x: x['score'])

        # Remaining indicators (not needed in inner loop)
        vol_info = volume_analysis(volume, close)
        ema_info = is_above_key_emas(close)
        atr = calculate_atr(high, low, close).iloc[-1]

        current_price = float(close.iloc[-1])
        p5_price = best['p5']['price']
        epa = best['epa']

        # Risk/Reward calculation
        if best['type'] == 'Bullish':
            entry = current_price
            stop_loss = p5_price * 0.98
            target = epa
            risk = entry - stop_loss
            reward = target - entry
        else:
            entry = current_price
            stop_loss = p5_price * 1.02
            target = epa
            risk = stop_loss - entry
            reward = entry - target

        if risk <= 0:
            return None

        rr_ratio = reward / risk
        if rr_ratio < 2.0:
            return None

        # Wave description
        wave_desc = (
            f"P1={best['p1']['price']:.2f} -> P2={best['p2']['price']:.2f} -> "
            f"P3={best['p3']['price']:.2f} -> P4={best['p4']['price']:.2f} -> "
            f"P5={best['p5']['price']:.2f}"
        )

        # Pattern quality labels
        sweet_zone_quality = "Excellent" if abs(best['p5_deviation']) <= 1.5 else (
            "Good" if abs(best['p5_deviation']) <= 3.0 else "Fair"
        )

        if best['type'] == 'Bullish':
            if current_price > p5_price * 1.03:
                status = "Bounce in progress"
            elif current_price > p5_price:
                status = "Early bounce from P5"
            else:
                status = "At/near P5 sweet zone"
        else:
            if current_price < p5_price * 0.97:
                status = "Reversal in progress"
            elif current_price < p5_price:
                status = "Early reversal from P5"
            else:
                status = "At/near P5 sweet zone"

        move_range = abs(epa - p5_price)
        if best['type'] == 'Bullish':
            target_50 = p5_price + move_range * 0.50
            target_100 = epa
        else:
            target_50 = p5_price - move_range * 0.50
            target_100 = epa

        total_score = best['score']

        return {
            'symbol': symbol.replace('.NS', ''),
            'sector': 'N/A',
            'pattern_type': best['type'],
            'status': status,
            'confidence': round(total_score, 1),
            'current_price': round(current_price, 2),
            'sweet_zone_quality': sweet_zone_quality,

            # 5 wave points
            'p1': round(best['p1']['price'], 2),
            'p2': round(best['p2']['price'], 2),
            'p3': round(best['p3']['price'], 2),
            'p4': round(best['p4']['price'], 2),
            'p5': round(best['p5']['price'], 2),
            'p5_deviation': round(best['p5_deviation'], 2),

            # Target
            'epa': round(epa, 2),
            'target_50': round(target_50, 2),
            'target_100': round(target_100, 2),

            # Trade setup
            'entry_price': round(current_price, 2),
            'stop_loss': round(stop_loss, 2),
            'rr_ratio': f"1:{rr_ratio:.1f}",
            'rr_value': round(rr_ratio, 1),
            'potential_pct': round(abs(epa - current_price) / current_price * 100, 1),

            # Pattern details
            'convergence': round(best['convergence'], 4),
            'bars_since_p5': best['bars_since_p5'],
            'wave_description': wave_desc,

            # Technical indicators
            'rsi': round(current_rsi, 1),
            'macd_status': "Bullish Crossover" if has_macd_crossover else (
                "Bullish" if current_macd > current_signal else "Bearish"
            ),
            'macd_histogram': "Rising" if (len(histogram) >= 2 and histogram.iloc[-1] > histogram.iloc[-2]) else "Declining",
            'vol_ratio_20': round(vol_info['vol_ratio_20'], 2),
            'volume_expansion': vol_info['volume_expansion'],
            'obv_trend': vol_info['obv_trend'],
            'is_accumulating': vol_info['is_accumulating'],
            'ema_alignment': ema_info['ema_alignment'],
            'above_ema200': ema_info['above_ema200'],

            # Invalidation level
            'invalidation': round(p5_price * (0.96 if best['type'] == 'Bullish' else 1.04), 2),
        }

    except Exception:
        return None
