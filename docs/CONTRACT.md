# Initial module contract

Python standard library, Python >=3.11. No remote or model calls in core.

`accounting.py`: Decimal-based validated event ledger and valuation/performance.
`briefing.py`: schema-validated research, deterministic short report + JSON context.
`storage.py`: local append-only versioned thesis/decision records.
`cli.py`: import, reconcile, demo, brief, serve commands. Root handles CLI/report/UI.

Normalize manual CSV events with columns:
`id,date,account,type,symbol,quantity,price,amount,fee,transfer_id`.
Use opaque account aliases `taxable` and `roth`, not account numbers.
Types: DEPOSIT, WITHDRAWAL, BUY, SELL, DIVIDEND, INTEREST, FEE, TRANSFER_IN,
TRANSFER_OUT, SPLIT. Dollar values are USD; positive amount is magnitude.
DEPOSIT/WITHDRAWAL are external portfolio flows; paired transfers are internal
at combined level but external per account. BUY/SELL amount is quantity*price
and fee separately. Refuse duplicate IDs, negative shares/cash, unpaired transfers,
unsupported events, malformed values. Fractional quantities supported.

End-of-day price CSV: `date,symbol,close,source,as_of`. Explicit raw close; split
events adjust shares. Do not double-count split-adjusted prices. Benchmark CSV:
`date,total_return_index,source,as_of` (reinvestment already included).

Module API is to be established by accounting owner and communicated to root.
No UI should imply live account sync, notification delivery, or fresh real quotes
when a synthetic fixture is displayed. Fixtures use fictional company tickers.
