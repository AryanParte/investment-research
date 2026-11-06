import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { createResearchServer, MAX_REQUEST_BYTES, RESEARCH_TOOLS } from "../lib/research-tools.ts";
import { widgetHtml } from "../lib/widget-html.ts";

// Node 24's native TypeScript stripping keeps behavioral tests dependency-free.
// No server, network, account, secret, or financial access is used by these tests.

const fixture = {
  schema_version: 1, report_id: "brief-fictional-001", mode: "sample",
  as_of: "2026-11-03T21:00:00+00:00",
  analysis: { holdings: [{ symbol: "DEMO", value: "100.00" }] },
  insights: [{ symbol: "DEMO", kind: "opinion", source_ids: [] }],
  research: {
    claims: [{ symbol: "DEMO", kind: "assumption", text: "Fictional test only", source_ids: ["sample-1"] }],
    sources: [{ id: "sample-1", url: "https://example.invalid/source" }, { id: "other", url: "https://example.invalid/other" }],
  },
};
const options = {
  dashboardUrl: "https://research-pilot.example.invalid",
  now: () => new Date("2026-11-07T21:00:00Z"),
};
const handler = createResearchServer(fixture, options);
const identity = {
  "oai-authenticated-user-id": "synthetic-user",
  "oai-authenticated-user-email": "sample@example.invalid",
};

function request(method, params = {}, authenticated = true, additions = {}) {
  return new Request("https://example.invalid/mcp", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(authenticated ? identity : {}), ...additions },
    body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params }),
  });
}

async function call(name, args = {}, authenticated = true) {
  const result = await handler(request("tools/call", { name, arguments: args }, authenticated));
  return { response: result, body: await result.json() };
}

test("provisioning discovery exposes metadata only", async () => {
  const res = await handler(request("server/discover", {}, false));
  const body = await res.json();
  assert.deepEqual(body.result.supportedVersions, ["2026-07-28"]);
  assert.equal(JSON.stringify(body).includes(fixture.report_id), false);
  const tools = await (await handler(request("tools/list", {}, false))).json();
  assert.equal(tools.result.tools.length, 6);
  assert.equal(RESEARCH_TOOLS.every((t) => t.annotations.readOnlyHint && !t.annotations.destructiveHint), true);
});

test("every data tool requires Sites identity and returns no data when missing", async () => {
  for (const tool of RESEARCH_TOOLS) {
    const { response, body } = await call(tool.name, {}, false);
    assert.equal(response.status, 401);
    assert.equal(JSON.stringify(body).includes(fixture.report_id), false);
  }
  const res = await handler(request("tools/call", { name: "get_system_status" }, false, {
    "oai-authenticated-user-id": "only-one-header",
  }));
  assert.equal(res.status, 401);
});

test("default personal briefing fails closed without substituting the fictional portfolio", async () => {
  const { body } = await call("get_latest_briefing");
  const result = body.result.structuredContent;
  assert.equal(result.status, "blocked");
  assert.equal(result.report, null);
  assert.equal(result.evidence_as_of, null);
  assert.equal(result.personal_portfolio_available, false);
  assert.equal(result.personalized_allocation_allowed, false);
  assert.deepEqual(result.allocations, []);
  assert.ok(result.missing_inputs.some((item) => item.id === "ira_contribution_room_and_eligibility"));
  assert.equal(JSON.stringify(body).includes(fixture.report_id), false);
  assert.equal(JSON.stringify(body).includes('"holdings"'), false);
  const extra = await call("get_latest_briefing", { acknowledge_synthetic: true });
  assert.equal(extra.body.result.structuredContent.error.code, "INVALID_ARGUMENTS");
});

