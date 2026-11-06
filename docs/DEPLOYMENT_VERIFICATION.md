# Pilot verification

This is a synthetic-data engineering pilot. The complete investment service and
phone briefing pipeline are **not yet functional**.

## November 5: evidence boundary repair

- The user changed GitHub source visibility to public and requested direct main
  commits. GitHub metadata confirmed public. Source contains only code and fictional
  fixtures; nested private/runtime artifacts and credential files are rejected by
  repository regression checks. Hosting remains owner-private with zero external visitors.
- Sites version 3, source `d444fe490c042bc94d7cb766642583d206fd1173`, deployed
  successfully at 00:17:03 UTC November 6 (7:17:03 PM Eastern November 5).
  It passed 23 gateway tests, full TypeScript checking and the official Site build.
- Authenticated `get_latest_briefing` at 00:17:10 UTC returned `status: blocked`,
  `report: null`, `allocations: []` and explicit missing-evidence reasons. It did not
  return the fictional holdings. `get_system_status` also returned the new evidence
  contract, disabled advice readiness and no financial permissions.
- New API tools provide explicit demo access and allocation-readiness checks.
  The existing connected client's tool catalog still showed the four older schemas
  at that time; existing tool calls reached the new implementation successfully.
  A fresh cloud task subsequently discovered and invoked the new readiness tool.
  Already-open chats may retain older schemas; their status/default reads still fail closed.
- Dashboard follow-up prompts explicitly distinguish fictional exploration from
  dated manual evidence. Its updated synthetic HTML hash is
  `17c03287deb32a6c7e54a0a500b537044fd302cf436023fa43433235af60330b`;
  the immutable fictional report remains `brief-e2b2b07bb6e6cfdc49e1`.
- A one-time cloud conversation regression was scheduled for 7:20 PM Eastern,
  automation `Automation_7c99814622bc8191b68cd576d5fb4cb2`, using the hypothetical
  $2,500 allocation question. The durable cloud task
  `01a1ae39-6a6c-7049-8e7b-f5a04078a051` completed at 7:19:51 PM Eastern, slightly
  before the scheduled time. Its actual calls were `assess_allocation_readiness`
  with amount 2500/USD/combined, `get_latest_briefing`, and `get_system_status`.
  Its final answer declined a personal split and stock picks, named the missing
  holdings/prices/IRA evidence, preserved the fictional report's November 3 date,
  and attributed its status claims to those tools. It did not invent holdings or
  give allocation amounts. The general-education paragraph was labeled as such;
  this test does not validate investment recommendations or future model responses.
  New phone push receipt was not independently re-confirmed for this test.
- Robinhood Trading MCP remains disconnected: reviewed official documentation and
  OAuth metadata do not establish broker-enforced read-only authorization. See
  `ROBINHOOD_READ_ONLY_REVIEW.md`. No OAuth authorization or broker action occurred.
- Local validation passed 90 Python tests, including 32 local-MCP cases, plus 23
  hosted gateway tests. An actual local CLI subprocess completed initialization,
  tool discovery, a fictional imported-report read and rejection of an unknown
  write tool. Independent review found and verified fixes for cross-account price
  inconsistencies, inherited Git-index overrides and raw CLI error disclosure.
  No real portfolio import, Codex MCP registration or local-to-cloud sync was tested.

The earlier private-repository and four-tool observations below are historical.

## November 3 engineering pilot

## Verified

