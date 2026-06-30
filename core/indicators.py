"""
Technical Indicators Module
Calculates RSI, MACD, Fibonacci levels, Volume analysis, and other indicators
needed for Elliott Wave screening.
"""

import numpy as np
import pandas as pd


def calculate_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Calculate Relative Strength Index."""
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """Calculate MACD, Signal line, and Histogram."""
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def calculate_ema(close: pd.Series, period: int) -> pd.Series:
    """Calculate Exponential Moving Average."""
    return close.ewm(span=period, adjust=False).mean()


def calculate_sma(close: pd.Series, period: int) -> pd.Series:
    """Calculate Simple Moving Average."""
    return close.rolling(window=period).mean()


def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Calculate Average True Range."""
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    return atr


def calculate_fibonacci_levels(wave1_start: float, wave1_end: float):
    """
    Calculate Fibonacci retracement and extension levels.
    Returns dict with retracement levels (for Wave 2) and extension levels (for Wave 3).
    """
    wave1_range = wave1_end - wave1_start
    
    retracement_levels = {
        "0.0%": wave1_end,
        "23.6%": wave1_end - 0.236 * wave1_range,
        "38.2%": wave1_end - 0.382 * wave1_range,
        "50.0%": wave1_end - 0.500 * wave1_range,
        "61.8%": wave1_end - 0.618 * wave1_range,
        "78.6%": wave1_end - 0.786 * wave1_range,
        "100.0%": wave1_start,
    }
    
    extension_levels = {
        "100%": wave1_end + wave1_range,
        "127.2%": wave1_end + 1.272 * wave1_range,
        "161.8%": wave1_end + 1.618 * wave1_range,
        "200%": wave1_end + 2.0 * wave1_range,
        "261.8%": wave1_end + 2.618 * wave1_range,
    }
    
    return retracement_levels, extension_levels


def volume_analysis(volume: pd.Series, close: pd.Series):
    """
    Analyze volume patterns for accumulation/distribution signals.
    Returns dict with volume metrics.
    """
    avg_20 = volume.rolling(window=20).mean()
    avg_50 = volume.rolling(window=50).mean()
    
    current_vol = volume.iloc[-1]
    avg_20_val = avg_20.iloc[-1]
    avg_50_val = avg_50.iloc[-1]
    
    # Volume ratio
    vol_ratio_20 = current_vol / avg_20_val if avg_20_val > 0 else 0
    vol_ratio_50 = current_vol / avg_50_val if avg_50_val > 0 else 0
    
    # Volume trend (last 10 days)
    recent_vol = volume.iloc[-10:]
    vol_trend = np.polyfit(range(len(recent_vol)), recent_vol.values, 1)[0]
    
    # On-Balance Volume (OBV)
    obv = (np.sign(close.diff()) * volume).fillna(0).cumsum()
    obv_trend = np.polyfit(range(min(20, len(obv))), obv.iloc[-20:].values, 1)[0]
    
    # Accumulation phase detection
    # Rising OBV with sideways/slightly declining price = accumulation
    price_change_20d = (close.iloc[-1] / close.iloc[-20] - 1) * 100 if len(close) >= 20 else 0
    obv_change_20d = obv.iloc[-1] - obv.iloc[-20] if len(obv) >= 20 else 0
    
    is_accumulating = obv_change_20d > 0 and price_change_20d < 5
    
    return {
        "current_volume": current_vol,
        "avg_20_volume": avg_20_val,
        "avg_50_volume": avg_50_val,
        "vol_ratio_20": vol_ratio_20,
        "vol_ratio_50": vol_ratio_50,
        "vol_trend": "Rising" if vol_trend > 0 else "Declining",
        "obv_trend": "Bullish" if obv_trend > 0 else "Bearish",
        "is_accumulating": is_accumulating,
        "volume_expansion": vol_ratio_20 > 1.3,
    }


def detect_rsi_divergence(close: pd.Series, rsi: pd.Series, lookback: int = 30):
    """
    Detect bullish RSI divergence (price makes lower low, RSI makes higher low).
    Returns True if bullish divergence is detected.
    """
    if len(close) < lookback or len(rsi) < lookback:
        return False
    
    recent_close = close.iloc[-lookback:]
    recent_rsi = rsi.iloc[-lookback:]
    
    # Find local minima in price
    price_lows = []
    rsi_lows = []
    
    for i in range(2, len(recent_close) - 2):
        if (recent_close.iloc[i] < recent_close.iloc[i-1] and 
            recent_close.iloc[i] < recent_close.iloc[i-2] and
            recent_close.iloc[i] < recent_close.iloc[i+1] and 
            recent_close.iloc[i] < recent_close.iloc[i+2]):
            price_lows.append((i, recent_close.iloc[i]))
            rsi_lows.append((i, recent_rsi.iloc[i]))
    
    if len(price_lows) < 2:
        return False
    
    # Check last two lows
    last_price_low = price_lows[-1][1]
    prev_price_low = price_lows[-2][1]
    last_rsi_low = rsi_lows[-1][1]
    prev_rsi_low = rsi_lows[-2][1]
    
    # Bullish divergence: price lower low, RSI higher low
    return last_price_low < prev_price_low and last_rsi_low > prev_rsi_low


def detect_macd_crossover(macd_line: pd.Series, signal_line: pd.Series, lookback: int = 5):
    """
    Detect recent bullish MACD crossover.
    Returns True if MACD crossed above signal line within lookback period.
    """
    for i in range(-lookback, 0):
        if (macd_line.iloc[i] > signal_line.iloc[i] and 
            macd_line.iloc[i-1] <= signal_line.iloc[i-1]):
            return True
    return False


def is_above_key_emas(close: pd.Series):
    """Check if price is above key EMAs (20, 50, 200)."""
    current = close.iloc[-1]
    ema20 = calculate_ema(close, 20).iloc[-1]
    ema50 = calculate_ema(close, 50).iloc[-1]
    ema200 = calculate_ema(close, 200).iloc[-1]
    
    return {
        "above_ema20": current > ema20,
        "above_ema50": current > ema50,
        "above_ema200": current > ema200,
        "ema20": ema20,
        "ema50": ema50,
        "ema200": ema200,
        "ema_alignment": ema20 > ema50 > ema200,  # Bullish alignment
    }
