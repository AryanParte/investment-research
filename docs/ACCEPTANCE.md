# Acceptance criteria and current truth

Do not call the entire product functional before all relevant rows pass.

| Boundary | Acceptance evidence | Initial status |
|---|---|---|
| Accounting | Independent expected totals, flows, dividends, fees, splits, transfers | Local and GitHub CI pass |
| Private import | Sanitized real export adapter + full statement reconciliation | Pending user data/adapter |
| Research | Primary-source provenance + factual review + freshness checks | Schema/fixture tests only |
| Market data | Real provider, licensed prices, benchmark total return, corporate actions | Not configured |
| Local pipeline | Fixture import → reconcile → compute → immutable report → dashboard | Pass, 52 Python tests and 15 gateway/artifact tests |
| Private GitHub | Metadata confirms private; source tree verified; CI run completes | Private; source uploaded; CI run 41753123848 passed |
| Private gateway | Owner-private access, unauthenticated reads denied, only bounded read tools | Deployed; anonymous and spoofed identity requests both HTTP 403 |
| Cloud retrieval | Fresh cloud ChatGPT chat reads exact report ID/source evidence | Not verified |
| Mobile UI | Phone shows dashboard or intentional Markdown fallback | User acceptance pending |
| Conversation | Follow-up cites same report/claim IDs; feedback persists | Local journal only; cloud pending |
| Recurring generation | Fresh input calculated without desktop available | Not configured |
| Scheduled delivery | Saved three-day cloud schedule + observed run | Not verified |
| Mobile push | Phone receives actual push and opens intended result | Not verified |
| Failure notification | Missing job, failed provider, revoked auth each alerts user | Not verified |
| Maintenance | Scheduled CI actually runs; failures surfaced; reviewed change/rollback | First PR CI passed; weekly recurrence/failure alerts not yet observed |

The hosted pilot returns an MCP endpoint but no plugin ID was returned by Sites,
and no research tools are available in this chat. Plugin connection is pending.
Browser authorization for local visual QA was denied; phone layout/interaction
acceptance is pending. See DEPLOYMENT_VERIFICATION.md for dated evidence.

## Phone acceptance script

1. Connect the private sample research plugin in ChatGPT Work using the same account.
2. Ask for the latest briefing; confirm the exact report ID and synthetic label.
3. Ask why the largest holding is flagged. Confirm quantities, source date and the
   review threshold match the report, rather than invented live data.
4. Close the desktop app / make the host unavailable, then run the cloud test.
5. Confirm notification arrival, destination, legibility and detail expansion.
6. Advance to another synthetic report and verify change attribution.
7. Inject stale/missing/auth failures and confirm explicit failure notification.

Production follows only after real-data and permission tests. A manual browser
preview and a synthetic pipeline success are not the phone end-to-end test.
