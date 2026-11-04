"""Local private, append-only research context. No financial account access."""
from __future__ import annotations

import hashlib
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path

KINDS = {"thesis", "decision", "feedback", "delivery_attempt", "delivery_receipt"}


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


class ContextStore:
    """Append facts without overwriting past decisions; hashes detect accidental edits.

    This is a single-writer local store, not encryption or tamper-proof storage.
    Hosted multi-user persistence requires authenticated transactions and backups.
    """

    def __init__(self, directory: str | Path):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.directory, 0o700)
        self.path = self.directory / "context.jsonl"

    def read(self) -> list[dict]:
        if not self.path.exists():
            return []
        result, previous = [], "genesis"
        for line in self.path.read_text().splitlines():
            row = json.loads(line)
            record_hash = row.pop("hash")
            if (row["previous_hash"] != previous or digest(row) != record_hash
                    or row.get("sequence") != len(result) + 1 or row.get("version") != 1 or row.get("kind") not in KINDS):
                raise ValueError("Context integrity verification failed")
            row["hash"] = record_hash
            result.append(row)
            previous = record_hash
        return result

    def append(self, kind: str, subject: str, content: dict, *, recorded_at: str | None = None) -> dict:
        if kind not in KINDS or not isinstance(subject, str) or not subject.strip() or len(subject) > 200 or not isinstance(content, dict):
            raise ValueError("Invalid context record")
        if kind == "decision":
            required = {"reason", "alternatives", "expected_outcome", "review_date"}
            if not required.issubset(content):
                raise ValueError("Decision needs reason, alternatives, expected outcome and review date")
            if (not isinstance(content["reason"], str) or not content["reason"].strip()
                    or not isinstance(content["expected_outcome"], str) or not content["expected_outcome"].strip()
                    or not isinstance(content["alternatives"], list)
                    or any(not isinstance(item, str) or not item.strip() for item in content["alternatives"])):
                raise ValueError("Decision reasoning and alternatives require explicit text")
            date.fromisoformat(content["review_date"])
        timestamp = recorded_at or datetime.now(timezone.utc).isoformat()
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("Context timestamps require an explicit time zone")
        existing = self.read()
        row = {
            "version": 1, "kind": kind, "subject": subject,
            "recorded_at": parsed.astimezone(timezone.utc).isoformat(),
            "sequence": len(existing) + 1,
            "previous_hash": existing[-1]["hash"] if existing else "genesis",
            "content": content,
        }
        row["hash"] = digest(row)
        fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        with os.fdopen(fd, "a") as stream:
            stream.write(canonical(row) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        return row

    def latest(self, kind: str, subject: str) -> dict | None:
        return next((row for row in reversed(self.read()) if row["kind"] == kind and row["subject"] == subject), None)
