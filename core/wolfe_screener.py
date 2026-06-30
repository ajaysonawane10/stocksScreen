"""
NSE Wolfe Wave Screener - Main Entry Point
Screens all NSE stocks for bullish and bearish Wolfe Wave setups.
Generates comprehensive analysis report.
"""

import os
import sys
import time
import datetime
import warnings
warnings.filterwarnings('ignore')
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import numpy as np
from tabulate import tabulate

from core.nse_symbols import get_all_symbols, NIFTY_50, NIFTY_NEXT_50, MIDCAP_SELECT
from core.wolfe_wave import analyze_wolfe_wave
from utils.excel_exporter import export_wolfe_wave_to_excel
from core.data_provider import download_stock_data

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


def _analyze_single(args):
    """Worker function: analyze one stock. Returns result dict or None."""
    symbol, df = args
    result = analyze_wolfe_wave(df, symbol)
    if result:
        clean_symbol = symbol.replace('.NS', '')
        result['sector'] = SECTOR_MAP.get(clean_symbol, 'Other')
    return result


def run_screening(all_data):
    """Run Wolfe Wave analysis on all stocks in parallel."""
    results = []
    total = len(all_data)
    completed = 0

    # Use up to 8 threads — NumPy releases the GIL, so threading gives real speedup
    max_workers = min(8, os.cpu_count() or 4)

    print(f"[2/4] Running Wolfe Wave analysis ({max_workers} parallel workers)...")

    items = list(all_data.items())
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_symbol = {
            executor.submit(_analyze_single, item): item[0]
            for item in items
        }
        for future in as_completed(future_to_symbol):
            completed += 1
            symbol = future_to_symbol[future]
            clean_symbol = symbol.replace('.NS', '')

            pct = completed / total * 100
            filled = int(pct / 2)
            bar = '#' * filled + '-' * (50 - filled)
            print(f"\r  [{bar}] {pct:.0f}% ({completed}/{total}) Last: {clean_symbol:<15}",
                  end='', flush=True)

            try:
                result = future.result()
                if result:
                    results.append(result)
            except Exception:
                pass

    print(f"\n  [OK] Found {len(results)} Wolfe Wave setups\n")
    return results


def filter_and_rank(results, min_confidence=50):
    """Filter by minimum confidence and rank stocks."""
    filtered = [r for r in results if r['confidence'] >= min_confidence]
    filtered.sort(key=lambda x: x['confidence'], reverse=True)
    
    for i, r in enumerate(filtered):
        r['rank'] = i + 1
    
    return filtered


