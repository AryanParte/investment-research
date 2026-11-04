"""Copy the fictional, self-contained demo into a Sites overlay or checkout.

Never use this source-bundling path for personal account data. No external calls.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    report_bytes = (ROOT / "dist/report.json").read_bytes()
    report = json.loads(report_bytes)
    html = (ROOT / "dist/briefing.html").read_text(encoding="utf-8")
    if (report.get("mode") != "sample" or report.get("schema_version") != 1
            or report.get("research", {}).get("dataset") != "synthetic"
            or report.get("status", {}).get("quote_feed") != "synthetic"):
        raise ValueError("Only the synthetic demo is permitted in this source overlay")
    # Compare the actual embedded JSON, not merely the presence of a report ID.
    match = re.search(r"window\.INVESTMENT_REPORT=(.*?);</script>", html, re.DOTALL)
    if not match or json.loads(match.group(1)) != report:
        raise ValueError("Bundled UI and report JSON differ; regenerate the sample bundle")
    checkout = args.checkout.resolve()
    lib = checkout / "lib"
    dashboard = checkout / "public/dashboard"
    lib.mkdir(parents=True, exist_ok=True)
    dashboard.mkdir(parents=True, exist_ok=True)
    (lib / "sample-report.json").write_bytes(report_bytes)
    (lib / "widget-html.ts").write_text(
        "// Generated from the fictional sample only. Regenerate with sync_sample.py.\n"
        "export const widgetHtml: string = " + json.dumps(html, ensure_ascii=True) + ";\n",
        encoding="utf-8",
    )
    (dashboard / "index.html").write_text(html, encoding="utf-8")
    print(json.dumps({
        "mode": "sample",
        "report_id": report["report_id"],
        "report_sha256": hashlib.sha256(report_bytes).hexdigest(),
        "html_sha256": hashlib.sha256(html.encode("utf-8")).hexdigest(),
    }))


if __name__ == "__main__":
    main()