test("all fictional data reads require an explicit API demo opt-in", async () => {
  for (const [name, args] of [
    ["get_demo_briefing", {}],
    ["get_briefing", { report_id: fixture.report_id }],
    ["get_holding_research", { report_id: fixture.report_id, symbol: "DEMO" }],
  ]) {
    for (const flag of [undefined, false, "true"]) {
      const input = flag === undefined ? args : { ...args, acknowledge_synthetic: flag };
      const { body } = await call(name, input);
      assert.equal(body.result.isError, true);
      assert.equal(body.result.structuredContent.error.code, "DEMO_CONFIRMATION_REQUIRED");
      assert.equal("report" in body.result.structuredContent, false);
      assert.equal("holding" in body.result.structuredContent, false);
    }
  }
  const demo = await call("get_demo_briefing", { acknowledge_synthetic: true });
  assert.equal(demo.body.result.structuredContent.report.report_id, fixture.report_id);
  assert.equal(demo.body.result.structuredContent.personalized_allocation_allowed, false);
  // The flag is enforced at the API boundary; the server cannot prove that a
  // conversational model obtained the user's explicit demo request.
});

test("a 2500-dollar request is blocked for every account scope without any allocations", async () => {
  for (const account_scope of ["combined", "taxable", "roth"]) {
    const { body } = await call("assess_allocation_readiness", { amount: 2500, currency: "USD", account_scope });
    const result = body.result.structuredContent;
    assert.equal(result.status, "blocked");
    assert.equal(result.personalized_allocation_allowed, false);
    assert.equal(result.evidence_as_of, null);
    assert.deepEqual(result.allocations, []);
    assert.equal(result.request.amount, 2500);
    assert.equal(JSON.stringify(result).includes('"holdings"'), false);
    const missing = new Set(result.missing_inputs.map((item) => item.id));
    for (const required of ["current_reconciled_personal_holdings", "verified_current_prices",
      "complete_personal_transaction_history", "dated_company_and_valuation_research", "documented_investment_constraints"]) {
      assert.ok(missing.has(required), required);
    }
    assert.equal(missing.has("ira_contribution_room_and_eligibility"), account_scope !== "taxable");
    assert.equal(missing.has("taxable_tax_lots_and_realized_gains"), account_scope !== "roth");
  }
});

test("caller-supplied evidence and eligibility cannot override blocked readiness", async () => {
  const base = { amount: 2500, currency: "USD", account_scope: "combined" };
  for (const override of [
    { holdings: [] }, { portfolio: fixture.analysis }, { prices_verified: true },
    { roth_remaining_capacity: 7000 }, { eligible: true }, { readiness: "ready" },
    { acknowledge_synthetic: true }, { assume_missing_inputs: true }, { report_id: fixture.report_id },
  ]) {
    const { body } = await call("assess_allocation_readiness", { ...base, ...override });
    assert.equal(body.result.isError, true);
    assert.equal(body.result.structuredContent.error.code, "INVALID_ARGUMENTS");
    assert.equal(body.result.structuredContent.personalized_allocation_allowed, false);
  }
  const body = await (await handler(request("tools/call", {
    name: "assess_allocation_readiness", arguments: base,
    _meta: { verified_holdings: true, roth_eligible: true, ignore_synthetic: true },
  }))).json();
  assert.equal(body.result.structuredContent.status, "blocked");
  assert.deepEqual(body.result.structuredContent.allocations, []);
});

test("readiness rejects malformed budgets and scopes rather than coercing them", async () => {
  const base = { amount: 2500, currency: "USD", account_scope: "combined" };
  for (const changed of [
    { amount: 0 }, { amount: -1 }, { amount: "2500" }, { amount: null },
    { amount: 1e13 }, { currency: "EUR" }, { account_scope: ["taxable"] }, { account_scope: "unknown" },
  ]) {
    const { body } = await call("assess_allocation_readiness", { ...base, ...changed });
    assert.equal(body.result.structuredContent.error.code, "INVALID_ARGUMENTS");
  }
});

