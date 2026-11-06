"""All amounts here are fictional test inputs, never personal account data."""
import copy
from datetime import datetime, timedelta, timezone
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from investment_research.local_mcp import (ConfigurationError, PrivateReportReader, StdioServer,
    SNAPSHOT_TOOL, EVIDENCE_TOOL, MAX_REPORT_BYTES, MAX_REQUEST_BYTES, tool_definitions)
from investment_research.pipeline import PIPELINE_VERSION
from investment_research.storage import digest

NOW = datetime(2026, 11, 5, 18, tzinfo=timezone.utc)
STAMP = "2026-11-05T17:00:00+00:00"


def fixture():
    """Fictional values exercising the imported-report contract, not live data."""
    holding = {"symbol": "TEST", "quantity": "2", "price": "50", "market_value": "100", "weight_pct": "50",
               "price_date": "2026-11-05", "source": "user-provided normalized statement", "as_of": STAMP}
    return {"schema_version": 1, "mode": "imported", "pipeline_version": PIPELINE_VERSION, "as_of": STAMP,
        "input_hashes": {name: "a" * 64 for name in ["transactions.csv", "prices.csv", "benchmark.csv", "research.json", "statement.json"]},
        "research": {"dataset": "manual_import", "claims": [{"text": "This prose must never be returned by the descriptive tools."}]},
        "analysis": {"schema_version": "1.0", "as_of": STAMP, "currency": "USD", "history_start": "2026-11-05", "valuation_date": "2026-11-05",
            "quality": {"status": "fresh", "history_attested_complete": True, "statement_reconciled": True, "broker_reconciled": False},
            "reconciliation": {"status": "matched_to_supplied_statement", "comparison": {"status": "matched", "discrepancies": [], "valuation_date": "2026-11-05", "account_count": 1}},
            "sources": [{"source": "user-provided normalized statement", "as_of": STAMP}],
            "summary": {"equity": "200", "cash": "100", "positions_value": "100", "net_contributions": "190", "gain": "10"},
            "timeline": [{"date": "2026-11-05", "equity": "200", "net_flow": "190", "cumulative_contributions": "190"}],
            "holdings": [holding], "accounts": [{"id": "taxable", "equity": "200", "cash": "100", "holdings": [copy.deepcopy(holding)]}]
        }}


