# Acceptance criteria and current truth

Do not call the entire product functional before all relevant rows pass.

| Boundary | Acceptance evidence | Initial status |
|---|---|---|
| Accounting | Independent expected totals, flows, dividends, fees, splits, transfers | Local and GitHub CI pass |
| Private import | Sanitized real export adapter + full statement reconciliation | Pending user data/adapter |
| Research | Primary-source provenance + factual review + freshness checks | Schema/fixture tests only |
| Market data | Real provider, licensed prices, benchmark total return, corporate actions | Not configured |
| Local pipeline | Fixture import → reconcile → compute → immutable report → dashboard | Pass, 108 Python tests and 23 hosted gateway/artifact tests including the independent-gateway policy prototype |
| Source privacy | User-authorized visibility; no private data, credentials or runtime artifacts | User made source public November 5; dashboard remains owner-private. Nested private-path regression checks added |
| Private gateway | Owner-private access, unauthenticated reads denied, only bounded read tools | Deployed; anonymous and spoofed identity requests both HTTP 403 |
| Cloud retrieval | Fresh cloud ChatGPT chat reads exact report ID/source evidence | Separate durable cloud task read exact report and holding research successfully |
| Mobile UI | Phone shows dashboard or intentional Markdown fallback | User confirmed linked private dashboard readable and interactive; embedded widget not verified |
| Conversation | Follow-up cites same report/claim IDs; feedback persists | Local journal only; cloud pending |
| Recurring generation | Fresh input calculated without desktop available | Not configured |
| Scheduled delivery | Saved three-day cloud schedule + observed run | One-time cloud sample run completed at 8:24:47 PM Eastern for saved 8:25 PM test. Production recurrence not configured |
| Mobile push | Phone receives actual push and opens intended result | User confirmed push arrived and opened the sample briefing |
| Failure notification | Missing job, failed provider, revoked auth each alerts user | Not verified |
| Maintenance | Scheduled CI actually runs; failures surfaced; reviewed change/rollback | First PR CI passed; weekly recurrence/failure alerts not yet observed |
| Dependency safety | Audit production and build dependencies; inspect runtime reachability | Production-only audit zero; full audit has 37 flagged entries. Personal-data readiness blocked |
| Personal advice gate | Missing/sample/stale evidence cannot produce personal allocations | Hosted v3 defaults to blocked; explicit demo opt-in; 23 gateway regressions pass. Native reads and a fresh cloud $2,500 conversation test declined unsupported allocations |
| Broker read-only authority | Broker-enforced authorization excludes every financial mutation | Unverified; Robinhood Trading MCP not connected. Public metadata advertises only internal scope |
| Independent gateway alternative | Codex cannot access the broader broker token, change policy, deploy a bypass or use an owner session | Design and 18 mock policy tests only. Current desktop/Sites control plane fails this isolation requirement; separate admin/agent boundary and exact OAuth permissions must be verified before linking |
| Local MCP | Protected imported reports, content integrity, source/history/reconciliation checks | Fixed stdio read tools implemented; no live account import or mobile/cloud connection claimed |

The user connected the private pilot plugin. Hosted report and exact-version
holding research retrieval pass both here and in the separate scheduled cloud task.
Browser authorization for local visual QA was denied; the user subsequently
verified mobile dashboard behavior and actual push receipt. See
DEPLOYMENT_VERIFICATION.md for dated evidence.

## Phone acceptance script

1. Connect the private sample research plugin in ChatGPT Work using the same account.
2. Explicitly ask for a fictional demo briefing; confirm the exact report ID and
   synthetic label. A default personal briefing request must instead return unavailable.
3. Ask why the largest holding is flagged. Confirm quantities, source date and the
   review threshold match the report, rather than invented live data.
4. Close the desktop app / make the host unavailable, then run the cloud test.
5. Confirm notification arrival, destination, legibility and detail expansion.
6. Advance to another synthetic report and verify change attribution.
7. Inject stale/missing/auth failures and confirm explicit failure notification.

Production follows only after real-data and permission tests. A manual browser
preview and a synthetic pipeline success are not the phone end-to-end test.
