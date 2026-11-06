"""Local, read-only MCP access to a deliberately selected private import.

Legacy MCP 2025-11-25 stdio profile; no HTTP listener, network calls, financial
credentials, broker SDK, file writes, recommendations, or transaction actions.
Standard output carries MCP responses to the invoking client, never debug logs.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import json
import os
from pathlib import Path
import re
import stat
import subprocess
from typing import BinaryIO, Callable

from .pipeline import PIPELINE_VERSION
from .storage import digest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_VERSIONS = ("2025-11-25", "2025-06-18")
MAX_REPORT_BYTES = 2_000_000
MAX_HEALTH_BYTES = 32_768
MAX_REQUEST_BYTES = 65_536
MAX_RESPONSE_BYTES = 1_000_000
SNAPSHOT_TOOL = "read_local_portfolio_snapshot"
EVIDENCE_TOOL = "read_local_evidence_status"
INPUT_NAMES = {"transactions.csv", "prices.csv", "benchmark.csv", "research.json", "statement.json"}

BLOCKER_MESSAGES = {
    "REPORT_MISSING": "No current private report is available in the selected directory.",
    "FILE_UNSAFE": "The selected report files do not meet private-file security requirements.",
    "FILE_TOO_LARGE": "A report file exceeds the bounded reader limit.",
    "FILE_CHANGED": "A report changed while it was being read; retry after generation completes.",
    "REPORT_INVALID": "The private report is malformed or fails its schema checks.",
    "REPORT_INTEGRITY": "The report content identity or input-hash inventory is invalid.",
    "SAMPLE_REJECTED": "Synthetic reports cannot supply personal portfolio facts.",
    "HISTORY_INCOMPLETE": "Complete inception history has not been attested.",
    "UNRECONCILED": "The import has not matched a supplied statement for the same valuation date.",
    "REPORT_STALE": "The report or valuation evidence is too old for a current snapshot.",
    "SOURCE_UNAVAILABLE": "Dated source provenance is missing or invalid.",
    "GENERATION_FAILED": "The most recent generation did not complete for this report.",
    "ACCOUNT_FACTS_INVALID": "Imported cash, positions, or account totals do not reconcile.",
}


class ConfigurationError(ValueError):
    """Only generic configuration messages may cross the process boundary."""


class SnapshotBlocked(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(BLOCKER_MESSAGES[code])


def _json(raw: bytes, *, object_required: bool = True):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result

    def invalid_constant(_):
        raise ValueError("Nonfinite JSON constant")

    value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=invalid_constant)
    if object_required and not isinstance(value, dict):
        raise ValueError("JSON object required")
    return value


def _time(value: object) -> datetime:
    if not isinstance(value, str):
        raise SnapshotBlocked("SOURCE_UNAVAILABLE")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise SnapshotBlocked("SOURCE_UNAVAILABLE") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise SnapshotBlocked("SOURCE_UNAVAILABLE")
    return parsed.astimezone(timezone.utc)


def _number(value: object, *, nonnegative: bool = False) -> Decimal:
    if not isinstance(value, str) or len(value) > 80:
        raise SnapshotBlocked("ACCOUNT_FACTS_INVALID")
    try:
        result = Decimal(value)
    except InvalidOperation:
        raise SnapshotBlocked("ACCOUNT_FACTS_INVALID") from None
    if not result.is_finite() or abs(result) > Decimal("1e20") or (nonnegative and result < 0):
        raise SnapshotBlocked("ACCOUNT_FACTS_INVALID")
    return result


def _alias(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,30}", value):
        raise SnapshotBlocked("ACCOUNT_FACTS_INVALID")
    return value


def _symbol(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Z][A-Z0-9.-]{0,15}", value):
        raise SnapshotBlocked("ACCOUNT_FACTS_INVALID")
    return value


def _source(value: object) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 1000 or any(ord(char) < 32 for char in value):
        raise SnapshotBlocked("SOURCE_UNAVAILABLE")
    lowered = value.lower()
    if any(marker in lowered for marker in ("synthetic", "fictional", "example.invalid")):
        raise SnapshotBlocked("SAMPLE_REJECTED")
    return value


def _private_directory_fd(root: Path, relative: Path) -> int:
    """Walk components via directory FDs so symlink replacement cannot escape."""
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY") or not hasattr(os, "geteuid"):
        raise ConfigurationError("This platform does not provide the required file protections")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    descriptor = os.open(root, flags)
    try:
        metadata = os.fstat(descriptor)
        if metadata.st_uid != os.geteuid() or metadata.st_mode & 0o022:
            raise ConfigurationError("Repository root owner or permissions are invalid")
        for component in relative.parts:
            child = os.open(component, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
            metadata = os.fstat(descriptor)
            if metadata.st_uid != os.geteuid() or metadata.st_mode & 0o022:
                raise ConfigurationError("Private directory owner or permissions are invalid")
        if os.fstat(descriptor).st_mode & 0o077:
            raise ConfigurationError("The selected report directory must be owner-only")
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


class PrivateReportReader:
    """Read one configured directory; tools cannot supply paths or select files.

    The owner must select an absolute directory under this checkout's ignored
    `private/` or `runtime/`. This reader never creates or repairs directories.
    Git checks are read-only, bounded, and do not use a shell or credentials.
    """

    def __init__(self, directory: Path, *, repository_root: Path = REPOSITORY_ROOT,
                 max_age_hours: int = 96, clock: Callable[[], datetime] | None = None):
        if not isinstance(max_age_hours, int) or isinstance(max_age_hours, bool) or not 1 <= max_age_hours <= 96:
            raise ConfigurationError("Freshness threshold must be within one to 96 hours")
        self.root = Path(repository_root).resolve(strict=True)
        selected = Path(directory)
        if not selected.is_absolute() or ".." in selected.parts:
            raise ConfigurationError("Select an explicit absolute private directory without traversal")
        try:
            relative = selected.relative_to(self.root)
        except ValueError:
            raise ConfigurationError("Directory must be within this checkout's private runtime area") from None
        if len(relative.parts) < 2 or relative.parts[0] not in {"private", "runtime"}:
            raise ConfigurationError("Select a dedicated directory beneath private or runtime")
        self.relative = relative
        self.max_age = timedelta(hours=max_age_hours)
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        try:
            descriptor = _private_directory_fd(self.root, self.relative)
            os.close(descriptor)
            self._check_git_exclusion()
        except (OSError, subprocess.SubprocessError) as exc:
            raise ConfigurationError("Private directory security validation failed") from exc

    def _check_git_exclusion(self) -> None:
        targets = [str(self.relative / name) for name in ("report.json", "health.json")]
        # Client launch environments must not redirect this privacy check to an
        # empty alternate index, different repository, or injected Git config.
        environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        environment.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
                           GIT_CONFIG_SYSTEM=os.devnull, GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0")
        prefix = ["git", "-c", "core.fsmonitor=false", "-c", "core.untrackedCache=false", "-C", str(self.root)]
        checkout = subprocess.run(prefix + ["rev-parse", "--show-toplevel"],
                                  env=environment, capture_output=True, timeout=5, check=False)
        if checkout.returncode != 0 or os.fsdecode(checkout.stdout).rstrip("\n") != str(self.root):
            raise ConfigurationError("Private reports require their own checked-out repository")
        tracked = subprocess.run(prefix + ["ls-files", "-z", "--", str(self.relative)],
                                 env=environment, capture_output=True, timeout=5, check=False)
        # Check each path independently; one ignored file cannot hide a negated
        # health/report exception in the repository's ignore rules.
        if tracked.returncode != 0 or tracked.stdout:
            raise ConfigurationError("Private report directory must be ignored and contain no tracked files")
        for target in targets:
            result = subprocess.run(prefix + ["check-ignore", "--quiet", "--no-index", "--", target],
                                    env=environment, capture_output=True, timeout=5, check=False)
            if result.returncode != 0:
                raise ConfigurationError("Both private report files must be excluded from Git")

    def _read(self, name: str, limit: int) -> dict:
        # name is an internal constant, never a tool argument.
        if name not in {"report.json", "health.json"}:
            raise SnapshotBlocked("FILE_UNSAFE")
        directory_fd = descriptor = None
        try:
            directory_fd = _private_directory_fd(self.root, self.relative)
            descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory_fd)
            before = os.fstat(descriptor)
            if (not stat.S_ISREG(before.st_mode) or before.st_uid != os.geteuid()
                    or before.st_mode & 0o077 or before.st_nlink != 1):
                raise SnapshotBlocked("FILE_UNSAFE")
            if before.st_size <= 0 or before.st_size > limit:
                raise SnapshotBlocked("FILE_TOO_LARGE")
            chunks, count = [], 0
            while count <= limit:
                chunk = os.read(descriptor, min(65_536, limit + 1 - count))
                if not chunk:
                    break
                chunks.append(chunk)
                count += len(chunk)
            if count > limit:
                raise SnapshotBlocked("FILE_TOO_LARGE")
            after = os.fstat(descriptor)
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise SnapshotBlocked("FILE_CHANGED")
            return _json(b"".join(chunks))
        except FileNotFoundError:
            raise SnapshotBlocked("REPORT_MISSING") from None
        except SnapshotBlocked:
            raise
        except (OSError, ConfigurationError):
            raise SnapshotBlocked("FILE_UNSAFE") from None
        except (ValueError, TypeError, RecursionError):
            # Preserve already classified safe failures, but never report raw JSON.
            raise SnapshotBlocked("REPORT_INVALID") from None
        finally:
            if descriptor is not None:
                os.close(descriptor)
            if directory_fd is not None:
                os.close(directory_fd)

    def _fresh(self, timestamp: object, now: datetime) -> datetime:
        parsed = _time(timestamp)
        age = now - parsed
        if age < timedelta(0) or age > self.max_age:
            raise SnapshotBlocked("REPORT_STALE")
        return parsed

    def _holdings(self, rows: object, equity: Decimal, valuation_day: date, now: datetime) -> list[dict]:
        if not isinstance(rows, list) or len(rows) > 500:
            raise SnapshotBlocked("ACCOUNT_FACTS_INVALID")
        result, seen = [], set()
        for row in rows:
            if not isinstance(row, dict):
                raise SnapshotBlocked("ACCOUNT_FACTS_INVALID")
            symbol = _symbol(row.get("symbol"))
            if symbol in seen:
                raise SnapshotBlocked("ACCOUNT_FACTS_INVALID")
            seen.add(symbol)
            quantity = _number(row.get("quantity"), nonnegative=True)
            price = _number(row.get("price"), nonnegative=True)
            value = _number(row.get("market_value"), nonnegative=True)
            if quantity <= 0 or price <= 0 or abs(quantity * price - value) > Decimal("0.01"):
                raise SnapshotBlocked("ACCOUNT_FACTS_INVALID")
            if row.get("price_date") != valuation_day.isoformat():
                raise SnapshotBlocked("SOURCE_UNAVAILABLE")
            source = _source(row.get("source"))
            source_time = self._fresh(row.get("as_of"), now)
            if source_time.date() < valuation_day:
                raise SnapshotBlocked("SOURCE_UNAVAILABLE")
            if equity == 0 and value > 0:
                raise SnapshotBlocked("ACCOUNT_FACTS_INVALID")
            weight = value / equity * 100 if equity else Decimal(0)
            result.append({"symbol": symbol, "quantity": str(quantity), "price": str(price), "market_value": str(value),
                           "weight_pct": format(weight, ".6f"), "price_date": valuation_day.isoformat(),
                           "source": source, "source_as_of": source_time.isoformat()})
        return result

    def _validate(self, report: dict, health: dict, now: datetime) -> dict:
        if report.get("mode") == "sample" or report.get("research", {}).get("dataset") == "synthetic":
            raise SnapshotBlocked("SAMPLE_REJECTED")
        if (report.get("mode") != "imported" or report.get("schema_version") != 1
                or report.get("pipeline_version") != PIPELINE_VERSION):
            raise SnapshotBlocked("REPORT_INVALID")
        expected_id = "brief-" + digest({key: value for key, value in report.items() if key != "report_id"})[:20]
        if report.get("report_id") != expected_id:
            raise SnapshotBlocked("REPORT_INTEGRITY")
        hashes = report.get("input_hashes")
        if (not isinstance(hashes, dict) or set(hashes) != INPUT_NAMES
                or any(not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value) for value in hashes.values())):
            raise SnapshotBlocked("REPORT_INTEGRITY")
        report_time = self._fresh(report.get("as_of"), now)
        analysis = report.get("analysis")
        if not isinstance(analysis, dict) or analysis.get("schema_version") != "1.0" or analysis.get("currency") != "USD":
            raise SnapshotBlocked("REPORT_INVALID")
        if _time(analysis.get("as_of")) != report_time:
            raise SnapshotBlocked("REPORT_INVALID")
        quality = analysis.get("quality", {})
        if quality.get("history_attested_complete") is not True:
            raise SnapshotBlocked("HISTORY_INCOMPLETE")
        if (quality.get("statement_reconciled") is not True
                or analysis.get("reconciliation", {}).get("status") != "matched_to_supplied_statement"
                or quality.get("broker_reconciled") is not False):
            raise SnapshotBlocked("UNRECONCILED")
        if quality.get("status") != "fresh":
            raise SnapshotBlocked("REPORT_STALE")
        valuation_day = date.fromisoformat(analysis["valuation_date"])
        if valuation_day > now.date() or (now.date() - valuation_day).days > self.max_age.total_seconds() // 86400:
            raise SnapshotBlocked("REPORT_STALE")
        if (health.get("status") != "generated" or health.get("report_id") != expected_id
                or health.get("valuation_date") != valuation_day.isoformat()):
            raise SnapshotBlocked("GENERATION_FAILED")
        self._fresh(health.get("generated_at"), now)
        source_time = self._fresh(health.get("source_as_of"), now)
        if source_time.date() < valuation_day:
            raise SnapshotBlocked("SOURCE_UNAVAILABLE")
        sources = analysis.get("sources")
        if not isinstance(sources, list) or not sources or len(sources) > 1000:
            raise SnapshotBlocked("SOURCE_UNAVAILABLE")
        for source in sources:
            _source(source.get("source"))
            if _time(source.get("as_of")) > now:
                raise SnapshotBlocked("SOURCE_UNAVAILABLE")
        summary = analysis.get("summary", {})
        amounts = {name: _number(summary.get(name), nonnegative=name in {"equity", "cash", "positions_value"})
                   for name in ("equity", "cash", "positions_value", "net_contributions", "gain")}
        if (abs(amounts["equity"] - amounts["cash"] - amounts["positions_value"]) > Decimal("0.01")
                or abs(amounts["equity"] - amounts["net_contributions"] - amounts["gain"]) > Decimal("0.01")):
            raise SnapshotBlocked("ACCOUNT_FACTS_INVALID")
        timeline = analysis.get("timeline")
        if (not isinstance(timeline, list) or not timeline or len(timeline) > 20_000
                or timeline[0].get("date") != analysis.get("history_start") or timeline[-1].get("date") != valuation_day.isoformat()):
            raise SnapshotBlocked("HISTORY_INCOMPLETE")
        previous_day, cumulative = None, Decimal(0)
        for observation in timeline:
            day = date.fromisoformat(observation["date"])
            if day > valuation_day or (previous_day is not None and day <= previous_day):
                raise SnapshotBlocked("HISTORY_INCOMPLETE")
            previous_day = day
            _number(observation.get("equity"), nonnegative=True)
            cumulative += _number(observation.get("net_flow"))
            if abs(cumulative - _number(observation.get("cumulative_contributions"))) > Decimal("0.01"):
                raise SnapshotBlocked("ACCOUNT_FACTS_INVALID")
        if (abs(_number(timeline[-1].get("equity")) - amounts["equity"]) > Decimal("0.01")
                or abs(cumulative - amounts["net_contributions"]) > Decimal("0.01")):
            raise SnapshotBlocked("ACCOUNT_FACTS_INVALID")
        holdings = self._holdings(analysis.get("holdings"), amounts["equity"], valuation_day, now)
        if abs(sum((Decimal(row["market_value"]) for row in holdings), Decimal(0)) - amounts["positions_value"]) > Decimal("0.01") * max(1, len(holdings)):
            raise SnapshotBlocked("ACCOUNT_FACTS_INVALID")
        account_rows = analysis.get("accounts")
        if not isinstance(account_rows, list) or not account_rows or len(account_rows) > 20:
            raise SnapshotBlocked("ACCOUNT_FACTS_INVALID")
        comparison = analysis.get("reconciliation", {}).get("comparison", {})
        if (comparison.get("status") != "matched" or comparison.get("discrepancies") != []
                or comparison.get("valuation_date") != valuation_day.isoformat()
                or comparison.get("account_count") != len(account_rows)):
            raise SnapshotBlocked("UNRECONCILED")
        accounts, seen = [], set()
        combined_shares, combined_values = {}, {}
        combined_marks = {row["symbol"]: row for row in holdings}
        for account in account_rows:
            alias = _alias(account.get("id"))
            if alias in seen:
                raise SnapshotBlocked("ACCOUNT_FACTS_INVALID")
            seen.add(alias)
            equity, cash = _number(account.get("equity"), nonnegative=True), _number(account.get("cash"), nonnegative=True)
            positions = self._holdings(account.get("holdings"), equity, valuation_day, now)
            if abs(equity - cash - sum((Decimal(row["market_value"]) for row in positions), Decimal(0))) > Decimal("0.01") * max(1, len(positions)):
                raise SnapshotBlocked("ACCOUNT_FACTS_INVALID")
            for row in positions:
                symbol = row["symbol"]
                mark = combined_marks.get(symbol)
                # Each symbol has one valuation mark in the source pipeline.
                # Matching portfolio totals alone would allow offsetting price
                # errors to hide between account and combined views.
                if (mark is None or Decimal(row["price"]) != Decimal(mark["price"])
                        or any(row[field] != mark[field] for field in ("price_date", "source", "source_as_of"))):
                    raise SnapshotBlocked("ACCOUNT_FACTS_INVALID")
                combined_shares[symbol] = combined_shares.get(symbol, Decimal(0)) + Decimal(row["quantity"])
                combined_values[symbol] = combined_values.get(symbol, Decimal(0)) + Decimal(row["market_value"])
            accounts.append({"alias": alias, "equity": str(equity), "cash": str(cash), "holdings": positions})
        if (abs(sum((Decimal(row["equity"]) for row in accounts), Decimal(0)) - amounts["equity"]) > Decimal("0.01") * len(accounts)
                or abs(sum((Decimal(row["cash"]) for row in accounts), Decimal(0)) - amounts["cash"]) > Decimal("0.01") * len(accounts)
                or combined_shares != {row["symbol"]: Decimal(row["quantity"]) for row in holdings}):
            raise SnapshotBlocked("ACCOUNT_FACTS_INVALID")
        if any(abs(combined_values[row["symbol"]] - Decimal(row["market_value"])) > Decimal("0.01") * len(accounts)
               for row in holdings):
            raise SnapshotBlocked("ACCOUNT_FACTS_INVALID")
        return {"report_id": expected_id, "as_of": report_time.isoformat(), "valuation_date": valuation_day.isoformat(), "currency": "USD",
                "summary": {name: str(value) for name, value in amounts.items()}, "holdings": holdings, "accounts": accounts,
                "provenance": {"origin": "manual_import", "statement_match": "user_supplied_endpoint_comparison",
                               "broker_authenticated": False, "history_complete": "user_attested_not_independently_verified",
                               "report_content_hash_verified": True, "input_hashes_bound": True, "input_contents_revalidated": False,
                               "source_authenticity": "declared_not_independently_verified", "valuation_source_as_of": source_time.isoformat()},
                "limitations": ["Descriptive account facts only; no current valuation or investment recommendation is supported.",
                                "Statement authenticity and complete historical coverage have not been independently verified.",
                                "Contribution totals are net external flows, not certified IRA tax-year contribution room."]}

    def evidence(self, *, include_snapshot: bool = False) -> dict:
        now = self.clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ConfigurationError("The evaluation clock must be timezone-aware")
        now = now.astimezone(timezone.utc)
        result = {"status": "unavailable", "checked_at": now.isoformat(), "can_recommend": False,
                  "allowed_use": "descriptive_account_facts_only", "snapshot": None,
                  "gates": {"portfolio": "blocked", "current_fundamentals": "not_implemented", "valuation": "not_implemented",
                            "tax_lots_and_eligibility": "not_implemented", "recommendations": "disabled"},
                  "financial_capabilities": [], "blockers": []}
        try:
            # Recheck exclusions each request; no newly tracked private report may
            # become a data source after the server was launched.
            self._check_git_exclusion()
            report = self._read("report.json", MAX_REPORT_BYTES)
            status = self._read("health.json", MAX_HEALTH_BYTES)
            snapshot = self._validate(report, status, now)
            result["status"] = "available"
            result["gates"]["portfolio"] = "manual_import_validated"
            result["report_id"] = snapshot["report_id"]
            result["as_of"] = snapshot["as_of"]
            result["valuation_date"] = snapshot["valuation_date"]
            result["provenance"] = snapshot["provenance"]
            if include_snapshot:
                result["snapshot"] = snapshot
        except SnapshotBlocked as exc:
            result["blockers"] = [{"code": exc.code, "message": BLOCKER_MESSAGES[exc.code]}]
        except (ConfigurationError, OSError, subprocess.SubprocessError):
            result["blockers"] = [{"code": "FILE_UNSAFE", "message": BLOCKER_MESSAGES["FILE_UNSAFE"]}]
        except (ValueError, KeyError, TypeError, AttributeError, ArithmeticError, RecursionError):
            result["blockers"] = [{"code": "REPORT_INVALID", "message": BLOCKER_MESSAGES["REPORT_INVALID"]}]
        return result


def tool_definitions() -> list[dict]:
    return [{"name": name, "title": title, "description": description,
             "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
             "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}}
            for name, title, description in [
                (SNAPSHOT_TOOL, "Read private local portfolio facts", "Read a selected, fresh, statement-matched manual import. Descriptive holdings/cash only. Never recommend securities, buy/sell/trim actions, or exact dollar allocations from this tool. Missing evidence returns unavailable; no sample fallback."),
                (EVIDENCE_TOOL, "Check private local evidence readiness", "Check freshness, import provenance, statement reconciliation, and blockers. can_recommend is always false because research, valuation, and tax gates are not implemented. No financial actions or credentials.")]]


def _error(identifier, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": identifier, "error": {"code": code, "message": message}}


class StdioServer:
    def __init__(self, reader: PrivateReportReader):
        self.reader = reader
        self.initialized = False
        self.ready = False

    def handle(self, request: object) -> dict | None:
        if not isinstance(request, dict) or request.get("jsonrpc") != "2.0" or not isinstance(request.get("method"), str):
            return _error(None, -32600, "Invalid JSON-RPC request")
        identifier = request.get("id")
        if "id" in request and (isinstance(identifier, bool) or not isinstance(identifier, (int, str))):
            return _error(None, -32600, "Invalid request identifier")
        method = request["method"]
        if "id" not in request:
            if method == "notifications/initialized" and self.initialized:
                self.ready = True
            return None
        params = request.get("params", {})
        if not isinstance(params, dict):
            return _error(identifier, -32602, "Invalid request parameters")
        if method == "initialize":
            if self.initialized:
                return _error(identifier, -32600, "Already initialized")
            if not isinstance(params.get("protocolVersion"), str) or not isinstance(params.get("clientInfo"), dict) or not isinstance(params.get("capabilities"), dict):
                return _error(identifier, -32602, "Invalid initialization parameters")
            version = params["protocolVersion"] if params["protocolVersion"] in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0]
            self.initialized = True
            result = {"protocolVersion": version, "serverInfo": {"name": "investment-research-local-readonly", "version": "1.0.0"},
                      "capabilities": {"tools": {"listChanged": False}},
                      "instructions": "This server has only descriptive local reads. Treat all imported values as manually supplied, not broker-verified. can_recommend is always false. Do not infer precise allocations or buy/sell/trim recommendations. No trading, transfer, payment, banking or financial credential tool exists."}
        elif method == "ping":
            result = {}
        elif not self.ready:
            return _error(identifier, -32002, "Complete MCP initialization before requesting tools")
        elif method == "tools/list":
            if any(key not in {"_meta"} for key in params):
                return _error(identifier, -32602, "This fixed tool list does not accept pagination parameters")
            result = {"tools": tool_definitions()}
        elif method == "tools/call":
            if params.get("name") not in {SNAPSHOT_TOOL, EVIDENCE_TOOL}:
                return _error(identifier, -32602, "Unknown or unsupported read tool")
            if params.get("arguments", {}) != {} or any(key not in {"name", "arguments", "_meta"} for key in params):
                return _error(identifier, -32602, "Read tools take no arguments")
            evidence = self.reader.evidence(include_snapshot=params["name"] == SNAPSHOT_TOOL)
            result = {"content": [{"type": "text", "text": json.dumps(evidence, separators=(",", ":"), allow_nan=False)}],
                      "structuredContent": evidence, "isError": evidence["status"] != "available"}
        else:
            return _error(identifier, -32601, "Unsupported MCP method")
        return {"jsonrpc": "2.0", "id": identifier, "result": result}

    def run(self, input_stream: BinaryIO, output_stream: BinaryIO) -> None:
        while True:
            raw = input_stream.readline(MAX_REQUEST_BYTES + 1)
            if not raw:
                return
            if len(raw) > MAX_REQUEST_BYTES:
                while raw and not raw.endswith(b"\n"):
                    raw = input_stream.readline(MAX_REQUEST_BYTES + 1)
                response = _error(None, -32600, "MCP request exceeds size limit")
            else:
                try:
                    response = self.handle(_json(raw, object_required=False))
                except (ValueError, TypeError, UnicodeError, RecursionError):
                    response = _error(None, -32700, "Invalid JSON message")
                except Exception:
                    # Never allow raw paths, report data, or tracebacks onto logs.
                    response = _error(None, -32603, "Local read failed")
            if response is not None:
                encoded = json.dumps(response, separators=(",", ":"), allow_nan=False).encode("utf-8")
                if len(encoded) > MAX_RESPONSE_BYTES:
                    encoded = json.dumps(_error(response.get("id"), -32603, "Read response exceeds size limit")).encode("utf-8")
                output_stream.write(encoded + b"\n")
                output_stream.flush()