def generate_report(ranked_results, all_results, output_file="wolfe_wave_report.md"):
    """Generate comprehensive Wolfe Wave markdown report."""
    
    print(f"[3/4] Generating report...")
    
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')
    
    # Separate bullish and bearish
    bullish = [r for r in ranked_results if r['pattern_type'] == 'Bullish']
    bearish = [r for r in ranked_results if r['pattern_type'] == 'Bearish']
    all_bullish = [r for r in all_results if r['pattern_type'] == 'Bullish']
    all_bearish = [r for r in all_results if r['pattern_type'] == 'Bearish']
    
    lines = []
    lines.append(f"# Wolfe Wave Screener Report - NSE India")
    lines.append(f"")
    lines.append(f"**Generated:** {now}")
    lines.append(f"**Stocks Scanned:** ~150 | **Wolfe Wave Setups Found:** {len(all_results)} "
                 f"(Bullish: {len(all_bullish)}, Bearish: {len(all_bearish)}) | "
                 f"**Ranked (score >= 50):** {len(ranked_results)}")
    lines.append(f"")
    lines.append(f"---")
    lines.append(f"")
    
    # ============== WHAT IS A WOLFE WAVE ==============
    lines.append(f"## What is a Wolfe Wave?")
    lines.append(f"")
    lines.append(f"A Wolfe Wave is a **natural 5-wave reversal pattern** discovered by Bill Wolfe. "
                 f"It identifies points of equilibrium in price action where supply and demand converge.")
    lines.append(f"")
    lines.append(f"**Bullish Wolfe Wave (Buy Setup):**")
    lines.append(f"```")
    lines.append(f"  P2 ----__                  EPA Target")
    lines.append(f"  /        \\    P4 ----__   /")
    lines.append(f" /          \\  /        \\ /")
    lines.append(f"P1           P3          P5  <-- Entry (Sweet Zone)")
    lines.append(f"```")
    lines.append(f"- P1-P3-P5 form the lower trendline (support)")
    lines.append(f"- P2-P4 form the upper trendline (resistance)")
    lines.append(f"- Lines CONVERGE (wedge pattern)")
    lines.append(f"- P5 touches/overshoots the 1-3 line = **Sweet Zone** = Entry")
    lines.append(f"- Target (EPA) = 1-4 line extended to P5 time")
    lines.append(f"")
    lines.append(f"**Bearish Wolfe Wave (Sell Setup):** Mirror image of bullish.")
    lines.append(f"")
    lines.append(f"---")
    lines.append(f"")
    
    # ============== MAIN TABLE ==============
    lines.append(f"## Ranked Wolfe Wave Setups")
    lines.append(f"")
    
    display_results = ranked_results[:25] if ranked_results else sorted(
        all_results, key=lambda x: x['confidence'], reverse=True
    )[:25]
    
    if not display_results:
        lines.append(f"> No Wolfe Wave patterns detected in the current scan.")
        lines.append(f"")
    else:
        table_data = []
        for i, r in enumerate(display_results):
            direction = "BULL" if r['pattern_type'] == 'Bullish' else "BEAR"
            table_data.append([
                i + 1,
                r['symbol'],
                r['sector'],
                direction,
                f"{r['confidence']:.0f}",
                r['sweet_zone_quality'],
                f"Rs.{r['current_price']:.0f}",
                f"Rs.{r['p5']:.0f}",
                f"Rs.{r['epa']:.0f}",
                f"Rs.{r['stop_loss']:.0f}",
                r['rr_ratio'],
                f"{r['potential_pct']:.1f}%",
                r['status'],
            ])
        
        headers = ["#", "Stock", "Sector", "Dir", "Score", "Sweet Zone",
                   "CMP", "P5", "EPA Target", "Stop Loss", "R:R",
                   "Potential", "Status"]
        
        lines.append(tabulate(table_data, headers=headers, tablefmt="pipe"))
        lines.append(f"")
    
    lines.append(f"---")
    lines.append(f"")
    
    # ============== DETAILED ANALYSIS ==============
    lines.append(f"## Detailed Stock Analysis")
    lines.append(f"")
    
    for r in display_results:
        direction_icon = "BUY" if r['pattern_type'] == 'Bullish' else "SELL"
        star = "**" if r['confidence'] >= 70 else ""
        
        lines.append(f"### {star}{r['symbol']}{star} ({r['sector']}) -- "
                     f"{r['pattern_type']} Wolfe Wave | Score: {r['confidence']:.0f}/100")
        lines.append(f"")
        lines.append(f"**Signal:** {direction_icon} | **CMP:** Rs.{r['current_price']:.2f} | "
                     f"**Status:** {r['status']}")
        lines.append(f"")
        
        # 1. Wave Points
        lines.append(f"#### 1. Wolfe Wave Points")
        lines.append(f"| Point | Price | Role |")
        lines.append(f"|-------|-------|------|")
        if r['pattern_type'] == 'Bullish':
            lines.append(f"| P1 | Rs.{r['p1']:.2f} | Initial low |")
            lines.append(f"| P2 | Rs.{r['p2']:.2f} | First high |")
            lines.append(f"| P3 | Rs.{r['p3']:.2f} | Lower low (< P1) |")
            lines.append(f"| P4 | Rs.{r['p4']:.2f} | Lower high (P1 < P4 < P2) |")
            lines.append(f"| P5 | Rs.{r['p5']:.2f} | Sweet zone entry (near 1-3 line) |")
        else:
            lines.append(f"| P1 | Rs.{r['p1']:.2f} | Initial high |")
            lines.append(f"| P2 | Rs.{r['p2']:.2f} | First low |")
            lines.append(f"| P3 | Rs.{r['p3']:.2f} | Higher high (> P1) |")
            lines.append(f"| P4 | Rs.{r['p4']:.2f} | Higher low (P2 < P4 < P1) |")
            lines.append(f"| P5 | Rs.{r['p5']:.2f} | Sweet zone entry (near 1-3 line) |")
        lines.append(f"")
        
        # 2. Sweet Zone
        lines.append(f"#### 2. Sweet Zone Analysis")
        lines.append(f"- **P5 deviation from 1-3 line:** {r['p5_deviation']:.2f}%")
        lines.append(f"- **Sweet zone quality:** {r['sweet_zone_quality']}")
        lines.append(f"- **Line convergence factor:** {r['convergence']:.4f}")
        lines.append(f"- **Bars since P5:** {r['bars_since_p5']}")
        lines.append(f"")
        
        # 3. EPA Target
        lines.append(f"#### 3. EPA Target (Estimated Price at Arrival)")
        lines.append(f"- **50% target:** Rs.{r['target_50']:.2f}")
        lines.append(f"- **100% EPA target:** Rs.{r['epa']:.2f}")
        lines.append(f"- **Potential move:** {r['potential_pct']:.1f}%")
        lines.append(f"")
        
        # 4. Trade Setup
        lines.append(f"#### 4. Trade Setup")
        lines.append(f"| Parameter | Value |")
        lines.append(f"|-----------|-------|")
        lines.append(f"| Direction | {r['pattern_type']} ({direction_icon}) |")
        lines.append(f"| Entry Price | Rs.{r['entry_price']:.2f} |")
        lines.append(f"| Stop Loss | Rs.{r['stop_loss']:.2f} |")
        lines.append(f"| Target (50% EPA) | Rs.{r['target_50']:.2f} |")
        lines.append(f"| Target (100% EPA) | Rs.{r['epa']:.2f} |")
        lines.append(f"| Risk/Reward | {r['rr_ratio']} |")
        lines.append(f"| Invalidation | Rs.{r['invalidation']:.2f} |")
        lines.append(f"")
        
        # 5. Technical Indicators
        lines.append(f"#### 5. Technical Confirmation")
        rsi_status = ("Bullish zone" if 50 <= r['rsi'] <= 70 else
                     ("Neutral" if 40 <= r['rsi'] < 50 else
                     ("Oversold bounce" if r['rsi'] < 40 else "Overbought")))
        lines.append(f"- **RSI(14):** {r['rsi']:.1f} -- {rsi_status}")
        lines.append(f"- **MACD:** {r['macd_status']} | Histogram: {r['macd_histogram']}")
        lines.append(f"- **Volume (vs 20d avg):** {r['vol_ratio_20']:.2f}x")
        lines.append(f"- **OBV Trend:** {r['obv_trend']}")
        lines.append(f"- **Accumulation:** {'Yes' if r['is_accumulating'] else 'No'}")
        lines.append(f"- **EMA Alignment (20>50>200):** {'Bullish' if r['ema_alignment'] else 'Not aligned'}")
        lines.append(f"- **Above 200 EMA:** {'Yes' if r['above_ema200'] else 'No'}")
        lines.append(f"")
        lines.append(f"---")
        lines.append(f"")
    
    # ============== CATEGORIZED LISTS ==============
    lines.append(f"## Categorized Recommendations")
    lines.append(f"")
    
    # A. Top Bullish
    lines.append(f"### A. Top 10 Bullish Wolfe Wave Setups (Buy Candidates)")
    lines.append(f"")
    top_bull = [r for r in display_results if r['pattern_type'] == 'Bullish'][:10]
    if top_bull:
        for i, r in enumerate(top_bull):
            medal = ["1st", "2nd", "3rd"][i] if i < 3 else f"{i+1}."
            lines.append(f"{medal} **{r['symbol']}** ({r['sector']}) -- "
                        f"Score: {r['confidence']:.0f} | Sweet Zone: {r['sweet_zone_quality']} | "
                        f"Entry: Rs.{r['current_price']:.0f} | EPA: Rs.{r['epa']:.0f} | "
                        f"R:R {r['rr_ratio']} | Potential: {r['potential_pct']:.1f}%")
    else:
        lines.append(f"> No bullish Wolfe Wave setups found currently.")
    lines.append(f"")
    
    # B. Top Bearish
    lines.append(f"### B. Top 10 Bearish Wolfe Wave Setups (Sell/Short Candidates)")
    lines.append(f"")
    top_bear = [r for r in display_results if r['pattern_type'] == 'Bearish'][:10]
    if top_bear:
        for i, r in enumerate(top_bear):
            medal = ["1st", "2nd", "3rd"][i] if i < 3 else f"{i+1}."
            lines.append(f"{medal} **{r['symbol']}** ({r['sector']}) -- "
                        f"Score: {r['confidence']:.0f} | Sweet Zone: {r['sweet_zone_quality']} | "
                        f"Entry: Rs.{r['current_price']:.0f} | EPA: Rs.{r['epa']:.0f} | "
                        f"R:R {r['rr_ratio']} | Potential: {r['potential_pct']:.1f}%")
    else:
        lines.append(f"> No bearish Wolfe Wave setups found currently.")
    lines.append(f"")
    
    # C. Highest R:R setups
    lines.append(f"### C. Top 5 Highest Risk-Reward Setups")
    lines.append(f"")
    by_rr = sorted(display_results, key=lambda x: x['rr_value'], reverse=True)[:5]
    if by_rr:
        for i, r in enumerate(by_rr):
            lines.append(f"{i+1}. **{r['symbol']}** ({r['pattern_type']}) -- "
                        f"R:R {r['rr_ratio']} | Score: {r['confidence']:.0f} | "
                        f"Potential: {r['potential_pct']:.1f}%")
    lines.append(f"")
    
    # D. Sweet zone sniper entries
    lines.append(f"### D. Sweet Zone Sniper Entries (Excellent P5 precision)")
    lines.append(f"")
    sweet_entries = [r for r in display_results if r['sweet_zone_quality'] == 'Excellent'][:5]
    if sweet_entries:
        for i, r in enumerate(sweet_entries):
            lines.append(f"{i+1}. **{r['symbol']}** ({r['pattern_type']}) -- "
                        f"P5 deviation: {r['p5_deviation']:.2f}% | "
                        f"Score: {r['confidence']:.0f} | R:R {r['rr_ratio']}")
    else:
        lines.append(f"> No setups with 'Excellent' sweet zone precision found.")
    lines.append(f"")
    
    # E. Stocks to watch
    lines.append(f"### E. Watchlist - Patterns Forming (Score 40-50)")
    lines.append(f"")
    watchlist = [r for r in all_results 
                 if r['confidence'] >= 40 and r['confidence'] < 50]
    watchlist.sort(key=lambda x: x['confidence'], reverse=True)
    if watchlist[:5]:
        for i, r in enumerate(watchlist[:5]):
            lines.append(f"{i+1}. **{r['symbol']}** ({r['pattern_type']}) -- "
                        f"Score: {r['confidence']:.0f} | {r['status']} | "
                        f"Needs: momentum confirmation")
    else:
        lines.append(f"> No patterns in the forming stage currently.")
    lines.append(f"")
    
    # ============== METHODOLOGY ==============
    lines.append(f"---")
    lines.append(f"")
    lines.append(f"## Methodology")
    lines.append(f"")
    lines.append(f"### Wolfe Wave Detection Rules")
    lines.append(f"| Rule | Description |")
    lines.append(f"|------|-------------|")
    lines.append(f"| 5-Point Structure | P1-P2-P3-P4-P5 alternating swing highs/lows |")
    lines.append(f"| Convergence | 1-3 and 2-4 trendlines must converge (wedge) |")
    lines.append(f"| Sweet Zone | P5 must be within 3% of the 1-3 trendline extension |")
    lines.append(f"| EPA Target | Line from P1 through P4, projected to P5 time |")
    lines.append(f"| Minimum R:R | 1:2 or better required |")
    lines.append(f"| Recency | P5 must have formed within the last 25 bars |")
    lines.append(f"")
    lines.append(f"### Scoring System (100 points)")
    lines.append(f"| Component | Points | Criteria |")
    lines.append(f"|-----------|--------|----------|")
    lines.append(f"| Pattern Geometry | 40 | Sweet zone precision, convergence quality, symmetry, EPA potential |")
    lines.append(f"| Recency | 15 | How recently P5 formed (fresher = higher score) |")
    lines.append(f"| Price Action | 15 | Bounce/reversal from P5 area confirmation |")
    lines.append(f"| Volume/Momentum | 15 | RSI zone, volume exhaustion at P5, MACD trend |")
    lines.append(f"")
    lines.append(f"### Disclaimer")
    lines.append(f"This is a **quantitative screening tool**, not financial advice. "
                 f"Wolfe Waves are probabilistic patterns. Always:")
    lines.append(f"- Verify wave points on actual charts before trading")
    lines.append(f"- Confirm the 1-3 and 2-4 trendline convergence visually")
    lines.append(f"- Wait for price action confirmation at P5 (reversal candle)")
    lines.append(f"- Use proper position sizing (max 2-3% risk per trade)")
    lines.append(f"- Respect stop-loss levels strictly")
    lines.append(f"- Book partial profits at 50% EPA level")
    lines.append(f"")
    lines.append(f"---")
    lines.append(f"*Report generated by NSE Wolfe Wave Screener v1.0*")
    
    report_text = "\n".join(lines)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report_text)
    
    print(f"  [OK] Report saved to {output_file}\n")
    return report_text


