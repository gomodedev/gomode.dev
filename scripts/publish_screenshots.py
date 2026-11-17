#!/usr/bin/env python3
"""Import this website’s referenced Android, caic, and mddb screenshots from their owning repositories.

This site’s Git-tracked pages decide which captures it needs. Each referenced
capture must exist in its owning repository and be a WebP image. Native scenes
come from Go Mode's e2e/screenshots/android; product scenes come from the real
caic and mddb frontend screenshot suites, using their sample data. The site's
public/screenshots then holds exactly those files; Git restores it if a copy is
interrupted.
"""

import argparse
import shutil
import subprocess
import sys

from check_screenshots import ROOT, is_webp, referenced

REPOSITORIES = ROOT.parent
SOURCE = REPOSITORIES / "gomode/e2e/screenshots/android"
PRODUCT_CAPTURES = {
    "caic-mobile.webp": REPOSITORIES / "caic/e2e/screenshots/frontend/mobile/overview.webp",
    "caic-tasks.webp": REPOSITORIES / "caic/e2e/screenshots/frontend/desktop/overview.webp",
    "mddb-editor.webp": REPOSITORIES / "mddb/e2e/screenshots/docs/document-editor.webp",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    destination = ROOT / "public/screenshots"
    try:
        names = referenced()
        if not names:
            raise ValueError(f"{ROOT} references no screenshots")
        sources = {name: PRODUCT_CAPTURES.get(name, SOURCE / name) for name in sorted(names)}
        for name, path in sources.items():
            if not path.is_file():
                raise ValueError(f"{name} is referenced by {ROOT.name} but missing from {path}")
            if not is_webp(path):
                raise ValueError(f"{path.name} is not a WebP image")
        destination.mkdir(parents=True, exist_ok=True)
        for stale in destination.iterdir():
            if stale.name not in names:
                stale.unlink()
        for name, path in sources.items():
            shutil.copyfile(path, destination / name)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"publish_screenshots: {error}", file=sys.stderr)
        return 1
    print(f"Published {len(names)} captures to {destination}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
