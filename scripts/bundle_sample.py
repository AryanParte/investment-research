#!/usr/bin/env python3
"""Create a self-contained fictional dashboard for the private MCP UI pilot."""
import base64
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def bundle(report: dict, html: str, css: str, javascript: str) -> str:
    if report.get("mode") != "sample":
        raise ValueError("Only fictional data may be bundled into the pilot source")
    data = json.dumps(report, allow_nan=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    # The template and program are project source, never imported financial HTML.
    stylesheet_tags = ('<link rel="stylesheet" href="styles.css">', '<link rel="stylesheet" href="./styles.css">')
    if sum(html.count(tag) for tag in stylesheet_tags) != 1:
        raise ValueError("Dashboard template changed; exactly one stylesheet is required")
    if re.search(r"</style", css, re.IGNORECASE):
        raise ValueError("Stylesheet contains an HTML closing delimiter")
    for tag in stylesheet_tags:
        html = html.replace(tag, '<style>' + css + '</style>')
    data_program = 'window.INVESTMENT_REPORT=' + data + ';'
    program = re.sub(r"</script", lambda match: match.group(0).replace('</', '<\\/'), javascript, flags=re.IGNORECASE)
    tag = '<script>' + data_program + '</script><script>' + program + '</script>'
    # A classic inline script ignores defer. Remove the external head script and
    # append the inline program after the complete DOM, before closing the body.
    html, count = re.subn(r'<script\b[^>]*\bsrc="(?:\./)?app\.js"[^>]*>\s*</script>', '', html, flags=re.IGNORECASE)
    if count != 1 or len(re.findall(r'</body\s*>', html, flags=re.IGNORECASE)) != 1:
        raise ValueError("Dashboard template changed; inspect the bundler before publishing")
    html = re.sub(r'</body\s*>', lambda _: tag + '\n</body>', html, flags=re.IGNORECASE)
    def csp_hash(text):
        return "'sha256-" + base64.b64encode(hashlib.sha256(text.encode('utf-8')).digest()).decode('ascii') + "'"
    policy = ("default-src 'none'; script-src " + csp_hash(data_program) + " " + csp_hash(program)
              + "; style-src " + csp_hash(css) + "; img-src data:; connect-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'")
    html, count = re.subn(r'<meta\b[^>]*\bhttp-equiv=["\']Content-Security-Policy["\'][^>]*>',
                         lambda _: '<meta http-equiv="Content-Security-Policy" content="' + policy + '">', html, flags=re.IGNORECASE)
    if count != 1:
        raise ValueError("Dashboard template changed; exactly one CSP declaration is required")
    return html


if __name__ == "__main__":
    report = json.loads((ROOT / "dist/report.json").read_text())
    result = bundle(report, (ROOT / "web/index.html").read_text(), (ROOT / "web/styles.css").read_text(), (ROOT / "web/app.js").read_text())
    (ROOT / "dist/briefing.html").write_text(result)
    print("Self-contained synthetic dashboard bundled; no private data permitted.")
