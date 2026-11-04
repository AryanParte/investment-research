# Mobile delivery and shared-context architecture audit

Checked 2026-11-03 (America/New_York). This is a documentation and tool-contract audit, not proof that the user's account has every feature or that a notification has arrived. No schedules, plugins, Pages, or financial connections were created during this audit.

## Decision

Use a **cloud ChatGPT Work conversation** as the continuing research interface. Keep the investment engine and authoritative research records independent of chat memory. Use a **native cloud scheduled task in that same conversation every three days** to retrieve a versioned briefing through a private, authenticated, financially read-only data interface. This is the simplest first delivery path to validate. Codex develops and maintains the engine separately.

There is also an officially documented **MCP Events** route for the engine to signal `briefing.ready` or `pipeline.failed` into a subscribed Work chat. It is a legitimate option if deterministic engine-triggered delivery is needed; it adds a hosted endpoint, durable subscription state, callback verification, signatures, retry handling, and integration tests. It should not be implemented as an undocumented webhook into an arbitrary ChatGPT conversation.

The phone pairing is helpful for reviewing local development, but it is not the cloud scheduler and does not make the laptop's files accessible while the laptop is off.

## Verified capability matrix

| Requirement | Official evidence | Actual status in this session |
|---|---|---|
| Continue Codex work from ChatGPT mobile | Mobile/remote docs describe starting, steering, and reviewing a cloud task or a task on an awake connected computer. | User reports pairing. Phone UI and push not observed. |
| Work conversation synchronization | New eligible Work chats can sync across desktop, web, mobile. Existing chats retain their original mode. Conversation sync does not upload a local project folder. | Current local Codex chat must not be presumed to be the future cloud briefing chat. |
| Unattended cloud recurrence | Web Chat/Work scheduled tasks can use uploaded files and connected tools, and can return to the same chat. Local desktop project schedules need the app running/computer on. | Available `automation_update` concrete schema exposes local cron and thread/local heartbeat. It does not establish a cloud ChatGPT task creation path from this local tool. |
| Push notification | Notification settings expose account-dependent push, email, or SMS channels. | Device permission, account category, actual push delivery, and deep link destination all unverified. |
| Interactive in-chat dashboard | MCP Apps optional UI renders alongside conversation; portable `ui/message` supports follow-up messages and `tools/call` retrieves detail. | No custom integration connected. Must test on user's phone. |
| Native Visualize dashboard | Official availability table says mobile is rolling out to eligible accounts. | Cannot promise mobile rendering just because desktop visualization works. |
| Persistent shared research | Chat/Work can use connected services, project context, files, and Pages. Pages support references, interactive visualizations, and conversation beside the page. | Exact private destination and read access still need configuration/verification. |
| GitHub integration | GitHub plugin/tool access to repository files exists; native scheduled events include PR activity. | GitHub is suitable for code, CI and engineering review. Do not use public artifacts/logs as the portfolio store. Private-repository access must be checked for the cloud chat separately. |
| External engine triggering a chat | MCP Events supports authenticated subscriptions to a plugin's events in Work Cloud chats/dots; ChatGPT supplies verified signed callback details. | Supported protocol, not configured or tested here. Ordinary arbitrary chat injection is not established. |
| Page-hosted automations | Current connected tool descriptions expose cloud Page controllers/workers. Public Space docs separately say Keep Updated is not available at launch and instruct users to verify schedules/runs. | Treat tool availability as a candidate account capability, not proof of a stable notification product. Do not make it the first dependency without an actual test. |

