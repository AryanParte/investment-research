"""Reproducible starter cleanup must refuse ambiguity and preserve old source."""
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "integrations/sites-pilot/prepare_starter.py"


class StarterSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(prefix="investment-starter-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for directory in ("app/mcp", "worker", "lib", "components/ui", "hooks"):
            (self.root / directory).mkdir(parents=True, exist_ok=True)
        self.manifest = {
            "name": "site-creator-vinext-starter",
            "dependencies": {"next": "16.3.4", "zod": "3.25.76"},
            "devDependencies": {"vinext": "1.0.0-beta.5", "eslint-config-next": "16.3.4"},
        }
        (self.root / "package.json").write_text(json.dumps(self.manifest))
        (self.root / "app/mcp/route.ts").write_text("export const sample = true;")
        (self.root / "worker/index.ts").write_text("export default {};")
        (self.root / "components/ui/example.ts").write_text("export const oldSource = true;")
        (self.root / "lib/connector-errors.mts").write_text('import { z } from "zod/v4";')

    def run_script(self, *flags):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--checkout", str(self.root), *flags],
            capture_output=True, text=True, check=False,
        )

    def assert_original_unchanged(self):
        self.assertEqual(json.loads((self.root / "package.json").read_text()), self.manifest)
        self.assertEqual((self.root / "components/ui/example.ts").read_text(), "export const oldSource = true;")
        self.assertFalse((self.root / ".sites-runtime").exists())

    def test_fresh_starter_confirmation_is_required_before_any_change(self):
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--fresh-starter", result.stderr)
        self.assert_original_unchanged()

    def test_symlink_in_removable_tree_refuses_all_changes(self):
        link = self.root / "components/ui/link"
        link.symlink_to(self.root / "package.json")
        result = self.run_script("--fresh-starter")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("symlink", result.stderr)
        self.assert_original_unchanged()
        link.unlink()
        original_lib = self.root / "original-lib"
        (self.root / "lib").rename(original_lib)
        (self.root / "lib").symlink_to(original_lib, target_is_directory=True)
        result = self.run_script("--fresh-starter")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("symlink", result.stderr)
        self.assert_original_unchanged()
        self.assertTrue((original_lib / "connector-errors.mts").exists())

    def test_cleanup_archives_original_source_and_preserves_worker(self):
        result = self.run_script("--fresh-starter")
        self.assertEqual(result.returncode, 0, result.stderr)
        backup = self.root / json.loads(result.stdout)["backup"]
        self.assertEqual(json.loads((backup / "package.json").read_text()), self.manifest)
        self.assertEqual((backup / "components/ui/example.ts").read_text(), "export const oldSource = true;")
        self.assertEqual((backup / "lib/connector-errors.mts").read_text(), 'import { z } from "zod/v4";')
        self.assertFalse((self.root / "components").exists())
        self.assertEqual((self.root / "worker/index.ts").read_text(), "export default {};")
        manifest = json.loads((self.root / "package.json").read_text())
        self.assertEqual(manifest["dependencies"], {"next": "16.4.5"})
        self.assertEqual(manifest["overrides"]["sharp"], "0.35.5")


if __name__ == "__main__":
    unittest.main()