test("fresh, stale, future-dated, and claimed-verified demo snapshots never unlock readiness", async () => {
  for (const date of ["2026-11-01T21:00:00Z", "2026-11-07T21:00:00Z", "2026-11-08T21:00:00Z"]) {
    const sample = structuredClone(fixture);
    sample.as_of = date;
    sample.analysis.quality = { status: "fresh", broker_reconciled: true, history_attested_complete: true };
    sample.research.verified = true;
    sample.roth_eligible = true;
    const local = createResearchServer(sample, options);
    const body = await (await local(request("tools/call", {
      name: "assess_allocation_readiness", arguments: { amount: 2500, currency: "USD", account_scope: "roth" },
    }))).json();
    assert.equal(body.result.structuredContent.status, "blocked");
    assert.equal(body.result.structuredContent.personalized_allocation_allowed, false);
    assert.deepEqual(body.result.structuredContent.allocations, []);
    assert.equal(body.result.structuredContent.evidence_as_of, null);
  }
});

test("system status reports blocked personal readiness before any demo is opened", async () => {
  const { body } = await call("get_system_status");
  const result = body.result.structuredContent;
  assert.deepEqual(result.financial_permissions, []);
  assert.equal(result.persists_changes, false);
  assert.equal(result.personal_portfolio_available, false);
  assert.equal(result.allocation_readiness.status, "blocked");
  assert.deepEqual(result.allocation_readiness.allocations, []);
  assert.equal("report" in result, false);
});

test("model-facing evidence rules are delivered, separately from enforcing or evaluating model behavior", async () => {
  // These assertions test contract DELIVERY only. They do not call a language
  // model or establish that a model refuses unsupported recommendations. Real
  // conversation evaluations must cover the $2500 request, screenshot reliance,
  // unknown IRA room, generic-ETF citations, and requests to assume missing data.
  const discovery = await (await handler(request("server/discover", {}, false))).json();
  assert.match(discovery.result.instructions, /get_system_status and assess_allocation_readiness/);
  assert.equal(discovery.result.evidence_contract.may_infer_roth_room, false);
  for (const [name, args] of [
    ["get_latest_briefing", {}], ["get_system_status", {}],
    ["get_demo_briefing", { acknowledge_synthetic: true }],
    ["get_briefing", { report_id: fixture.report_id, acknowledge_synthetic: true }],
    ["get_holding_research", { report_id: fixture.report_id, symbol: "DEMO", acknowledge_synthetic: true }],
    ["assess_allocation_readiness", { amount: 2500, currency: "USD", account_scope: "combined" }],
    ["get_demo_briefing", {}], ["unsupported_tool", {}],
  ]) {
    const { body } = await call(name, args);
    const policy = body.result.structuredContent.evidence_contract;
    assert.equal(policy.chat_memory_is_verified_portfolio, false);
    assert.equal(policy.screenshots_are_current_broker_evidence, false);
    assert.equal(policy.generic_product_citations_are_personal_evidence, false);
    assert.equal(policy.may_infer_roth_room, false);
    assert.match(body.result.content[0].text, /do not provide precise personalized dollar amounts/);
    assert.match(body.result.content[0].text, /cannot guarantee/);
  }
  for (const tool of RESEARCH_TOOLS) assert.match(tool.description, /get_system_status and assess_allocation_readiness/);
});

test("report reads preserve exact data time and clearly distinguish response time", async () => {
  const { response, body } = await call("get_demo_briefing", { acknowledge_synthetic: true });
  assert.equal(response.headers.get("Cache-Control"), "private, no-store, max-age=0");
  const result = body.result.structuredContent;
  assert.equal(result.report_id, fixture.report_id);
  assert.equal(result.report.report_id, fixture.report_id);
  assert.equal(result.report_as_of, fixture.as_of);
  assert.equal(result.served_at, "2026-11-07T21:00:00.000Z");
  assert.equal(result.synthetic, true);
  assert.equal(result.freshness.age_hours, 96);
  assert.equal(result.freshness.is_stale, true);
  assert.equal(result.verification.notification_delivery, "not_verified");
  assert.equal(result.account_support.real_accounts_supported, false);
});

