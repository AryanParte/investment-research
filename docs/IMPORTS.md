# Manual input contract

No financial account integration is required. Import locally; never paste account
credentials. Use opaque account aliases such as `taxable` and `roth`. Strip account
numbers and identifying statement headers before ingestion.

An input directory contains `transactions.csv`, `prices.csv`, `benchmark.csv`,
`research.json`, and optionally `statement.json`. The `samples/` files demonstrate
the exact supported schema. CSV headers and event order are validated. Files must
represent the complete history from zero balances for performance calculations.

## Events

`id,date,account,type,symbol,quantity,price,amount,fee,transfer_id`

Dates are ISO calendar dates; USD values are positive magnitudes encoded as plain
decimal strings. Stable event IDs prevent duplicate import. BUY and SELL are
historical records, not instructions; amount must equal quantity × price, with
fee separate. Same-date event order is preserved. SPLIT quantity is the multiplier
(2 for 2:1); use raw closes, not split-adjusted closes. A dividend reinvestment is
a DIVIDEND and separate BUY. Paired TRANSFER_OUT/TRANSFER_IN must match date,
amount and transfer ID. They cancel at combined scope. Transfers here are only
records; do not interpret a taxable-to-IRA transfer as tax advice or IRA eligibility.

Unknown broker codes, mergers, spin-offs, return of capital, in-kind transfers,
options, margin, and multiple currencies require an explicit adapter extension.
Do not guess their accounting. Deposits and withdrawals count as external flows;
dividends and interest count as investment income. IRA contribution tax years,
rollovers, conversions and employer/broker promotional credits need separate
classification before contribution-room or tax reporting can be offered.

## Prices and benchmark

Prices: `date,symbol,close,source,as_of`. Raw USD close; timezone-aware provenance.
Benchmark: `date,total_return_index,source,as_of`. Same valuation dates and currency.
The benchmark index must already include reinvestment; never add dividends twice.
No silent price forward-fill. Observations and source timestamps after the chosen
analysis time are rejected. Calendar-day freshness is a conservative MVP check,
not a complete exchange holiday calendar. Missing benchmark dates can hide gaps;
production must validate against a trusted exchange calendar.

For real S&P 500 comparison use a licensed total-return series, or explicitly name
an investable fund total-return proxy and account for its fees. No current market
data license/provider has been configured. SEC filings are primary fundamental
sources, not a substitute for historical prices and dividend/corporate-action data.

## Research and statement

`research.json` must have `dataset: "imported"` for private imports, timestamped
HTTPS source records and classified claims. Facts and estimates require source IDs;
material claims require `thesis_impact`. Source linkage is not independent factual
verification: research needs primary-source review. Estimates retain their original
vintage. Do not overwrite them after an earnings release.

Statement: valuation_date and each account's cash and exact holding quantities.
Reconciliation matches imported endpoint records to the supplied statement; it
does not independently contact or authenticate a broker. Differences block report
publication instead of being silently rounded away.

Production storage must separate `ledger_imported_at`, `holdings_confirmed_at`,
`prices_as_of`, `benchmark_as_of`, `research_retrieved_at`, and `generated_at`.
A fresh quote does not prove fresh holdings. Manual updates are required after
trades or cash movements; the system must display last-confirmed holdings until then.