- GitHub API metadata confirms `AryanParte/investment-research` is private.
- Source commit `9c6f8ccbbd20e90df40306c91a8b30abdf901db5` passed private
  [CI run 41753123848](https://github.com/AryanParte/investment-research/actions/runs/41753123848):
  52 Python tests, 15 gateway/artifact tests, privacy/capability guard, synthetic
  generation, CSP-protected bundling and browser JavaScript syntax.
- The separate Sites checkout passed full TypeScript checking and the prescribed
  production build. Source commit `8e4a13b11fc37c1831ed8c75a9ec62dac1ee22ad`
  was pushed and packaged by the official source helper.
- Native deployment reached `succeeded` on 2026-11-04 at 01:18:57 UTC
  (November 3 at 8:18:57 PM Eastern), with MCP capability enabled.
- [Private sample dashboard](https://investment-research-pilot-aryan.clearbat36.chatgpt.site).
  Access metadata contains only the owner; there are no external visitors,
  groups, editors or additional users.
- POST requests to the hosted research endpoint with no authentication and with
  forged identity headers both returned HTTP 403. No data was disclosed.
- Dashboard, widget and read tools use report `brief-e2b2b07bb6e6cfdc49e1`.
  Sample HTML SHA-256:
  `87945e97ee55fab61541bea249fdcd3c1f3a01e5f1a39a0acd66e732b142df51`.
  The short generated briefing is 49 seconds at the documented reading rate.
- No broker/bank connection, financial credential, transaction endpoint,
  recurring investment, paid market feed or personal portfolio import exists.
- After the user connected the private plugin, `get_latest_briefing` returned the
  exact report at 01:20:53 UTC. `get_holding_research(NOVA, report_id)` then returned
  the matching 28 fictional shares, 25.874126% weight, thesis version 1 and the
  source-linked utilization estimate at 01:21:04 UTC. This proves hosted tool
  retrieval for this authenticated Codex caller, not fresh cloud/mobile access.

## Pending integration gate

The initial post-deployment metadata had no plugin ID. Provisioning subsequently
completed and the user confirmed connection. The four research tools are now
available, and authenticated reads passed. No duplicate Site or alternate
authentication path was needed.

A one-time cloud sample delivery test was saved and enabled for November 3 at
8:25 PM America/New_York, with `RRULE:FREQ=DAILY;COUNT=1` and exact DTSTART.
Automation ID: `Automation_a6e5c0888d70819188cd8f0bab794423`.
The save response had null next/last-run and conversation fields. A later observed
run completed successfully on the `durable` cloud executor at 8:24:47 PM Eastern,
slightly before the saved 8:25 PM time. Task ID:
`01a1a428-41e4-73ba-8974-81a04986703d`.

The run called the private plugin's `get_latest_briefing`, then
`get_holding_research` with the identical report ID. Its final sample briefing
preserved the source date, correct contribution/gain/benchmark amounts and source
qualifications, and included the private dashboard link. It did not read desktop
files. This verifies a real cloud scheduled read → research follow-up → generated
text result for the synthetic pilot.

The result is a **separate cloud Work/Codex task**, not an injected message in the
user's existing ordinary ChatGPT conversation. The user subsequently confirmed:
"Yes, push arrived and opened the briefing" and "Yes, it works on my phone"
for the linked dashboard's readability, account switch and expandable insights.
This completes the synthetic cloud-read → briefing → mobile-push → linked-dashboard
acceptance test. Embedded in-chat widget rendering, continued phone conversation
and an explicit laptop-off test remain unverified. No production three-day
recurrence has been configured; reading the fixed sample does not refresh it.

Browser authorization for localhost QA was denied. Static responsive/accessibility
review passed, and the user later confirmed the deployed linked dashboard works on
their phone. Desktop visual appearance and embedded ChatGPT widget presentation
remain unobserved. No alternate browser route was used to bypass that refusal.

## Production gates

Hosting version 2 was subsequently built from source commit
`473519ce61f35fa3c7186d47c9be06003b8bf2b4` and deployed successfully at
8:34:31 PM Eastern. Authenticated retrieval at 8:35:05 PM returned the identical
report object, and access metadata still showed only the owner. The hardened
build passed 55 Python tests, 15 gateway tests and full TypeScript/build checks.
The production-only npm audit returned zero findings; the full audit still has
37 flagged build/development entries, including 10 high severity. See
`integrations/sites-pilot/docs/DEPENDENCY_REMEDIATION.md`; those findings must be
reviewed before personal data is introduced.

Real manual-import adapter and complete history; primary-source research ingestion;
licensed live prices and total-return benchmark; private cloud calculation/storage;
versioned conversation feedback persistence; taxable-lot modeling; successful
scheduled generation without a desktop; observed mobile notification and intended
destination; independent missed-job alert and backup/restore tests.

A saved schedule, successful deployment or denied anonymous request does not prove
the remaining gates. Keep this record and ACCEPTANCE.md updated as evidence arrives.
