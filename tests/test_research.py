import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from investment_research.briefing import validate_research
from investment_research.storage import ContextStore


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.as_of = datetime(2026, 11, 3, 22, tzinfo=timezone.utc)
        self.research = {"sources": [{"id": "s1", "url": "https://example.invalid/release", "published_at": "2026-11-02T20:00:00Z", "retrieved_at": "2026-11-03T21:00:00Z"}], "claims": [{"id": "c1", "kind": "fact", "text": "Synthetic fact", "source_ids": ["s1"], "material": True, "thesis_impact": "Test hypothesis"}]}

    def test_provenance_required(self):
        self.research["claims"][0]["source_ids"] = []
        with self.assertRaises(ValueError):
            validate_research(self.research, self.as_of, sample=True)

    def test_future_source_rejected(self):
        self.research["sources"][0]["published_at"] = "2026-11-04T00:00:00Z"
        with self.assertRaises(ValueError):
            validate_research(self.research, self.as_of, sample=True)

    def test_synthetic_source_never_live(self):
        with self.assertRaises(ValueError):
            validate_research(self.research, self.as_of)

    def test_unsafe_source_rejected(self):
        self.research["sources"][0]["url"] = "javascript:alert(1)"
        with self.assertRaises(ValueError):
            validate_research(self.research, self.as_of, sample=True)

    def test_append_history_and_tampering(self):
        with tempfile.TemporaryDirectory() as temp:
            store = ContextStore(temp)
            store.append("thesis", "NOVA", {"assumption": "Earlier version"})
            store.append("thesis", "NOVA", {"assumption": "Revised version"})
            self.assertEqual(len(store.read()), 2)
            self.assertEqual(store.latest("thesis", "NOVA")["sequence"], 2)
            store.path.write_text(store.path.read_text().replace("Earlier", "Changed"))
            with self.assertRaisesRegex(ValueError, "integrity"):
                store.read()

    def test_decision_must_record_reason(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                ContextStore(temp).append("decision", "NOVA", {"action": "hold"})


if __name__ == "__main__":
    unittest.main()
