"""Regression checks for the offline bundler and privacy-preserving CLI."""
import base64
import hashlib
from html.parser import HTMLParser
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("bundle_sample", ROOT / "scripts" / "bundle_sample.py")
bundler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bundler)


class Document(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.remote_assets = []
        self.blocks = []
        self.current = None
        self.policy = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "script" and attrs.get("src") or tag == "link" and attrs.get("rel") == "stylesheet":
            self.remote_assets.append(attrs)
        if tag == "meta" and attrs.get("http-equiv", "").lower() == "content-security-policy":
            self.policy = attrs["content"]
        if tag in {"script", "style"}:
            self.current = [tag, ""]

    def handle_data(self, data):
        if self.current is not None:
            self.current[1] += data

    def handle_endtag(self, tag):
        if self.current is not None and self.current[0] == tag:
            self.blocks.append(self.current)
            self.current = None


class ScriptTests(unittest.TestCase):
    def setUp(self):
        self.html = '<!doctype html><html><head><meta http-equiv="Content-Security-Policy" content="default-src \'self\'"><link rel="stylesheet" href="./styles.css"><script defer src="./app.js"></script></head><body><div id="dashboard">Sample</div></body></html>'

    def test_bundle_inlines_all_assets_after_dom_with_exact_csp_hashes(self):
        output = bundler.bundle({"mode": "sample", "title": "Synthetic"}, self.html, "body { color: teal }", 'document.getElementById("dashboard").textContent="Ready";')
        document = Document()
        document.feed(output)
        self.assertEqual(document.remote_assets, [])
        self.assertEqual([block[0] for block in document.blocks], ["style", "script", "script"])
        self.assertGreater(output.index("<script>"), output.index('<div id="dashboard">'))
        self.assertLess(output.rindex("</script>"), output.index("</body>"))
        self.assertNotIn("unsafe-inline", document.policy)
        self.assertIn("connect-src 'none'", document.policy)
        for _, content in document.blocks:
            expected = "'sha256-" + base64.b64encode(hashlib.sha256(content.encode()).digest()).decode() + "'"
            self.assertIn(expected, document.policy)

    def test_embedded_report_cannot_terminate_script_or_create_markup(self):
        marker = '</script><script>alert("not executable")</script>\u2028&'
        output = bundler.bundle({"mode": "sample", "text": marker}, self.html, "body{}", 'const literal = "</SCRIPT>";')
        document = Document()
        document.feed(output)
        self.assertEqual(len([block for block in document.blocks if block[0] == "script"]), 2)
        data_program = document.blocks[1][1]
        restored = json.loads(data_program.removeprefix("window.INVESTMENT_REPORT=").removesuffix(";"))
        self.assertEqual(restored["text"], marker)
        self.assertNotIn("</script>", data_program.lower())

    def test_imported_data_and_changed_templates_rejected(self):
        with self.assertRaisesRegex(ValueError, "fictional"):
            bundler.bundle({"mode": "imported"}, self.html, "", "")
        for html in [self.html.replace('<link rel="stylesheet" href="./styles.css">', ""),
                     self.html.replace('</body>', ""),
                     self.html.replace('http-equiv="Content-Security-Policy"', 'name="unexpected"')]:
            with self.subTest(html=html), self.assertRaises(ValueError):
                bundler.bundle({"mode": "sample"}, html, "", "")

    def test_cli_demo_output_contains_metadata_only(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, str(ROOT / "scripts" / "run.py"), "demo", "--output", directory], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            metadata = json.loads(result.stdout)
            self.assertEqual(set(metadata), {"status", "mode", "report_id", "delivery", "reading_seconds"})
            self.assertEqual(metadata["mode"], "sample")
            self.assertEqual(metadata["delivery"], "not_verified")
            self.assertNotIn("holdings", result.stdout)

    def test_cli_bad_date_logs_no_traceback_or_input_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, str(ROOT / "scripts" / "run.py"), "build", "--input", directory,
                                     "--output", str(Path(directory) / "out"), "--as-of", "invalid-date-sensitive-marker"], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn("Traceback", result.stderr)
            self.assertNotIn("sensitive-marker", result.stderr)


if __name__ == "__main__":
    unittest.main()
