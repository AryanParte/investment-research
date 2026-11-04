import sampleReport from "@/lib/sample-report.json";
import { createResearchServer } from "@/lib/research-tools";
import { widgetHtml } from "@/lib/widget-html";

export const dynamic = "force-dynamic";

const handle = createResearchServer(sampleReport, {
  dashboardUrl: "https://YOUR-PRIVATE-SITE.chatgpt.site",
  widgetHtml,
});

export const POST = handle;
export const GET = handle;
export const PUT = handle;
export const PATCH = handle;
export const DELETE = handle;
