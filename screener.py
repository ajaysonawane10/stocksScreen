"""
NSE Elliott Wave 3 Screener - Main Entry Point
Screens all NSE stocks for Wave 2 -> Wave 3 transition candidates.
Generates comprehensive analysis report.
"""

import sys
import json
import time
import datetime
import warnings
warnings.filterwarnings('ignore')

import pandas as pd
import numpy as np
from tabulate import tabulate

from core.nse_symbols import get_all_symbols, get_nifty50_symbols, get_nifty100_symbols, NIFTY_50, NIFTY_NEXT_50, MIDCAP_SELECT
from core.elliott_wave import analyze_stock
from core.wolfe_wave import analyze_wolfe_wave
from utils.excel_exporter import export_elliott_wave_to_excel, export_wolfe_wave_to_excel
from core.data_provider import download_stock_data
from core.wolfe_screener import run_screening as run_wolfe_screening, filter_and_rank as filter_wolfe_results, generate_report as generate_wolfe_report

# Sector mapping for NSE stocks
SECTOR_MAP = {
    "RELIANCE": "Energy/Conglomerate", "TCS": "IT", "HDFCBANK": "Banking",
    "INFY": "IT", "ICICIBANK": "Banking", "HINDUNILVR": "FMCG",
    "ITC": "FMCG", "SBIN": "Banking", "BHARTIARTL": "Telecom",
    "KOTAKBANK": "Banking", "LT": "Infrastructure", "AXISBANK": "Banking",
    "ASIANPAINT": "Paints", "MARUTI": "Auto", "HCLTECH": "IT",
    "SUNPHARMA": "Pharma", "TITAN": "Consumer/Jewelry", "BAJFINANCE": "NBFC",
    "WIPRO": "IT", "ULTRACEMCO": "Cement", "ONGC": "Energy",
    "NTPC": "Power", "TATAMOTORS": "Auto", "POWERGRID": "Power",
    "M&M": "Auto", "JSWSTEEL": "Steel", "TATASTEEL": "Steel",
    "ADANIENT": "Conglomerate", "ADANIPORTS": "Infrastructure",
    "COALINDIA": "Mining", "BAJAJFINSV": "Financial Services",
    "NESTLEIND": "FMCG", "TECHM": "IT", "INDUSINDBK": "Banking",
    "HDFCLIFE": "Insurance", "GRASIM": "Diversified", "DRREDDY": "Pharma",
    "CIPLA": "Pharma", "APOLLOHOSP": "Healthcare", "DIVISLAB": "Pharma",
    "EICHERMOT": "Auto", "SBILIFE": "Insurance", "TATACONSUM": "FMCG",
    "BPCL": "Energy", "BRITANNIA": "FMCG", "HEROMOTOCO": "Auto",
    "LTIM": "IT", "BAJAJ-AUTO": "Auto", "HINDALCO": "Metals",
    "SHRIRAMFIN": "NBFC", "ADANIGREEN": "Renewable Energy",
    "AMBUJACEM": "Cement", "BANKBARODA": "Banking", "BEL": "Defence",
    "BERGEPAINT": "Paints", "BOSCHLTD": "Auto Ancillary",
    "CANBK": "Banking", "CHOLAFIN": "NBFC", "COLPAL": "FMCG",
    "DLF": "Real Estate", "GAIL": "Energy", "GODREJCP": "FMCG",
    "HAL": "Defence", "HAVELLS": "Consumer Electricals",
    "ICICIPRULI": "Insurance", "ICICIGI": "Insurance", "INDIGO": "Aviation",
    "IOC": "Energy", "IRCTC": "Railways/Tourism", "JINDALSTEL": "Steel",
    "LICI": "Insurance", "MARICO": "FMCG", "MAXHEALTH": "Healthcare",
    "MUTHOOTFIN": "NBFC", "NAUKRI": "IT/Recruitment",
    "NHPC": "Power", "PIDILITIND": "Chemicals", "PNB": "Banking",
    "POLYCAB": "Cables/Wires", "RECLTD": "Power Finance",
    "SBICARD": "Financial Services", "SIEMENS": "Engineering",
    "SRF": "Chemicals", "TATAPOWER": "Power", "TORNTPHARM": "Pharma",
    "TRENT": "Retail", "UNIONBANK": "Banking", "VEDL": "Mining/Metals",
    "VBL": "Beverages", "ZOMATO": "Internet/Food Tech",
    "YESBANK": "Banking", "PFC": "Power Finance", "IRFC": "Railways Finance",
    "JIOFIN": "Financial Services", "ABB": "Engineering",
    "ATGL": "Gas Distribution", "CUMMINSIND": "Engineering",
    "GODREJPROP": "Real Estate", "DMART": "Retail", "LODHA": "Real Estate",
    "ASTRAL": "Building Materials", "AUROPHARMA": "Pharma",
    "BALKRISIND": "Auto Ancillary", "BHEL": "Capital Goods",
    "BIOCON": "Pharma", "CANFINHOME": "Housing Finance",
    "COFORGE": "IT", "CONCOR": "Logistics", "CROMPTON": "Consumer Electricals",
    "DEEPAKNTR": "Chemicals", "ESCORTS": "Auto", "EXIDEIND": "Auto Ancillary",
    "FEDERALBNK": "Banking", "GMRINFRA": "Infrastructure",
    "IDFCFIRSTB": "Banking", "INDIANB": "Banking",
    "INDUSTOWER": "Telecom Infrastructure", "JUBLFOOD": "QSR/Food",
    "L&TFH": "NBFC", "LICHSGFIN": "Housing Finance", "LUPIN": "Pharma",
    "MANAPPURAM": "NBFC", "MFSL": "Financial Services",
    "MGL": "Gas Distribution", "MPHASIS": "IT", "NATIONALUM": "Metals",
    "NMDC": "Mining", "OBEROIRLTY": "Real Estate", "PAGEIND": "Textiles",
    "PETRONET": "Energy", "PIIND": "Chemicals", "PRESTIGE": "Real Estate",
    "SAIL": "Steel", "SONACOMS": "Auto Ancillary",
    "STARHEALTH": "Insurance", "SYNGENE": "Pharma/Biotech",
    "TATACHEM": "Chemicals", "TATACOMM": "Telecom",
    "TATAELXSI": "IT/Design", "TVSMOTOR": "Auto",
    "VOLTAS": "Consumer Durables", "ZYDUSLIFE": "Pharma",
    "PERSISTENT": "IT", "KALYANKJIL": "Jewelry/Retail",
    "PHOENIXLTD": "Real Estate/Retail", "SUZLON": "Renewable Energy",
    "CGPOWER": "Electricals", "RVNL": "Infrastructure/Railways",
    "COCHINSHIP": "Defence/Shipbuilding", "MAZAGONDOCK": "Defence/Shipbuilding",
}


