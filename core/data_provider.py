"""
Unified data provider for stock screeners.
Priority order:
  1. NSE India via stock-nse-india Node.js bridge (nse_fetch.js) — direct NSE data
  2. TradingView WebSocket client
  3. Yahoo Finance (yfinance) — final fallback

The Node.js bridge avoids NSE's Cloudflare/WAF blocking that affects Python requests.
"""

from __future__ import annotations

import datetime
import json
import os
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Iterable, Optional

import pandas as pd

try:
    import yfinance as yf
except Exception:
    yf = None

# Path to our Node.js fetcher script (same directory as this file)
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
NSE_FETCH_JS = os.path.join(_THIS_DIR, "nse_fetch.js")

# ---------------------------------------------------------------------------
# NSE India via Node.js bridge
# ---------------------------------------------------------------------------

def _period_to_dates(period: str = "1y"):
    """Convert yfinance-style period string to (start_date, end_date) ISO strings."""
    end = datetime.date.today()
    period_map = {
        "1d": 1, "5d": 5, "1mo": 30, "3mo": 90,
        "6mo": 180, "1y": 365, "2y": 730, "5y": 1825,
    }
    days = period_map.get(period, 365)
    start = end - datetime.timedelta(days=days)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def _parse_nse_rows(rows: list) -> Optional[pd.DataFrame]:
    """Convert list of {date, open, high, low, close, volume} dicts to a DataFrame."""
    if not rows:
        return None

    records = []
    for r in rows:
        try:
            records.append({
                "Date":   pd.to_datetime(r["date"], dayfirst=True),
                "Open":   float(r.get("open")   or 0),
                "High":   float(r.get("high")   or 0),
                "Low":    float(r.get("low")    or 0),
                "Close":  float(r.get("close")  or 0),
                "Volume": float(r.get("volume") or 0),
            })
        except (ValueError, TypeError, KeyError):
            continue

    if not records:
        return None

    df = (pd.DataFrame(records)
            .drop_duplicates("Date")
            .sort_values("Date")
            .set_index("Date"))
    df = df[df["Close"] > 0].dropna(subset=["Close", "Volume"])
    return df if len(df) >= 120 else None


def download_from_nse_india(symbols: Iterable[str], period: str = "1y",
                             interval: str = "1d") -> Dict[str, pd.DataFrame]:
    """
    Fetch daily OHLCV data for all symbols by calling the nse_fetch.js Node.js script.
    The script uses the stock-nse-india npm package which bypasses NSE's Cloudflare WAF.

    Symbols are fetched in batches to avoid overloading the Node.js process and
    to allow progress reporting.
    """
    if interval not in ("1d", "1D", "d", "D", "daily"):
        return {}

    if not os.path.exists(NSE_FETCH_JS):
        print(f"  [NSE] nse_fetch.js not found at {NSE_FETCH_JS}, skipping.")
        return {}

    symbols = [s.replace(".NS", "").replace(".BO", "") for s in symbols]
    total = len(symbols)
    start_date, end_date = _period_to_dates(period)

    print(f"  [NSE] Fetching {total} symbols via Node.js bridge ({start_date} to {end_date})...",
          flush=True)

    all_data: Dict[str, pd.DataFrame] = {}

    # Process in batches of 15 — each batch is one Node.js call
    # Node.js fetches them sequentially inside, but we run multiple batches in parallel
    BATCH_SIZE = 15
    batches = [symbols[i:i + BATCH_SIZE] for i in range(0, total, BATCH_SIZE)]


    def _fetch_batch(batch_syms: list) -> list:
        """Run one node nse_fetch.js call for a batch; return parsed JSON list."""
        cmd = ["node", NSE_FETCH_JS] + batch_syms + ["--start", start_date, "--end", end_date]
        # Write output to a temp file to avoid Windows pipe buffer deadlock
        # (capture_output=True hangs when stdout > ~4KB on Windows)
        tmp = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json',
                                             delete=False, dir=_THIS_DIR) as f:
                tmp = f.name
            with open(tmp, 'w') as out_f:
                proc = subprocess.run(
                    cmd,
                    stdout=out_f,
                    stderr=subprocess.DEVNULL,
                    timeout=180,
                    cwd=_THIS_DIR,
                )
            if proc.returncode != 0:
                return []
            with open(tmp, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            if not content:
                return []
            return json.loads(content)
        except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception):
            return []
        finally:
            if tmp and os.path.exists(tmp):
                try:
                    os.unlink(tmp)
                except Exception:
                    pass

    # Run up to 3 batches in parallel (Node.js processes)
    MAX_PARALLEL = 3
    batches_done = 0
    with ThreadPoolExecutor(max_workers=MAX_PARALLEL) as executor:
        futures = {executor.submit(_fetch_batch, batch): batch for batch in batches}
        for future in as_completed(futures):
            batches_done += 1
            items = future.result()
            for item in items:
                sym_clean = item.get("symbol", "")
                rows = item.get("rows", [])
                df = _parse_nse_rows(rows)
                if df is not None:
                    # Store under .NS key to match screener expectations
                    all_data[f"{sym_clean}.NS"] = df

            pct = batches_done / len(batches) * 100
            bar = "#" * int(pct / 2) + "-" * (50 - int(pct / 2))
            print(f"\r  [{bar}] {pct:.0f}% - fetched {len(all_data)}/{total}", end="", flush=True)

    print(f"\n  [NSE] Successfully fetched {len(all_data)}/{total} symbols.")
    return all_data