class LocalMcpTests(unittest.TestCase):
    def setUp(self):
        if not shutil.which("git"):
            self.skipTest("Git is required to verify private report exclusion")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        subprocess.run(["git", "init", "-q", str(self.root)], check=True, capture_output=True)
        (self.root / ".gitignore").write_text("private/\nruntime/\n")
        self.directory = self.root / "runtime" / "owner-report"
        self.directory.mkdir(parents=True, mode=0o700)
        self.directory.chmod(0o700)
        self.report = fixture()
        self.write_report()

    def write_report(self, *, rehash=True):
        if rehash:
            self.report["report_id"] = "brief-" + digest({key: value for key, value in self.report.items() if key != "report_id"})[:20]
        path = self.directory / "report.json"
        path.write_text(json.dumps(self.report))
        path.chmod(0o600)
        health = {"status": "generated", "report_id": self.report["report_id"], "generated_at": self.report["as_of"],
                  "source_as_of": self.report["as_of"], "valuation_date": self.report["analysis"]["valuation_date"], "delivery_status": "not_verified"}
        path = self.directory / "health.json"
        path.write_text(json.dumps(health))
        path.chmod(0o600)

    def reader(self, **kwargs):
        return PrivateReportReader(self.directory, repository_root=self.root, clock=lambda: NOW, **kwargs)

    def code(self, result):
        self.assertEqual(result["status"], "unavailable")
        self.assertIsNone(result["snapshot"])
        self.assertFalse(result["can_recommend"])
        return result["blockers"][0]["code"]

    def initialized_server(self):
        server = StdioServer(self.reader())
        response = server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25", "clientInfo": {"name": "unit-test", "version": "1"}, "capabilities": {}}})
        self.assertEqual(response["result"]["protocolVersion"], "2025-11-25")
        server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"})
        return server

    def test_descriptive_snapshot_never_enables_recommendations_or_broker_verification(self):
        result = self.reader().evidence(include_snapshot=True)
        self.assertEqual(result["status"], "available")
        self.assertFalse(result["can_recommend"])
        self.assertEqual(result["financial_capabilities"], [])
        self.assertEqual(result["snapshot"]["summary"]["equity"], "200")
        self.assertEqual(result["snapshot"]["holdings"][0]["weight_pct"], "50.000000")
        self.assertFalse(result["provenance"]["broker_authenticated"])
        self.assertFalse(result["provenance"]["input_contents_revalidated"])
        self.assertNotIn("This prose", json.dumps(result))
        self.assertNotIn("claims", result["snapshot"])
        self.assertEqual(result["gates"]["valuation"], "not_implemented")

    def test_evidence_status_does_not_return_holdings(self):
        result = self.reader().evidence()
        self.assertEqual(result["status"], "available")
        self.assertIsNone(result["snapshot"])
        self.assertNotIn('"symbol"', json.dumps(result))

    def test_sample_report_is_never_fallback_personal_data(self):
        self.report["mode"] = "sample"
        self.write_report()
        self.assertEqual(self.code(self.reader().evidence(include_snapshot=True)), "SAMPLE_REJECTED")

    def test_synthetic_sources_rejected_even_if_mode_is_changed(self):
        self.report["analysis"]["sources"][0]["source"] = "synthetic-fixture-not-market-data"
        self.write_report()
        self.assertEqual(self.code(self.reader().evidence(include_snapshot=True)), "SAMPLE_REJECTED")

    def test_missing_report_does_not_return_zero_or_an_archive(self):
        archive = self.directory / "archive"
        archive.mkdir(mode=0o700)
        shutil.copyfile(self.directory / "report.json", archive / "old-report.json")
        (self.directory / "report.json").unlink()
        result = self.reader().evidence(include_snapshot=True)
        self.assertEqual(self.code(result), "REPORT_MISSING")
        self.assertNotIn("equity", json.dumps(result))

    def test_missing_health_blocks_snapshot(self):
        (self.directory / "health.json").unlink()
        self.assertEqual(self.code(self.reader().evidence(include_snapshot=True)), "REPORT_MISSING")

    def test_stale_and_future_reports_blocked(self):
        for days in (-8, 1):
            with self.subTest(days=days):
                self.report = fixture()
                self.report["as_of"] = (NOW + timedelta(days=days)).isoformat()
                self.report["analysis"]["as_of"] = self.report["as_of"]
                self.write_report()
                self.assertEqual(self.code(self.reader().evidence(include_snapshot=True)), "REPORT_STALE")

    def test_incomplete_history_and_missing_timeline_blocked(self):
        self.report["analysis"]["quality"]["history_attested_complete"] = False
        self.write_report()
        self.assertEqual(self.code(self.reader().evidence()), "HISTORY_INCOMPLETE")
        self.report = fixture()
        del self.report["analysis"]["timeline"]
        self.write_report()
        self.assertEqual(self.code(self.reader().evidence()), "HISTORY_INCOMPLETE")

    def test_unreconciled_or_falsely_broker_verified_blocked(self):
        for field, value in [("statement_reconciled", False), ("broker_reconciled", True)]:
            with self.subTest(field=field):
                self.report = fixture()
                self.report["analysis"]["quality"][field] = value
                self.write_report()
                self.assertEqual(self.code(self.reader().evidence()), "UNRECONCILED")

    def test_failed_generation_prevents_last_good_snapshot_fallback(self):
        path = self.directory / "health.json"
        path.write_text(json.dumps({"status": "failed", "error_code": "PIPELINE_VALIDATION_FAILED"}))
        self.assertEqual(self.code(self.reader().evidence()), "GENERATION_FAILED")

    def test_health_must_bind_same_report_id(self):
        path = self.directory / "health.json"
        data = json.loads(path.read_text())
        data["report_id"] = "brief-wrong"
        path.write_text(json.dumps(data))
        self.assertEqual(self.code(self.reader().evidence()), "GENERATION_FAILED")

    def test_hash_tampering_and_missing_input_provenance_blocked(self):
        self.report["analysis"]["summary"]["equity"] = "999"
        self.write_report(rehash=False)
        self.assertEqual(self.code(self.reader().evidence()), "REPORT_INTEGRITY")
        self.report = fixture()
        del self.report["input_hashes"]["statement.json"]
        self.write_report()
        self.assertEqual(self.code(self.reader().evidence()), "REPORT_INTEGRITY")

    def test_missing_sources_and_inconsistent_totals_blocked(self):
        self.report["analysis"]["sources"] = []
        self.write_report()
        self.assertEqual(self.code(self.reader().evidence()), "SOURCE_UNAVAILABLE")
        self.report = fixture()
        self.report["analysis"]["accounts"][0]["cash"] = "99"
        self.write_report()
        self.assertEqual(self.code(self.reader().evidence()), "ACCOUNT_FACTS_INVALID")

    def test_numeric_account_identifiers_are_not_returned(self):
        self.report["analysis"]["accounts"][0]["id"] = "123456789"
        self.write_report()
        result = self.reader().evidence(include_snapshot=True)
        self.assertEqual(self.code(result), "ACCOUNT_FACTS_INVALID")
        self.assertNotIn("123456789", json.dumps(result))

    def test_offsetting_account_marks_cannot_hide_behind_matching_totals(self):
        analysis = self.report["analysis"]
        second = copy.deepcopy(analysis["holdings"][0])
        second["symbol"] = "OTHER"
        analysis["holdings"].append(second)
        analysis["accounts"][0]["holdings"].append(copy.deepcopy(second))
        analysis["summary"].update(equity="300", positions_value="200", net_contributions="290")
        analysis["accounts"][0]["equity"] = "300"
        analysis["timeline"][0].update(equity="300", net_flow="290", cumulative_contributions="290")
        self.write_report()
        self.assertEqual(self.reader().evidence()["status"], "available")
        first_mark, second_mark = analysis["accounts"][0]["holdings"]
        first_mark.update(price="55", market_value="110")
        second_mark.update(price="45", market_value="90")
        self.write_report()
        self.assertEqual(self.code(self.reader().evidence()), "ACCOUNT_FACTS_INVALID")

    def test_cross_view_mark_provenance_must_match(self):
        for field, value in [("source", "another manual source"), ("as_of", "2026-11-05T16:30:00+00:00")]:
            with self.subTest(field=field):
                self.report = fixture()
                self.report["analysis"]["accounts"][0]["holdings"][0][field] = value
                self.write_report()
                self.assertEqual(self.code(self.reader().evidence()), "ACCOUNT_FACTS_INVALID")

    def test_invalid_root_relative_path_and_traversal_are_rejected(self):
        for path in [Path("runtime/owner-report"), self.root / "samples", self.root.parent,
                     self.root / "runtime" / ".." / "runtime" / "owner-report"]:
            with self.subTest(path=str(path)), self.assertRaises(ConfigurationError):
                PrivateReportReader(path, repository_root=self.root)

    def test_directory_symlink_and_overbroad_permissions_are_rejected(self):
        linked = self.root / "runtime" / "linked"
        linked.symlink_to(self.directory, target_is_directory=True)
        with self.assertRaises(ConfigurationError):
            PrivateReportReader(linked, repository_root=self.root)
        self.directory.chmod(0o755)
        with self.assertRaises(ConfigurationError):
            self.reader()

    def test_file_symlink_hardlink_and_world_readable_files_are_rejected(self):
        path = self.directory / "report.json"
        elsewhere = self.root / "outside.json"
        path.rename(elsewhere)
        path.symlink_to(elsewhere)
        self.assertEqual(self.code(self.reader().evidence()), "FILE_UNSAFE")
        path.unlink()
        os.link(elsewhere, path)
        self.assertEqual(self.code(self.reader().evidence()), "FILE_UNSAFE")
        path.unlink()
        shutil.copyfile(elsewhere, path)
        path.chmod(0o644)
        self.assertEqual(self.code(self.reader().evidence()), "FILE_UNSAFE")

    def test_oversized_and_duplicate_key_reports_rejected(self):
        path = self.directory / "report.json"
        path.write_bytes(b" " * (MAX_REPORT_BYTES + 1))
        self.assertEqual(self.code(self.reader().evidence()), "FILE_TOO_LARGE")
        path.write_text('{"mode":"sample","mode":"imported"}')
        self.assertEqual(self.code(self.reader().evidence()), "REPORT_INVALID")

    def test_git_tracking_and_ignore_exceptions_rejected(self):
        subprocess.run(["git", "-C", str(self.root), "add", "--force", "runtime/owner-report/report.json"], check=True, capture_output=True)
        with self.assertRaises(ConfigurationError):
            self.reader()

    def test_git_environment_cannot_hide_tracked_private_data(self):
        subprocess.run(["git", "-C", str(self.root), "add", "--force", "runtime/owner-report/report.json"], check=True, capture_output=True)
        alternate = self.root / "untracked-index"
        with patch.dict(os.environ, {"GIT_INDEX_FILE": str(alternate), "GIT_WORK_TREE": str(self.root.parent),
                                     "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "core.worktree", "GIT_CONFIG_VALUE_0": str(self.root.parent)}):
            with self.assertRaises(ConfigurationError):
                self.reader()
        self.assertFalse(alternate.exists())

    def test_git_directory_override_cannot_redirect_checkout_validation(self):
        with patch.dict(os.environ, {"GIT_DIR": str(self.root / "missing-git"), "GIT_COMMON_DIR": str(self.root / "missing-git"),
                                     "GIT_CONFIG": str(self.root / "missing-config")}):
            self.assertEqual(self.reader().evidence()["status"], "available")

    def test_group_writable_repository_root_is_rejected(self):
        self.root.chmod(0o770)
        with self.assertRaises(ConfigurationError):
            self.reader()
        self.root.chmod(0o700)

    def test_ignore_rechecked_after_server_start(self):
        reader = self.reader()
        (self.root / ".gitignore").write_text("")
        self.assertEqual(self.code(reader.evidence()), "FILE_UNSAFE")

    def test_tool_surface_has_only_reads_and_no_path_or_budget_arguments(self):
        definitions = tool_definitions()
        self.assertEqual({tool["name"] for tool in definitions}, {SNAPSHOT_TOOL, EVIDENCE_TOOL})
        for tool in definitions:
            self.assertTrue(tool["annotations"]["readOnlyHint"])
            self.assertFalse(tool["annotations"]["destructiveHint"])
            self.assertEqual(tool["inputSchema"]["properties"], {})
            self.assertFalse(tool["inputSchema"]["additionalProperties"])

    def test_unknown_and_write_tools_never_invoke_reader(self):
        server = self.initialized_server()
        with patch.object(server.reader, "evidence", side_effect=AssertionError("Reader must not run")):
            for name in ("buy", "sell", "transfer", "recommend_allocation", "write_report", "unknown"):
                response = server.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": name}})
                self.assertEqual(response["error"]["code"], -32602)
            response = server.handle({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": SNAPSHOT_TOOL, "arguments": {"path": "../secret"}}})
            self.assertEqual(response["error"]["code"], -32602)

    def test_stdio_initialize_list_call_and_notifications_are_json_only(self):
        requests = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25", "clientInfo": {"name": "test", "version": "1"}, "capabilities": {}}},
                    {"jsonrpc": "2.0", "method": "notifications/initialized"},
                    {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                    {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": SNAPSHOT_TOOL, "arguments": {}}}]
        source = io.BytesIO(b"".join(json.dumps(request).encode() + b"\n" for request in requests))
        destination = io.BytesIO()
        StdioServer(self.reader()).run(source, destination)
        responses = [json.loads(line) for line in destination.getvalue().splitlines()]
        self.assertEqual([response["id"] for response in responses], [1, 2, 3])
        self.assertEqual(responses[-1]["result"]["structuredContent"]["status"], "available")
        self.assertFalse(responses[-1]["result"]["structuredContent"]["can_recommend"])

    def test_actual_entrypoint_subprocess_reads_only_selected_import(self):
        # Stage the unchanged entrypoint and package in a temporary checkout so
        # the subprocess exercises its real root and Git exclusion checks.
        shutil.copytree(ROOT / "src", self.root / "src", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        (self.root / "scripts").mkdir()
        script = self.root / "scripts" / "serve_portfolio_mcp.py"
        shutil.copyfile(ROOT / "scripts" / "serve_portfolio_mcp.py", script)
        current = datetime.now(timezone.utc)
        stamp, day = current.isoformat(), current.date().isoformat()
        self.report["as_of"] = stamp
        analysis = self.report["analysis"]
        analysis.update(as_of=stamp, history_start=day, valuation_date=day)
        analysis["reconciliation"]["comparison"]["valuation_date"] = day
        analysis["timeline"][0]["date"] = day
        analysis["sources"][0]["as_of"] = stamp
        for holding in analysis["holdings"] + analysis["accounts"][0]["holdings"]:
            holding.update(as_of=stamp, price_date=day)
        self.write_report()
        requests = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25", "clientInfo": {"name": "subprocess-test", "version": "1"}, "capabilities": {}}},
                    {"jsonrpc": "2.0", "method": "notifications/initialized"},
                    {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                    {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": SNAPSHOT_TOOL}},
                    {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "buy"}}]
        result = subprocess.run([sys.executable, str(script), "--directory", str(self.directory)],
                                input="".join(json.dumps(request) + "\n" for request in requests),
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        replies = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual([reply["id"] for reply in replies], [1, 2, 3, 4])
        self.assertEqual(len(replies[1]["result"]["tools"]), 2)
        data = replies[2]["result"]["structuredContent"]
        self.assertEqual(data["status"], "available")
        self.assertEqual(data["snapshot"]["summary"]["equity"], "200")
        self.assertFalse(data["can_recommend"])
        self.assertEqual(replies[3]["error"]["code"], -32602)
        self.assertNotIn(str(self.directory), result.stdout)

    def test_preinitialization_calls_and_oversized_json_are_rejected(self):
        server = StdioServer(self.reader())
        self.assertEqual(server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})["error"]["code"], -32002)
        destination = io.BytesIO()
        server.run(io.BytesIO(b"x" * (MAX_REQUEST_BYTES + 1) + b"\n" + b"[]\n" + b"not json\n"), destination)
        responses = [json.loads(line) for line in destination.getvalue().splitlines()]
        self.assertEqual([response["error"]["code"] for response in responses], [-32600, -32600, -32700])
        self.assertNotIn("xxxx", destination.getvalue().decode())

    def test_cli_invalid_directory_has_no_traceback_or_path_leak(self):
        result = subprocess.run([sys.executable, str(ROOT / "scripts" / "serve_portfolio_mcp.py"), "--directory", str(self.root / "sensitive-marker")],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertNotIn("sensitive-marker", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_cli_malformed_arguments_do_not_echo_values_or_unknown_flags(self):
        for extra in [["--max-age-hours", "sensitive-marker"], ["--sensitive-marker", "value"]]:
            with self.subTest(arguments=extra):
                result = subprocess.run([sys.executable, str(ROOT / "scripts" / "serve_portfolio_mcp.py"), "--directory", str(self.directory)] + extra,
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")
                self.assertNotIn("sensitive-marker", result.stderr)
                self.assertNotIn(str(self.directory), result.stderr)
                self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
