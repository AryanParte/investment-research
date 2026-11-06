# Robinhood MCP read-only review

Reviewed **November 5, 2026, approximately 7:10 p.m. America/New_York** (November 6, 00:10 UTC). Public documentation and unauthenticated HTTPS metadata only. No installation, login, OAuth authorization, account opening, tool execution, or financial action occurred. This file contains no personal account data.

**Decision: do not connect the trading MCP yet. Broker-enforced read-only authorization has not been verified. Continue with manual imports.** This is an unresolved permission requirement, not a claim that Robinhood cannot support it.

## Official documentation

Robinhood identifies `https://agent.robinhood.com/mcp/trading` as its external-agent MCP endpoint. Its documentation says the connection can read all Robinhood accounts, account numbers, positions, balances, transactions, and order history; trading is restricted to the dedicated Agentic account. Therefore existing Individual and Roth accounts appear to be within the stated read coverage. **Roth inclusion is an inference from “all” accounts, not a verified account-specific API test.** The page does not document selectable account-only read scopes. It describes authentication prompting the customer to open a dedicated MCP account; whether read-only onboarding can bypass this is unknown. [Onboarding an external agent](https://robinhood.com/us/en/support/articles/agentic-trading-overview/)

The published external-agent tool inventory includes:

| Research/account reads | Financial mutation capabilities also documented |
| --- | --- |
| `get_accounts`, `get_portfolio` | `place_equity_order`, `cancel_equity_order` |
| `get_equity_positions`, `get_equity_tax_lots`, `get_equity_orders` | `place_option_order`, `exercise_option` |
| `get_realized_pnl`, `get_pnl_trade_history` | `place_crypto_order`, `place_advanced_order` |
| Quotes, financials, earnings, SEC filings | Additional order cancellations and watchlist/settings mutations |

The same documentation says trade approvals for external MCP accounts default **off**, are still rolling out, and may be unavailable. When enabled, orders require manual placement in Robinhood. This setting is a trade-approval control, not documentation of a separate read-only authorization grant. [Trading with your agent](https://robinhood.com/us/en/support/articles/trading-with-your-agent/)

## Public authorization metadata observed

Unauthenticated GETs returned HTTP 200 from these official endpoints:

- [Protected-resource metadata](https://agent.robinhood.com/.well-known/oauth-protected-resource/mcp/trading): resource and authorization server both identify the trading MCP; `scopes_supported` was `["internal"]`, and bearer tokens use the authorization header.
- [Authorization-server metadata](https://agent.robinhood.com/.well-known/oauth-authorization-server/mcp/trading): `scopes_supported` was also `["internal"]`; authorization-code and refresh-token grants, PKCE `S256`, and an OAuth registration endpoint were advertised.

The corresponding root metadata URLs returned the same values. A plain GET of `/mcp/trading` returned HTTP 405; that is not evidence about an authenticated tool's permissions. No token or registration request was made.

**Interpretation:** no granular read-only scope is advertised in the metadata reviewed. The name `internal` does not establish its privileges. An undocumented server-side account permission might exist, but its existence and enforcement remain unverified. Metadata is evidence of the advertised authorization surface, not a security certification.

## Conditions before any connection

Robinhood must document or demonstrate a credential whose broker-enforced authorization excludes every financial mutation, including orders, cancellations, exercises, transfers, deposits, and withdrawals. It must cover the existing account types without requiring an agent trading account or trading authorization. A prompt saying “read only,” hidden client tools, an unfunded account, approval-on settings, or a proxy retaining a more powerful token does not meet this project's boundary.

Ask Robinhood support for the precise permission/scope identifier, the supported no-trading onboarding path, and authoritative enforcement documentation. Also verify per-account selection and the completeness/pagination of cash flows, dividends, fees, corporate actions, transfers, and IRA contribution-year information. Position snapshots and order history alone do not establish a complete performance ledger. Do not attempt a live financial mutation to test rejection; require a documented sandbox or other non-executing verification mechanism first.

## Supported fallback

Robinhood documents downloadable CSV activity reports for brokerage and retirement accounts through **Account → Reports and statements → Reports → Generate new report**, with account/date selection. Generation may take up to 24 hours. Futures, crypto, and spending activity are excluded. Account statements can provide endpoint balances for reconciliation. [Finding your reports and statements](https://robinhood.com/us/en/support/articles/finding-your-reports-and-statements/)

Import exported records into the explicitly selected private runtime store, map account numbers to local aliases, and keep raw exports, reports, logs, credentials, and personal holdings out of Git and CI artifacts. No brokerage credential is necessary for this path. Any broader account-data automation remains disabled until the permission requirement is satisfied.
