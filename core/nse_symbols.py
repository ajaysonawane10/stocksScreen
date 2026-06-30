"""
NSE Stock Universe - Nifty 500 constituents for Elliott Wave screening.
Uses yfinance-compatible ticker format (.NS suffix).
"""

# Nifty 50 + Nifty Next 50 + key midcap/smallcap stocks
# These are the most liquid NSE stocks suitable for institutional analysis

NIFTY_50 = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK",
    "HINDUNILVR", "ITC", "SBIN", "BHARTIARTL", "KOTAKBANK",
    "LT", "AXISBANK", "ASIANPAINT", "MARUTI", "HCLTECH",
    "SUNPHARMA", "TITAN", "BAJFINANCE", "WIPRO", "ULTRACEMCO",
    "ONGC", "NTPC", "TATAMOTORS", "POWERGRID", "M&M",
    "JSWSTEEL", "TATASTEEL", "ADANIENT", "ADANIPORTS", "COALINDIA",
    "BAJAJFINSV", "NESTLEIND", "TECHM", "INDUSINDBK", "HDFCLIFE",
    "GRASIM", "DRREDDY", "CIPLA", "APOLLOHOSP", "DIVISLAB",
    "EICHERMOT", "SBILIFE", "TATACONSUM", "BPCL", "BRITANNIA",
    "HEROMOTOCO", "LTIM", "BAJAJ-AUTO", "HINDALCO", "SHRIRAMFIN"
]

NIFTY_NEXT_50 = [
    "ADANIGREEN", "AMBUJACEM", "BANKBARODA", "BEL", "BERGEPAINT",
    "BOSCHLTD", "CANBK", "CHOLAFIN", "COLPAL", "DLF",
    "GAIL", "GODREJCP", "HAL", "HAVELLS", "ICICIPRULI",
    "ICICIGI", "INDIGO", "IOC", "IRCTC", "JINDALSTEL",
    "LICI", "MARICO", "MAXHEALTH", "MUTHOOTFIN", "NAUKRI",
    "NHPC", "PIDILITIND", "PNB", "POLYCAB", "RECLTD",
    "SBICARD", "SIEMENS", "SRF", "TATAPOWER", "TORNTPHARM",
    "TRENT", "UNIONBANK", "VEDL", "VBL", "ZOMATO",
    "YESBANK", "PFC", "IRFC", "JIOFIN", "ABB",
    "ATGL", "CUMMINSIND", "GODREJPROP", "DMART", "LODHA"
]

MIDCAP_SELECT = [
    "ASTRAL", "AUROPHARMA", "BALKRISIND", "BHEL", "BIOCON",
    "CANFINHOME", "COFORGE", "CONCOR", "CROMPTON", "DEEPAKNTR",
    "ESCORTS", "EXIDEIND", "FEDERALBNK", "GMRINFRA", "IDFCFIRSTB",
    "INDIANB", "INDUSTOWER", "JUBLFOOD", "L&TFH", "LICHSGFIN",
    "LUPIN", "MANAPPURAM", "MFSL", "MGL", "MPHASIS",
    "NATIONALUM", "NMDC", "OBEROIRLTY", "PAGEIND", "PETRONET",
    "PIIND", "PRESTIGE", "SAIL", "SONACOMS", "STARHEALTH",
    "SYNGENE", "TATACHEM", "TATACOMM", "TATAELXSI", "TVSMOTOR",
    "VOLTAS", "ZYDUSLIFE", "PERSISTENT", "KALYANKJIL", "PHOENIXLTD",
    "SUZLON", "CGPOWER", "RVNL", "COCHINSHIP", "MAZAGONDOCK"
]

def get_all_symbols():
    """Return all NSE symbols with .NS suffix for yfinance."""
    all_stocks = NIFTY_50 + NIFTY_NEXT_50 + MIDCAP_SELECT
    # Remove duplicates while preserving order
    seen = set()
    unique = []
    for s in all_stocks:
        if s not in seen:
            seen.add(s)
            unique.append(s)
    return [f"{s}.NS" for s in unique]

def get_nifty50_symbols():
    return [f"{s}.NS" for s in NIFTY_50]

def get_nifty100_symbols():
    all_stocks = NIFTY_50 + NIFTY_NEXT_50
    seen = set()
    unique = []
    for s in all_stocks:
        if s not in seen:
            seen.add(s)
            unique.append(s)
    return [f"{s}.NS" for s in unique]
