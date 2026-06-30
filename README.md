# 📈 NSE Stock Screener

Automated screener for **Elliott Wave** and **Wolfe Wave** patterns across NSE stocks (Nifty 50 + Nifty Next 50 + select midcaps).

## Quick Start

```bash
pip install -r requirements.txt
python screener.py
```

Reports are generated in the `output/` directory:
- `EW_DDMMYYYY.xlsx` — Elliott Wave setups
- `WW_DDMMYYYY.xlsx` — Wolfe Wave setups

## Project Structure

```
├── screener.py              # Main entry point
├── core/                    # Analysis engine
│   ├── indicators.py        # RSI, MACD, Fibonacci, volume analysis
│   ├── elliott_wave.py      # Elliott Wave detection
│   ├── wolfe_wave.py        # Wolfe Wave detection
│   ├── wolfe_screener.py    # Wolfe Wave screening pipeline
│   ├── nse_symbols.py       # Stock universe (Nifty 50/100/midcap)
│   ├── data_provider.py     # Multi-source data fetcher (NSE/TV/yfinance)
│   └── nse_fetch.js         # Node.js bridge for NSE India data
├── utils/                   # Export & delivery
│   ├── excel_exporter.py    # Formatted Excel report generation
│   └── send_telegram.py     # Telegram Bot API delivery
├── tests/                   # Debug & test scripts
├── output/                  # Generated reports (gitignored)
├── docs/                    # Reference notes
├── .github/workflows/       # CI/CD (daily run + Telegram delivery)
└── requirements.txt
```

## Data Sources (priority order)

1. **NSE India** — via `nse_fetch.js` Node.js bridge (fastest, direct)
2. **TradingView** — WebSocket client (optional)
3. **Yahoo Finance** — `yfinance` fallback (most reliable from non-Indian IPs)

## Automated Daily Run

The GitHub Actions workflow runs at **3:45 PM IST (Mon–Fri)** and delivers both Excel reports to Telegram. See [`.github/workflows/stock-screener.yml`](.github/workflows/stock-screener.yml).

**Required GitHub Secrets:** `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
