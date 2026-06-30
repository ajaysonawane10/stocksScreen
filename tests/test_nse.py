import time
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.data_provider import download_from_nse_india

symbols = [
    "TCS.NS", "RELIANCE.NS", "INFY.NS", "HDFCBANK.NS", "SBIN.NS",
    "ICICIBANK.NS", "WIPRO.NS", "BAJFINANCE.NS", "MARUTI.NS", "TATAMOTORS.NS"
]

print(f"Testing NSE India data provider with {len(symbols)} symbols...")
t = time.time()
data = download_from_nse_india(symbols, period="1y")
elapsed = time.time() - t

print(f"\nResults: {len(data)}/{len(symbols)} symbols in {elapsed:.1f}s")
for sym, df in data.items():
    close = df["Close"].iloc[-1]
    print(f"  {sym:<20} {len(df):>3} rows  last_close={close:.2f}")
