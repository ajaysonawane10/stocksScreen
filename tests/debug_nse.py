import requests
import time

NSE_BASE = "https://www.nseindia.com"
NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
}

session = requests.Session()
session.headers.update(NSE_HEADERS)

# Prime cookies
print("Priming session cookies...")
r = session.get(NSE_BASE, timeout=10)
print(f"Homepage: {r.status_code}, cookies: {list(session.cookies.keys())}")
time.sleep(1)

# Try historical endpoint
url = f"{NSE_BASE}/api/historical/cm/equity"
params = {
    "symbol": "TCS",
    "series": '["EQ"]',
    "from": "22-06-2025",
    "to": "22-06-2026",
}
print(f"\nFetching TCS historical data...")
r2 = session.get(url, params=params, timeout=15)
print(f"Status: {r2.status_code}")
print(f"Response (first 500 chars): {r2.text[:500]}")