Sources: [Mobile](https://learn.chatgpt.com/docs/mobile), [remote connections](https://learn.chatgpt.com/docs/remote-connections), [Work sync](https://learn.chatgpt.com/docs/get-started-with-work), [projects and file access](https://learn.chatgpt.com/docs/projects), [scheduled tasks](https://learn.chatgpt.com/docs/automations), [notifications](https://learn.chatgpt.com/docs/notifications), [MCP UI](https://developers.openai.com/plugins/build/chatgpt-ui), [Visualizations](https://learn.chatgpt.com/docs/visualizations), [Pages](https://learn.chatgpt.com/docs/space/pages), [Space recurring work](https://learn.chatgpt.com/docs/space/agents), [MCP Events](https://developers.openai.com/plugins/build/mcp-events).

## Recommended staged implementation

### Stage A: self-contained engine and sample dashboard

- Build deterministic ledger normalization, reconciliation, performance calculations, risk metrics and report rendering locally, using fictional data.
- A report is an immutable record identified by `report_id` and a schema version. The dashboard and the model consume the **same** record; do not compute portfolio metrics independently in JavaScript and prose.
- Include generation time, ledger/import time, market-price time, benchmark time, research source timestamps, completeness status, error categories, and the prior report ID.
- Every material research claim has a claim type (fact/estimate/assumption/opinion), a source URL, publication date if known, retrieval time, and associated thesis IDs.
- Offer a concise Markdown fallback alongside the interactive HTML. Aim for 250–350 visible words, expandable source-backed detail, and zero forced insight count when evidence does not justify an action.
- Data-quality failures must produce explicit unavailable/stale states, never carry forward a number labeled current.

### Stage B: private shared data and cloud conversation

- Keep code and synthetic fixtures in the private GitHub project. Store real imports and generated personal reports outside source control, Actions artifacts, and logs.
- Select one user-owned, authenticated cloud destination. A dedicated storage/API service is the durable design; a private connected Drive/Library artifact can be a lower-complexity pilot if the cloud chat can reliably retrieve a known version. Test the exact read path, rather than assuming a file link grants access.
- A custom remote MCP server may expose bounded reads such as `get_latest_briefing`, `get_briefing(report_id)`, `get_holding_research(symbol, report_id)`, `get_thesis(symbol)`, `get_decision_history`, and nonpersisting `analyze_scenario`.
- It must have no broker/bank credential, trading SDK, proxy endpoint, arbitrary HTTP action, or financial write operation. Financial read-only must be enforced by what the server can do and what credentials it possesses; `readOnlyHint` alone is not a security boundary.
- User-authorized decision/thesis journaling is a separate, explicitly scoped nonfinancial write if enabled later. Do not label journal writes read-only. Preserve revisions instead of silently replacing previous reasoning.
- Create a dedicated cloud Work chat in the same account/workspace and put stable policy, data-source identity, report schema, privacy constraints, and research rules in its durable context. Opening a random new chat must not be assumed to inherit everything.

### Stage C: recurring delivery and dashboard

- First run the exact briefing request manually in the cloud Work chat with synthetic data. Test report retrieval, source detail, and a follow-up question tied to the same `report_id`.
- Use the ChatGPT web Scheduled interface to save the same-chat cloud task, then inspect its saved cadence and enabled state. Every three local calendar days in America/New_York is distinct from exactly 72 hours around DST; document the chosen semantics. A day-of-month cron expression `*/3` is not an exact three-day interval across month boundaries.
- A scheduled task should read the newest complete report, explain data freshness, compare with the previous delivered report, and deliver an explicit failure/staleness notice if the expected report is missing. Avoid unrelated news.
- For a custom dashboard, use the current MCP Apps bridge. `ui/message` can submit a user-initiated follow-up such as “Explain concentration alert A in report R.” Retain a readable text response for clients that cannot render the component. Feature-detect optional host capabilities. Never add payment or broker controls.
- Test actual push on the phone while the desktop app is closed. A scheduled-task success record is not evidence that the operating system displayed a notification.

### Stage D: engine-triggered events if warranted

- The engine can publish `briefing.ready` or `pipeline.failed` via the official MCP Events subscription protocol, limited to the authenticated user's records.
- The callback URL and secret must come from ChatGPT's `events/subscribe`; verify the callback challenge and sign deliveries with Standard Webhooks. Persist subscription state and retry idempotently. Limit event payloads to the report ID/status, retrieving personal details through authenticated read tools.
- A webhook `2xx` is only acknowledgment of receipt. It does not certify a generated reply, rendered widget, push delivery, or that the user opened it. Record those stages separately, marking unobservable stages unknown.
- This route is available in supported Work Cloud chats/dots, subject to feature and workspace access. It is not a general endpoint for posting arbitrary messages into ordinary ChatGPT chats.

## Reliability and failure boundaries

A cloud scheduler and private storage are required for independence from the user's desktop. Cloud Work tasks can retrieve connected data but cannot access an offline local folder. Cloud jobs may also consume plan usage and encounter account limits; no documented unlimited availability or delivery SLA was verified.

Use two separate states: `brief_generated` and `brief_delivery_status`. Keep the source import time separate from report time. With manual portfolio imports, future briefings can update market prices against the last known holdings, but cannot claim current holdings or contributions without a fresh import/user reconciliation.

A task that never starts cannot notify about its own failure. Provide an independent cloud watchdog for missing reports and a separately tested fallback alert channel. Built-in GitHub workflow failure notification is useful for engineering failures, but by itself does not prove that a scheduled workflow ran or that ChatGPT delivered the briefing. Never promise every failure will generate a mobile alert until the missed-run, backend-failure, revoked-auth, and delivery-failure tests have succeeded.

## Required participation / unresolved configuration

1. Confirm the same ChatGPT account/workspace has Work Cloud, Scheduled, required connected-data access, and mobile widget/Visualize support.
2. Select and authorize private cloud hosting/storage, plus any limited read-only market-data credentials. No financial credential is required for the import-based MVP.
3. Connect the private research MCP/plugin or pilot document source to the intended **cloud** chat. An installed desktop-only plugin does not establish mobile availability.
4. Enable the relevant ChatGPT notification category and mobile OS permission, then acknowledge receipt of a real test notification.
5. Choose a briefing time. Use a reasonable proposed local time, but verify the saved schedule rather than assuming natural-language cadence parsing.
6. Verify an independent failure-notification channel. This could be account-native email/push if supported and tested; do not introduce Slack/Gmail permissions merely to manufacture a delivery bridge.

## Acceptance tests before calling the system functional

- Import synthetic holdings/transactions, reconcile, value, compute benchmark and generate report without network or brokerage access.
- Cloud Work retrieves that exact report, renders the mobile UI or intentional fallback, and cites its `report_id` and freshness.
- User taps an insight and asks a follow-up; response uses the same holdings/claim evidence. User disagreement is recorded as a versioned thesis amendment when authorized.
- A scheduled execution happens with desktop app closed and computer unavailable, and the phone receives a notification that opens the intended conversation.
- Advance the fixture to a new report; the next update compares with the last delivered report, not an unrelated run.
- Inject stale prices, missing imports, failed data provider, revoked read credentials, duplicate delivery, and missing scheduled execution. Verify honest unavailable states and the agreed failure alerts.
- Verify no financial actions exist in server tool discovery, code dependencies, credential scopes, or dashboard controls. Validate unauthenticated access fails and that no personal portfolio data enters source control, CI logs/artifacts, analytics, or public URLs.

## Additional official implementation references

- [Plugin architecture](https://developers.openai.com/plugins/concepts/plugins)
- [Build an MCP server](https://developers.openai.com/plugins/build/mcp-server)
- [Connect and test a plugin](https://developers.openai.com/plugins/deploy/connect-chatgpt)
- [Plugin availability across surfaces](https://learn.chatgpt.com/docs/plugins)
- [Plugin UI troubleshooting](https://developers.openai.com/plugins/deploy/troubleshooting)
- [Annotation and permission boundaries](https://developers.openai.com/plugins/plugin-guidelines)
- [API webhooks](https://developers.openai.com/api/docs/guides/webhooks) — these deliver API lifecycle events to the developer's service; they are not themselves a ChatGPT mobile push channel.

## Account-provided Sites pilot (follow-up investigation)

The installed Sites skill and actual tools provide a practical alternative to provisioning a separate server and OAuth implementation for the first private cloud retrieval test. Read references: `sites/SKILL.md`, `references/site-mcp-server.md`, `references/recurring-updates.md`, and `references/identity-and-secrets.md` in the installed Sites package. This evidence is a current local capability contract, distinct from a verified deployment.

### Concrete safe sample-only path

1. Create a separate Sites checkout using the supplied Vinext starter for server behavior. Put only fictional report data and the current dashboard in it. A purely static Site is enough for the visual pilot but cannot implement the hosted `/mcp` endpoint required for this retrieval test.
2. Add `capabilities: ["mcp"]` to the hosting manifest and implement stateless JSON-RPC `POST /mcp`: `server/discover` for protocol `2026-07-28`, `tools/list`, and `tools/call`. Expose only `get_latest_briefing`, `get_briefing`, and `get_holding_research` over bundled fictional JSON. Include accurate `readOnlyHint: true`, `destructiveHint: false`, and bounded `openWorldHint: false`. Reject unknown tools, malformed inputs, and absent identity. No trading SDK, bank/broker token, generic URL fetch, or externally callable write function.
3. Register exactly once using `sites.create_site`, retaining its ID and source credential without printing secrets. Omit `enable_plugins`: that flag is for visitor-connected external apps, not the Site's own MCP capability. Follow source helper/push/package/private deploy workflow. The sample is safe for the source and deployment bundle because it contains no user holdings.
4. Confirm owner-only access and successful deployment. The platform authenticates MCP requests and checks Site view access before forwarding them. A private app/plugin is provisioned on publication; it may connect automatically. This avoids scaffolding a separate OAuth server.
5. Read `get_site(include_mcp_connection:true)` and retain only nonsecret connection metadata for inspection. If the new tools are available, call a read tool and check the report ID/hash. Otherwise use the exact returned `plugin_id` with `suggest_plugins`; the user may need Install/Connect or a new chat for tool availability.
6. Retrieve the same sample from a fresh cloud Work chat and from the phone, then ask a follow-up linked to its report ID. A successful local tool call proves hosted MCP read access for that local caller only; it does not prove cloud/mobile availability.
7. Before any Site schedule, retrieve fresh `get_site` metadata. A missing/null `automations` field blocks schedule creation; an empty array permits duplicate checking, not proof that update logic works. Retain the exact `schedule_request_id` for `create_schedule.request_id` and reuse it on uncertain retries.
8. Once sample retrieval is verified, a **read-only sample delivery test** can be scheduled through `sites.create_schedule`. Its prompt must explicitly call the synthetic report a test, preserve its actual source time, and not claim a newly generated live portfolio. A short one-time cloud delivery test is more informative than declaring an unobserved recurring task functional. Inspect the returned task and the eventual result. Establish the recurring cadence only with accurate production/pilot labeling.

`sites.create_schedule` expressly creates and links a cloud task, so it addresses the local-desktop scheduler gap. Its exposed fields are `title`, `prompt`, `schedule` (iCal VEVENT), and `timezone`; **there is no destination conversation field**. Therefore it does not establish same-chat delivery, mobile push behavior, or automatic context retention. The task result/link must be inspected and the phone tested. The Site MCP is what preserves retrievable context across whichever conversation receives the task result.

### Important limits of this pilot

- A private Site and its source repository do **not** automatically create the user-requested private repository on their own GitHub account. Track that requirement separately.
- A fictional snapshot requires no database writer. Genuine unattended refresh requires a cloud-callable writer/data pipeline, durable storage, fresh market input, and independently verified source access. Do not imply that scheduling reads refreshes data.
- Sites runs JavaScript on Cloudflare Workers. A Python ledger engine on the laptop will remain unavailable while the laptop is off; production must deploy the calculation job separately or port only after matching accounting tests. Use versioned reports as the interface so hosting choice does not change calculation semantics.
- Sites gateway identity and read permissions solve Site access, not broker access. No Robinhood connection is needed or proposed for this pilot.
- Do not generate a Sites bypass credential merely to inspect the capability. If supported service access already exists, it is not visitor identity or connected-app consent. The MCP user path is simpler for the read-only pilot.
- The Sites skill requires verifying an intended unattended writer and reading back persisted output before calling a recurring **update** ready. No writer is implemented or tested by a static report read.
- Direct use of the Pages hosted controller would enable an additional default controller, and public Space docs advise verifying recurring work separately. It is less direct than the Sites `create_schedule` cloud task for this initial pilot.