# ---------------------------------------------------------------------------
# TradingView (optional)
# ---------------------------------------------------------------------------

DEFAULT_DAILY_BARS = 500

try:
    from tradingview.client import TradingViewWebSocketClient
except Exception:
    TradingViewWebSocketClient = None


def to_tradingview_symbol(symbol: str) -> str:
    clean = symbol.replace(".NS", "").replace(".BO", "").replace(".BZ", "")
    return clean if clean.startswith("NSE:") else f"NSE:{clean}"


def _normalize_tv_data(raw_rows, symbol: str) -> Optional[pd.DataFrame]:
    rows = list(raw_rows)
    if not rows:
        return None
    df = pd.DataFrame([{
        "Date":   pd.to_datetime(row.bar_time, unit="s"),
        "Open":   float(row.open),
        "High":   float(row.high),
        "Low":    float(row.low),
        "Close":  float(row.close),
        "Volume": float(row.volume),
    } for row in rows])
    if df.empty:
        return None
    df = df.drop_duplicates("Date").sort_values("Date").set_index("Date")
    return df[["Open", "High", "Low", "Close", "Volume"]]


def download_from_tradingview(symbols: Iterable[str], period: str = "1y",
                               interval: str = "1d") -> Dict[str, pd.DataFrame]:
    if TradingViewWebSocketClient is None:
        return {}
    symbols = list(symbols)
    all_data: Dict[str, list] = {}
    try:
        for i in range(0, len(symbols), 10):
            batch = symbols[i:i + 10]
            client = TradingViewWebSocketClient()
            for sym in batch:
                client.add_symbol(to_tradingview_symbol(sym))
            for ohlc in client.fetch_ohlc(interval="D", past_bar=DEFAULT_DAILY_BARS):
                key = ohlc.symbol.split(":", 1)[-1] if ":" in ohlc.symbol else ohlc.symbol
                all_data.setdefault(key, []).append(ohlc)
            time.sleep(0.2)
        normalized = {}
        for sym in symbols:
            clean = sym.replace(".NS", "")
            if clean in all_data:
                df = _normalize_tv_data(all_data[clean], sym)
                if df is not None:
                    normalized[sym] = df
        return normalized
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Yahoo Finance fallback
# ---------------------------------------------------------------------------

def download_from_yfinance(symbols: Iterable[str], period: str = "1y",
                            interval: str = "1d") -> Dict[str, pd.DataFrame]:
    """Fallback data download using Yahoo Finance."""
    if yf is None:
        return {}
    all_data: Dict[str, pd.DataFrame] = {}
    symbols = list(symbols)
    for i in range(0, len(symbols), 20):
        batch = symbols[i:i + 20]
        try:
            data = yf.download(
                " ".join(batch), period=period, interval=interval,
                group_by="ticker", progress=False, threads=True,
            )
            for sym in batch:
                try:
                    df = data.copy() if len(batch) == 1 else data[sym].copy()
                    df = df.dropna(subset=["Close", "Volume"])
                    if len(df) >= 120:
                        if isinstance(df.columns, pd.MultiIndex):
                            df.columns = df.columns.get_level_values(0)
                        all_data[sym] = df
                except Exception:
                    pass
        except Exception:
            pass
        time.sleep(0.3)
    return all_data


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def download_stock_data(symbols: Iterable[str], period: str = "1y",
                        interval: str = "1d") -> Dict[str, pd.DataFrame]:
    """
    Download stock data using the fastest available source:
      1. NSE India via nse_fetch.js Node.js bridge  <-- fastest, direct NSE source
      2. TradingView WebSocket client
      3. Yahoo Finance (yfinance fallback)
    """
    symbols = list(symbols)

    # 1. Try NSE India Node.js bridge
    nse_data = download_from_nse_india(symbols, period=period, interval=interval)
    if nse_data and len(nse_data) >= len(symbols) * 0.6:
        return nse_data

    # 2. Try TradingView for missing symbols
    missing = [s for s in symbols if s not in nse_data]
    tv_data = download_from_tradingview(missing, period=period, interval=interval)
    if tv_data:
        nse_data.update(tv_data)
        if len(nse_data) >= len(symbols) * 0.6:
            return nse_data

    # 3. Fall back to yfinance for remaining
    still_missing = [s for s in symbols if s not in nse_data]
    if still_missing:
        print(f"  [YF]  Fetching {len(still_missing)} symbols via yfinance...")
        yf_data = download_from_yfinance(still_missing, period=period, interval=interval)
        nse_data.update(yf_data)

    return nse_data
