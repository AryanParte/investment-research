# Private Sites integration pilot

This is the reproducible application overlay for the private, **fictional-data-only**
Sites pilot. It contains no Site registration, Site ID, source credential, account
identity, private financial input, or deployment runtime. The main Python project
remains the accounting engine. This overlay reads its versioned sample output; it
does not run Python in Cloudflare Workers or refresh a portfolio in the cloud.

The gateway exposes six read-only research tools, plus an optional bundled MCP
Apps dashboard. Report IDs, thesis versions, and source timestamps are shared by
the UI and tools. No financial transaction capability exists. See
`docs/MCP-PILOT.md` for protocol, authentication, and verification boundaries.

`get_latest_briefing` now returns blocked with no report because this deployment
has no personal portfolio. `assess_allocation_readiness` returns missing evidence
and no allocations. Fictional exploration uses `get_demo_briefing` with an explicit
`acknowledge_synthetic: true`; exact report and holding reads require that flag too.
Schedules that intentionally test a demo must request it explicitly. No tool accepts
caller-provided holdings, eligibility or verification overrides. Server responses
and discovery instruct the model to abstain from personal allocations when blocked;
this is not a guarantee that every conversational response will obey.

## Reproduce the source

1. In the core repository, run the documented demo and `python3 scripts/bundle_sample.py`.
   Both inputs must remain fictional. `sync_sample.py` refuses non-synthetic mode
   and checks that the JSON embedded in the HTML equals the complete report object.
2. Create a new empty Sites checkout with the officially supplied Vinext starter
   through the installed Sites plugin. The pilot was prepared with Sites 1.1.3;
   preserve its Worker, Vite, authentication, and build integrations. Do not copy an
   existing deployment's identity, `.openai/`, runtime, environment, or Git metadata.
3. Apply the `app/`, `lib/`, `public/`, `tests/`, and `docs/` files from this overlay.
   The root `app/page.tsx` uses the starter's `app/chatgpt-auth.ts`. Keep that supplied
   helper. Replace the placeholder dashboard URL in `app/mcp/route.ts` with the
   actual owner-private Site URL after registration. It is non-secret configuration,
   not a credential. Registration and publication are separate authorized steps.
4. From the core repository, regenerate the sample artifacts into the actual checkout:

   ```sh
   python3 integrations/sites-pilot/sync_sample.py --checkout /absolute/path/to/site-checkout
   ```

5. Add only `"mcp"` to the Site hosting manifest's capabilities while preserving the
   registered ID and other required starter fields. No connected broker/plugin,
   database, bucket, or financial credential is needed. Keep the Site owner-private.
6. Only for a fresh official starter with the app overlay applied, run
   `prepare_starter.py --fresh-starter --checkout /absolute/path/to/site-checkout`.
   It refuses unfamiliar starter versions, symlinks, or application imports of the
   removable UI scaffolding. It moves unused starter components into a unique,
   ignored `.sites-runtime/unused-ui-backup/` directory and removes their dependencies,
   including the unused Zod-based connector error view. Worker/auth/build support is
   retained. Then copy `runtime/package.json` and `runtime/package-lock.json` into the
   checkout root to reproduce the tested resolution. Do not copy the test-only
   package manifest from this overlay root.
7. Use Node 24 for behavioral tests; these tests need no npm installation. Install
   framework dependencies using the Sites helper for the separate typecheck/build:

   ```sh
   node --test tests/mcp.test.mjs
   node node_modules/typescript/bin/tsc --noEmit
   node /absolute/path/to/installed/sites/scripts/build-site.mjs
   ```

8. Follow the Sites source-helper packaging/private publication workflow. Do not
   deploy by copying opaque build files or reusing someone else's project identity.

The overlay intentionally does not duplicate the entire framework starter or its
dependency installation. Sanitized runtime manifests preserve the audited package
resolution without Site identity or credentials. `sync_sample.py` can also update the bundled synthetic assets in this
overlay by omitting `--checkout`. Generated sample assets are permitted in source;
real account reports must never use this bundling path.

The tiny `package.json` here defines only the dependency-free CI test environment.
Do not copy it over the Sites starter's framework package manifest or package lock.

## Dependency maintenance

The initial template audit found vulnerable production packages, so this pilot
uses Next and eslint-config-next **16.4.5** and explicit patched resolutions for
sharp **0.35.5**, source-map-js **1.2.2**, fast-uri **3.1.9**, and
baseline-browser-mapping **2.11.0**. These are dated minimum remediation choices,
not a claim that those versions will remain free of advisories. Review updates
and remove overrides when supported upstream ranges resolve safely on their own.

CI can run `npm audit --omit=dev --audit-level=moderate` in `runtime/` from its lockfile
without installing dependencies; production and development dependency reviews
remain distinct. Never automatically apply forceful audit fixes or deploy an
unreviewed dependency update. Require gateway tests, full Site typechecking, the
official Site build, and a new audit before republishing a dependency change.

## What still needs separate acceptance tests

Unit tests and a successful build establish local behavior only. Verify the private
deployed endpoint, plugin discovery, exact report retrieval, and follow-up evidence.
Then test cloud recurrence, physical phone push receipt, and mobile widget rendering
separately. A static snapshot does not become fresh when a schedule reads it. The
gateway keeps notification, mobile, and cloud scheduling verification flags unset.

The gateway trusts identity headers injected by the Sites access gateway. It must
never be served behind a public origin that lets a caller forge those headers.
No personal data may be added until private storage, source handling, and account
authorization receive a separate review. No trading or money permissions may ever
be added, regardless of future hosting changes.