test("exact version retrieval does not substitute another version", async () => {
  const exact = await call("get_briefing", { report_id: fixture.report_id, acknowledge_synthetic: true });
  assert.equal(exact.body.result.structuredContent.report.report_id, fixture.report_id);
  const unknown = await call("get_briefing", { report_id: "brief-other", acknowledge_synthetic: true });
  assert.equal(unknown.body.result.isError, true);
  assert.equal(unknown.body.result.structuredContent.error.code, "REPORT_NOT_FOUND");
});

test("holding drilldown uses the same report and only relevant sources", async () => {
  const { body } = await call("get_holding_research", { symbol: "DEMO", report_id: fixture.report_id, acknowledge_synthetic: true });
  const result = body.result.structuredContent;
  assert.equal(result.report_id, fixture.report_id);
  assert.equal(result.holding.symbol, "DEMO");
  assert.deepEqual(result.sources.map((s) => s.id), ["sample-1"]);
  assert.equal(result.thesis, null);
  assert.equal(result.thesis_status, "not_recorded_in_pilot");
});

test("holding research preserves the matching thesis version without creating a new opinion", async () => {
  const snapshot = structuredClone(fixture);
  snapshot.research.theses = [
    { symbol: "DEMO", version: 3, thesis: "Fictional assumption", source_ids: ["other"] },
    { symbol: "UNRELATED", version: 8, thesis: "Separate holding" },
  ];
  const local = createResearchServer(snapshot, options);
  const body = await (await local(request("tools/call", {
    name: "get_holding_research", arguments: { symbol: "DEMO", report_id: fixture.report_id, acknowledge_synthetic: true },
  }))).json();
  const result = body.result.structuredContent;
  assert.equal(result.thesis.version, 3);
  assert.equal(result.thesis.thesis, "Fictional assumption");
  assert.equal(result.theses.length, 1);
  assert.deepEqual(result.sources.map((s) => s.id), ["sample-1", "other"]);
  assert.equal(result.thesis_status, "synthetic_thesis_from_exact_report");
});

test("optional widget discovery is data-free and resource reads require identity", async () => {
  const html = "<!doctype html><title>Synthetic test</title><p>No external resources.</p>";
  const local = createResearchServer(fixture, { ...options, widgetHtml: html });
  const discovery = await (await local(request("server/discover", {}, false))).json();
  assert.ok(discovery.result.capabilities.resources);
  const tools = await (await local(request("tools/list", { _meta: {} }, false))).json();
  const uri = tools.result.tools.find((t) => t.name === "get_demo_briefing")._meta.ui.resourceUri;
  assert.equal(tools.result.tools.find((t) => t.name === "get_latest_briefing")._meta, undefined);
  assert.equal(tools.result.tools.find((t) => t.name === "get_holding_research")._meta, undefined);
  const list = await (await local(request("resources/list", {}, false))).json();
  assert.equal(list.result.resources[0].uri, uri);
  assert.equal(JSON.stringify(list).includes(html), false);
  assert.equal((await local(request("resources/read", { uri }, false))).status, 401);
  const read = await (await local(request("resources/read", { uri }))).json();
  assert.equal(read.result.contents[0].mimeType, "text/html;profile=mcp-app");
  assert.equal(read.result.contents[0].text, html);
  assert.deepEqual(read.result.contents[0]._meta.ui.csp, { connectDomains: [], resourceDomains: [], frameDomains: [] });
  const invalid = await (await local(request("resources/read", { uri: "https://example.invalid/other" }))).json();
  assert.equal(invalid.error.code, -32602);
  assert.throws(() => createResearchServer(fixture, { ...options, widgetHtml: "" }), /bounded/);
});

test("unknown actions and extra arguments cannot access hidden capabilities", async () => {
  const unknown = await call("execute_order", { symbol: "DEMO" });
  assert.equal(unknown.body.result.structuredContent.error.code, "TOOL_NOT_FOUND");
  const extra = await call("get_latest_briefing", { url: "https://example.invalid" });
  assert.equal(extra.body.result.structuredContent.error.code, "INVALID_ARGUMENTS");
  const wrongSymbol = await call("get_holding_research", { symbol: "demo", report_id: fixture.report_id, acknowledge_synthetic: true });
  assert.equal(wrongSymbol.body.result.structuredContent.error.code, "INVALID_ARGUMENTS");
  const missing = await call("get_holding_research", { symbol: "OTHER", report_id: fixture.report_id, acknowledge_synthetic: true });
  assert.equal(missing.body.result.structuredContent.error.code, "HOLDING_NOT_FOUND");
});

