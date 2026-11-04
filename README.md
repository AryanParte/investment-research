# Investment Research

A private, recommendation-only portfolio accounting and research system.
**No brokerage, banking, payments, financial credentials or trade execution.**

Status: **local synthetic-data MVP**. A separate owner-private Sites pilot tests
cloud report retrieval. Live data ingestion, scheduled production generation,
ChatGPT mobile push, in-chat widgets and unattended maintenance are not yet
verified. A report being generated does not mean it was delivered.

## Run without installing dependencies

Requires Python 3.11 or newer. Runtime uses the Python standard library; the
dashboard uses browser JavaScript, CSS and SVG without external libraries.

```sh
python3 -m unittest discover -s tests -v
python3 scripts/check_boundaries.py
python3 scripts/run.py demo
python3 scripts/run.py serve
```

Open `http://127.0.0.1:8765`. All sample companies, prices, events and benchmark
values are fictional. The historical sample date stays fixed; generation never
relabels old observations as current. The preview binds only to loopback and has
no write API. Stop it with Ctrl-C.

## What works locally

- Validated manual normalized CSV inputs, Decimal accounting, fractional shares,
  fees, dividends, splits and paired cash transfers across account aliases.
- Combined/per-account valuations and cash-flow-adjusted performance, a
  cash-flow-matched total-return benchmark and flow-adjusted maximum drawdown.
- Explicit inception-history attestation and optional statement reconciliation.
- Immutable report IDs and source hashes; reports retain their source dates.
- Bounded short brief, expandable detail, allocation and return charts, and
  hypothetical contribution scenarios that do not move money.
- Facts, estimates, assumptions and opinions are distinct. Material claims need
  provenance and an explanation of thesis impact.
- Append-only local research/decision history; failure/freshness detection.

## Important calculation limits

Daily TWR is an **estimate using an end-of-day external-flow convention**. Exact
intraday cash-flow valuations are not available. Benchmark observations must be a
total-return index; raw price-only S&P 500 quotes are not interchangeable. Returns
are pre-tax. XIRR, tax-lot accounting, wash-sale calculations, corporate actions
other than splits, non-USD assets, margin and options are not implemented.
Unsupported events fail explicitly. Sample data never establish actual investment
performance. Endpoint reconciliation does not independently prove complete history.

## Private manual imports

Read [the import specification](docs/IMPORTS.md). Place private files under
`private/` (ignored by Git) or a separate protected directory. The MVP does not
pretend to parse arbitrary Robinhood exports. A sanitized sample export is needed
to build and validate a broker-specific adapter.

```sh
python3 scripts/run.py build --input private/import-001 --output runtime/briefings --as-of 2026-11-03T22:00:00+00:00 --complete-history
python3 scripts/run.py health --directory runtime/briefings
```

Do not assert complete history unless the import starts at inception and includes
all relevant accounts and events. Never put personal reports in source control,
CI artifacts, issue text or logs. Do not deploy the local preview publicly.

## Project map

```text
src/investment_research/   deterministic accounting, research, context and reports
samples/                  fictional fixtures only
tests/                    expected-value, failure, privacy and pipeline tests
web/                      buildless responsive dashboard
scripts/                  local entry point and repository boundary checks
docs/                     architecture, source audit, roadmap and operating plan
.github/workflows/        synthetic-data CI and weekly engineering checks
integrations/             sample-only hosted read-tool pilot source (when built)
private/ runtime/ dist/   ignored local input and generated output
```

Start with [architecture](docs/ARCHITECTURE.md), [verification](docs/ACCEPTANCE.md),
[operations](docs/OPERATIONS.md), and [third-party review](docs/REPOSITORY_AUDIT.md).

## Development

Use `codex/` branches, small pull requests, CI and review before merging. Do not
auto-merge dependency or agent changes. No production-deploy workflow is enabled
until private hosting, authorization and rollback tests pass. The budget the user
mentions in chat is an input to a scenario, never permission to schedule purchases.

This repository must remain private. GitHub hosts code and synthetic fixtures;
private runtime financial records belong in a separate access-controlled store.