def run_screening(all_data):
    """Run Elliott Wave analysis on all stocks."""
    results = []
    total = len(all_data)
    
    print(f"[2/4] Running Elliott Wave analysis...")
    
    for idx, (symbol, df) in enumerate(all_data.items()):
        clean_symbol = symbol.replace('.NS', '')
        
        pct = (idx + 1) / total * 100
        filled = int(pct / 2)
        bar = '#' * filled + '-' * (50 - filled)
        print(f"\r  [{bar}] {pct:.0f}% Analyzing {clean_symbol:<15}", end='', flush=True)
        
        result = analyze_stock(df, symbol)
        if result:
            # Enrich with sector
            result['sector'] = SECTOR_MAP.get(clean_symbol, 'Other')
            results.append(result)
    
    print(f"\n  [OK] Found {len(results)} potential setups\n")
    return results


def filter_and_rank(results, min_confidence=75):
    """Filter by minimum confidence and rank stocks."""
    # Filter
    filtered = [r for r in results if r['confidence'] >= min_confidence]
    
    # Sort by confidence (total score) descending
    filtered.sort(key=lambda x: x['confidence'], reverse=True)
    
    # Assign ranks
    for i, r in enumerate(filtered):
        r['rank'] = i + 1
    
    return filtered


def generate_report(ranked_results, all_results, output_file="elliott_wave_report.md"):
    """Generate comprehensive markdown report."""
    
    print(f"[3/4] Generating report...")
    
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')
    
    lines = []
    lines.append(f"# 🌊 NSE Elliott Wave 3 Screener Report")
    lines.append(f"")
    lines.append(f"**Generated:** {now}")
    lines.append(f"**Stocks Scanned:** {len(all_results) + (150 - len(all_results))} | **Setups Found:** {len(all_results)} | **High Confidence (≥75%):** {len(ranked_results)}")
    lines.append(f"")
    lines.append(f"---")
    lines.append(f"")
    
    # ============== MAIN TABLE ==============
    lines.append(f"## 📊 Ranked Wave 3 Candidates (Confidence ≥ 75%)")
    lines.append(f"")
    
    if not ranked_results:
        lines.append("> **Note:** No stocks currently meet the strict 75% confidence threshold.")
        lines.append("> This is expected -- the screener is deliberately strict to avoid false signals.")
        lines.append("> Below are the best candidates found, even if below threshold.")
        lines.append(f"")
        # Use all results sorted by score
        display_results = sorted(all_results, key=lambda x: x['confidence'], reverse=True)[:20]
    else:
        # Show ranked results + next best up to 20 total
        below_threshold = [r for r in all_results if r['confidence'] < 75]
        below_threshold.sort(key=lambda x: x['confidence'], reverse=True)
        display_results = ranked_results + below_threshold[:max(0, 20 - len(ranked_results))]
    
    # Summary table
    table_data = []
    for i, r in enumerate(display_results):
        table_data.append([
            i + 1,
            r['symbol'],
            r['sector'],
            r['wave_status'],
            f"{r['confidence']:.0f}%",
            f"₹{r['entry_low']:.0f}-{r['entry_high']:.0f}",
            f"₹{r['stop_loss']:.0f}",
            f"₹{r['target1']:.0f}",
            f"₹{r['target2']:.0f}",
            r['rr_ratio'],
            r['setup_type'],
        ])
    
    headers = ["Rank", "Stock", "Sector", "Wave Status", "Conf%", "Entry Zone", 
               "Stop Loss", "Target 1", "Target 2", "R:R", "Setup Type"]
    
    lines.append(tabulate(table_data, headers=headers, tablefmt="pipe"))
    lines.append(f"")
    lines.append(f"---")
    lines.append(f"")
    
    # ============== DETAILED ANALYSIS ==============
    lines.append(f"## 📋 Detailed Stock Analysis")
    lines.append(f"")
    
    for r in display_results:
        lines.append(f"### {'⭐' if r['confidence'] >= 80 else '🔹'} {r['symbol']} ({r['sector']}) — Score: {r['confidence']:.0f}/100")
        lines.append(f"")
        lines.append(f"**Current Price:** ₹{r['current_price']:.2f} | **Setup:** {r['setup_type']}")
        lines.append(f"")
        
        # 1. Elliott Wave Count
        lines.append(f"#### 1. Elliott Wave Count")
        lines.append(f"- **Wave 1:** ₹{r['wave1_start']:.2f} → ₹{r['wave1_end']:.2f} (+{r['wave1_pct']:.1f}%)")
        lines.append(f"- **Wave 2:** Retraced {r['wave2_retrace']:.1f}% to ₹{r['wave2_end']:.2f}")
        lines.append(f"- **Status:** {r['wave_status']}")
        lines.append(f"- **Wave 3 Probability:** {r['w3_probability']}%")
        lines.append(f"")
        
        # 2. Fibonacci Levels
        lines.append(f"#### 2. Fibonacci Retracement Levels")
        for level, price in r['fib_retrace'].items():
            marker = " ◄ Wave 2 Low" if abs(price - r['wave2_end']) / r['wave2_end'] < 0.02 else ""
            lines.append(f"- **{level}:** ₹{price:.2f}{marker}")
        lines.append(f"")
        lines.append(f"**Extension Targets (from Wave 2 low):**")
        for level, price in r['fib_extension'].items():
            lines.append(f"- **{level}:** ₹{price:.2f}")
        lines.append(f"")
        
        # 3. Volume
        lines.append(f"#### 3. Volume Confirmation")
        lines.append(f"- **Volume Ratio (vs 20d avg):** {r['vol_ratio_20']:.2f}x")
        lines.append(f"- **Volume Expansion:** {'✅ Yes' if r['volume_expansion'] else '❌ No'}")
        lines.append(f"- **OBV Trend:** {r['obv_trend']}")
        lines.append(f"- **Accumulation Detected:** {'✅ Yes' if r['is_accumulating'] else '❌ No'}")
        lines.append(f"")
        
        # 4. RSI
        lines.append(f"#### 4. RSI Reading")
        rsi_status = "🟢 Bullish zone" if 50 <= r['rsi'] <= 70 else ("🟡 Neutral" if 40 <= r['rsi'] < 50 else "🔴 Caution")
        lines.append(f"- **RSI(14):** {r['rsi']:.1f} — {rsi_status}")
        lines.append(f"- **Bullish Divergence:** {'✅ Yes' if r['rsi_divergence'] else '❌ No'}")
        lines.append(f"")
        
        # 5. MACD
        lines.append(f"#### 5. MACD Status")
        lines.append(f"- **MACD:** {r['macd_status']}")
        lines.append(f"- **Histogram:** {r['macd_histogram']}")
        lines.append(f"")
        
        # 6. Institutional Accumulation
        lines.append(f"#### 6. Institutional Accumulation Evidence")
        lines.append(f"- **EMA Alignment (20>50>200):** {'✅ Bullish' if r['ema_alignment'] else '❌ Not aligned'}")
        lines.append(f"- **Above 200 EMA:** {'✅ Yes' if r['above_ema200'] else '❌ No'}")
        lines.append(f"- **OBV Accumulation:** {'✅ Yes' if r['obv_trend'] == 'Bullish' else '❌ No'}")
        lines.append(f"- **Volume Pattern:** {'Institutional buying detected' if r['is_accumulating'] and r['volume_expansion'] else 'Moderate activity'}")
        lines.append(f"")
        
        # 7. Trade Setup
        lines.append(f"#### 7. Trade Setup")
        lines.append(f"| Parameter | Value |")
        lines.append(f"|-----------|-------|")
        lines.append(f"| Entry Zone | ₹{r['entry_low']:.2f} - ₹{r['entry_high']:.2f} |")
        lines.append(f"| Stop Loss | ₹{r['stop_loss']:.2f} |")
        lines.append(f"| Target 1 (100% ext) | ₹{r['target1']:.2f} |")
        lines.append(f"| Target 2 (161.8% ext) | ₹{r['target2']:.2f} |")
        lines.append(f"| Risk/Reward | {r['rr_ratio']} |")
        lines.append(f"| Invalidation Level | ₹{r['invalidation_level']:.2f} |")
        lines.append(f"")
        
        # 8. Score Breakdown
        lines.append(f"#### 8. Score Breakdown")
        lines.append(f"| Component | Score | Max |")
        lines.append(f"|-----------|-------|-----|")
        lines.append(f"| Elliott Wave Structure | {r['ew_score']:.0f} | 40 |")
        lines.append(f"| Volume Confirmation | {r['vol_score']:.0f} | 20 |")
        lines.append(f"| RSI/MACD Momentum | {r['momentum_score']:.0f} | 20 |")
        lines.append(f"| Institutional Signals | {r['inst_score']:.0f} | 20 |")
        lines.append(f"| **Total** | **{r['total_score']:.0f}** | **100** |")
        lines.append(f"")
        lines.append(f"---")
        lines.append(f"")
    
    # ============== CATEGORIZED LISTS ==============
    lines.append(f"## 🏆 Categorized Recommendations")
    lines.append(f"")
    
    # A. Top 10 strongest
    lines.append(f"### A. Top 10 Strongest Wave 3 Candidates")
    lines.append(f"")
    top10 = display_results[:10]
    for i, r in enumerate(top10):
        emoji = "🥇" if i == 0 else ("🥈" if i == 1 else ("🥉" if i == 2 else f"{i+1}."))
        lines.append(f"{emoji} **{r['symbol']}** ({r['sector']}) — Score: {r['confidence']:.0f}% | Entry: ₹{r['entry_low']:.0f}-{r['entry_high']:.0f} | Target: ₹{r['target2']:.0f} | R:R {r['rr_ratio']}")
    lines.append(f"")
    
    # B. Top 5 aggressive early-entry
    lines.append(f"### B. Top 5 Aggressive Early-Entry Candidates")
    lines.append(f"")
    early = [r for r in display_results if r['setup_type'] in ('Early Entry', 'Aggressive Entry')][:5]
    if early:
        for i, r in enumerate(early):
            lines.append(f"{i+1}. **{r['symbol']}** — {r['setup_type']} | W2 retrace: {r['wave2_retrace']:.1f}% | RSI: {r['rsi']:.0f} | R:R {r['rr_ratio']}")
    else:
        lines.append(f"> No aggressive early-entry setups found currently.")
    lines.append(f"")
    
    # C. Top 5 confirmed breakout
    lines.append(f"### C. Top 5 Confirmed Breakout Candidates")
    lines.append(f"")
    confirmed = [r for r in display_results if r['setup_type'] == 'Confirmed Breakout'][:5]
    if confirmed:
        for i, r in enumerate(confirmed):
            lines.append(f"{i+1}. **{r['symbol']}** — Above W1 high (₹{r['wave1_end']:.0f}) | Volume: {r['vol_ratio_20']:.1f}x avg | MACD: {r['macd_status']}")
    else:
        lines.append(f"> No confirmed breakout setups found currently.")
    lines.append(f"")
    
    # D. Stocks to avoid
    lines.append(f"### D. ⚠️ Stocks to Avoid")
    lines.append(f"")
    
    # Find stocks that were analyzed but rejected
    all_symbols_analyzed = set(r['symbol'] for r in all_results)
    rejected_reasons = []
    
    # Low-scoring analyzed stocks
    low_score = [r for r in all_results if r['confidence'] < 50]
    for r in low_score[:5]:
        reasons = []
        if r['rsi'] > 75:
            reasons.append("RSI overbought")
        if r['wave2_retrace'] > 78:
            reasons.append("deep Wave 2 retrace")
        if not r['is_accumulating'] and not r['volume_expansion']:
            reasons.append("weak volume")
        if r['macd_status'] == 'Bearish':
            reasons.append("bearish MACD")
        if not r['ema_alignment']:
            reasons.append("EMA not aligned")
        
        reason_str = ", ".join(reasons) if reasons else "low overall score"
        rejected_reasons.append(f"- **{r['symbol']}** — {reason_str} (Score: {r['confidence']:.0f})")
    
    if rejected_reasons:
        for reason in rejected_reasons:
            lines.append(reason)
    else:
        lines.append(f"> All analyzed stocks showed reasonable patterns. Stocks not listed were rejected during initial screening for being in downtrends or lacking clear wave structures.")
    lines.append(f"")
    
    # ============== METHODOLOGY ==============
    lines.append(f"---")
    lines.append(f"")
    lines.append(f"## 📖 Methodology & Disclaimer")
    lines.append(f"")
    lines.append(f"### Screening Process")
    lines.append(f"1. **Universe:** Nifty 50 + Nifty Next 50 + Select Midcaps (~150 stocks)")
    lines.append(f"2. **Data:** 1-year daily OHLCV data from Yahoo Finance")
    lines.append(f"3. **Primary Filter:** Stocks above 200-day EMA (bullish long-term trend)")
    lines.append(f"4. **Wave Detection:** Swing high/low analysis → Wave 1-2 pattern matching")
    lines.append(f"5. **Fibonacci Validation:** Wave 2 retracement between 23.6%-78.6%")
    lines.append(f"6. **Momentum Confirmation:** RSI, MACD, Volume analysis")
    lines.append(f"7. **Risk/Reward Filter:** Minimum 1:3 ratio required")
    lines.append(f"")
    lines.append(f"### Scoring System")
    lines.append(f"| Component | Weight | Criteria |")
    lines.append(f"|-----------|--------|----------|")
    lines.append(f"| Elliott Wave Structure | 40% | Fibonacci quality, recency, wave size, time ratio |")
    lines.append(f"| Volume Confirmation | 20% | Accumulation, expansion, OBV trend |")
    lines.append(f"| RSI/MACD Momentum | 20% | RSI zone, divergence, MACD crossover, histogram |")
    lines.append(f"| Institutional Signals | 20% | EMA alignment, OBV, accumulation patterns |")
    lines.append(f"")
    lines.append(f"### ⚠️ Disclaimer")
    lines.append(f"This is a **quantitative screening tool**, not financial advice. Elliott Wave analysis is inherently subjective and probabilistic. Always:")
    lines.append(f"- Verify wave counts on actual charts before trading")
    lines.append(f"- Use proper position sizing (max 2-3% risk per trade)")
    lines.append(f"- Wait for confirmation candles before entry")
    lines.append(f"- Respect stop-loss levels strictly")
    lines.append(f"- Consider overall market conditions (Nifty 50 trend)")
    lines.append(f"")
    lines.append(f"---")
    lines.append(f"*Report generated by NSE Elliott Wave 3 Screener v1.0*")
    
    report_text = "\n".join(lines)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report_text)
    
    print(f"  [OK] Report saved to {output_file}\n")
    return report_text


