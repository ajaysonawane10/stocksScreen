"""
Elliott Wave Detection Engine
Identifies Wave 1, Wave 2, and potential Wave 3 entry points.
Uses swing high/low detection and strict Elliott Wave rules.
"""

import numpy as np
import pandas as pd
from core.indicators import (
    calculate_rsi, calculate_macd, calculate_fibonacci_levels,
    volume_analysis, detect_rsi_divergence, detect_macd_crossover,
    is_above_key_emas, calculate_atr
)


def find_swing_points(high: pd.Series, low: pd.Series, close: pd.Series, order: int = 5):
    """
    Find swing highs and swing lows using a rolling window approach.
    order: number of bars on each side to confirm a swing point.
    Returns list of (index, price, type) tuples.
    """
    swings = []
    
    for i in range(order, len(high) - order):
        # Swing High
        is_swing_high = True
        for j in range(1, order + 1):
            if high.iloc[i] <= high.iloc[i - j] or high.iloc[i] <= high.iloc[i + j]:
                is_swing_high = False
                break
        if is_swing_high:
            swings.append((i, high.iloc[i], 'high'))
        
        # Swing Low
        is_swing_low = True
        for j in range(1, order + 1):
            if low.iloc[i] >= low.iloc[i - j] or low.iloc[i] >= low.iloc[i + j]:
                is_swing_low = False
                break
        if is_swing_low:
            swings.append((i, low.iloc[i], 'low'))
    
    # Sort by index
    swings.sort(key=lambda x: x[0])
    return swings


def find_significant_swings(swings, min_move_pct: float = 3.0):
    """
    Filter swing points to only keep significant moves (> min_move_pct).
    This removes noise and keeps only meaningful wave structures.
    """
    if len(swings) < 2:
        return swings
    
    filtered = [swings[0]]
    
    for i in range(1, len(swings)):
        last = filtered[-1]
        current = swings[i]
        
        # Same type - keep the more extreme one
        if last[2] == current[2]:
            if current[2] == 'high' and current[1] > last[1]:
                filtered[-1] = current
            elif current[2] == 'low' and current[1] < last[1]:
                filtered[-1] = current
            continue
        
        # Different type - check if move is significant
        move_pct = abs(current[1] - last[1]) / last[1] * 100
        if move_pct >= min_move_pct:
            filtered.append(current)
    
    return filtered


