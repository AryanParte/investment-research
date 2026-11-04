# Third-party repository audit

Reviewed 2026-11-03. This is a static source review, not a security certification or a demonstration that upstream tests pass. Neither repository was installed as a skill/plugin, none of its scripts or tests was executed, and no brokerage connector was enabled. Public sources were downloaded into an isolated scratch directory with checkout hooks disabled. Python syntax was parsed using the standard-library AST parser without importing or executing upstream code.

## Decision

Do not install either complete plugin into the investment system. Use selected engineering practices from Matt Pocock's repository as project documentation. Adapt a small number of SEC ingestion and event-deduplication ideas from the day-trading repository only after addressing the limitations below. Build the portfolio ledger, performance accounting, research decision records, and delivery pipeline as first-party modules. Neither upstream repository provides the required end-to-end investment product.

The financial execution boundary must be enforced by absence: no broker SDK, trading MCP, transaction credentials, order endpoints, bank integration, or order-execution tool. A prompt that promises to ask before executing does not satisfy the user's prohibition on possessing execution capability.

## Exact versions reviewed

| Repository | Pinned revision | Observed maintenance | License |
|---|---|---|---|
| Jakeschincariol/day-trader-skill | `3d0f4ef6986f4984b7c6bd46f7ff4f87744c3abd` | One reachable commit, dated 2026-10-20; no tags; not archived | MIT, copyright 2026 Jake Schincariol |
| mattpocock/skills | `4ae2317ddb22b046e26455e4f9c9b3aaaf62212d` | 553 reachable commits; latest 2026-10-31; tagged through v1.3.2; not archived | MIT, copyright 2026 Matt Pocock |

These are source-history observations, not promises of future support. Both repositories are primarily controlled by their respective author. Public issue activity was also inspected, but popularity and issue volume are not correctness evidence.

