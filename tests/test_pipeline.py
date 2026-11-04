"""Local synthetic end-to-end pipeline tests; no account/network access."""
import copy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from investment_research.pipeline import build, health
from investment_research.briefing import build_briefing, render_markdown, validate_research
from investment_research.storage import canonical, digest, ContextStore
from investment_research.accounting import DataQualityError

AS_OF = datetime(2026, 11, 3, 22, tzinfo=timezone.utc)


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.inputs = self.directory / "inputs"
        shutil.copytree(ROOT / "samples", self.inputs)
        self.output = self.directory / "output"
        self.web = self.directory / "web"
        self.web.mkdir()
        for name, content in {"index.html": "<!doctype html><p>Sample</p>", "styles.css": "p {color: black}", "app.js": "'use strict';"}.items():
            (self.web / name).write_text(content)

    def build(self, **kwargs):
        return build(self.inputs, self.output, as_of=kwargs.pop("as_of", AS_OF), complete_history=True, sample=True, web_dir=self.web, **kwargs)

    def change_research(self, change):
        path = self.inputs / "research.json"
        data = json.loads(path.read_text())
        change(data)
        path.write_text(json.dumps(data))

    def test_full_pipeline_immutable_report_provenance_and_reading_budget(self):
        report = self.build()
        self.assertEqual(report["analysis"]["summary"]["equity"], "6006.00")
        self.assertEqual(report["analysis"]["reconciliation"]["status"], "matched_to_supplied_statement")
        self.assertFalse(report["analysis"]["quality"]["broker_reconciled"])
        self.assertTrue(report["analysis"]["quality"]["statement_reconciled"])
        self.assertEqual(report["status"]["delivery"], "not_verified")
        self.assertEqual(report["input_hashes"]["statement.json"], hashlib.sha256((self.inputs / "statement.json").read_bytes()).hexdigest())
        expected = "brief-" + digest({key: value for key, value in report.items() if key != "report_id"})[:20]
        self.assertEqual(report["report_id"], expected)
        self.assertEqual(json.loads((self.output / "archive" / (expected + ".json")).read_text()), report)
        self.assertLessEqual(report["reading_words"], 360)
        self.assertLessEqual(report["estimated_read_seconds"], 120)
        self.assertIn("[fixture-grid-1](<https://research.example.invalid/grid-update>)", (self.output / "briefing.md").read_text())
        self.assertEqual((self.output / "report.json").stat().st_mode & 0o777, 0o600)

    def test_identical_rerun_restores_assets_and_health_without_changing_report(self):
        first = self.build()
        saved = (self.output / "report.json").read_bytes()
        (self.output / "index.html").unlink()
        (self.output / "briefing.md").unlink()
        (self.output / "health.json").write_text('{"status":"failed"}')
        (self.web / "styles.css").write_text("p {color: blue}")
        again = self.build()
        self.assertEqual(first, again)
        self.assertEqual(saved, (self.output / "report.json").read_bytes())
        self.assertEqual(len(list((self.output / "archive").glob("*.json"))), 1)
        self.assertEqual((self.output / "styles.css").read_text(), "p {color: blue}")
        status = json.loads((self.output / "health.json").read_text())
        self.assertEqual(status["status"], "generated")
        self.assertEqual(status["source_as_of"], "2026-11-03T21:00:00+00:00")
        self.assertEqual(status["delivery_status"], "not_verified")

    def test_changed_statement_bytes_change_identity_even_if_endpoints_same(self):
        first = self.build()
        path = self.inputs / "statement.json"
        path.write_text(path.read_text() + "\n")
        second = self.build()
        self.assertNotEqual(first["report_id"], second["report_id"])
        self.assertEqual(first["analysis"], second["analysis"])
        self.assertEqual(len(list((self.output / "archive").glob("*.json"))), 2)

    def test_failed_import_preserves_latest_good_report_and_sets_failed_health(self):
        self.build()
        good = (self.output / "report.json").read_bytes()
        path = self.inputs / "transactions.csv"
        path.write_text(path.read_text() + path.read_text().splitlines()[-1] + "\n")
        with self.assertRaisesRegex(DataQualityError, "Duplicate"):
            self.build()
        self.assertEqual((self.output / "report.json").read_bytes(), good)
        status = json.loads((self.output / "health.json").read_text())
        self.assertEqual(status["status"], "failed")
        self.assertNotIn("demo-", canonical(status))

    def test_failed_asset_preflight_preserves_latest_good_report(self):
        self.build()
        good = (self.output / "report.json").read_bytes()
        (self.web / "app.js").unlink()
        with self.assertRaises(OSError):
            self.build(as_of=AS_OF + timedelta(hours=1))
        self.assertEqual((self.output / "report.json").read_bytes(), good)
        self.assertEqual(json.loads((self.output / "health.json").read_text())["status"], "failed")

    def test_stale_import_fails_instead_of_forging_current_timestamp(self):
        self.build()
        good = (self.output / "report.json").read_bytes()
        with self.assertRaisesRegex(DataQualityError, "stale"):
            self.build(as_of=AS_OF + timedelta(days=8))
        self.assertEqual((self.output / "report.json").read_bytes(), good)
        self.assertEqual(json.loads((self.output / "health.json").read_text())["status"], "failed")

    def test_sources_required_and_unsafe_text_escaped(self):
        self.change_research(lambda data: data["claims"][0].update(text="<img src=x onerror=alert(1)> [unexpected](javascript:bad)"))
        report = self.build()
        rendered = render_markdown(report)
        self.assertNotIn("<img", rendered)
        self.assertIn("&lt;img", rendered)
        self.assertIn("\\[unexpected\\]", rendered)
        self.change_research(lambda data: data["claims"][0].update(source_ids=[]))
        with self.assertRaisesRegex(ValueError, "require provenance"):
            self.build()

    def test_main_briefing_cannot_exceed_two_minutes(self):
        self.change_research(lambda data: data["claims"][0].update(text="risk " * 310))
        with self.assertRaisesRegex(ValueError, "reading budget"):
            self.build()
        self.assertFalse((self.output / "report.json").exists())

    def test_duplicate_claims_and_multiline_source_urls_rejected(self):
        self.change_research(lambda data: data["claims"].append(copy.deepcopy(data["claims"][0])))
        with self.assertRaisesRegex(ValueError, "Duplicate claim"):
            self.build()
        path = self.inputs / "research.json"
        original = json.loads((ROOT / "samples" / "research.json").read_text())
        original["sources"][0]["url"] = "https://example.com/\n<script>"
        path.write_text(json.dumps(original))
        with self.assertRaisesRegex(ValueError, "unsafe characters"):
            self.build()

    def test_unchanged_sources_do_not_repeat_material_alerts(self):
        first = self.build()
        second = self.build(as_of=AS_OF + timedelta(hours=1))
        self.assertTrue(first["insights"])
        self.assertFalse(second["insights"])
        self.assertEqual(Decimal(second["changes_since_previous"]["investment_gain"]), 0)

    def test_incompatible_mode_and_revised_history_suppress_comparison(self):
        first = self.build()
        other_mode = copy.deepcopy(first)
        other_mode["mode"] = "imported"
        second = build_briefing(first["analysis"], first["research"], as_of=AS_OF + timedelta(hours=1), previous=other_mode, sample=True)
        self.assertIsNone(second["changes_since_previous"])
        revised = copy.deepcopy(first)
        revised["analysis"]["timeline"][0]["equity"] = "1.00"
        second = build_briefing(first["analysis"], first["research"], as_of=AS_OF + timedelta(hours=1), previous=revised, sample=True)
        self.assertIsNone(second["changes_since_previous"])

    def test_new_deposit_changes_value_without_becoming_investment_gain(self):
        self.build()
        path = self.inputs / "transactions.csv"
        path.write_text(path.read_text() + "demo-017,2026-11-04,taxable,DEPOSIT,,,,100,0,\n")
        path = self.inputs / "prices.csv"
        rows = [row.replace("2026-11-03", "2026-11-04") for row in path.read_text().splitlines() if row.startswith("2026-11-03")]
        path.write_text(path.read_text() + "\n".join(rows) + "\n")
        path = self.inputs / "benchmark.csv"
        path.write_text(path.read_text() + path.read_text().splitlines()[-1].replace("2026-11-03", "2026-11-04") + "\n")
        path = self.inputs / "statement.json"
        statement = json.loads(path.read_text())
        statement["valuation_date"] = "2026-11-04"
        for account in statement["accounts"]:
            if account["id"] == "taxable":
                account["cash"] = str(Decimal(account["cash"]) + 100)
        path.write_text(json.dumps(statement))
        second = self.build(as_of=AS_OF + timedelta(days=1))
        self.assertEqual(Decimal(second["changes_since_previous"]["value_change"]), 100)
        self.assertEqual(Decimal(second["changes_since_previous"]["net_external_flows"]), 100)
        self.assertEqual(Decimal(second["changes_since_previous"]["investment_gain"]), 0)

    def test_watchdog_distinguishes_generation_sources_and_delivery(self):
        self.build()
        current = datetime.now(timezone.utc)
        path = self.output / "health.json"
        status = json.loads(path.read_text())
        status.update(generated_at=current.isoformat(), source_as_of=(current - timedelta(days=5)).isoformat(), research_as_of=current.isoformat())
        path.write_text(json.dumps(status))
        checked = health(self.output, now=current + timedelta(seconds=1))
        self.assertFalse(checked["overdue"])
        self.assertTrue(checked["source_stale"])
        self.assertFalse(checked["research_stale"])
        self.assertTrue(checked["delivery_unverified"])
        self.assertTrue(checked["action_required"])
        self.assertFalse(checked["alert_delivered"])

    def test_watchdog_rejects_unbound_delivery_receipt_and_corrupt_health(self):
        self.build()
        now = datetime.now(timezone.utc)
        path = self.output / "health.json"
        status = json.loads(path.read_text())
        status.update(delivery_status="verified", delivery_report_id="wrong-report", delivered_at=now.isoformat())
        path.write_text(json.dumps(status))
        self.assertTrue(health(self.output, now=now)["delivery_unverified"])
        path.write_text("not json")
        self.assertEqual(health(self.output, now=now)["status"], "invalid")
        path.write_text("[]")
        self.assertEqual(health(self.output, now=now)["status"], "invalid")

    def test_malformed_research_object_records_failed_health(self):
        (self.inputs / "research.json").write_text("[]")
        with self.assertRaises(DataQualityError):
            self.build()
        self.assertEqual(json.loads((self.output / "health.json").read_text())["status"], "failed")

    def test_context_decision_records_have_reasoning_and_aware_timestamp(self):
        store = ContextStore(self.directory / "context")
        content = {"reason": "Synthetic thesis milestone", "alternatives": ["Keep allocation"], "expected_outcome": "Review future evidence", "review_date": "2026-12-01"}
        with self.assertRaisesRegex(ValueError, "time zone"):
            store.append("decision", "NOVA", content, recorded_at="2026-11-03T12:00:00")
        record = store.append("decision", "NOVA", content, recorded_at="2026-11-03T12:00:00-05:00")
        self.assertEqual(record["recorded_at"], "2026-11-03T17:00:00+00:00")
        self.assertEqual(store.latest("decision", "NOVA"), record)


if __name__ == "__main__":
    unittest.main()
