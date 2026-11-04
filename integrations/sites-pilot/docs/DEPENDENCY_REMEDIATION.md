# Sites pilot dependency remediation

Checked 2026-11-03. This records a dependency update and its bounded validation;
it is not a claim of complete security or readiness for personal financial data.

The original installed template's `npm audit --omit=dev --json` reported six
vulnerable production-package entries: one critical, three high, and two moderate.
After the changes below, the same production audit returned **zero reported
vulnerabilities** at every severity. No financial connection or permission was added.

| Dependency | Original | Remediated resolution |
| --- | --- | --- |
| next | 16.3.4 | 16.4.5 |
| eslint-config-next (development) | 16.3.4 | 16.4.5 |
| sharp | 0.35.4 | 0.35.5 |
| source-map-js | 1.2.1 | 1.2.2 |
| fast-uri | 3.1.7 | 3.1.9 |
| baseline-browser-mapping | 2.10.30 | 2.11.0 |
| zod (direct production dependency) | 3.25.76 | Removed with its unused consumer |

Twenty unused direct UI dependencies and their unused starter component files were
removed after reviewing imports. The active app did not consume that component
tree, hooks, class-name helper, or Zod-based connector error presentation helper.
The dashboard has its own bundled CSS and JavaScript. Worker routing, private Site
authentication, the Sites build integration, connector context, and database
scaffolding were retained. The report and dashboard content are unchanged.

The removal list is explicit in `prepare_starter.py`. For future fresh checkouts,
that script requires `--fresh-starter`, verifies the expected starter/Vinext version,
refuses symlinks or active imports of the removable files, and archives old source
and the package manifest under ignored `.sites-runtime/unused-ui-backup/` before
changing the dependency manifest. Three regression tests cover its refusal and
backup behavior. Do not apply it indiscriminately to customized applications.

The supplied installer initially read stale cached registry metadata and reported
ETARGET for the fixed Next ESLint packages. Exact registry lookup confirmed they
exist. The lock was refreshed online with scripts disabled, then the official
Sites installer completed successfully. The reproducible manifest and lock in
`runtime/` contain only credential-free public npm package URLs; no Site identity,
account data, local paths, or runtime state was copied.

Validation after installation: 55 Python tests, 15 MCP/protocol/artifact tests,
full Site TypeScript checking, privacy/capability regression checks, and the official
Sites production build all passed. Publication and hosted invocation are separate.
Tests locally used Node 23.7 native type stripping; CI is configured for Node 24.

The production audit excludes development-only packages. For example, Zod 3.25.76
still exists as a development transitive dependency. Some framework packages are
declared development dependencies even though their build output is deployed.
Therefore a zero production audit is **not** a full build-tool audit, runtime
reachability analysis, penetration test, or guarantee against future advisories.
Weekly audits and dependency PRs must preserve these scope distinctions.
A separate full `npm audit --json` after remediation reported 37 affected package
entries (0 critical, 10 high, 26 moderate, 1 low), including build/framework chains
through Vinext, Vite and React Server Components. These remain an explicit blocker
for introducing personal data until compatibility-safe upgrades and deployed
runtime reachability have been reviewed. Do not interpret package-manager
`devDependency` labels as proof that a vulnerable module cannot enter the Worker.
The full audit is recorded separately from the production-only CI gate; no audit
finding was suppressed or force-fixed.

Maintain the patched overrides until upstream-supported ranges resolve safely.
Review dependency updates, run the gateway/accounting regressions, typecheck and
official build, and repeat the relevant audits before publishing. Do not use
forceful automatic audit fixes or grant financial capabilities during maintenance.
