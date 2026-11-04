# Pilot verification — November 3, 2026 (America/New_York)

This is a synthetic-data engineering pilot. The complete investment service and
phone briefing pipeline are **not yet functional**.

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
The save response had null next/last-run and conversation fields. It proves saved
configuration only. The actual cloud run, result destination, mobile push and
widget rendering still need verification. No production three-day recurrence has
been configured; reading the fixed sample does not refresh it.

Browser authorization for localhost QA was denied. Static responsive/accessibility
review passed, but desktop visual appearance, mobile rendering, tap behavior and
ChatGPT widget presentation remain unobserved. No alternate browser route was
used to bypass that refusal.

## Production gates

Real manual-import adapter and complete history; primary-source research ingestion;
licensed live prices and total-return benchmark; private cloud calculation/storage;
versioned conversation feedback persistence; taxable-lot modeling; successful
scheduled generation without a desktop; observed mobile notification and intended
destination; independent missed-job alert and backup/restore tests.

A saved schedule, successful deployment or denied anonymous request does not prove
the remaining gates. Keep this record and ACCEPTANCE.md updated as evidence arrives.
