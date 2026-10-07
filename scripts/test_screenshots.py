#!/usr/bin/env python3
# Regression tests for standalone screenshot imports, input rejection, and interruption recovery.

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# A real 2x3 lossless WebP, generated once for the dimension and integrity contract.
IMAGE = bytes.fromhex("524946461e000000574542505650384c110000002f0180000007d0fffef7bfff8188e87f0000")
SCRIPT = Path(__file__).with_name("screenshots.py")


class ScreenshotImportTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "site/scripts").mkdir(parents=True)
        (self.root / "site/public").mkdir()
        self.source = self.root / "producer"
        self.source.mkdir()
        shutil.copyfile(SCRIPT, self.root / "site/scripts/screenshots.py")
        (self.root / "site/public/index.html").write_text('<img src="/screenshots/connections.webp">')
        self.data = {
            "schemaVersion": 1,
            "producer": "gomode",
            "platform": "android",
            "source": {"revision": "a" * 40, "inputsSha256": "b" * 64},
            "scenarios": [
                {
                    "name": "connections",
                    "file": "connections.webp",
                    "width": 2,
                    "height": 3,
                    "sha256": hashlib.sha256(IMAGE).hexdigest(),
                    "description": "A fixture capture",
                }
            ],
        }
        (self.source / "connections.webp").write_bytes(IMAGE)
        self.save_catalog()

    def save_catalog(self):
        (self.source / "manifest.json").write_text(json.dumps(self.data))

    def run_cli(self, *arguments):
        return subprocess.run(
            [sys.executable, str(self.root / "site/scripts/screenshots.py"), *arguments],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_imported_assets_check_without_producer(self):
        self.assertEqual(self.run_cli("--source", str(self.source)).returncode, 0)
        shutil.rmtree(self.source)
        checked = self.run_cli("--check")
        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assertIn("Checked 1 captures", checked.stdout)

    def test_corrupt_source_preserves_published_directory(self):
        self.assertEqual(self.run_cli("--source", str(self.source)).returncode, 0)
        destination = self.root / "site/public/screenshots"
        before = {path.name: path.read_bytes() for path in destination.iterdir()}
        (self.source / "connections.webp").write_bytes(IMAGE[:-1] + b"x")
        rejected = self.run_cli("--source", str(self.source))
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("differs from catalog", rejected.stderr)
        self.assertEqual({path.name: path.read_bytes() for path in destination.iterdir()}, before)

    def interrupted_import(self, failure, after_publication=False):
        self.assertEqual(self.run_cli("--source", str(self.source)).returncode, 0)
        destination = self.root / "site/public/screenshots"
        before = {path.name: path.read_bytes() for path in destination.iterdir()}
        self.data["scenarios"][0]["description"] = "A refreshed fixture capture"
        self.save_catalog()
        script = self.root / "site/scripts/screenshots.py"
        injection = f"""
import os
import runpy
import sys
from pathlib import Path
from unittest.mock import patch
original = os.replace
def interrupt(source, target):
    if Path(source).name == "next":
        if {after_publication!r}:
            original(source, target)
        {failure}
    return original(source, target)
sys.argv = [{str(script)!r}, "--source", {str(self.source)!r}]
with patch("os.replace", side_effect=interrupt):
    runpy.run_path({str(script)!r}, run_name="__main__")
"""
        result = subprocess.run([sys.executable, "-c", injection], capture_output=True, text=True, check=False)
        self.assertNotEqual(result.returncode, 0)
        return destination, before

    def test_keyboard_interrupt_restores_previous_catalog(self):
        destination, before = self.interrupted_import("raise KeyboardInterrupt")
        self.assertTrue(destination.is_dir(), "Interrupt must not destroy the published catalog")
        self.assertEqual({path.name: path.read_bytes() for path in destination.iterdir()}, before)
        self.assertEqual(self.run_cli("--check").returncode, 0)

    def test_rename_error_restores_previous_catalog(self):
        destination, before = self.interrupted_import('raise OSError("Publish failure")')
        self.assertEqual({path.name: path.read_bytes() for path in destination.iterdir()}, before)
        self.assertEqual(self.run_cli("--check").returncode, 0)

    def test_forced_exit_after_publication_keeps_valid_new_catalog(self):
        destination, before = self.interrupted_import("os._exit(91)", after_publication=True)
        published = {path.name: path.read_bytes() for path in destination.iterdir()}
        self.assertNotEqual(published, before)
        self.assertNotEqual(self.run_cli("--check").returncode, 0)
        (self.source / "connections.webp").write_bytes(IMAGE[:-1] + b"x")
        self.assertNotEqual(self.run_cli("--source", str(self.source)).returncode, 0)
        self.assertFalse((self.root / "site/.screenshots-previous").exists())
        self.assertEqual({path.name: path.read_bytes() for path in destination.iterdir()}, published)
        self.assertEqual(self.run_cli("--check").returncode, 0)

    def test_recovery_preserves_backup_if_published_catalog_is_corrupt(self):
        destination, before = self.interrupted_import("os._exit(91)", after_publication=True)
        (destination / "connections.webp").write_bytes(b"corrupt")
        self.assertNotEqual(self.run_cli("--source", str(self.source)).returncode, 0)
        backup = self.root / "site/.screenshots-previous"
        self.assertEqual({path.name: path.read_bytes() for path in backup.iterdir()}, before)
        self.assertEqual((destination / "connections.webp").read_bytes(), b"corrupt")

    def test_forced_exit_preserves_backup_and_check_is_read_only(self):
        destination, before = self.interrupted_import("os._exit(91)")
        backup = self.root / "site/.screenshots-previous"
        self.assertTrue(backup.is_dir(), "Forced exit must retain a recoverable previous catalog")
        self.assertEqual({path.name: path.read_bytes() for path in backup.iterdir()}, before)
        files_before = {
            str(path.relative_to(self.root)): path.read_bytes() for path in self.root.rglob("*") if path.is_file()
        }
        checked = self.run_cli("--check")
        self.assertNotEqual(checked.returncode, 0)
        self.assertIn("interrupted", checked.stderr)
        self.assertEqual(
            {str(path.relative_to(self.root)): path.read_bytes() for path in self.root.rglob("*") if path.is_file()},
            files_before,
        )
        self.assertFalse(destination.exists())
        (self.source / "connections.webp").write_bytes(IMAGE[:-1] + b"x")
        recovered = self.run_cli("--source", str(self.source))
        self.assertNotEqual(recovered.returncode, 0, "Recovery must not mask invalid new input")
        self.assertFalse(backup.exists())
        self.assertEqual({path.name: path.read_bytes() for path in destination.iterdir()}, before)
        self.assertEqual(self.run_cli("--check").returncode, 0)

    def test_wrong_dimensions_and_unsafe_filename_are_rejected(self):
        scene = self.data["scenarios"][0]
        scene["height"] = 4
        self.save_catalog()
        self.assertNotEqual(self.run_cli("--source", str(self.source)).returncode, 0)
        scene["height"] = 3
        scene["file"] = "../connections.webp"
        self.save_catalog()
        rejected = self.run_cli("--source", str(self.source))
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("safe WebP filenames", rejected.stderr)
        self.assertFalse((self.root / "site/public/screenshots").exists())

    def test_symlinked_public_rejects_import_without_touching_external_tree(self):
        external = self.root / "external"
        shutil.copytree(self.root / "site/public", external)
        (external / "screenshots").mkdir()
        (external / "screenshots/keep.txt").write_text("External data must remain untouched")
        public = self.root / "site/public"
        shutil.rmtree(public)
        public.symlink_to(external, target_is_directory=True)
        before = {
            str(path.relative_to(external)): path.read_bytes() if path.is_file() else None
            for path in external.rglob("*")
        }
        for arguments in (("--source", str(self.source)), ("--check",)):
            rejected = self.run_cli(*arguments)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("symlink", rejected.stderr)
            self.assertEqual(
                {
                    str(path.relative_to(external)): path.read_bytes() if path.is_file() else None
                    for path in external.rglob("*")
                },
                before,
            )
        self.assertFalse((self.root / "site/.screenshots-import.lock").exists())
        self.assertTrue(public.is_symlink())

    def test_symlinked_backup_and_lock_reject_import_before_mutation(self):
        external = self.root / "external"
        external.mkdir()
        (external / "keep.txt").write_text("External data must remain untouched")
        for name, target in ((".screenshots-previous", external), (".screenshots-import.lock", external / "keep.txt")):
            with self.subTest(name=name):
                managed = self.root / "site" / name
                managed.symlink_to(target, target_is_directory=target.is_dir())
                rejected = self.run_cli("--source", str(self.source))
                self.assertNotEqual(rejected.returncode, 0)
                self.assertIn("symlink", rejected.stderr)
                self.assertEqual((external / "keep.txt").read_text(), "External data must remain untouched")
                self.assertTrue(managed.is_symlink())
                self.assertFalse((self.root / "site/public/screenshots").exists())
                managed.unlink()

    def test_missing_referenced_capture_rejects_import(self):
        (self.root / "site/public/index.html").write_text('<img src="/screenshots/hosted-service.webp">')
        rejected = self.run_cli("--source", str(self.source))
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("missing a screenshot", rejected.stderr)


if __name__ == "__main__":
    unittest.main()
