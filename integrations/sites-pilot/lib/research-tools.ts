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

const emptyInput = {
  type: "object", properties: {}, additionalProperties: false,
};
const reportIdProperty = {
  type: "string", minLength: 1, maxLength: 100,
  description: "Exact immutable report_id returned by get_latest_briefing.",
};

const objectList = { type: "array", items: { type: "object" } };
const outputProperties = {
  report_id: { type: "string" }, report_as_of: { type: "string" }, served_at: { type: "string" },
  mode: { const: "sample" }, synthetic: { const: true }, dashboard_url: { type: "string" },
  freshness: { type: "object" }, account_support: { type: "object" }, verification: { type: "object" },
};
function outputSchema(extra: JsonRecord, required: string[]) {
  return {
    type: "object",
    oneOf: [
      {
        properties: { ...outputProperties, ...extra },
        required: [...Object.keys(outputProperties), ...required], additionalProperties: false,
      },
      {
        properties: { error: {
          type: "object", properties: { code: { type: "string" }, message: { type: "string" } },
          required: ["code", "message"], additionalProperties: false,
        } },
        required: ["error"], additionalProperties: false,
      },
    ],
  };
}
const briefingOutput = outputSchema({ report: { type: "object" } }, ["report"]);

export const RESEARCH_TOOLS = [
  {
    name: "get_latest_briefing",
    title: "Read the fictional investment briefing",
    description: "Retrieve this private pilot's fixed synthetic report with source time and freshness. It is not a live portfolio, market feed, or investment recommendation.",
    inputSchema: emptyInput,
    outputSchema: briefingOutput,
    annotations: ANNOTATIONS,
  },
  {
    name: "get_briefing",
    title: "Read an exact briefing version",
    description: "Retrieve the same synthetic report by its exact report_id so a follow-up uses consistent evidence. Unknown versions are unavailable; no fallback to another date.",
    inputSchema: {
      type: "object", properties: { report_id: reportIdProperty },
      required: ["report_id"], additionalProperties: false,
    },
    outputSchema: briefingOutput,
    annotations: ANNOTATIONS,
  },
  {
    name: "get_holding_research",
    title: "Read holding evidence from a briefing",
    description: "Retrieve a fictional holding and its existing claims, sources, and insights from an exact report. Missing research is labeled missing; no new claims are generated.",
    inputSchema: {
      type: "object",
      properties: {
        symbol: { type: "string", pattern: "^[A-Z][A-Z0-9.-]{0,14}$", maxLength: 15 },
        report_id: reportIdProperty,
      },
      required: ["symbol", "report_id"], additionalProperties: false,
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
    description: "Read synthetic report freshness and the pilot's verified scope. Account connections, live data, financial actions, and verified notification delivery are absent.",
    inputSchema: emptyInput,
    outputSchema: outputSchema({
      financial_permissions: { type: "array", maxItems: 0 },
      live_market_data: { const: false }, persists_changes: { const: false },
    }, ["financial_permissions", "live_market_data", "persists_changes"]),
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
    content: [{ type: "text", text: message }],
    structuredContent: { error: { code, message } },
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
    ...(widgetHtml && ["get_latest_briefing", "get_briefing"].includes(tool.name)
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

  function toolResult(name: string, args: JsonRecord): JsonRecord {
    if (name === "get_latest_briefing" || name === "get_system_status") {
      if (!onlyKeys(args, [])) return toolError("INVALID_ARGUMENTS", "This tool accepts an empty arguments object only.");
    } else if (name === "get_briefing" || name === "get_holding_research") {
      const allowed = name === "get_briefing" ? ["report_id"] : ["report_id", "symbol"];
      if (!onlyKeys(args, allowed) || typeof args.report_id !== "string" || args.report_id.length > 100 || !args.report_id) {
        return toolError("INVALID_ARGUMENTS", "An exact report_id is required; additional arguments are not accepted.");
      }
      if (args.report_id !== report.report_id) return toolError("REPORT_NOT_FOUND", "That report version is unavailable. No alternate version was substituted.");
    } else {
      return toolError("TOOL_NOT_FOUND", "Unsupported tool. Only the four documented read-only research tools exist.");
    }

    const envelope = context();
    let payload: JsonRecord;
    if (name === "get_system_status") {
      payload = { ...envelope, financial_permissions: [], live_market_data: false, persists_changes: false };
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
        ...envelope, symbol: args.symbol, holding, claims, insights,
        sources: records(research.sources).filter((source) => typeof source.id === "string" && sourceIds.has(source.id)),
        theses,
        thesis: theses.length === 1 ? theses[0] : null,
        thesis_status: theses.length === 1 ? "synthetic_thesis_from_exact_report"
          : theses.length > 1 ? "multiple_versions_in_report_no_selection_made" : "not_recorded_in_pilot",
        research_status: claims.length ? "synthetic_claims_only" : "no_company_research_recorded",
      };
    } else {
      payload = { ...envelope, report };
    }
    return {
      isError: false,
      content: [{
        type: "text",
        text: `SYNTHETIC PILOT — not your portfolio and not current market research. Report ${report.report_id}, source time ${report.as_of}. See structuredContent for evidence and freshness. Private dashboard: ${dashboard.href}. Notification and mobile delivery are unverified.`,
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
      return success(id, { resultType: "complete", supportedVersions: ["2026-07-28"], capabilities });
    }
    if (message.method === "initialize") {
      const requested = params.protocolVersion;
      return success(id, {
        protocolVersion: requested === "2025-06-18" ? requested : "2025-03-26",
        capabilities,
        serverInfo: { name: "investment-research-sample", version: "0.1.0" },
      });
    }
    if (message.method === "ping") return success(id, {});
    if (message.method === "tools/list") {
      if (!onlyKeys(params, ["_meta"])) return rpcError(id, -32602, "No pagination parameters are supported.", 400);
      return success(id, { tools });
    }
    if (widgetHtml && message.method === "resources/list") {
      if (!onlyKeys(params, ["_meta"])) return rpcError(id, -32602, "No pagination parameters are supported.", 400);
      return success(id, { resources: [{ uri: widgetUri, name: "synthetic-investment-briefing", mimeType: WIDGET_MIME }] });
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
