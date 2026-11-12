#!/usr/bin/env python3
# Import and recoverably publish the referenced Go Mode Android captures used by this website.

"""Import referenced Go Mode Android captures into the committed static assets.

Pages reference the curated set of captures. Imports copy only those WebP files,
validate their headers, and recoverably exchange the published directory.
"""

from __future__ import annotations

import argparse
import fcntl
import os
import re
import shutil
import struct
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCREENSHOT_NAME = re.compile(r"[a-z-]+\.webp")
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_IMAGE_EDGE = 8192


def referenced_files() -> set[str]:
    paths = (
        [ROOT / "public/index.html"]
        if (ROOT / "public/index.html").is_file()
        else [
            ROOT / "index.md",
            *sorted((ROOT / "guide").glob("*.md")),
        ]
    )
    result = {name for path in paths for name in re.findall(r"/screenshots/([a-z-]+\.webp)", path.read_text())}
    if not result:
        raise ValueError("site does not reference any screenshots")
    return result


def webp_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as stream:
        header = stream.read(30)
    if len(header) < 30 or header[:4] != b"RIFF" or header[8:12] != b"WEBP":
        raise ValueError(f"Invalid WebP image: {path.name}")
    if struct.unpack("<I", header[4:8])[0] + 8 != path.stat().st_size:
        raise ValueError(f"Invalid WebP container size: {path.name}")
    chunk = header[12:16]
    if chunk == b"VP8X":
        width, height = int.from_bytes(header[24:27], "little") + 1, int.from_bytes(header[27:30], "little") + 1
    elif chunk == b"VP8L" and header[20] == 0x2F:
        bits = int.from_bytes(header[21:25], "little")
        width, height = (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    elif chunk == b"VP8 " and header[23:26] == b"\x9d\x01\x2a":
        encoded = struct.unpack("<HH", header[26:30])
        width, height = encoded[0] & 0x3FFF, encoded[1] & 0x3FFF
    else:
        raise ValueError(f"Unsupported WebP header: {path.name}")
    if not 0 < width <= MAX_IMAGE_EDGE or not 0 < height <= MAX_IMAGE_EDGE:
        raise ValueError(f"Invalid WebP dimensions: {path.name}")
    return width, height


def validate_captures(directory: Path, expected: set[str]) -> None:
    """Verify the exact image inventory and valid WebP headers."""
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError(f"Missing or symlinked screenshot directory: {directory.name}")
    actual = set()
    for path in directory.iterdir():
        if path.is_symlink() or not path.is_file() or SCREENSHOT_NAME.fullmatch(path.name) is None:
            raise ValueError(f"Unexpected screenshot file: {path.name}")
        if not 0 < path.stat().st_size <= MAX_IMAGE_BYTES:
            raise ValueError(f"Invalid image size: {path.name}")
        webp_dimensions(path)
        actual.add(path.name)
    if actual != expected:
        missing, unused = sorted(expected - actual), sorted(actual - expected)
        raise ValueError(f"Screenshot inventory disagrees with page references: missing {missing}, unused {unused}")


def reject_unsafe_managed_path(path: Path) -> None:
    if not path.is_relative_to(ROOT):
        raise ValueError(f"Managed screenshot path escapes the repository: {path}")
    current = ROOT
    for component in path.relative_to(ROOT).parts:
        current /= component
        if current.is_symlink():
            raise ValueError(f"Managed screenshot path contains a symlink: {current}")
    if not path.resolve().is_relative_to(ROOT):
        raise ValueError(f"Managed screenshot path escapes the repository: {path}")


def selected_source(source: Path, needed: set[str]) -> list[Path]:
    """Return the referenced captures, rejecting missing or invalid WebP images."""
    if source.is_symlink() or not source.is_dir():
        raise ValueError(f"Missing or symlinked capture source: {source}")
    selected = []
    for name in sorted(needed):
        path = source / name
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"Capture source is missing a screenshot referenced by a page: {name}")
        if not 0 < path.stat().st_size <= MAX_IMAGE_BYTES:
            raise ValueError(f"Invalid image size: {name}")
        webp_dimensions(path)
        selected.append(path)
    return selected


def import_captures(source: Path, destination: Path, needed: set[str]) -> list[str]:
    previous = ROOT / ".screenshots-previous"
    # These Unix development tools serialize writers; process exit releases the lock.
    with (ROOT / ".screenshots-import.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if previous.exists():
            if destination.exists():
                # A published new set wins only after its images are confirmed.
                validate_captures(destination, needed)
                shutil.rmtree(previous)
            else:
                os.replace(previous, destination)
        selected = selected_source(source, needed)
        with tempfile.TemporaryDirectory(prefix=".screenshots-stage-", dir=ROOT) as temporary:
            stage = Path(temporary) / "next"
            stage.mkdir()
            for path in selected:
                shutil.copyfile(path, stage / path.name)
            validate_captures(stage, needed)
            # Two renames leave a brief gap, so the previous set lives outside
            # temporary cleanup. A forced exit leaves it recoverable on the next import.
            try:
                if destination.exists():
                    os.replace(destination, previous)
                os.replace(stage, destination)
            except BaseException:
                if previous.exists() and not destination.exists():
                    os.replace(previous, destination)
                raise
            if previous.exists():
                shutil.rmtree(previous)
        return [path.name for path in selected]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__ or "Import or check Go Mode Android captures.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="Check committed website assets without a sibling checkout")
    mode.add_argument("--source", type=Path, help="Producer directory containing the referenced WebP images")
    args = parser.parse_args()
    started = time.monotonic()
    destination = ROOT / "public/screenshots"
    try:
        # Reject redirected public, backup, and lock paths before opening or moving anything.
        for path in (destination, ROOT / ".screenshots-previous", ROOT / ".screenshots-import.lock"):
            reject_unsafe_managed_path(path)
        needed = referenced_files()
        if args.check:
            if (ROOT / ".screenshots-previous").exists():
                raise ValueError("Screenshot publication was interrupted; rerun --source to recover before checking")
            validate_captures(destination, needed)
            selected = sorted(needed)
        else:
            selected = import_captures(args.source.resolve(), destination, needed)
        size = sum((destination / name).stat().st_size for name in selected)
        operation = "Checked" if args.check else "Imported"
        print(f"{operation} {len(selected)} captures, {size:,} bytes in {time.monotonic() - started:.3f}s")
        return 0
    except (OSError, ValueError) as error:
        print(f"Screenshots: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
