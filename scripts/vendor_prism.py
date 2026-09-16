#!/usr/bin/env python3
"""Rebuild the self-hosted Prism bundle from pinned upstream components.

The site is a static GitHub Pages tree with no build step, so syntax
highlighting ships as one committed bundle rather than a CDN reference: a
third-party CDN would be an uncontrolled runtime dependency on a page whose
entire point is digest-pinned evidence.

Components are concatenated in dependency order and every input is verified
against a recorded SHA-256 before it is written, so a rebuild either
reproduces the committed bytes or fails loudly.

Usage: uv run scripts/vendor_prism.py [--check]
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "assets/prism.js"
VERSION = "1.29.0"
BASE = f"https://cdnjs.cloudflare.com/ajax/libs/prism/{VERSION}/components"

# Dependency order matters: clike seeds javascript/go, javascript seeds
# typescript, and core must define Prism before any component registers.
COMPONENTS: tuple[tuple[str, str], ...] = (
    ("prism-core.min.js", "e2624d4f66cc5f171cd460896b106630f7666a1e638b42dd9ddefd0ca7758683"),
    ("prism-clike.min.js", "c76ba4e240932bdc75546be30e550f5ba5e13815ff71511c76e9e27ac3072444"),
    ("prism-markup.min.js", "879fc9d256c352d980e053857fa707330853b8bfb67ce284ea661a24dec5756e"),
    ("prism-json.min.js", "956d86baa5ae7ec4106758f354ac2d140bdcd7fc103dece02f73ed12b8d663e4"),
    ("prism-yaml.min.js", "719c8e8b8c344dc9de510c729f65ba840b1502a0a8e7e25e2ad19ee715f65c02"),
    ("prism-python.min.js", "ed4385685bcf2d4935c8dbbab4bde16603da1329e092d2bf36c3dadd67e9a85c"),
    ("prism-javascript.min.js", "0345ea83e12b7b974e953c79a64dea35a40308309449db70b82020fb688ac321"),
    ("prism-typescript.min.js", "852f5513bb9ca9db247f86ecfce74acc91c541749d34929157240518fef8152a"),
    ("prism-go.min.js", "1225b4afb593126d4082da5fd2b131aede39831c2b2a62d6b07ea025acd2bf3f"),
    ("prism-bash.min.js", "6260814110e5182f2956e3bd257429548d9dbf2a9b66a63719b26cf9fac966a7"),
)

HEADER = f"""/*!
 * Prism {VERSION} — MIT License — https://prismjs.com
 * Copyright (c) 2012 Lea Verou
 *
 * Self-hosted bundle. Do not edit by hand: regenerate with
 *   uv run scripts/vendor_prism.py
 * Languages: markup, json, yaml, python, javascript, typescript, go, bash.
 * Full licence text: assets/prism.LICENSE.txt
 */
"""


def fetch(name: str) -> bytes:
    with urllib.request.urlopen(f"{BASE}/{name}", timeout=30) as response:
        return response.read()


def build() -> bytes:
    parts = [HEADER.encode()]
    for name, expected in COMPONENTS:
        data = fetch(name)
        actual = hashlib.sha256(data).hexdigest()
        if actual != expected:
            raise SystemExit(f"{name}: digest {actual} does not equal pinned {expected}")
        parts.append(data.rstrip() + b"\n")
    return b"".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="compare without writing")
    args = parser.parse_args()
    bundle = build()
    if args.check:
        if not BUNDLE.is_file() or BUNDLE.read_bytes() != bundle:
            print(f"FAIL: {BUNDLE.relative_to(ROOT)} differs from the pinned components")
            return 1
        print("prism bundle matches the pinned components")
        return 0
    BUNDLE.write_bytes(bundle)
    print(f"wrote {BUNDLE.relative_to(ROOT)} ({len(bundle)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
