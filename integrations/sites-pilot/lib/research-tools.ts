/**
 * Financially read-only MCP interface over one immutable, fictional report.
 * Sites' private gateway is the trust boundary for the injected identity headers.
 * Never expose this handler at an origin that permits callers to forge those headers.
 * No brokerage clients, network calls, writes, logging, or model calls belong here.
 */

type JsonRecord = Record<string, unknown>;
type RpcId = string | number | null;

export type SampleReport = JsonRecord & {
  report_id: string;
  schema_version: number;
  mode: "sample";
  as_of: string;
  analysis: JsonRecord;
};

type ServerOptions = {
  dashboardUrl: string;
  now?: () => Date;
  /** Trusted, self-contained build output only; never HTML supplied by a tool caller. */
  widgetHtml?: string;
};

export const MAX_REQUEST_BYTES = 32 * 1024;
export const STALE_AFTER_HOURS = 72;
const MAX_REPORT_BYTES = 1024 * 1024;
const MAX_WIDGET_BYTES = 2 * 1024 * 1024;
const WIDGET_MIME = "text/html;profile=mcp-app";
const USER_ID_HEADER = "oai-authenticated-user-id";
const USER_EMAIL_HEADER = "oai-authenticated-user-email";
const ANNOTATIONS = {
  readOnlyHint: true,
  destructiveHint: false,
  openWorldHint: false,
  idempotentHint: true,
};

export const MODEL_INSTRUCTIONS = "Before personalized portfolio or account-allocation advice, call get_system_status and assess_allocation_readiness. When readiness is blocked, do not provide precise personalized dollar amounts, percentages, ticker allocations, Roth/taxable splits, or buy/trim/sell instructions. State the missing evidence and offer clearly labeled general education only. Never treat synthetic fixtures, chat memory, or screenshots as current verified broker holdings. Never infer Roth eligibility or contribution room from age, salary, account balance, or an assumed filing status. An explicit demo request permits fictional exploration only and cannot unlock personal advice. Cite evidence appropriate to each claim: an ETF factsheet supports product facts, not this user's allocation, concentration, suitability, or IRA room; tax rules alone do not establish personal eligibility. Do not replace missing evidence with assumptions or implied verification. These are model behavior requirements; this read-only server cannot guarantee that a conversational model follows them.";
const ADVICE_GUARD = "Before personalized advice, call get_system_status and assess_allocation_readiness. Blocked readiness prohibits precise personalized allocations; generic product citations do not establish portfolio evidence.";
const EVIDENCE_CONTRACT = {
  version: "2026-11-05.1",
  personal_portfolio_available: false,
  personalized_allocation_allowed: false,
  model_must_check: ["get_system_status", "assess_allocation_readiness"],
  chat_memory_is_verified_portfolio: false,
  screenshots_are_current_broker_evidence: false,
  may_infer_roth_room: false,
  demo_is_personal_evidence: false,
  generic_product_citations_are_personal_evidence: false,
  server_enforcement: "No personal report, allocations, or eligibility override is provided. Demo reads require explicit API opt-in.",
  model_behavior_limit: "Instruction delivery is testable; model adherence and absence of hallucination require separate conversation evaluation.",
};

function evidencePolicy(): JsonRecord {
  return {
    model_instructions: MODEL_INSTRUCTIONS,
    evidence_contract: EVIDENCE_CONTRACT,
    personal_portfolio_available: false,
    personalized_allocation_allowed: false,
  };
}

const emptyInput = {
  type: "object", properties: {}, additionalProperties: false,
};
const reportIdProperty = {
  type: "string", minLength: 1, maxLength: 100,
  description: "Exact immutable fictional report_id returned by get_demo_briefing; never a personal portfolio ID.",
};
const demoConfirmation = {
  type: "boolean", const: true,
  description: "Set true only after the user explicitly requests a fictional demo. This is not evidence or permission for personal advice.",
};

