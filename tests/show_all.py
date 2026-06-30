"""Quick script to show all 31 results from the screener."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import warnings
warnings.filterwarnings('ignore')
from screener import download_stock_data, run_screening, SECTOR_MAP
from core.nse_symbols import get_all_symbols

symbols = get_all_symbols()
all_data = download_stock_data(symbols, period='1y', interval='1d')
all_results = run_screening(all_data)

# Sort all results by confidence
all_results.sort(key=lambda x: x['confidence'], reverse=True)

print()
print('='*120)
print('COMPLETE RESULTS - ALL SETUPS FOUND (sorted by score)')
print('='*120)
print(f"{'#':>3} {'Symbol':<15} {'Score':>6} {'Wave Status':<42} {'RSI':>6} {'MACD':<20} {'R:R':<8} {'Type'}")
print('-'*120)
for i, r in enumerate(all_results):
    sym = r['symbol']
    score = f"{r['confidence']:.1f}"
    ws = r['wave_status']
    rsi = f"{r['rsi']:.1f}"
    macd = r['macd_status']
    rr = r['rr_ratio']
    st = r['setup_type']
    print(f"{i+1:3d} {sym:<15} {score:>6} {ws:<42} {rsi:>6} {macd:<20} {rr:<8} {st}")