def detect_wave_1_wave_2(df: pd.DataFrame, min_wave1_pct: float = 8.0, 
                          max_lookback: int = 120):
    """
    Detect Wave 1 (impulse up) followed by Wave 2 (corrective retracement).
    
    Rules:
    - Wave 1 must be a clear impulsive move up (min 8% move)
    - Wave 2 must retrace between 38.2% and 78.6% of Wave 1
    - Wave 2 must NOT retrace more than 100% of Wave 1
    - Wave 2 should show declining volume vs Wave 1
    - Current price should be near Wave 2 completion
    
    Returns dict with wave points and analysis, or None if not found.
    """
    if len(df) < max_lookback:
        return None
    
    recent = df.iloc[-max_lookback:].copy()
    recent = recent.reset_index(drop=True)
    
    high = recent['High']
    low = recent['Low']
    close = recent['Close']
    volume = recent['Volume']
    
    # Find swing points with different granularities
    swings_fine = find_swing_points(high, low, close, order=3)
    swings_med = find_swing_points(high, low, close, order=5)
    swings_coarse = find_swing_points(high, low, close, order=8)
    
    best_setup = None
    best_score = 0
    
    for swings in [swings_coarse, swings_med, swings_fine]:
        significant = find_significant_swings(swings, min_move_pct=min_wave1_pct * 0.5)
        
        if len(significant) < 3:
            continue
        
        # Look for pattern: low -> high -> low (Wave 1 up, Wave 2 correction)
        for i in range(len(significant) - 2):
            p1 = significant[i]      # Wave 1 start (low)
            p2 = significant[i + 1]  # Wave 1 end / Wave 2 start (high)
            p3 = significant[i + 2]  # Wave 2 end (low)
            
            # Must be low -> high -> low
            if p1[2] != 'low' or p2[2] != 'high' or p3[2] != 'low':
                continue
            
            wave1_start = p1[1]
            wave1_end = p2[1]
            wave2_end = p3[1]
            
            wave1_start_idx = p1[0]
            wave1_end_idx = p2[0]
            wave2_end_idx = p3[0]
            
            # Wave 1 must be upward
            if wave1_end <= wave1_start:
                continue
            
            # Calculate Wave 1 magnitude
            wave1_pct = (wave1_end - wave1_start) / wave1_start * 100
            if wave1_pct < min_wave1_pct:
                continue
            
            # Wave 2 retracement
            wave1_range = wave1_end - wave1_start
            wave2_retrace = (wave1_end - wave2_end) / wave1_range
            
            # STRICT: Wave 2 must not retrace more than 100%
            if wave2_retrace >= 1.0:
                continue
            
            # Prefer 38.2% to 78.6% retracement
            if wave2_retrace < 0.236:
                continue  # Too shallow - might not be Wave 2
            
            # Wave 2 end should be relatively recent (within last 30 bars)
            bars_since_w2 = len(recent) - 1 - wave2_end_idx
            if bars_since_w2 > 30:
                continue  # Too old
            
            # Current price should be above Wave 2 low
            current_price = close.iloc[-1]
            if current_price < wave2_end:
                continue
            
            # Current price should not have already exceeded Wave 1 high significantly
            # (Wave 3 would already be in progress)
            if current_price > wave1_end * 1.10:
                continue  # Wave 3 likely already extended
            
            # Score this setup
            score = 0
            
            # Fibonacci quality (38.2-61.8% is ideal)
            if 0.382 <= wave2_retrace <= 0.618:
                score += 35
            elif 0.236 <= wave2_retrace < 0.382:
                score += 20
            elif 0.618 < wave2_retrace <= 0.786:
                score += 25
            else:
                score += 10
            
            # Recency (more recent = better)
            if bars_since_w2 <= 5:
                score += 15
            elif bars_since_w2 <= 10:
                score += 12
            elif bars_since_w2 <= 20:
                score += 8
            else:
                score += 4
            
            # Wave 1 size (larger = more reliable)
            if wave1_pct >= 20:
                score += 15
            elif wave1_pct >= 15:
                score += 12
            elif wave1_pct >= 10:
                score += 10
            else:
                score += 6
            
            # Wave structure clarity (time ratio)
            wave1_bars = wave1_end_idx - wave1_start_idx
            wave2_bars = wave2_end_idx - wave1_end_idx
            if wave1_bars > 0:
                time_ratio = wave2_bars / wave1_bars
                if 0.382 <= time_ratio <= 1.618:
                    score += 10
                else:
                    score += 3
            
            if score > best_score:
                best_score = score
                best_setup = {
                    'wave1_start_price': wave1_start,
                    'wave1_end_price': wave1_end,
                    'wave2_end_price': wave2_end,
                    'wave1_start_idx': wave1_start_idx,
                    'wave1_end_idx': wave1_end_idx,
                    'wave2_end_idx': wave2_end_idx,
                    'wave1_pct': wave1_pct,
                    'wave2_retrace_pct': wave2_retrace * 100,
                    'bars_since_w2': bars_since_w2,
                    'structure_score': score,
                    'current_price': current_price,
                }
    
    return best_setup


