# Local private portfolio reads

This stdio server provides **descriptive account facts only** from a deliberately
selected manual import. It has no broker connection, HTTP listener, financial
credentials, write tools, recommendations, or transaction capabilities. It does
not connect your existing private cloud pilot to local data.

The two tools are:

- `read_local_portfolio_snapshot`: current validated imported cash and holdings,
  account aliases, calculated weights, source dates, and provenance limitations.
- `read_local_evidence_status`: readiness and blockers, without holding values.

Both return `can_recommend: false`. Research, current fundamentals, valuation,
tax-lot and eligibility checks are not implemented here. A descriptive snapshot
cannot justify a precise dollar allocation or a buy, hold, trim, or sell call.
The server exposes no allocation method; its tool instructions also tell the
client not to infer one. Instructions cannot guarantee that a downstream model
will never hallucinate, so client-level evaluation remains required.

## Select a private store

Use a dedicated absolute directory under this checkout's ignored `runtime/` or
`private/` directory, for example `<checkout>/runtime/owner-portfolio`. The final
directory must be owned by the current user and mode `0700`. Both `report.json`
and `health.json` must be owner-only regular files (`0600`) with one hard link.
The server does not create, chmod, repair, or populate that directory.

Generate the files with the existing local pipeline from normalized manual
imports and a separately supplied endpoint statement. See [IMPORTS.md](IMPORTS.md).
Never place real input or output files under `samples/`, `web/`, source code, or
Git. Do not use the demo report as a placeholder for personal data.

The reader rejects directories outside the permitted area, relative paths,
traversal components, symlinked directories/files, linked report files, broadly
readable report files, tracked private files, ignored-file exceptions, and large
files. Git exclusion is rechecked for every read. Files are opened read-only
through directory file descriptors with no-follow protections. The checkout and
directory chain must be owned by the current user and not writable by other
users. Git checks pin the actual checkout and ignore inherited repository, index,
worktree, and config overrides. Supported hosts
need Python 3.11+, Git, and POSIX no-follow file APIs (macOS/Linux).

## Launch explicitly

```sh
python3 /absolute/checkout/scripts/serve_portfolio_mcp.py \
  --directory /absolute/checkout/runtime/owner-portfolio
```

Configure that command and its fixed arguments in a trusted local MCP client.
Use the client's documented setup; this document does not claim that a connection
has been registered. There are no environment secrets. Tools cannot change the
directory, choose a file, provide a budget, execute an import, or mutate a report.
The client receives the selected financial facts in its tool response; review
that client's data handling before connecting it. Read-only describes capability,
not a promise that the model provider never processes the supplied data.

No normal logs are written. Standard output contains only newline-delimited
JSON-RPC messages intended for the invoking client. Errors contain generic codes,
not raw records, account numbers, paths, or tracebacks.

## Data gates

The current producer schema calls private manual reports `mode: imported`; a
`sample` report is rejected. A supported report must satisfy all of these:

1. Supported schema and pipeline version; content-derived report ID verifies.
2. Exact SHA-256 inventory includes transaction, price, benchmark, research, and
   statement inputs. These hashes bind the report to declared inputs; the reader
   does not reread the original input files or authenticate the broker.
3. Complete inception history is explicitly attested. Timeline dates and cash
   flows reconcile; missing history never becomes a zero return or sample.
4. Endpoint cash and shares matched the supplied statement at the same date.
   This remains **user-supplied manual evidence**, not broker verification.
5. Report, generation, and latest valuation source timestamps are not in the
   future and are at most 96 hours old by default. `--max-age-hours` can tighten
   the threshold to 1–96 hours. No exchange-calendar exemption is assumed.
6. The latest health record says generation succeeded for this exact report ID.
   A failed newer run blocks use of the last good report as a current snapshot.
7. Required source declarations are present; synthetic markers are rejected.
   Cash, holdings, per-account totals, combined quantities, and per-symbol market
   values reconcile. Each symbol has the same price and dated source declaration
   in the combined and per-account views.

On failure, tools return `status: unavailable`, `snapshot: null`, a safe blocker
code, and `can_recommend: false`. There is no archive, demo, screenshot, cached
history, or zero-valued fallback. Historical research prose and suggested insight
cards are deliberately not returned by these descriptive tools.

## Protocol and verification status

This implementation targets the official **MCP 2025-11-25 legacy stdio profile**
and also negotiates 2025-06-18. The lifecycle is `initialize`,
`notifications/initialized`, then `tools/list` and `tools/call`. It supports
`ping`, bounded newline-delimited UTF-8 JSON-RPC, generic protocol errors, and
read-only tool annotations. It is not an implementation of the newer 2026 MCP
lifecycle. The annotations supplement the actual fixed read-only handlers; they
do not establish authorization by themselves.

Official references: [stdio framing](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports),
[initialization](https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle),
[tool discovery and calls](https://modelcontextprotocol.io/specification/2025-11-25/server/tools).

Automated tests cover the local protocol and file/data gates using fictional
temporary fixtures, including launching the actual entrypoint as a subprocess
and completing initialization, discovery, a snapshot read, and refusal of an
unknown write tool. They do not prove Codex client registration, a real account
import, ChatGPT mobile access, cloud synchronization, scheduled execution, push
notifications, or mobile delivery. The cloud pilot's personal-data gate remains
unchanged; do not upload this private report to it.

Manual acceptance must verify the configured client's handshake and two-tool
surface, a genuine local import's statement comparison, a stale/missing-data
refusal, and a request for a precise allocation remaining unsupported. Keep
delivery and recommendation capabilities disabled until separately reviewed.
