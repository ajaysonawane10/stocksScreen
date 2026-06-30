const path = require('path');
const NSE_MODULE = path.join(
    process.env.APPDATA || process.env.HOME,
    'npm', 'node_modules', 'stock-nse-india'
);
const { NseIndia } = require(NSE_MODULE);

async function main() {
    const args = process.argv.slice(2);
    let symbols = [];
    let startDate = new Date();
    startDate.setFullYear(startDate.getFullYear() - 1);
    let endDate = new Date();

    // Parse args: symbols come before flags
    let i = 0;
    while (i < args.length) {
        if (args[i] === '--start') {
            startDate = new Date(args[i + 1]);
            i += 2;
        } else if (args[i] === '--end') {
            endDate = new Date(args[i + 1]);
            i += 2;
        } else {
            symbols.push(args[i]);
            i++;
        }
    }

    if (symbols.length === 0) {
        process.stderr.write('No symbols provided\n');
        process.exit(1);
    }

    const nse = new NseIndia();
    const results = [];

    for (const symbol of symbols) {
        try {
            const historicalData = await nse.getEquityHistoricalData(symbol, {
                start: startDate,
                end: endDate
            });

            // historicalData is an array of { data: [...] } chunks
            const rows = [];
            for (const chunk of historicalData) {
                for (const r of (chunk.data || [])) {
                    // API returns lowercase ch* fields
                    const close = r.chClosingPrice || r.CH_CLOSING_PRICE;
                    const date  = r.mtimestamp     || r.CH_TIMESTAMP;
                    if (close && date) {
                        rows.push({
                            date:   date,
                            open:   r.chOpeningPrice   || r.CH_OPENING_PRICE   || close,
                            high:   r.chTradeHighPrice || r.CH_TRADE_HIGH_PRICE || close,
                            low:    r.chTradeLowPrice  || r.CH_TRADE_LOW_PRICE  || close,
                            close:  close,
                            volume: r.chTotTradedQty   || r.CH_TOT_TRADED_QTY  || 0
                        });
                    }
                }
            }

            results.push({ symbol, rows });
        } catch (err) {
            // Include failed symbol with empty rows
            results.push({ symbol, rows: [], error: err.message });
        }
    }

    process.stdout.write(JSON.stringify(results));
}

main().catch(err => {
    process.stderr.write(`Fatal: ${err.message}\n`);
    process.exit(1);
});
