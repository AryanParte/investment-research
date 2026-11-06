# Architecture decision — 2026-11-03

## Product boundaries

Research, accounting, scenarios and recommendations only. No financial write
tools, brokerage/bank credentials, payment authorization, generic broker proxy,
recurring purchases or autonomous execution. Start with secure manual imports.
Read-only labels alone are not authorization: any future broker adapter requires
verified provider-enforced read-only permissions and independent scope inspection.

## Preferred production design

```text
User-provided files ──> Private ingestion + event ledger
Read-only data feeds ─> Source cache + provenance
                             │
                 Deterministic Python calculation job
                             │
                Versioned private reports + research journal
                             │
            Authenticated, bounded research retrieval tools
                             │
             Cloud ChatGPT Work scheduled briefing
                             │
              ChatGPT mobile + continuing conversation

Code-only GitHub ──> synthetic CI / reviewed changes ──> private deployment
Independent watchdog ──> separately verified failure notification
```

The language model researches and explains; it does not calculate the authoritative
ledger or grant itself permissions. UI, prose and conversations use the same
report ID, claim IDs, source timestamps, thesis versions and decision history.
Chat memory is a convenience, not the database. User disagreements become explicit
versioned assumptions; they do not silently rewrite historical decisions.

## Delivery choice and what pairing changes

Phone pairing enables access to an awake connected host. It does not make a local
scheduler cloud-hosted. Official cloud ChatGPT Work schedules and authenticated
plugins are the preferred delivery mechanism. The local Codex automation tool
does not by itself establish a cloud notification workflow.

Use one cloud Work conversation where supported. Schedule every three calendar
days at a fixed America/New_York time (proposed 6 PM). This differs from an exact
72-hour interval across DST. Do not use day-of-month `*/3` cron as a substitute.
If native same-chat scheduled retrieval is unavailable, supported MCP Events may
wake a subscribed Work chat. There is no assumed general-purpose API to inject
messages into arbitrary ordinary ChatGPT conversations.

The actual Sites schedule acceptance test created a separate durable cloud
Work/Codex task. It did not post into the existing ordinary ChatGPT conversation.
The user confirmed its push opened the result on the phone, and the linked private
dashboard worked. This is the verified first delivery path: a new scheduled
result plus the same authenticated report service for follow-up questions.
Same-chat recurrence and embedded mobile widgets remain optional, unverified
enhancements. Retain exact report IDs so a separate research chat can retrieve
the same evidence without depending on inherited chat memory.

## Safe pilot

The account-provided Sites service offers owner-private hosting, ChatGPT sign-in,
read-only MCP tools and cloud scheduling. A synthetic snapshot pilot tests those
boundaries without financial data or API keys. Tool discovery contains only
report and research reads; no financial actions exist. Native tool-returned
Markdown is the portable fallback. The buildless dashboard offers report-scoped
copyable questions and a feature-detected in-chat follow-up bridge. Its embedded
MCP UI is implemented but not yet verified on mobile; the linked dashboard is.

Sites runs JavaScript Workers. The Python calculation engine cannot be assumed to
run there. For production, deploy the Python job on a private scheduled compute
service and publish only versioned authenticated reports to the presentation layer.
Alternatively port the engine only after identical accounting test vectors pass.
Do not run personal portfolio jobs in public CI or store portfolios in artifacts.

The gateway pilot is intentionally read-only and bundled with fictional fixtures.
It is not a cloud portfolio updater. Repeatedly reading that snapshot does not
refresh it. Its timestamp and synthetic banner must persist forever.

## Data and costs

Initial local runtime has no paid API and no third-party Python/browser runtime
dependencies. Market data/provider cost, private compute/storage cost, and ChatGPT
plan usage are separate. No paid service is activated. Select a single licensed
daily-price/total-return source after checking coverage, freshness, redistribution,
corporate actions and actual price. Prefer SEC/company investor relations for
primary filings. Cache by source ID and date; do not refetch unchanged documents.

Research brief: <=360 main-view words, up to three meaningful insights, no forced
recommendations. Quarterly research reviews and event-driven updates support long
horizons; discovery can include any sector. Research candidates are not holdings.

## Engineering and account setup

- GitHub repo: temporarily public as requested November 5; code and fictional tests
  only. Reviewed, tested direct commits to main; the hosted data service stays private.
- Cloud data permissions: minimum storage/read scopes; no brokerage permissions.
- Market feed key (if needed): user supplies through secret manager, never chat/Git.
- ChatGPT private plugin: verify connection in the intended cloud/mobile surface.
- Phone notification: user enables OS/app category and acknowledges an actual test.
- Independent watchdog: must prove both missed-job detection and alert delivery.

See MOBILE_INTEGRATION_AUDIT.md for official sources and rollout limitations.
