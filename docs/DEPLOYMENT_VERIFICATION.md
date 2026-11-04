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

## Pending integration gate

Sites reports the `/mcp` endpoint and OAuth resource, but no plugin ID. The new
research tools are absent from this chat; plugin search did not find the private
pilot. The user has been asked to check Plugins → Personal → Created by you and
connect the pilot if available. Do not invent an identifier or create a duplicate
Site to work around provisioning.

An authenticated hosted report read, a fresh cloud-chat read, and a report-scoped
conversation still need verification. No schedule has been created. A one-time
sample phone delivery test should precede the production three-day recurrence.

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
