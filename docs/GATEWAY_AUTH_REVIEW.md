# Robinhood gateway authorization review

Reviewed **November 5, 2026, 7:54 p.m. America/New_York** (November 6, 00:54 UTC).
Evidence: official Robinhood pages, two unauthenticated metadata GETs, and the
official MCP specification. No OAuth registration, authorization request, login,
token exchange, account creation, authenticated tool call, or financial action.

## Decision under the updated instruction

The user's updated instruction permits evaluating a separately administered
gateway with broader upstream credentials and an enforced read-only downstream
surface. This supersedes the native-read-only-scope prerequisite in
[ROBINHOOD_READ_ONLY_REVIEW.md](ROBINHOOD_READ_ONLY_REVIEW.md); its dated factual
observations remain useful. **Account authorization is still not granted.**

A gateway is technically plausible, but arbitrary hosted-client onboarding and
the exact granted permissions have not been verified. Proceed with an isolated,
mock-tested design. Do not describe the upstream credential as read-only or claim
Robinhood has approved this particular gateway.

## What Robinhood documents

The official external-agent endpoint is
`https://agent.robinhood.com/mcp/trading`. Robinhood says it reads all accounts,
account numbers, positions, balances, transactions, and order history. Trades are
limited to the dedicated Agentic account. Existing Individual and Roth coverage
is suggested by “all” accounts; Roth-specific fields and completeness remain
untested. Authentication is described as prompting an MCP-account opening flow.
A read-only path that avoids creating that account is not documented.

Robinhood supports external agents, several named platforms, and localhost
platforms; it directs other platforms to support. This establishes external-client
support, not unrestricted acceptance of every custom hosted OAuth client or
redirect URI. [Official external-agent onboarding](https://robinhood.com/us/en/support/articles/agentic-trading-overview/)

The published external-agent inventory includes `get_accounts`, `get_portfolio`,
`get_equity_positions`, `get_equity_orders`, `get_equity_tax_lots`,
`get_realized_pnl`, and `get_pnl_trade_history`. It also includes order placement,
cancellation, option exercise, and other mutations. Thus the upstream product is
not a read-only API. Trade approvals for external MCP accounts default **off** and
are still rolling out. When enabled, they require manual order placement; they do
not establish a read-only OAuth grant. The page says agents cannot transfer,
stake, or lend crypto, but that statement does not define every privilege of a
particular bearer token. [Official tool inventory and approval controls](https://robinhood.com/us/en/support/articles/trading-with-your-agent/)

## Public OAuth metadata observed

Both endpoints returned HTTP 200 without credentials:

| Field | Observed value |
| --- | --- |
| Resource / issuer | `https://agent.robinhood.com/mcp/trading` |
| Advertised scopes | `["internal"]` |
| Bearer token transport | Authorization header |
| Authorization endpoint | `https://robinhood.com/oauth` |
| Grant types | `authorization_code`, `refresh_token` |
| Response type / PKCE | `code` / `S256` |
| Token endpoint | `https://api.robinhood.com/oauth2/token/` |
| Token endpoint client authentication | `none` |
| Registration endpoint | `https://agent.robinhood.com/oauth/trading/register` |

Sources: [protected-resource metadata](https://agent.robinhood.com/.well-known/oauth-protected-resource/mcp/trading),
[authorization-server metadata](https://agent.robinhood.com/.well-known/oauth-authorization-server/mcp/trading).

`internal` is opaque: metadata neither enumerates its actual permissions nor
advertises a granular read scope. `none` describes client authentication at the
token endpoint; it does **not** mean unauthenticated portfolio access. The
registration endpoint is advertised but was not invoked. No client-credentials
grant was advertised. Registration acceptance, required metadata, allowed callback
URIs, consent text, access-token lifetime/audience, refresh rotation, and revocation
behavior remain unknown. No exact token privileges can be reported before an
approved consent flow and vendor documentation establish them.

## Proposed authorization separation

This is a project design, not a verified Robinhood deployment:

1. A separately administered collector acts as the Robinhood MCP/OAuth client.
   Only this service may hold upstream access/refresh tokens. Its host, secret
   store, IAM, source promotion, and deployment controls must be outside Codex's
   shell, filesystem, environment, and existing Sites administration identity.
2. The collector has a fixed allowlist of reviewed account/holdings/balance/history
   reads and fixed upstream destinations. It accepts no arbitrary URL, HTTP call,
   MCP method, tool name, account selector, or unvalidated arguments from agents.
   Every financial mutation, including orders, cancellations, exercises, deposits,
   withdrawals, and transfers, is denied; approval toggles are not the boundary.
3. The collector publishes minimized, validated snapshots to a private store.
   Account numbers remain inside the collector; downstream records use aliases.
   The ChatGPT plugin and portfolio engine can retrieve snapshots but cannot
   trigger broker requests, obtain upstream tokens, modify the allowlist, or
   deploy a replacement collector. New upstream tools remain denied by default.
4. Downstream access uses independent authorization. Never forward Robinhood
   tokens through the plugin or reuse a downstream bearer token upstream. MCP's
   authorization rules distinguish resource audiences, and its security guidance
   warns about token passthrough and confused-deputy proxy designs.
   [MCP authorization](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization),
   [MCP security guidance](https://modelcontextprotocol.io/docs/2025-11-25/tutorials/security/security_best_practices)

This is **gateway-enforced read-only access**. A compromise of the separately
credentialed collector may expose broader upstream privileges. The architecture
does not turn an unrestricted upstream token into broker-enforced read-only access.

## Evidence required before sign-in

- Confirm Robinhood accepts the chosen custom client and callback, and clarify
  whether onboarding requires opening an Agentic/MCP account. Do not create one
  as an incidental integration step.
- Present the concrete deployment/IAM separation, finalized read allowlist,
  retention/redaction policy, and actual upstream consent wording. If the consent
  screen does not enumerate privileges, label the missing details and obtain
  authoritative clarification; do not infer a permission list from `internal`.
- Verify that Codex cannot access secrets, change policy, assume the collector's
  identity, invoke an alternate credentialed path, or deploy a bypass. Demonstrate
  denials with mocks or a documented non-executing sandbox only.
- Establish per-account schemas, pagination, timestamps, and cash-flow coverage.
  Published tool names do not prove complete deposits, withdrawals, dividends,
  fees, corporate actions, internal transfers, or IRA contribution-year records.
- Obtain explicit authorization for account linking. The user signs in directly
  on Robinhood's supported page; no passwords, codes, or tokens enter chat.

Until these steps are complete, the collector remains uncredentialed and manual
imports remain the available portfolio-data path. No broker connection, scheduled
collection, credential isolation, or live permission enforcement is claimed tested
by this document.
