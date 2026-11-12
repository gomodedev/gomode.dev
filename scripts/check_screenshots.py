#!/usr/bin/env python3
# Checks that public/screenshots holds exactly the WebP captures this site's pages reference.

import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
REFERENCE = re.compile(r"/screenshots/([a-z-]+\.webp)")


def main() -> int:
    pages = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-z", "--", "*.md", "*.html"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split("\0")
    expected = {name for page in pages if page for name in REFERENCE.findall((ROOT / page).read_text(encoding="utf-8"))}
    directory = ROOT / "public/screenshots"
    actual = {path.name for path in directory.iterdir()} if directory.is_dir() else set()
    errors = [f"missing {name}" for name in sorted(expected - actual)]
    errors += [f"unreferenced {name}" for name in sorted(actual - expected)]
    for name in sorted(expected & actual):
        with (directory / name).open("rb") as stream:
            header = stream.read(12)
        if header[:4] != b"RIFF" or header[8:12] != b"WEBP":
            errors.append(f"not WebP {name}")
    if errors:
        print(f"public/screenshots: {', '.join(errors)}", file=sys.stderr)
        print("Publish with: uv run --locked python ../gomode/scripts/publish_screenshots.py .", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