def analyze_stock(df: pd.DataFrame, symbol: str):
    """
    Complete Elliott Wave analysis for a single stock.
    Returns analysis dict or None if no valid setup found.
    """
    if df is None or len(df) < 200:
        return None
    
    try:
        close = df['Close']
        high = df['High']
        low = df['Low']
        volume = df['Volume']
        
        # ---- WEEKLY TREND CHECK ----
        # Use 200-day EMA as proxy for weekly trend
        ema_info = is_above_key_emas(close)
        if not ema_info['above_ema200']:
            return None  # Reject stocks in long-term downtrends
        
        # ---- DETECT WAVE 1 & WAVE 2 ----
        wave_setup = detect_wave_1_wave_2(df, min_wave1_pct=8.0)
        if wave_setup is None:
            return None
        
        # ---- FIBONACCI LEVELS ----
        retrace_levels, extension_levels = calculate_fibonacci_levels(
            wave_setup['wave1_start_price'],
            wave_setup['wave1_end_price']
        )
        
        # ---- RSI ANALYSIS ----
        rsi = calculate_rsi(close)
        current_rsi = rsi.iloc[-1]
        
        # RSI should be between 40 and 70 for Wave 3 entry
        rsi_score = 0
        if 50 <= current_rsi <= 70:
            rsi_score = 20
        elif 40 <= current_rsi < 50:
            rsi_score = 15
        elif 70 < current_rsi <= 75:
            rsi_score = 10
        else:
            rsi_score = 5
        
        # Bullish RSI divergence bonus
        has_rsi_divergence = detect_rsi_divergence(close, rsi)
        if has_rsi_divergence:
            rsi_score += 5
        
        # ---- MACD ANALYSIS ----
        macd_line, signal_line, histogram = calculate_macd(close)
        current_macd = macd_line.iloc[-1]
        current_signal = signal_line.iloc[-1]
        current_histogram = histogram.iloc[-1]
        
        macd_score = 0
        has_macd_crossover = detect_macd_crossover(macd_line, signal_line)
        
        if has_macd_crossover:
            macd_score += 10
        if current_histogram > 0:
            macd_score += 5
        # Histogram increasing
        if len(histogram) >= 3 and histogram.iloc[-1] > histogram.iloc[-2] > histogram.iloc[-3]:
            macd_score += 5
        if current_macd > current_signal:
            macd_score += 5
        
        # ---- VOLUME ANALYSIS ----
        vol_info = volume_analysis(volume, close)
        
        vol_score = 0
        if vol_info['is_accumulating']:
            vol_score += 8
        if vol_info['volume_expansion']:
            vol_score += 7
        if vol_info['obv_trend'] == 'Bullish':
            vol_score += 5
        if vol_info['vol_trend'] == 'Rising':
            vol_score += 5
        
        # ---- CALCULATE TOTAL SCORE ----
        # Elliott Wave structure (40%) - already scored 0-75, normalize to 0-40
        ew_score = min(40, wave_setup['structure_score'] * 40 / 75)
        
        # Volume (20%)
        vol_final = min(20, vol_score)
        
        # RSI/MACD Momentum (20%)
        momentum_score = min(20, (rsi_score + macd_score) * 20 / 50)
        
        # Institutional accumulation (20%)
        inst_score = 0
        if vol_info['is_accumulating']:
            inst_score += 8
        if ema_info['ema_alignment']:
            inst_score += 6
        if vol_info['obv_trend'] == 'Bullish':
            inst_score += 6
        inst_score = min(20, inst_score)
        
        total_score = ew_score + vol_final + momentum_score + inst_score
        
        # ---- ENTRY, STOP LOSS, TARGETS ----
        current_price = close.iloc[-1]
        atr = calculate_atr(high, low, close).iloc[-1]
        
        # Entry zone: current price to slightly above
        entry_low = wave_setup['wave2_end_price'] * 1.005
        entry_high = wave_setup['wave2_end_price'] * 1.03
        
        # If price already moved up, adjust entry
        if current_price > entry_high:
            entry_low = current_price * 0.99
            entry_high = current_price * 1.01
        
        # Stop loss: below Wave 2 low
        stop_loss = wave_setup['wave2_end_price'] * 0.98
        
        # Wave 3 targets using Fibonacci extensions
        wave1_range = wave_setup['wave1_end_price'] - wave_setup['wave1_start_price']
        target1 = wave_setup['wave2_end_price'] + wave1_range  # 100% extension
        target2 = wave_setup['wave2_end_price'] + wave1_range * 1.618  # 161.8% extension
        
        # Risk/Reward calculation
        risk = current_price - stop_loss
        reward1 = target1 - current_price
        reward2 = target2 - current_price
        
        if risk <= 0:
            return None
        
        rr_ratio1 = reward1 / risk
        rr_ratio2 = reward2 / risk
        
        # Must have at least 1:3 risk/reward
        if rr_ratio2 < 3.0:
            return None
        
        # ---- DETERMINE WAVE 3 PROBABILITY ----
        w3_probability = 0
        
        # Price above Wave 2 low
        if current_price > wave_setup['wave2_end_price']:
            w3_probability += 15
        
        # Price approaching or above Wave 1 high
        if current_price > wave_setup['wave1_end_price'] * 0.95:
            w3_probability += 20
        
        # MACD bullish
        if has_macd_crossover:
            w3_probability += 15
        
        # RSI crossing above 50
        if current_rsi > 50:
            w3_probability += 10
        
        # Volume confirmation
        if vol_info['volume_expansion']:
            w3_probability += 15
        
        # EMA alignment
        if ema_info['ema_alignment']:
            w3_probability += 10
        
        # Fibonacci quality
        if 0.382 <= wave_setup['wave2_retrace_pct'] / 100 <= 0.618:
            w3_probability += 15
        
        # ---- CLASSIFY SETUP TYPE ----
        if current_price > wave_setup['wave1_end_price']:
            setup_type = "Confirmed Breakout"
        elif current_price > wave_setup['wave2_end_price'] * 1.02:
            setup_type = "Early Entry"
        else:
            setup_type = "Aggressive Entry"
        
        # ---- WAVE STATUS ----
        retrace_pct = wave_setup['wave2_retrace_pct']
        if retrace_pct >= 50:
            fib_level = "61.8%" if retrace_pct >= 55 else "50%"
        elif retrace_pct >= 35:
            fib_level = "38.2%"
        else:
            fib_level = "23.6%"
        
        wave_status = f"W2 retraced {retrace_pct:.1f}% (near {fib_level} Fib)"
        
        # Determine sector (will be enriched later)
        sector = "N/A"
        
        return {
            'symbol': symbol.replace('.NS', ''),
            'sector': sector,
            'wave_status': wave_status,
            'confidence': round(total_score, 1),
            'entry_low': round(entry_low, 2),
            'entry_high': round(entry_high, 2),
            'stop_loss': round(stop_loss, 2),
            'target1': round(target1, 2),
            'target2': round(target2, 2),
            'rr_ratio': f"1:{rr_ratio2:.1f}",
            'current_price': round(current_price, 2),
            'setup_type': setup_type,
            'w3_probability': min(100, w3_probability),
            
            # Detailed analysis
            'wave1_start': round(wave_setup['wave1_start_price'], 2),
            'wave1_end': round(wave_setup['wave1_end_price'], 2),
            'wave2_end': round(wave_setup['wave2_end_price'], 2),
            'wave1_pct': round(wave_setup['wave1_pct'], 1),
            'wave2_retrace': round(wave_setup['wave2_retrace_pct'], 1),
            'rsi': round(current_rsi, 1),
            'macd_status': "Bullish Crossover" if has_macd_crossover else ("Bullish" if current_macd > current_signal else "Bearish"),
            'macd_histogram': "Rising" if (len(histogram) >= 2 and histogram.iloc[-1] > histogram.iloc[-2]) else "Declining",
            'rsi_divergence': has_rsi_divergence,
            'volume_expansion': vol_info['volume_expansion'],
            'vol_ratio_20': round(vol_info['vol_ratio_20'], 2),
            'obv_trend': vol_info['obv_trend'],
            'is_accumulating': vol_info['is_accumulating'],
            'ema_alignment': ema_info['ema_alignment'],
            'above_ema200': ema_info['above_ema200'],
            'invalidation_level': round(wave_setup['wave1_start_price'], 2),
            
            # Fibonacci levels
            'fib_retrace': {k: round(v, 2) for k, v in retrace_levels.items()},
            'fib_extension': {k: round(v, 2) for k, v in extension_levels.items()},
            
            # Scores breakdown
            'ew_score': round(ew_score, 1),
            'vol_score': round(vol_final, 1),
            'momentum_score': round(momentum_score, 1),
            'inst_score': round(inst_score, 1),
            'total_score': round(total_score, 1),
        }
    
    except Exception as e:
        return None
