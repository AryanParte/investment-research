# Read-only synthetic report gateway

This gateway is a **sample-only integration pilot**. It has no account connection,
market feed, model call, storage writer, network client, or financial action. Reads
return one immutable report; a successful call does not refresh the data or prove
that a scheduled notification reached a phone.

`lib/research-tools.ts` contains the transport-independent handler. The Next/Vinext
route at `app/mcp/route.ts` imports the generated `lib/sample-report.json` and binds
the private dashboard URL. The report must be schema version 1 and marked `sample`.
This validation is a format guard, not a substitute for inspecting the fixture to
ensure that no real personal data was included.

## Trust boundary

Sites authenticates the caller and checks private Site access before forwarding a
request. Every `tools/call` and optional `resources/read` also requires nonempty
`oai-authenticated-user-id` and `oai-authenticated-user-email` headers. No identity is
logged or returned. This contract is only secure behind the Sites gateway. Never
expose the handler through a public origin that accepts caller-forged headers.

Metadata-only discovery and listing work without injected identity to support
platform provisioning. They disclose tool schemas and an optional fictional
resource identifier, never the report contents. The deployment must remain private.
Production use would require a reviewed account authorization and private data
storage design; this pilot explicitly reports real accounts as unsupported.

Requests are bounded to 32 KiB; compressed and non-JSON requests, unsupported
methods, extra tool arguments, arbitrary resource URLs, and unknown report versions
are rejected. All responses use private/no-store caching. Tool annotations describe
the implementation but are not the security mechanism.

## Protocol and tools

- `server/discover`: MCP 2026-07-28 stateless discovery.
- `initialize`: limited legacy compatibility for 2025-03-26/2025-06-18.
- `tools/list` and `tools/call`: six read-only tools with structured output schemas.
- `get_latest_briefing`: blocked personal-data response; no report or allocations.
- `get_demo_briefing(acknowledge_synthetic: true)`: explicit fictional demo only.
- `get_briefing(report_id, acknowledge_synthetic: true)`: retrieve only that exact
  fictional version; never silently substitute or use as personal evidence.
- `get_holding_research(symbol, report_id, acknowledge_synthetic: true)`: fictional holding evidence, matching
  thesis versions, and their sources. If several thesis versions are present, retain
  them and mark the selection ambiguous instead of choosing one by guesswork.
- `get_system_status`: explicit capabilities, freshness, and unverified delivery state.
- `assess_allocation_readiness(amount, currency, account_scope)`: always blocked in
  this pilot. It returns missing personal/research evidence and an empty allocation
  list. Caller-supplied evidence, eligibility and override fields are rejected.

Discovery, tool descriptions and every tool result carry the evidence contract.
The model is instructed to check status/readiness before personal advice, never
infer current holdings or IRA room from conversation history, and distinguish
product-source citations from evidence for a personal allocation. These instructions
reduce risk but cannot enforce a host model's prose. Conversation evaluation is separate.

The envelope distinguishes immutable `report_as_of` from runtime `served_at`.
The 72-hour review flag is a pilot display rule, not a claim that any market data is
current. Future-dated fixtures are labeled. Unknown or missing evidence stays missing.

## Optional in-chat UI

Pass `widgetHtml` to `createResearchServer` only after generating a trusted,
self-contained HTML artifact from the same sample report. The server then exposes
`resources/list` and authenticated `resources/read`, and attaches the resource URI
only to the two briefing tools. Its MIME type is `text/html;profile=mcp-app`.

The URI includes the report ID so hosts cannot reuse another snapshot from cache.
The registered CSP has empty connection, asset, and frame allowlists. Therefore all
CSS, scripts, and fictional report data must be bundled inline: no `/report.json`
fetch, remote fonts, external scripts, frames, or runtime data calls. HTML is trusted
code prepared at build time; never populate it from untrusted tool arguments or
research-source HTML. The dashboard must render source text through safe text APIs.

The portable MCP Apps bridge and actual phone rendering are not tested by the unit
suite. The bundled dashboard may feature-detect the documented ChatGPT compatibility
bridge for follow-ups; its presence and behavior still need a host test. Copyable
follow-up questions provide an intentional fallback. Report retrieval remains usable
without any widget. No push, cloud recurrence, or ongoing research service is claimed.

Official references: [UI resources and MCP Apps](https://developers.openai.com/plugins/build/chatgpt-ui),
[UI metadata and output schemas](https://developers.openai.com/plugins/reference).
The Sites gateway contract is documented in the installed Sites skill's
`references/site-mcp-server.md`.

## Local verification

Use Node 24 for dependency-free behavioral tests. Type checking and the framework
build separately require the Site checkout's declared development dependencies:

```sh
node --test tests/mcp.test.mjs
node node_modules/typescript/bin/tsc --noEmit --target ES2022 --module ESNext --moduleResolution bundler --skipLibCheck --strict lib/research-tools.ts
```

The tests use native TypeScript stripping and fictional identity headers. They do
not call the network or create a production identity fallback. They verify
read-only discovery, authentication failure, exact report identity, timestamps,
missing data, thesis versions, unsupported actions, body limits, optional resource
auth/CSP, immutability, and exact report/UI artifact equality. A deployment build and actual private MCP invocation
are separate acceptance checks; neither is implied by these tests.
