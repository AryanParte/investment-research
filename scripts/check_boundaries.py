#!/usr/bin/env python3
"""Fail CI if tracked code introduces forbidden financial access or private files."""
import ast
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BLOCKED_IMPORTS = {"robin_stocks", "alpaca", "alpaca_trade_api", "ib_insync", "ccxt", "plaid", "stripe"}
BLOCKED_DIRS = {"private", "runtime", "data", "dist", "reports", "node_modules"}


def main():
    tracked = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True).stdout.decode().split("\0")
    if not any(tracked):
        tracked = [str(p.relative_to(ROOT)) for folder in ("src", "web", "tests", "samples", "scripts", "docs")
                   for p in (ROOT / folder).rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    errors = []
    for name in filter(None, tracked):
        path = Path(name)
        if path.parts[0] in BLOCKED_DIRS or path.name.startswith(".env") or path.suffix in {".db", ".sqlite", ".log"}:
            errors.append(f"Private/runtime artifact tracked: {name}")
        full = ROOT / path
        if not full.is_file() or full.suffix in {".png", ".zip"}:
            continue
        text = full.read_text()
        if re.search(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", text) or re.search(r"\b(?:ghp_|sk-proj-)[A-Za-z0-9_-]{20,}", text):
            errors.append(f"Credential-like content detected: {name}")
        if path.suffix == ".py":
            tree = ast.parse(text, filename=name)
            for node in ast.walk(tree):
                modules = [n.name for n in node.names] if isinstance(node, ast.Import) else [node.module or ""] if isinstance(node, ast.ImportFrom) else []
                if any(m.split(".")[0] in BLOCKED_IMPORTS for m in modules):
                    errors.append(f"Forbidden financial integration: {name}")
        if path.parts[0] in {"src", "web"} and re.search(r"https?://[^\s\"']*(?:robinhood|alpaca|plaid|stripe)\.", text):
            errors.append(f"Forbidden financial endpoint in application code: {name}")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("Privacy and financial-capability boundary checks passed. This is a regression guard, not a complete security audit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
