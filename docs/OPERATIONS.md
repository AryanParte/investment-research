# Reliability and maintenance

## Separation of states

Record generated, available-to-reader, retrieved-in-chat, notification-sent (if
observable), phone-received (user confirmed), and opened separately. Never infer
delivery from successful generation or a webhook acknowledgment. Every attempted
delivery uses a stable report ID and idempotency key.

The local `health` command detects missing/failed generation and old source data.
It does not send alerts. A watchdog must run independently of the generator:
a job that never starts cannot report its own failure. Production alerting remains
blocked until the chosen channel and missed-run scenario are tested.

## Engineering cadence

- Each pull request/push: expected-value accounting tests, pipeline failure tests,
  privacy/capability boundary checks, syntax checks and synthetic dashboard build.
- Weekly GitHub Actions: the same regression suite and production dependency
  advisory checks against the sanitized hosting lockfile. Dependabot creates
  reviewed update PRs for GitHub Actions and hosting npm dependencies. Copying a
  dependency update into the actual Site still requires its full build and
  private deployment checks. No private imports, report attachments or debug dumps.
- Monthly: inspect dependency/security advisories, data provider contracts,
  benchmark methodology, stale-source behavior and research prompt evaluations.
- Each deployment: compare synthetic golden fixtures, require review, preserve
  last working version and test authenticated access before switching.
- Periodic Codex maintenance: can inspect CI failures and prepare a branch/PR
  when its supported cloud/local execution environment is configured. No claim
  that an unattended Codex maintenance agent is currently active.

## Research evaluations

Regression cases: unverified claim rejected; future evidence excluded; a falling
price is not sufficient to label value; a good business is not enough to recommend
an allocation; user disagreement is preserved as a revision; stale holdings block
precise new-money allocation; missing facts produce a research task; no forced
action card in an uneventful period; scenario never becomes a trading instruction.

Measure citation accuracy, accounting consistency, data freshness, unsupported
recommendation rate and reading length. Score decisions against a matched
benchmark and a versioned do-nothing alternative after costs/taxes where modeled.
No claims of an investing edge or prediction reliability from backtests alone.

## Recovery

Provider failures: bounded timeouts/retries, preserve cached evidence with original
timestamps, mark unavailable/stale, do not publish fresh-looking stale results.
Import failures: reject atomically; keep last valid snapshot labeled with its date.
Duplicate events/reports: reject or return identical report, never double-count.
Auth revoked: deny access; alert through a separately authorized channel.
Missed job: independent watchdog compares expected run and last successful report.
Missed notification: mark unknown until observed; do not claim guaranteed receipt.
No recovery workflow may request financial execution permissions.

## Privacy

No analytics, tracking pixels, third-party chart CDNs, or financial content in logs.
Keep aliases rather than account numbers. Private records are encrypted at rest
by the selected hosting platform and protected by identity-based access (not yet
configured for real data). Local hash chaining detects accidental edits but is
neither encryption nor protection from a privileged attacker. Backups must be
encrypted, access-controlled, versioned and restore-tested. Do not store personal
records in GitHub even though this repository is private.
