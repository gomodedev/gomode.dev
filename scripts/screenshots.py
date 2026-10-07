#!/usr/bin/env python3
# Validate and recoverably publish the Go Mode Android screenshot catalog used by this website.

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import shutil
import struct
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAX_IMAGE_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True)
class Scenario:
    name: str
    file: str
    width: int
    height: int
    sha256: str
    description: str


def referenced_files() -> set[str]:
    paths = (
        [ROOT / "public/index.html"]
        if (ROOT / "public/index.html").is_file()
        else [
            ROOT / "index.md",
            *sorted((ROOT / "guide").glob("*.md")),
        ]
    )
    return {name for path in paths for name in re.findall(r"/screenshots/([a-z-]+\.webp)", path.read_text())}


def webp_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as stream:
        header = stream.read(30)
    if len(header) < 30 or header[:4] != b"RIFF" or header[8:12] != b"WEBP":
        raise ValueError(f"Invalid WebP image: {path.name}")
    if struct.unpack("<I", header[4:8])[0] + 8 != path.stat().st_size:
        raise ValueError(f"Invalid WebP container size: {path.name}")
    chunk = header[12:16]
    if chunk == b"VP8X":
        return int.from_bytes(header[24:27], "little") + 1, int.from_bytes(header[27:30], "little") + 1
    if chunk == b"VP8L" and header[20] == 0x2F:
        bits = int.from_bytes(header[21:25], "little")
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    if chunk == b"VP8 " and header[23:26] == b"\x9d\x01\x2a":
        width, height = struct.unpack("<HH", header[26:30])
        return width & 0x3FFF, height & 0x3FFF
    raise ValueError(f"Unsupported WebP header: {path.name}")


def catalog(directory: Path) -> tuple[dict[str, object], list[Scenario]]:
    manifest = directory / "manifest.json"
    if manifest.stat().st_size > 1024 * 1024:
        raise ValueError("Screenshot catalog exceeds 1 MiB")
    data = json.loads(manifest.read_text())
    if (
        not isinstance(data, dict)
        or data.get("schemaVersion") != 1
        or data.get("producer") != "gomode"
        or data.get("platform") != "android"
    ):
        raise ValueError("Expected a schema 1 Go Mode Android catalog")
    source = data.get("source")
    if (
        not isinstance(source, dict)
        or not re.fullmatch(r"[0-9a-f]{40}", str(source.get("revision")))
        or not re.fullmatch(r"[0-9a-f]{64}", str(source.get("inputsSha256")))
    ):
        raise ValueError("Catalog requires source revision and input digest provenance")
    scenarios = [Scenario(**row) for row in data["scenarios"]]
    files = [scene.file for scene in scenarios]
    if len(set(files)) != len(files) or len({scene.name for scene in scenarios}) != len(scenarios):
        raise ValueError("Catalog contains duplicate files or scenario names")
    for scene in scenarios:
        if not re.fullmatch(r"[a-z-]+\.webp", scene.file) or not scene.description:
            raise ValueError("Catalog requires safe WebP filenames and descriptions")
        if (
            type(scene.width) is not int
            or type(scene.height) is not int
            or not 0 < scene.width <= 8192
            or not 0 < scene.height <= 8192
        ):
            raise ValueError(f"Invalid dimensions: {scene.file}")
        path = directory / scene.file
        if path.is_symlink() or not 0 < path.stat().st_size <= MAX_IMAGE_BYTES:
            raise ValueError(f"Invalid image size or symlink: {scene.file}")
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != scene.sha256 or webp_dimensions(path) != (scene.width, scene.height):
            raise ValueError(f"Image differs from catalog: {scene.file}")
    return data, scenarios


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


def selected_catalog(source: Path, needed: set[str]) -> tuple[dict[str, object], list[Scenario]]:
    data, scenarios = catalog(source)
    selected = [scene for scene in scenarios if scene.file in needed]
    if {scene.file for scene in selected} != needed:
        raise ValueError("Catalog is missing a screenshot referenced by a page")
    return data, selected


def import_captures(source: Path, destination: Path, needed: set[str]) -> list[Scenario]:
    previous = ROOT / ".screenshots-previous"
    # These Unix development tools serialize writers; process exit releases the lock.
    with (ROOT / ".screenshots-import.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if previous.exists():
            if destination.exists():
                # A published new catalog wins only after its integrity is confirmed.
                catalog(destination)
                shutil.rmtree(previous)
            else:
                os.replace(previous, destination)
        data, selected = selected_catalog(source, needed)
        data["scenarios"] = [row for row in data["scenarios"] if row["file"] in needed]
        with tempfile.TemporaryDirectory(prefix=".screenshots-stage-", dir=ROOT) as temporary:
            stage = Path(temporary) / "next"
            stage.mkdir()
            for scene in selected:
                shutil.copyfile(source / scene.file, stage / scene.file)
            (stage / "manifest.json").write_text(json.dumps(data, indent=2) + "\n")
            catalog(stage)
            # Two renames leave a brief gap, so the previous catalog lives outside
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
        return selected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__ or "Import or check Go Mode Android captures.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="Check committed website assets without a sibling checkout")
    mode.add_argument("--source", type=Path, help="Producer directory containing manifest.json and WebP images")
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
            _, selected = selected_catalog(destination, needed)
            if {path.name for path in destination.iterdir()} != needed | {"manifest.json"}:
                raise ValueError("Committed screenshot directory contains missing or unused files")
        else:
            selected = import_captures(args.source.resolve(), destination, needed)
        size = sum((destination / scene.file).stat().st_size for scene in selected)
        operation = "Checked" if args.check else "Imported"
        print(f"{operation} {len(selected)} captures, {size:,} bytes in {time.monotonic() - started:.3f}s")
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"Screenshot catalog: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