def main():
    """Main execution flow."""
    start_time = time.time()
    
    # Get all symbols
    symbols = get_all_symbols()
    
    # Download data
    all_data = download_stock_data(symbols, period="1y", interval="1d")
    
    # Run analysis
    all_results = run_screening(all_data)
    
    # Filter and rank
    print(f"[3/4] Filtering and ranking...")
    ranked = filter_and_rank(all_results, min_confidence=50)
    
    bullish_count = len([r for r in ranked if r['pattern_type'] == 'Bullish'])
    bearish_count = len([r for r in ranked if r['pattern_type'] == 'Bearish'])
    
    print(f"  [OK] {len(ranked)} setups pass threshold "
          f"(Bullish: {bullish_count}, Bearish: {bearish_count})\n")
    
    # Generate markdown report
    report_path = "wolfe_wave_report.md"
    report = generate_report(ranked, all_results, output_file=report_path)
    
    # Generate Excel report
    excel_path = export_wolfe_wave_to_excel(ranked, all_results)
    
    elapsed = time.time() - start_time
    
    print(f"[4/4] Complete!")
    print(f"{'='*70}")
    print(f"  Screening completed in {elapsed:.1f} seconds")
    print(f"  Stocks scanned: {len(all_data)}")
    print(f"  Wolfe Wave setups found: {len(all_results)}")
    print(f"  Ranked (score >= 50): {len(ranked)}")
    print(f"    - Bullish setups: {bullish_count}")
    print(f"    - Bearish setups: {bearish_count}")
    print(f"  Markdown Report: {report_path}")
    print(f"  Excel Report: {excel_path}")
    print(f"{'='*70}")
    
    # Quick summary
    if ranked:
        print(f"\n>>> TOP WOLFE WAVE SETUPS:")
        for r in ranked[:7]:
            direction = "BUY " if r['pattern_type'] == 'Bullish' else "SELL"
            print(f"   {direction} {r['symbol']:<15} Score:{r['confidence']:5.0f} | "
                  f"CMP: Rs.{r['current_price']:.0f} | "
                  f"EPA: Rs.{r['epa']:.0f} | "
                  f"R:R {r['rr_ratio']} | "
                  f"{r['sweet_zone_quality']} sweet zone")
    else:
        print(f"\n[!] No Wolfe Wave patterns found meeting minimum criteria.")


if __name__ == "__main__":
    main()
