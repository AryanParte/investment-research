#!/usr/bin/env python3
"""Local entry point; no installation, account credentials, or network required."""
import argparse
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from investment_research.pipeline import build, health


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo", help="Build fictional sample portfolio and dashboard")
    demo.add_argument("--output", type=Path, default=ROOT / "dist")
    imported = sub.add_parser("build", help="Build from your normalized local files")
    imported.add_argument("--input", type=Path, required=True)
    imported.add_argument("--output", type=Path, default=ROOT / "runtime" / "briefings")
    imported.add_argument("--as-of", required=True)
    imported.add_argument("--complete-history", action="store_true")
    serve = sub.add_parser("serve", help="Serve a local-only preview, no write API")
    serve.add_argument("--directory", type=Path, default=ROOT / "dist")
    serve.add_argument("--port", type=int, default=8765)
    status = sub.add_parser("health", help="Check local generation/freshness; does not send alerts")
    status.add_argument("--directory", type=Path, default=ROOT / "runtime" / "briefings")
    args = parser.parse_args()
    if args.command in {"demo", "build"}:
        sample = args.command == "demo"
        if not sample:
            try:
                relative = args.output.resolve().relative_to(ROOT)
            except ValueError:
                relative = None
            if relative is not None and (not relative.parts or relative.parts[0] not in {"runtime", "private", "reports", "data"}):
                parser.error("Private reports inside this repository must be under an ignored runtime/private/reports/data directory")
        try:
            as_of = datetime(2026, 11, 3, 22, tzinfo=timezone.utc) if sample else datetime.fromisoformat(args.as_of.replace("Z", "+00:00"))
            report = build(ROOT / "samples" if sample else args.input, args.output,
                as_of=as_of, complete_history=True if sample else args.complete_history, sample=sample, web_dir=ROOT / "web")
        except (ValueError, KeyError, OSError, TypeError):
            print("Build failed: input validation or local file error. No personal data logged.", file=sys.stderr)
            return 1
        print(json.dumps({"status": "generated", "mode": report["mode"], "report_id": report["report_id"],
                          "delivery": "not_verified", "reading_seconds": report["estimated_read_seconds"]}))
    elif args.command == "serve":
        class Handler(SimpleHTTPRequestHandler):
            def log_message(self, *_):
                pass
            def list_directory(self, _):
                self.send_error(403)
                return None
            def do_GET(self):
                if self.path.split("?", 1)[0] not in {"/", "/index.html", "/styles.css", "/app.js", "/report.json", "/health.json", "/briefing.md"}:
                    self.send_error(404)
                    return
                super().do_GET()
            def do_HEAD(self):
                if self.path.split("?", 1)[0] not in {"/", "/index.html", "/styles.css", "/app.js", "/report.json", "/health.json", "/briefing.md"}:
                    self.send_error(404)
                    return
                super().do_HEAD()
            def end_headers(self):
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
                super().end_headers()
        print(f"Local preview: http://127.0.0.1:{args.port}", flush=True)
        ThreadingHTTPServer(("127.0.0.1", args.port), partial(Handler, directory=str(args.directory))).serve_forever()
    else:
        result = health(args.directory, now=datetime.now(timezone.utc))
        print(json.dumps(result))
        return int(result["action_required"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
