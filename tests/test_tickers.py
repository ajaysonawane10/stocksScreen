"""Test alternative Yahoo Finance tickers for failing NSE symbols."""
import yfinance as yf
import warnings
warnings.filterwarnings('ignore')

test_symbols = {
    "TATAMOTORS.NS": ["TATAMTRDVT.NS", "TATMOTORS.NS"],
    "LTIM.NS": ["LTIMINDTREE.NS", "LTIM.NS"],
    "ZOMATO.NS": ["ETERNAL.NS", "ZOMATO.NS"],
    "GMRINFRA.NS": ["GMRAIRPORT.NS"],
    "MAZAGONDOCK.NS": ["MAZDOCK.NS"],
    "L&TFH.NS": ["LTFH.NS"],
}

for bad_sym, alternatives in test_symbols.items():
    print(f"\n--- {bad_sym} ---")
    for alt in alternatives:
        try:
            t = yf.Ticker(alt)
            hist = t.history(period="5d")
            if len(hist) > 0:
                last = hist["Close"].iloc[-1]
                print(f"  [OK] {alt} works! Last close: {last:.2f}")
            else:
                print(f"  [X]  {alt} - no data")
        except Exception as e:
            print(f"  [X]  {alt} - error: {e}")
