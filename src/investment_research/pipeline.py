"""Reproducible file pipeline. All writes are local reports, never money movement."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
from pathlib import Path
import tempfile

from .accounting import analyze, load_events, load_prices, load_benchmark, reconcile, DataQualityError
from .briefing import build_briefing, render_markdown, parse_time
from .storage import canonical, digest

PIPELINE_VERSION = "1.1.0"
INPUT_FILES = ("transactions.csv", "prices.csv", "benchmark.csv", "research.json")


def _report_id(report: dict) -> str:
    return "brief-" + digest({key: value for key, value in report.items() if key != "report_id"})[:20]


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False, encoding="utf-8") as stream:
        os.chmod(stream.name, 0o600)
        stream.write(text)
        stream.flush()
        os.fsync(stream.fileno())
        temporary = Path(stream.name)
    temporary.replace(path)


def build(input_dir: Path, output_dir: Path, *, as_of: datetime, complete_history: bool,
          sample: bool = False, web_dir: Path | None = None) -> dict:
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("Timezone-aware as_of is required")
    as_of = as_of.astimezone(timezone.utc)
    output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(output_dir, 0o700)
    try:
        # Snapshot bytes once: hashes must describe exactly what was analyzed,
        # even if an import is replaced while this run is in progress.
        inputs = {name: (input_dir / name).read_bytes() for name in INPUT_FILES}
        if (input_dir / "statement.json").exists():
            inputs["statement.json"] = (input_dir / "statement.json").read_bytes()
        research = json.loads(inputs["research.json"])
        if not isinstance(research, dict):
            raise DataQualityError("Research input must be a JSON object")
        if (research.get("dataset") == "synthetic") != sample:
            raise DataQualityError("Dataset mode does not match explicitly selected pipeline mode")
        files = {name: hashlib.sha256(value).hexdigest() for name, value in inputs.items()}
        with tempfile.TemporaryDirectory(prefix=".input-snapshot-", dir=output_dir) as directory:
            snapshot = Path(directory)
            for name in INPUT_FILES[:3]:
                (snapshot / name).write_bytes(inputs[name])
                os.chmod(snapshot / name, 0o600)
            prices = load_prices(snapshot / "prices.csv")
            benchmark = load_benchmark(snapshot / "benchmark.csv")
            analysis = analyze(load_events(snapshot / "transactions.csv"), prices,
                               benchmark, as_of=as_of, history_complete=complete_history)
        if "statement.json" in inputs:
            statement = json.loads(inputs["statement.json"])
            comparison = reconcile(analysis, statement)
            if comparison["status"] != "matched":
                raise DataQualityError("Imported history does not reconcile to the supplied statement")
            analysis["reconciliation"]["status"] = "matched_to_supplied_statement"
            analysis["reconciliation"]["comparison"] = comparison
            analysis["quality"]["broker_reconciled"] = False
            analysis["quality"]["statement_reconciled"] = True
            analysis["quality"]["statement_authenticity"] = "not_independently_verified"
        # Preflight presentation assets before touching the last good report.
        assets = {name: (web_dir / name).read_text(encoding="utf-8") for name in ("index.html", "styles.css", "app.js")} if web_dir else {}
        previous_path = output_dir / "report.json"
        previous = json.loads(previous_path.read_text()) if previous_path.exists() else None
        if previous is not None and not isinstance(previous, dict):
            raise DataQualityError("Previous report must be a JSON object")
        if previous and previous.get("pipeline_version") != PIPELINE_VERSION:
            previous = None  # An old producer is not silently treated as comparable.
        if previous and previous.get("report_id") != _report_id(previous):
            raise DataQualityError("Previous report integrity check failed")
        same = (previous and previous.get("input_hashes") == files and previous.get("as_of") == as_of.isoformat()
                and previous.get("mode") == ("sample" if sample else "imported"))
        if same:
            report = previous
        else:
            report = build_briefing(analysis, research, as_of=as_of, previous=previous, sample=sample)
            report["input_hashes"] = files
            report["pipeline_version"] = PIPELINE_VERSION
            report["report_id"] = _report_id(report)
        payload = json.dumps(report, indent=2, allow_nan=False) + "\n"
        archive = output_dir / "archive" / (report["report_id"] + ".json")
        if archive.exists() and archive.read_text() != payload:
            raise DataQualityError("Immutable report identifier collision")
        if not archive.exists():
            atomic_write(archive, payload)
        atomic_write(output_dir / "briefing.md", render_markdown(report))
        atomic_write(output_dir / "report.json", payload)
        for name, content in assets.items():
            atomic_write(output_dir / name, content)
        last_day = max(point.date for point in benchmark.values() if point.date.isoformat() == analysis["valuation_date"])
        observations = [point.as_of for point in prices.values() if point.date == last_day]
        observations.append(benchmark[last_day].as_of)
        research_times = [parse_time(source["retrieved_at"]) for source in research.get("sources", [])]
        # Generation, quote freshness, research freshness and delivery are distinct.
        # A successful rerun must refresh health/assets without forging fresh sources.
        atomic_write(output_dir / "health.json", canonical({"status": "generated", "report_id": report["report_id"],
            "generated_at": datetime.now(timezone.utc).isoformat(), "analysis_as_of": report["as_of"],
            "source_as_of": min(observations).isoformat(), "valuation_date": analysis["valuation_date"],
            "research_as_of": min(research_times).isoformat() if research_times else None,
            "delivery_status": "not_verified", "delivery_report_id": None}))
        return report
    except (ValueError, KeyError, OSError, TypeError):
        atomic_write(output_dir / "health.json", canonical({"status": "failed", "error_code": "PIPELINE_VALIDATION_FAILED",
            "observed_at": datetime.now(timezone.utc).isoformat(), "delivery_status": "not_verified"}))
        raise


def health(directory: Path, *, now: datetime, deadline_hours: int = 78) -> dict:
    """Detection only. An independent scheduler/alert channel must call this."""
    if now.tzinfo is None or now.utcoffset() is None or deadline_hours <= 0:
        raise ValueError("Watchdog requires an aware timestamp and positive deadline")
    path = directory / "health.json"
    if not path.exists():
        return {"status": "missing", "action_required": True, "alert_delivered": False}
    try:
        status = json.loads(path.read_text())
        if not isinstance(status, dict):
            raise ValueError("Health record must be a JSON object")
        def expired(value):
            if not value:
                return True
            age = now - parse_time(value)
            return age < timedelta(0) or age > timedelta(hours=deadline_hours)
        overdue = expired(status.get("generated_at"))
        source_stale = expired(status.get("source_as_of"))
        research_stale = expired(status.get("research_as_of"))
        delivery_unverified = not (status.get("delivery_status") == "verified"
            and status.get("delivery_report_id") == status.get("report_id")
            and not expired(status.get("delivered_at")))
        return {**status, "overdue": overdue, "source_stale": source_stale, "research_stale": research_stale,
                "delivery_unverified": delivery_unverified,
                "action_required": overdue or source_stale or research_stale or delivery_unverified or status.get("status") != "generated",
                "alert_delivered": False}
    except (ValueError, KeyError, TypeError, OSError):
        return {"status": "invalid", "action_required": True, "alert_delivered": False}
