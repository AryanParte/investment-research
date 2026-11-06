import contextlib
import importlib.util
import io
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location(
    "repository_boundary", Path(__file__).resolve().parents[1] / "scripts/check_boundaries.py")
boundary = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(boundary)


class RepositoryBoundaryTests(unittest.TestCase):
    def check_paths(self, paths):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in paths:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("{}")
            tracked = types.SimpleNamespace(stdout=("\0".join(paths) + "\0").encode())
            with patch.object(boundary, "ROOT", root), patch.object(boundary.subprocess, "run", return_value=tracked):
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    return boundary.main()

    def test_nested_private_artifacts_are_rejected_even_when_force_tracked(self):
        for name in ("integrations/custom/private/holdings.csv", "web/data/accounts.json", "docs/reports/portfolio.json"):
            with self.subTest(path=name):
                self.assertEqual(self.check_paths([name]), 1)

    def test_only_named_dependency_metadata_is_exempt(self):
        self.assertEqual(self.check_paths(sorted(boundary.DEPENDENCY_METADATA)), 0)
        self.assertEqual(self.check_paths(["integrations/sites-pilot/runtime/portfolio.json"]), 1)

    def test_credential_files_are_rejected(self):
        for name in ("config/client.pem", "config/account.key", "config/.env.production"):
            with self.subTest(path=name):
                self.assertEqual(self.check_paths([name]), 1)


if __name__ == "__main__":
    unittest.main()