const objectList = { type: "array", items: { type: "object" } };
const policyProperties = {
  model_instructions: { type: "string" }, evidence_contract: { type: "object" },
  personal_portfolio_available: { const: false }, personalized_allocation_allowed: { const: false },
};
const outputProperties = {
  ...policyProperties,
  report_id: { type: "string" }, report_as_of: { type: "string" }, served_at: { type: "string" },
  mode: { const: "sample" }, synthetic: { const: true }, dashboard_url: { type: "string" },
  freshness: { type: "object" }, account_support: { type: "object" }, verification: { type: "object" },
};
function outputSchema(extra: JsonRecord, required: string[], includeDemoContext = true) {
  const base = includeDemoContext ? outputProperties : policyProperties;
  return {
    type: "object",
    oneOf: [
      {
        properties: { ...base, ...extra },
        required: [...Object.keys(base), ...required], additionalProperties: false,
      },
      {
        properties: { ...policyProperties, error: {
          type: "object", properties: { code: { type: "string" }, message: { type: "string" } },
          required: ["code", "message"], additionalProperties: false,
        } },
        required: [...Object.keys(policyProperties), "error"], additionalProperties: false,
      },
    ],
  };
}
const briefingOutput = outputSchema({ report: { type: "object" } }, ["report"]);
const blockedProperties = {
  status: { const: "blocked" }, checked_at: { type: "string" },
  evidence_as_of: { type: "null" }, reason_codes: { type: "array", items: { type: "string" } },
  missing_inputs: objectList, allocations: { type: "array", maxItems: 0 },
  next_step: { type: "string" },
};

export const RESEARCH_TOOLS = [
  {
    name: "get_latest_briefing",
    title: "Check whether a personal briefing is available",
    description: `This pilot has no verified personal portfolio. Returns blocked with missing inputs and no report or allocations; never substitutes fictional data. Use get_demo_briefing only for an explicit demo request. ${ADVICE_GUARD}`,
    inputSchema: emptyInput,
    outputSchema: outputSchema({ ...blockedProperties, report: { type: "null" }, demo_available: { const: true } },
      [...Object.keys(blockedProperties), "report", "demo_available"], false),
    annotations: ANNOTATIONS,
  },
  {
    name: "get_demo_briefing",
    title: "Open an explicitly requested fictional demo",
    description: `Only after the user explicitly requests a demo, return fictional holdings and a sample dashboard. No demo value, source, or insight describes the user's accounts or supports personal recommendations. ${ADVICE_GUARD}`,
    inputSchema: {
      type: "object", properties: { acknowledge_synthetic: demoConfirmation },
      required: ["acknowledge_synthetic"], additionalProperties: false,
    },
    outputSchema: briefingOutput,
    annotations: ANNOTATIONS,
  },
  {
    name: "get_briefing",
    title: "Read an exact fictional demo version",
    description: `Requires explicit synthetic-demo opt-in. Retrieve only the exact fictional report_id; no substitute date and no personal portfolio evidence. ${ADVICE_GUARD}`,
    inputSchema: {
      type: "object", properties: { report_id: reportIdProperty, acknowledge_synthetic: demoConfirmation },
      required: ["report_id", "acknowledge_synthetic"], additionalProperties: false,
    },
    outputSchema: briefingOutput,
    annotations: ANNOTATIONS,
  },
  {
    name: "get_holding_research",
    title: "Read fictional holding evidence from a demo",
    description: `Requires explicit synthetic-demo opt-in. Returns fictional claims, sources, thesis versions, and insights from an exact sample report. They are never evidence of the user's holdings or current opportunities. ${ADVICE_GUARD}`,
    inputSchema: {
      type: "object",
      properties: {
        symbol: { type: "string", pattern: "^[A-Z][A-Z0-9.-]{0,14}$", maxLength: 15 },
        report_id: reportIdProperty,
        acknowledge_synthetic: demoConfirmation,
      },
      required: ["symbol", "report_id", "acknowledge_synthetic"], additionalProperties: false,
    },
    outputSchema: outputSchema({
      symbol: { type: "string" }, holding: { type: "object" }, claims: objectList, insights: objectList,
      sources: objectList, theses: objectList, thesis: { type: ["object", "null"] },
      thesis_status: { type: "string" }, research_status: { type: "string" },
    }, ["symbol", "holding", "claims", "insights", "sources", "theses", "thesis", "thesis_status", "research_status"]),
    annotations: ANNOTATIONS,
  },
  {
    name: "get_system_status",
    title: "Read pilot limitations and freshness",
    description: `Required before portfolio advice. Read the pilot's capabilities, missing evidence, and blocked readiness. This server has no verified personal holdings, current prices, IRA eligibility, or contribution-room record. ${ADVICE_GUARD}`,
    inputSchema: emptyInput,
    outputSchema: outputSchema({
      financial_permissions: { type: "array", maxItems: 0 },
      live_market_data: { const: false }, persists_changes: { const: false },
      allocation_readiness: { type: "object" },
    }, ["financial_permissions", "live_market_data", "persists_changes", "allocation_readiness"]),
    annotations: ANNOTATIONS,
  },
  {
    name: "assess_allocation_readiness",
    title: "Check evidence before recommending an allocation",
    description: `Required for a request such as 'I have $500 to invest'. This sample-only pilot always returns blocked, missing evidence, and an empty allocations array. Amount is an unsaved scenario budget, never an investment/contribution instruction. No portfolio, prices, evidence, eligibility, or override may be supplied as arguments. ${ADVICE_GUARD}`,
    inputSchema: {
      type: "object",
      properties: {
        amount: { type: "number", exclusiveMinimum: 0, maximum: 1_000_000_000_000 },
        currency: { type: "string", enum: ["USD"] },
        account_scope: { type: "string", enum: ["combined", "taxable", "roth"] },
      },
      required: ["amount", "currency", "account_scope"], additionalProperties: false,
    },
    outputSchema: outputSchema({ ...blockedProperties, request: {
      type: "object", properties: {
        amount: { type: "number" }, currency: { const: "USD" },
        account_scope: { enum: ["combined", "taxable", "roth"] },
      }, required: ["amount", "currency", "account_scope"], additionalProperties: false,
    } }, [...Object.keys(blockedProperties), "request"], false),
    annotations: ANNOTATIONS,
  },
] as const;

