#!/usr/bin/env python3
"""Launch a local stdio read-only server for an explicitly selected private import."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from investment_research.local_mcp import ConfigurationError, PrivateReportReader, StdioServer


class PrivateArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        # argparse normally echoes unknown options and invalid values. Those
        # may contain paths or mistakenly supplied credentials.
        self.exit(2, "Local portfolio MCP could not start: invalid command-line configuration.\n")


def main() -> int:
    parser = PrivateArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True, help="Absolute owner-only directory under this checkout's ignored private/ or runtime/")
    parser.add_argument("--max-age-hours", type=int, default=96, help="Maximum source age, 1–96 hours (default 96)")
    args = parser.parse_args()
    try:
        reader = PrivateReportReader(args.directory, max_age_hours=args.max_age_hours)
    except (ConfigurationError, OSError, ValueError):
        print("Local portfolio MCP could not start: private directory validation failed.", file=sys.stderr)
        return 2
    try:
        StdioServer(reader).run(sys.stdin.buffer, sys.stdout.buffer)
    except BrokenPipeError:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