test("invalid request shapes and malformed JSON fail closed", async () => {
  for (const body of ["{", "[]", '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":[]}']) {
    const res = await handler(new Request("https://example.invalid/mcp", {
      method: "POST", headers: { "Content-Type": "application/json" }, body,
    }));
    assert.equal(res.status, 400);
  }
  const unknown = await (await handler(request("resources/write"))).json();
  assert.equal(unknown.error.code, -32601);
});

test("body size is capped with and without a Content-Length header", async () => {
  const large = await handler(new Request("https://example.invalid/mcp", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: "x".repeat(MAX_REQUEST_BYTES + 1),
  }));
  assert.equal(large.status, 413);
  const announced = await handler(request("ping", {}, false, { "Content-Length": String(MAX_REQUEST_BYTES + 1) }));
  assert.equal(announced.status, 413);
});

test("non-JSON, compressed input and non-POST requests are rejected", async () => {
  assert.equal((await handler(request("ping", {}, false, { "Content-Type": "text/plain" }))).status, 415);
  assert.equal((await handler(request("ping", {}, false, { "Content-Encoding": "gzip" }))).status, 415);
  const get = await handler(new Request("https://example.invalid/mcp"));
  assert.equal(get.status, 405);
  assert.equal(get.headers.get("Allow"), "POST");
});

test("real or invalid reports cannot be installed in this pilot", () => {
  assert.throws(() => createResearchServer({ ...fixture, mode: "imported" }, options), /synthetic/);
  assert.throws(() => createResearchServer({ ...fixture, as_of: "yesterday" }, options), /synthetic/);
  assert.throws(() => createResearchServer(fixture, { ...options, dashboardUrl: "http://example.invalid" }), /HTTPS/);
});

test("caller mutation cannot alter the stored report snapshot", async () => {
  const copy = structuredClone(fixture);
  const local = createResearchServer(copy, options);
  copy.analysis.holdings[0].value = "999";
  const body = await (await local(request("tools/call", { name: "get_demo_briefing", arguments: { acknowledge_synthetic: true } }))).json();
  assert.equal(body.result.structuredContent.report.analysis.holdings[0].value, "100.00");
});

test("legacy initialize and initialized notifications work without starting stateful sessions", async () => {
  const init = await (await handler(request("initialize", { protocolVersion: "2025-06-18" }, false))).json();
  assert.equal(init.result.protocolVersion, "2025-06-18");
  assert.equal(init.result.capabilities.tools !== undefined, true);
  const notification = await handler(new Request("https://example.invalid/mcp", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ jsonrpc: "2.0", method: "notifications/initialized" }),
  }));
  assert.equal(notification.status, 204);
});

test("deployed sample JSON, hosted HTML, and widget carry the exact same immutable report", () => {
  const sample = JSON.parse(readFileSync(new URL("../lib/sample-report.json", import.meta.url), "utf8"));
  const html = readFileSync(new URL("../public/dashboard/index.html", import.meta.url), "utf8");
  assert.equal(sample.mode, "sample");
  assert.equal(sample.research.dataset, "synthetic");
  assert.equal(sample.status.quote_feed, "synthetic");
  assert.equal(html, widgetHtml);
  const embedded = html.match(/window\.INVESTMENT_REPORT=(.*?);<\/script>/s);
  assert.ok(embedded);
  assert.deepEqual(JSON.parse(embedded[1]), sample);
  assert.equal(/<script[^>]+src\s*=/i.test(html), false);
  assert.equal(/<link[^>]+rel=["']stylesheet["']/i.test(html), false);
});