function isRecord(value: unknown): value is JsonRecord {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function records(value: unknown): JsonRecord[] {
  return Array.isArray(value) ? value.filter(isRecord) : [];
}

function response(body: unknown, status = 200): Response {
  return new Response(body === null ? null : JSON.stringify(body), {
    status,
    headers: {
      ...(body === null ? {} : { "Content-Type": "application/json; charset=utf-8" }),
      "Cache-Control": "private, no-store, max-age=0",
      "Vary": "Authorization, Cookie, oai-authenticated-user-id, oai-authenticated-user-email",
      "X-Content-Type-Options": "nosniff",
    },
  });
}

function rpcError(id: RpcId, code: number, message: string, status = 200): Response {
  return response({ jsonrpc: "2.0", id, error: { code, message } }, status);
}

function success(id: RpcId, result: unknown): Response {
  return response({ jsonrpc: "2.0", id, result });
}

function toolError(code: string, message: string): JsonRecord {
  return {
    isError: true,
    content: [{ type: "text", text: `${message}\n\n${MODEL_INSTRUCTIONS}` }],
    structuredContent: { ...evidencePolicy(), error: { code, message } },
  };
}

function onlyKeys(value: JsonRecord, permitted: string[]): boolean {
  return Object.keys(value).every((key) => permitted.includes(key));
}

function validId(value: unknown): value is string | number {
  return (typeof value === "string" && value.length <= 128) ||
    (typeof value === "number" && Number.isSafeInteger(value));
}

function hasIdentity(request: Request): boolean {
  const userId = request.headers.get(USER_ID_HEADER)?.trim();
  const email = request.headers.get(USER_EMAIL_HEADER)?.trim();
  return Boolean(userId && email && userId.length <= 256 && email.length <= 320);
}

class BodyLimitError extends Error {}

async function boundedJson(request: Request): Promise<unknown> {
  const advertisedLength = request.headers.get("content-length");
  if (advertisedLength && (!/^\d+$/.test(advertisedLength) || Number(advertisedLength) > MAX_REQUEST_BYTES)) {
    throw new BodyLimitError();
  }
  const reader = request.body?.getReader();
  if (!reader) throw new SyntaxError();
  const chunks: Uint8Array[] = [];
  let total = 0;
  try {
    while (true) {
      const next = await reader.read();
      if (next.done) break;
      total += next.value.byteLength;
      if (total > MAX_REQUEST_BYTES) {
        await reader.cancel();
        throw new BodyLimitError();
      }
      chunks.push(next.value);
    }
  } finally {
    reader.releaseLock();
  }
  const bytes = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
}

/** Snapshot cloned on construction: UI and tool reads retain identical report identity. */
export function createResearchServer(inputReport: unknown, options: ServerOptions) {
  if (!isRecord(inputReport) || inputReport.mode !== "sample" ||
      typeof inputReport.report_id !== "string" || !/^brief-[A-Za-z0-9_-]{1,90}$/.test(inputReport.report_id) ||
      inputReport.schema_version !== 1 || !isRecord(inputReport.analysis) ||
      typeof inputReport.as_of !== "string" || !/(Z|[+-]\d{2}:\d{2})$/.test(inputReport.as_of) ||
      !Number.isFinite(Date.parse(inputReport.as_of))) {
    throw new Error("Pilot requires a valid synthetic report. Real account data is not supported.");
  }
  const encoded = JSON.stringify(inputReport);
  if (new TextEncoder().encode(encoded).byteLength > MAX_REPORT_BYTES) {
    throw new Error("Synthetic report exceeds the pilot response limit.");
  }
  const report = JSON.parse(encoded) as SampleReport;
  const widgetHtml = options.widgetHtml;
  if (widgetHtml !== undefined && (typeof widgetHtml !== "string" || !widgetHtml.trim() ||
      new TextEncoder().encode(widgetHtml).byteLength > MAX_WIDGET_BYTES)) {
    throw new Error("Widget must be a bounded, trusted, self-contained build artifact.");
  }
  // Each immutable bundled snapshot gets its own resource cache key.
  const widgetUri = `ui://investment/${report.report_id}/briefing-v1.html`;
  const capabilities = { tools: {}, ...(widgetHtml ? { resources: {} } : {}) };
  const tools = RESEARCH_TOOLS.map((tool) => ({
    ...tool,
    ...(widgetHtml && ["get_demo_briefing", "get_briefing"].includes(tool.name)
      ? { _meta: { ui: { resourceUri: widgetUri } } } : {}),
  }));
  const dashboard = new URL(options.dashboardUrl);
  if (dashboard.protocol !== "https:" || dashboard.username || dashboard.password || dashboard.search || dashboard.hash) {
    throw new Error("Dashboard must be a credential-free HTTPS origin or path.");
  }
  const now = options.now ?? (() => new Date());

  function context(): JsonRecord {
    const servedAt = now();
    if (!Number.isFinite(servedAt.getTime())) throw new Error("Invalid server time");
    const ageHours = (servedAt.getTime() - Date.parse(report.as_of)) / 3_600_000;
    return {
      ...evidencePolicy(),
      report_id: report.report_id,
      report_as_of: report.as_of,
      served_at: servedAt.toISOString(),
      mode: "sample",
      synthetic: true,
      dashboard_url: dashboard.href,
      freshness: {
        state: ageHours < 0 ? "future_dated_synthetic_snapshot" : "fixed_synthetic_snapshot",
        age_hours: Math.round(ageHours * 100) / 100,
        is_stale: ageHours > STALE_AFTER_HOURS,
        is_future_dated: ageHours < 0,
        review_after_hours: STALE_AFTER_HOURS,
        threshold_basis: "Pilot display rule only; not a market-data freshness standard.",
        notice: "Retrieving this report does not update its portfolio or prices. No live data is connected.",
      },
      account_support: {
        real_accounts_supported: false,
        brokerage_connection: "none",
        financial_actions: "absent",
      },
      verification: {
        notification_delivery: "not_verified",
        mobile_rendering: "not_verified",
        cloud_scheduled_run: "not_verified",
      },
    };
  }

  function blockedReadiness(scope: "combined" | "taxable" | "roth"): JsonRecord {
    const missing = [
      { id: "current_reconciled_personal_holdings", reason: "A dated, validated import of actual holdings, cash, and account types across the portfolio is unavailable. Screenshots and conversation memory are not a current reconciliation." },
      { id: "verified_current_prices", reason: "No real market-price feed or verified price timestamps for holdings and alternatives are available." },
      { id: "complete_personal_transaction_history", reason: "Actual deposits, withdrawals, trades, fees, and distributions have not been imported and reconciled." },
      { id: "dated_company_and_valuation_research", reason: "No verified current company/instrument research supports a portfolio-specific comparison. Product factsheets alone do not establish suitable allocation sizes." },
      { id: "documented_investment_constraints", reason: "Current horizon, liquidity needs, loss tolerance, and concentration limits are not recorded as validated research inputs." },
    ];
    if (scope !== "roth") missing.push({
      id: "taxable_tax_lots_and_realized_gains",
      reason: "Actual cost basis, holding periods, and realized gains are unavailable for taxable rotation analysis.",
    });
    if (scope !== "taxable") missing.push({
      id: "ira_contribution_room_and_eligibility",
      reason: "Tax year, filing status, relevant income/compensation, and contributions designated for that year across all traditional and Roth IRAs are unverified. Account balance is not contributions; no remaining room or eligibility may be inferred.",
    });
    return {
      ...evidencePolicy(),
      status: "blocked",
      checked_at: now().toISOString(),
      evidence_as_of: null,
      reason_codes: ["SYNTHETIC_ONLY_PILOT", "VERIFIED_PERSONAL_EVIDENCE_UNAVAILABLE"],
      missing_inputs: missing,
      allocations: [],
      next_step: "Explain the missing evidence. Offer general education or an explicitly requested fictional demo, not precise personal allocations. This pilot has no endpoint that can validate personal inputs or unlock readiness.",
    };
  }

  function toolResult(name: string, args: JsonRecord): JsonRecord {
    if (name === "get_latest_briefing" || name === "get_system_status") {
      if (!onlyKeys(args, [])) return toolError("INVALID_ARGUMENTS", "This tool accepts an empty arguments object only.");
    } else if (name === "get_demo_briefing") {
      if (!onlyKeys(args, ["acknowledge_synthetic"])) return toolError("INVALID_ARGUMENTS", "Only acknowledge_synthetic is accepted for a demo request.");
      if (args.acknowledge_synthetic !== true) return toolError("DEMO_CONFIRMATION_REQUIRED", "Only an explicitly requested fictional demo may be opened. Set acknowledge_synthetic=true only for that request; it never authorizes personal advice.");
    } else if (name === "get_briefing" || name === "get_holding_research") {
      const allowed = name === "get_briefing" ? ["report_id", "acknowledge_synthetic"] : ["report_id", "symbol", "acknowledge_synthetic"];
      if (!onlyKeys(args, allowed) || typeof args.report_id !== "string" || args.report_id.length > 100 || !args.report_id) {
        return toolError("INVALID_ARGUMENTS", "An exact report_id is required; additional arguments are not accepted.");
      }
      if (args.acknowledge_synthetic !== true) return toolError("DEMO_CONFIRMATION_REQUIRED", "This report contains fictional data only. Explicit synthetic-demo opt-in is required and does not permit personal recommendations.");
      if (args.report_id !== report.report_id) return toolError("REPORT_NOT_FOUND", "That report version is unavailable. No alternate version was substituted.");
    } else if (name === "assess_allocation_readiness") {
      if (!onlyKeys(args, ["amount", "currency", "account_scope"]) ||
          typeof args.amount !== "number" || !Number.isFinite(args.amount) || args.amount <= 0 || args.amount > 1_000_000_000_000 ||
          args.currency !== "USD" || typeof args.account_scope !== "string" || !["combined", "taxable", "roth"].includes(args.account_scope)) {
        return toolError("INVALID_ARGUMENTS", "Supply only a positive finite amount (at most 1 trillion), currency='USD', and account_scope='combined', 'taxable', or 'roth'. Personal data, eligibility assertions, and overrides are not accepted.");
      }
    } else {
      return toolError("TOOL_NOT_FOUND", "Unsupported tool. Only the six documented read-only research tools exist; none can generate personal allocations or execute financial actions.");
    }

    let payload: JsonRecord;
    let label: string;
    if (name === "get_latest_briefing") {
      payload = { ...blockedReadiness("combined"), report: null, demo_available: true };
      label = "PERSONAL BRIEFING BLOCKED: no verified personal portfolio exists in this pilot. No report or allocation is available; fictional data has not been substituted.";
    } else if (name === "assess_allocation_readiness") {
      payload = {
        ...blockedReadiness(args.account_scope as "combined" | "taxable" | "roth"),
        request: { amount: args.amount, currency: args.currency, account_scope: args.account_scope },
      };
      label = "ALLOCATION READINESS BLOCKED: the budget was noted only for this unsaved evidence check. No dollar/percentage allocations, ticker choices, account split, or Roth contribution capacity can be recommended from this pilot.";
    } else if (name === "get_system_status") {
      payload = { ...context(), financial_permissions: [], live_market_data: false, persists_changes: false,
        allocation_readiness: blockedReadiness("combined") };
      label = "PERSONAL EVIDENCE UNAVAILABLE: this system supports fictional demonstrations only. All personal allocation readiness is blocked. Any displayed report identity/freshness refers only to the synthetic demo.";
    } else if (name === "get_holding_research") {
      if (typeof args.symbol !== "string" || !/^[A-Z][A-Z0-9.-]{0,14}$/.test(args.symbol)) {
        return toolError("INVALID_ARGUMENTS", "symbol must be an uppercase ticker of at most 15 characters.");
      }
      const holding = records(report.analysis.holdings).find((item) => item.symbol === args.symbol);
      if (!holding) return toolError("HOLDING_NOT_FOUND", "That symbol is not a holding in this synthetic report.");
      const research = isRecord(report.research) ? report.research : {};
      const claims = records(research.claims).filter((item) => item.symbol === args.symbol);
      const insights = records(report.insights).filter((item) => item.symbol === args.symbol);
      const theses = records(research.theses).filter((item) => item.symbol === args.symbol);
      const sourceIds = new Set([...claims, ...insights, ...theses].flatMap((item) =>
        Array.isArray(item.source_ids) ? item.source_ids.filter((id): id is string => typeof id === "string") : []));
      payload = {
        ...context(), symbol: args.symbol, holding, claims, insights,
        sources: records(research.sources).filter((source) => typeof source.id === "string" && sourceIds.has(source.id)),
        theses,
        thesis: theses.length === 1 ? theses[0] : null,
        thesis_status: theses.length === 1 ? "synthetic_thesis_from_exact_report"
          : theses.length > 1 ? "multiple_versions_in_report_no_selection_made" : "not_recorded_in_pilot",
        research_status: claims.length ? "synthetic_claims_only" : "no_company_research_recorded",
      };
      label = `FICTIONAL DEMO ONLY: ${args.symbol} is not a verified personal holding. Report ${report.report_id}, source time ${report.as_of}. The demo cannot support personal recommendations.`;
    } else {
      payload = { ...context(), report };
      label = `EXPLICIT FICTIONAL DEMO — not your portfolio or current market research. Report ${report.report_id}, source time ${report.as_of}. Demo dashboard: ${dashboard.href}. No personal allocation is authorized by this demo.`;
    }
    return {
      isError: false,
      content: [{
        type: "text",
        text: `${label}\n\n${MODEL_INSTRUCTIONS}`,
      }],
      structuredContent: payload,
    };
  }

  return async function handleResearchRequest(request: Request): Promise<Response> {
    if (request.method !== "POST") {
      const denied = rpcError(null, -32600, "Only POST is supported.", 405);
      denied.headers.set("Allow", "POST");
      return denied;
    }
    if (!/^application\/json(?:\s*;|$)/i.test(request.headers.get("content-type") ?? "") ||
        ![null, "identity"].includes(request.headers.get("content-encoding"))) {
      return rpcError(null, -32600, "Use uncompressed application/json.", 415);
    }
    let message: unknown;
    try {
      message = await boundedJson(request);
    } catch (error) {
      return error instanceof BodyLimitError
        ? rpcError(null, -32600, "Request body exceeds the permitted size.", 413)
        : rpcError(null, -32700, "Invalid JSON request.", 400);
    }
    if (!isRecord(message) || message.jsonrpc !== "2.0" || typeof message.method !== "string" ||
        !onlyKeys(message, ["jsonrpc", "id", "method", "params"])) {
      return rpcError(null, -32600, "Invalid JSON-RPC request. Batch requests are unsupported.", 400);
    }
    if (message.method === "notifications/initialized" && !("id" in message)) return response(null, 204);
    if (!validId(message.id)) return rpcError(null, -32600, "A string or integer request ID is required.", 400);
    const id = message.id;
    const params = message.params ?? {};
    if (!isRecord(params)) return rpcError(id, -32602, "params must be an object.", 400);

    // Metadata-only discovery is available for Sites provisioning. No report or identity is returned.
    if (message.method === "server/discover") {
      return success(id, { resultType: "complete", supportedVersions: ["2026-07-28"], capabilities,
        instructions: MODEL_INSTRUCTIONS, evidence_contract: EVIDENCE_CONTRACT });
    }
    if (message.method === "initialize") {
      const requested = params.protocolVersion;
      return success(id, {
        protocolVersion: requested === "2025-06-18" ? requested : "2025-03-26",
        capabilities,
        serverInfo: { name: "investment-research-sample", version: "0.2.0" },
        instructions: MODEL_INSTRUCTIONS,
      });
    }
    if (message.method === "ping") return success(id, {});
    if (message.method === "tools/list") {
      if (!onlyKeys(params, ["_meta"])) return rpcError(id, -32602, "No pagination parameters are supported.", 400);
      return success(id, { tools });
    }
    if (widgetHtml && message.method === "resources/list") {
      if (!onlyKeys(params, ["_meta"])) return rpcError(id, -32602, "No pagination parameters are supported.", 400);
      return success(id, { resources: [{ uri: widgetUri, name: "explicit-fictional-demo-only", mimeType: WIDGET_MIME,
        description: "Fictional demonstration only. This resource never represents personal holdings or allocation advice." }] });
    }
    if (widgetHtml && message.method === "resources/read") {
      if (!hasIdentity(request)) return rpcError(id, -32001, "Authenticated Site identity is required.", 401);
      if (!onlyKeys(params, ["uri", "_meta"]) || params.uri !== widgetUri) {
        return rpcError(id, -32602, "Unknown resource. Only this bundled synthetic briefing is available.", 400);
      }
      return success(id, { contents: [{
        uri: widgetUri, mimeType: WIDGET_MIME, text: widgetHtml,
        _meta: { ui: { prefersBorder: true, csp: { connectDomains: [], resourceDomains: [], frameDomains: [] } } },
      }] });
    }
    if (message.method !== "tools/call") return rpcError(id, -32601, "Method not found.");
    if (!hasIdentity(request)) return rpcError(id, -32001, "Authenticated Site identity is required.", 401);
    if (!onlyKeys(params, ["name", "arguments", "_meta"]) || typeof params.name !== "string" || !isRecord(params.arguments ?? {})) {
      return rpcError(id, -32602, "A tool name and object arguments are required.", 400);
    }
    try {
      return success(id, toolResult(params.name, (params.arguments ?? {}) as JsonRecord));
    } catch {
      return success(id, toolError("UNAVAILABLE", "The synthetic report is temporarily unavailable. No live account or data feed was accessed."));
    }
  };
}