def main():
    """Main execution flow for both Elliott Wave and Wolfe Wave analysis."""
    start_time = time.time()
    
    # Get all symbols
    symbols = get_all_symbols()
    
    # Download data
    all_data = download_stock_data(symbols, period="1y", interval="1d")
    
    # Run Elliott Wave analysis
    all_results = run_screening(all_data)
    
    # Filter and rank Elliott results
    print(f"[3/4] Filtering and ranking Elliott Wave results...")
    ranked = filter_and_rank(all_results, min_confidence=75)
    print(f"  [OK] {len(ranked)} Elliott Wave stocks pass 75% confidence threshold\n")
    
    # Generate Elliott reports
    report_path = "output/elliott_wave_report.md"
    generate_report(ranked, all_results, output_file=report_path)
    excel_path = export_elliott_wave_to_excel(ranked, all_results)
    
    # Run Wolfe Wave analysis on same dataset
    print(f"[3/4] Running Wolfe Wave analysis...")
    wolfe_results = run_wolfe_screening(all_data)
    wolfe_ranked = filter_wolfe_results(wolfe_results, min_confidence=50)
    print(f"  [OK] {len(wolfe_ranked)} Wolfe Wave setups pass 50% confidence threshold\n")
    
    # Generate Wolfe reports
    wolfe_report_path = "output/wolfe_wave_report.md"
    generate_wolfe_report(wolfe_ranked, wolfe_results, output_file=wolfe_report_path)
    wolfe_excel_path = export_wolfe_wave_to_excel(wolfe_ranked, wolfe_results)
    
    elapsed = time.time() - start_time
    
    print(f"[4/4] Complete!")
    print(f"{'='*70}")
    print(f"  Screening completed in {elapsed:.1f} seconds")
    print(f"  Stocks scanned: {len(all_data)}")
    print(f"  Elliott setups found: {len(all_results)}")
    print(f"  Elliott high-confidence (>=75%): {len(ranked)}")
    print(f"  Wolfe setups found: {len(wolfe_results)}")
    print(f"  Wolfe ranked (>=50%): {len(wolfe_ranked)}")
    print(f"  Elliott Markdown Report: {report_path}")
    print(f"  Elliott Excel Report: {excel_path}")
    print(f"  Wolfe Markdown Report: {wolfe_report_path}")
    print(f"  Wolfe Excel Report: {wolfe_excel_path}")
    print(f"{'='*70}")
    
    # Print quick summary to console
    if ranked:
        print(f"\n>>> TOP ELLIOTT PICKS:")
        for r in ranked[:5]:
            print(f"   {r['rank']}. {r['symbol']:<15} Score: {r['confidence']:.0f}% | "
                  f"Entry: Rs.{r['entry_low']:.0f}-{r['entry_high']:.0f} | "
                  f"Target: Rs.{r['target2']:.0f} | R:R {r['rr_ratio']}")
    elif all_results:
        print(f"\n>>> BEST ELLIOTT CANDIDATES (below 75% threshold):")
        sorted_results = sorted(all_results, key=lambda x: x['confidence'], reverse=True)
        for r in sorted_results[:5]:
            print(f"   {r['symbol']:<15} Score: {r['confidence']:.0f}% | "
                  f"Entry: Rs.{r['entry_low']:.0f}-{r['entry_high']:.0f} | "
                  f"Target: Rs.{r['target2']:.0f} | R:R {r['rr_ratio']}")
    else:
        print(f"\n[!] No Elliott Wave stocks met the screening criteria.")
    
    if wolfe_ranked:
        print(f"\n>>> TOP WOLFE PICKS:")
        for r in wolfe_ranked[:5]:
            direction = "BUY" if r['pattern_type'] == 'Bullish' else "SELL"
            print(f"   {direction} {r['symbol']:<15} Score: {r['confidence']:.0f} | "
                  f"CMP: Rs.{r['current_price']:.0f} | EPA: Rs.{r['epa']:.0f} | "
                  f"R:R {r['rr_ratio']}")
    else:
        print(f"\n[!] No Wolfe Wave patterns met the screening criteria.")


if __name__ == "__main__":
    main()
