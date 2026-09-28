#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Package src/extension into dist/sphaera-lo-ai-assistant.oxt."""

import os
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "src", "extension")
DIST = os.path.join(ROOT, "dist")
OXT_NAME = "sphaera-lo-ai-assistant.oxt"

SKIP_DIRS = {"__pycache__"}
SKIP_FILES = {".DS_Store"}


def collect(base):
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in sorted(filenames):
            if name in SKIP_FILES or name.endswith(".pyc"):
                continue
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, base)
            yield full, rel.replace(os.sep, "/")


def main():
    if not os.path.isdir(SRC):
        raise SystemExit("missing %s" % SRC)
    os.makedirs(DIST, exist_ok=True)
    out = os.path.join(DIST, OXT_NAME)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for full, rel in collect(SRC):
            zf.write(full, rel)
    print("packed %s (%d files, %.1f KiB)" % (
        out, len(list(collect(SRC))), os.path.getsize(out) / 1024.0))


if __name__ == "__main__":
    main()