Pinned source trees: [day-trader-skill](https://github.com/Jakeschincariol/day-trader-skill/tree/3d0f4ef6986f4984b7c6bd46f7ff4f87744c3abd), [mattpocock/skills](https://github.com/mattpocock/skills/tree/4ae2317ddb22b046e26455e4f9c9b3aaaf62212d).

## Day-trader-skill

### What it actually contains

The reviewed tree has 85 tracked files, 11 skill folders, 24 Python files including tests, and 315 statically discovered `test_*` functions. The scripts use Python's standard library. The disclosure-reader feature additionally invokes an externally installed `pdftotext` binary; the broker setup introduces an external Alpaca MCP package. There is no package lock, GitHub Actions workflow, or repository `.gitignore` in this revision. The Python source parsed without syntax errors. Tests were inspected, not executed.

Its README explicitly describes day trading, minute-bar entry/exit timing, order tickets, paper accounts, and an execution stage. It also distinguishes this repository from the author's separate, older `trader-skill` repository. We have not silently substituted that other repository for the one requested. [README](https://github.com/Jakeschincariol/day-trader-skill/blob/3d0f4ef6986f4984b7c6bd46f7ff4f87744c3abd/README.md)

### Useful components and disposition

| Component | Recommendation | What is useful / required changes |
|---|---|---|
| `trader-analyst/facts.py` | Adapt selected ideas after hardening | SEC company-facts/submissions sources; fiscal labels; restatement recognition; derived-Q4 labels; stale-facts warning; filing/exhibit links; offline fixtures. Add strict units/currency, filing-as-of cutoffs, broader taxonomy handling, metric-level provenance, cash-flow/debt/share-count coverage, and explicit unsupported states. |
| `trader-news/news.py` | Adapt selected ideas | Stable event IDs, deduplication, filing-item labels, first-seen state, primary-source links, timestamps, and fixture-driven parsing. Replace keyword materiality with evidence linked to each thesis; separate no-news, partial-data, and provider-failure states. |
| `trader-alerts` | Adapt state/idempotency concepts only | Avoid repeated alerts and preserve timestamps. Do not reuse stop/target/flatten-by-close behavior. Use a maintained calendar or explicit close timestamps rather than carrying over a finite holiday table. |
| `trader-risk`, `trader-budget` | Adapt concepts, not order pipeline | Exposure limits and transparent arithmetic are relevant. Replace daily-trade, stop-distance and order approval rules with combined-account concentration, scenario losses, cash constraints, and recommendation-only allocation proposals. |
| `trader-broker` and MCP example | Reject entirely | Broker setup and model-directed place/cancel/close calls violate the no-execution mandate. Paper defaults and confirmation prompts do not remove this capability. |
| `trader-entry`, `trader-exit`, `trader-scanner` | Reject from MVP | Intraday setups, stop/target timing and thousands-of-charts scanning add noise, data load and complexity outside the longer-term process. |
| `trader-timemachine` | Reject from MVP | Intraday resampling is not an estimate of a multi-year company's intrinsic value or a demonstrated investing edge. Simulation assumptions and sampling error would require separate validation. |
| `trader-pelosi` | Reject from MVP | Delayed disclosure tracking is peripheral; introduces PDF parsing and a narrative-following distraction. |

### Material limitations and security implications

1. **Execution capability is agent-mediated, not absent.** `ticket.py` states that it does not call a broker itself, but its SKILL instructs the model to call `place_stock_order`, `cancel_order_by_id`, and related tools. The example launches `uvx alpaca-mcp-server` without a version pin and enables `account,trading,stock-data`. Do not copy the skill, config, launcher, credentials, or order-shaped interfaces. [Broker skill](https://github.com/Jakeschincariol/day-trader-skill/blob/3d0f4ef6986f4984b7c6bd46f7ff4f87744c3abd/trader-broker/SKILL.md), [MCP config](https://github.com/Jakeschincariol/day-trader-skill/blob/3d0f4ef6986f4984b7c6bd46f7ff4f87744c3abd/trader-broker/claude_desktop_config.example.json)

2. **XBRL units can be silently substituted.** `facts_for` selects the requested unit if present, otherwise the first available unit. Output labels values as US dollars. This can mislabel values for non-USD reporting or unusual tags. It reads only the `us-gaap` namespace even while accepting 20-F/40-F forms. Reject unsupported units/taxonomies explicitly rather than silently substituting. [facts.py lines 131–138](https://github.com/Jakeschincariol/day-trader-skill/blob/3d0f4ef6986f4984b7c6bd46f7ff4f87744c3abd/trader-analyst/facts.py#L131-L138)

3. **Historical reproducibility needs point-in-time data.** `periods` deliberately selects the latest restatement, with no as-of-publication cutoff. That is reasonable for a current restated view, but creates look-ahead bias if used to evaluate past investment decisions. Keep both period end and publication/availability time, plus the exact source version used. [facts.py lines 141–163](https://github.com/Jakeschincariol/day-trader-skill/blob/3d0f4ef6986f4984b7c6bd46f7ff4f87744c3abd/trader-analyst/facts.py#L141-L163)

4. **Quarter and EPS derivation is heuristic.** It classifies durations as 80–100 days, derives Q4 by subtracting three quarters, and allows this for diluted EPS. Annual EPS minus quarterly EPS is only approximate because share denominators differ; the header acknowledges that. New code should distinguish reported and estimated metrics individually and validate contiguous periods and share bases. [facts.py](https://github.com/Jakeschincariol/day-trader-skill/blob/3d0f4ef6986f4984b7c6bd46f7ff4f87744c3abd/trader-analyst/facts.py#L166-L210)

5. **News operational states need redesign.** SEC may be skipped if identification is missing; source errors appear as notes; the main exit code is based on whether new items exist. Thus a clean no-news result and provider failure are not a sufficient delivery-health contract. `news.json` is rewritten directly, without a transactional delivery acknowledgement. Use explicit success/degraded/failure state, atomic writes, and a separate delivered cursor so generating a report never falsely means it reached the phone. [news.py lines 512–542](https://github.com/Jakeschincariol/day-trader-skill/blob/3d0f4ef6986f4984b7c6bd46f7ff4f87744c3abd/trader-news/news.py#L512-L542)

6. **Free unofficial prices are unsuitable as the sole dependable feed.** The README admits Yahoo's endpoint is unofficial and can lag/change/rate-limit. The alerts source also notes a Stooq endpoint had returned 404. Provider reliability, usage rights, historical adjustments, corporate actions and quote freshness require independent validation. [README data warning](https://github.com/Jakeschincariol/day-trader-skill/blob/3d0f4ef6986f4984b7c6bd46f7ff4f87744c3abd/README.md), [alerts source](https://github.com/Jakeschincariol/day-trader-skill/blob/3d0f4ef6986f4984b7c6bd46f7ff4f87744c3abd/trader-alerts/alerts.py)

7. **It is not a correct portfolio-accounting engine.** The fill logger uses floats and rounded share counts, and operates on mutable portfolio JSON. It does not supply the required reconciled multi-account event ledger, contributions versus internal transfers, corporate-action history, matched-cash-flow benchmarks, or robust tax-lot accounting. Do not repurpose it as the source of truth. [ticket.py fill handling](https://github.com/Jakeschincariol/day-trader-skill/blob/3d0f4ef6986f4984b7c6bd46f7ff4f87744c3abd/trader-broker/ticket.py#L407-L437)

8. **Security hardening remains our responsibility.** Network reads have timeouts and SEC request pacing, but multiple independent workers need a shared request limiter. Response-size limits, redirect policy, schema validation, private-data exclusion, log redaction, and a versioned source archive need to be added. Headlines and filings are untrusted content, never instructions to an agent. No obvious arbitrary-shell execution was found in the reviewed financial-data scripts; this is a bounded static observation, not a malware guarantee.

### Maintenance judgment

The offline fixtures, reproducible examples, tests around stale SEC data and restatements, and plain-language caveats are useful. One published source commit and no CI/release history provide little evidence of ongoing maintenance. We should own any adapted code and its tests, not depend on the author responding to production incidents.

## mattpocock/skills

### What it actually contains

This is primarily a collection of engineering instructions and templates, not an application library. The reviewed tree has 184 tracked files. Package version is 1.3.2. `package.json` has two development-only dependencies for Changesets release management; the npm lock records 111 transitive packages and no `hasInstallScript` flags. Consuming selected Markdown guidance needs no npm install or runtime dependency. The pinned tree has release/issue-management Actions, but no dedicated behavioral skill-evaluation or application-test CI workflow. [Package](https://github.com/mattpocock/skills/blob/4ae2317ddb22b046e26455e4f9c9b3aaaf62212d/package.json), [workflows](https://github.com/mattpocock/skills/tree/4ae2317ddb22b046e26455e4f9c9b3aaaf62212d/.github/workflows)

### Selected practices

| Skill | Recommendation for this project |
|---|---|
| `domain-modeling` | Adopt precise definitions for contribution, transfer, transaction, valuation, return, estimate, thesis, insight, and delivery acknowledgement; record consequential architecture decisions. |
| `codebase-design` | Adopt small, testable public interfaces around ledger, ingestion, performance, research, briefing and delivery; avoid speculative agent layers. |
| `tdd` | Adapt behavior-first vertical slices and independent expected results, especially accounting and failure handling. The upstream demand to ask the user to approve every test boundary is unnecessary here: the user explicitly delegated engineering choices. |
| `diagnosing-bugs` | Adopt reproducible failures, minimized cases, competing hypotheses, targeted redacted diagnostics, and regression checks. Do not collect sensitive financial records through its terminal capture template. |
| `code-review` | Adapt separate checks for product requirements and engineering quality. Add explicit privacy and no-execution boundary review. |
| `research` | Adopt primary-source evidence, dated findings, exact source versions, and reproducible artifacts. Do not require a new subagent for every trivial question. |
| `to-spec` | Adapt the specification structure into repository-local docs. Do not copy conversation details/holdings into issues by default; avoid automatic publishing. |
| `retro` | Defer until the system has meaningful operational history; evaluate proposed process changes with measurable outcomes. |
| `implement-spec`, `wayfinder`, `chief-of-staff`, `software-factory` | Defer. A single maintainable pipeline is sufficient for the MVP; elaborate multi-agent task graphs add cost and operational complexity. |
| `git-guardrails-claude-code`, `setup-pre-commit`, other `misc` | Reject as dependencies. Upstream explicitly labels this bucket frozen and unmaintained. Use our own CI/branch controls and normal tooling. |

Selected source paths are under [skills/engineering at the audited revision](https://github.com/mattpocock/skills/tree/4ae2317ddb22b046e26455e4f9c9b3aaaf62212d/skills/engineering).

### Security and maintenance caveats

- **Do not run `scripts/link-skills.sh`.** It writes global skill folders, includes in-progress skills, and removes an existing non-symlink destination using `rm -rf`. This is a maintainer-only script, not the least-privilege selective installation needed here. [Source](https://github.com/mattpocock/skills/blob/4ae2317ddb22b046e26455e4f9c9b3aaaf62212d/scripts/link-skills.sh#L45-L60)
- **Do not auto-update prompt authority from upstream.** The README advertises plugins that update automatically. Pin reviewed guidance and review diffs before adopting new versions; a changed skill can instruct agents to alter files, publish issues, commit or merge even without a new runtime dependency. [README](https://github.com/mattpocock/skills/blob/4ae2317ddb22b046e26455e4f9c9b3aaaf62212d/README.md)
- **Do not treat the Git regex hook as a security boundary.** It matches textual patterns, depends on `jq`, and misses alternate command forms. The project's own frozen-misc note records reports of fail-open behavior and `git -C` bypasses. [Frozen-misc policy](https://github.com/mattpocock/skills/blob/4ae2317ddb22b046e26455e4f9c9b3aaaf62212d/.out-of-scope/frozen-misc-skills.md)
- **Do not copy release permissions wholesale.** The release workflow grants contents/PR writes and runs third-party Actions by moving version tags. Our CI should use narrowly scoped job permissions, SHA-pinned Actions, no personal portfolio data in artifacts, and no deployment secrets in pull-request validation. [Release workflow](https://github.com/mattpocock/skills/blob/4ae2317ddb22b046e26455e4f9c9b3aaaf62212d/.github/workflows/release.yml)
- **Promoted and experimental skills differ.** Upstream calls `in-progress` beta and subject to change or removal; `misc` is explicitly unmaintained. Recent source activity and release tags support active maintenance of promoted skills, not all folders. [Scope](https://github.com/mattpocock/skills/blob/4ae2317ddb22b046e26455e4f9c9b3aaaf62212d/SCOPE.md), [beta policy](https://github.com/mattpocock/skills/blob/4ae2317ddb22b046e26455e4f9c9b3aaaf62212d/skills/in-progress/README.md)

## Licensing and adoption controls

Both MIT licenses permit modification and reuse, including in a private/proprietary project, while requiring preservation of their copyright and permission notice for copied or substantial adapted material. If code or substantial prompt text is copied, record its exact upstream SHA, original path, modifications, and license notice in `THIRD_PARTY_NOTICES.md`. General engineering ideas can be implemented independently; do not claim the upstream software is installed when it is merely a design influence.

MIT licensing of the code does not grant redistribution rights to Yahoo, Nasdaq, or other market-data content. Review each data provider's terms separately before hosting or redistributing data. No personal portfolio data belongs in copied fixtures, GitHub logs or uploaded test artifacts.

Licenses: [Jake Schincariol MIT](https://github.com/Jakeschincariol/day-trader-skill/blob/3d0f4ef6986f4984b7c6bd46f7ff4f87744c3abd/LICENSE), [Matt Pocock MIT](https://github.com/mattpocock/skills/blob/4ae2317ddb22b046e26455e4f9c9b3aaaf62212d/LICENSE).

## Audit limits

This review inspected source trees, dependency declarations/lock metadata, scripts, selected instructions, fixture tests, licenses, commit history, and issue samples. It did not run upstream tests, install dependencies, audit third-party servers, verify all external claims in repository prose, scan every dependency against a vulnerability database, or exercise live market APIs. Any adopted code must pass our own tests and security checks before production use. None of these repositories proves a ChatGPT mobile notification, dashboard-delivery, or shared-context integration.
