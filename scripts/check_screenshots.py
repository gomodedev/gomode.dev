#!/usr/bin/env python3
# Own screenshot references and WebP validation, and check this site's committed capture inventory.

import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
REFERENCE = re.compile(r"/screenshots/([a-z-]+\.webp)")


def referenced() -> set[str]:
    pages = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-z", "--", "*.md", "*.html"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split("\0")
    return {name for page in pages if page for name in REFERENCE.findall((ROOT / page).read_text(encoding="utf-8"))}


def is_webp(path: pathlib.Path) -> bool:
    with path.open("rb") as stream:
        header = stream.read(12)
    return header[:4] == b"RIFF" and header[8:12] == b"WEBP"


def main() -> int:
    expected = referenced()
    directory = ROOT / "public/screenshots"
    actual = {path.name for path in directory.iterdir()} if directory.is_dir() else set()
    errors = [f"missing {name}" for name in sorted(expected - actual)]
    errors += [f"unreferenced {name}" for name in sorted(actual - expected)]
    for name in sorted(expected & actual):
        if not is_webp(directory / name):
            errors.append(f"not WebP {name}")
    if errors:
        print(f"public/screenshots: {', '.join(errors)}", file=sys.stderr)
        print(
            "Publish with: uv run --locked python scripts/publish_screenshots.py",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
