"""Prune unused starter UI and apply this pilot's audited dependency constraints.

Apply the pilot app/lib overlay to a fresh official Sites Vinext starter first.
No registration, hosting identity, credentials, or runtime state is touched.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
import tempfile


UNUSED_UI_PACKAGES = {
    "@base-ui/react", "@hookform/resolvers", "@shadcn/react",
    "class-variance-authority", "clsx", "cmdk", "date-fns",
    "embla-carousel-react", "input-otp", "lucide-react", "next-themes",
    "radix-ui", "react-day-picker", "react-hook-form", "react-resizable-panels",
    "recharts", "sonner", "tailwind-merge", "vaul", "zod",
}
REMOVED_FILES = ("lib/utils.ts", "lib/connector-errors.mts", "components.json")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--fresh-starter", action="store_true",
                        help="Confirm this is a fresh official starter with only the pilot overlay applied")
    args = parser.parse_args()
    if not args.fresh_starter:
        parser.error("--fresh-starter is required; do not run this cleanup on a customized application")
    if args.checkout.is_symlink():
        raise ValueError("Refusing a symlink checkout")
    root = args.checkout.resolve()
    manifest_path = root / "package.json"
    manifest = json.loads(manifest_path.read_text())
    if not (root / "app/mcp/route.ts").is_file() or not (root / "worker/index.ts").is_file():
        raise ValueError("Apply the pilot overlay to the official Vinext starter first")
    if (manifest.get("name") != "site-creator-vinext-starter" or
            manifest.get("devDependencies", {}).get("vinext") != "1.0.0-beta.5"):
        raise ValueError("Starter version changed; review this cleanup before applying")
    removable = [root / name for name in ("components", "hooks", *REMOVED_FILES)]
    for path in removable:
        for ancestor in path.parents:
            if ancestor == root:
                break
            if ancestor.is_symlink():
                raise ValueError("Refusing symlink ancestors of removable starter scaffolding")
        if path.is_symlink() or (path.is_dir() and any(child.is_symlink() for child in path.rglob("*"))):
            raise ValueError("Refusing symlinks in removable starter scaffolding")
    # Refuse to remove scaffolding if application code has begun consuming it.
    blocked = re.compile(r"(?:@/components|@/hooks|(?:@/lib/|\./)(?:utils|connector-errors))")
    for directory in ("app", "lib", "worker"):
        for path in (root / directory).rglob("*"):
            if not path.is_file() or path.suffix not in {".ts", ".tsx", ".mts"}:
                continue
            if path.relative_to(root).as_posix() in REMOVED_FILES or path.name == "widget-html.ts":
                continue
            if blocked.search(path.read_text()):
                raise ValueError(f"Application consumes removable scaffolding: {path.relative_to(root)}")
    dependencies = manifest["dependencies"]
    removed = sorted(set(dependencies) & UNUSED_UI_PACKAGES)
    for name in removed:
        dependencies.pop(name)
    dependencies["next"] = "16.4.5"
    manifest["devDependencies"]["eslint-config-next"] = "16.4.5"
    overrides = manifest.setdefault("overrides", {})
    overrides.update({
        "sharp": "0.35.5",
        "source-map-js": "1.2.2",
        "fast-uri": "3.1.9",
        "baseline-browser-mapping": "2.11.0",
    })
    overrides.setdefault("miniflare", {})["sharp"] = "0.35.5"
    # Preserve the old scaffold outside source control instead of deleting it.
    backup_root = root / ".sites-runtime/unused-ui-backup"
    if backup_root.is_symlink() or (root / ".sites-runtime").is_symlink():
        raise ValueError("Refusing a symlink backup destination")
    backup_root.mkdir(parents=True, exist_ok=True)
    backup = Path(tempfile.mkdtemp(prefix="starter-", dir=backup_root))
    shutil.copy2(manifest_path, backup / "package.json")
    for path in removable:
        if path.exists():
            destination = backup / path.relative_to(root)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), str(destination))
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"removed_unused_direct_dependencies": removed,
                      "next": "16.4.5", "patched_overrides": overrides,
                      "backup": str(backup.relative_to(root)),
                      "installation_required": True}))


if __name__ == "__main__":
    main()
