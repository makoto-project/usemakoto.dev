#!/usr/bin/env python3
"""Run the deploy workflow's validate job locally, against the pinned core commit.

The hosted workflow checks this repository out beside `makoto-project/makoto` at
the exact commit named by the candidate or release pin, then runs lint, tests,
and the site gate against that pair. This script reproduces that locally so a
push confirms a result instead of discovering one.

    uv run scripts/local_ci.py            # same checks as the validate job
    uv run scripts/local_ci.py --probe    # also verify the deployed site

The core checkout is a sibling directory (`../core` by default), which is the
layout `README.md` documents and the test suite expects. It is created on first
run and moved to the pinned commit on every run.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE_URL = "https://github.com/makoto-project/makoto"


def fail(message: str) -> int:
    print(f"local-ci: {message}", file=sys.stderr)
    return 1


def read_pin() -> tuple[str, str]:
    """Return (mode, commit) for the single candidate or release pin."""
    candidate = ROOT / "schema/core-candidate.json"
    release = ROOT / "schema/core-release.json"
    if candidate.is_file() and release.is_file():
        raise ValueError("candidate and release pins cannot coexist")
    pin_path = candidate if candidate.is_file() else release
    if not pin_path.is_file():
        raise ValueError("no candidate or release pin found under schema/")
    mode = "candidate" if pin_path == candidate else "release"
    return mode, json.loads(pin_path.read_text())["commit"]


def git(*arguments: str, cwd: Path) -> str:
    result = subprocess.run(
        ["git", *arguments], cwd=cwd, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def sync_core(core: Path, commit: str) -> None:
    """Put `core` at exactly `commit`, cloning it first if necessary."""
    if not (core / ".git").is_dir():
        print(f"local-ci: cloning {CORE_URL} into {core}")
        subprocess.run(
            ["git", "clone", "--quiet", CORE_URL, str(core)], check=True
        )
    if git("rev-parse", "HEAD", cwd=core) != commit:
        if git("status", "--porcelain", cwd=core):
            raise ValueError(f"core checkout has local changes: {core}")
        subprocess.run(
            ["git", "fetch", "--quiet", "--tags", "origin"], cwd=core, check=True
        )
        subprocess.run(
            ["git", "checkout", "--quiet", commit], cwd=core, check=True
        )
    print(f"local-ci: core at {git('rev-parse', 'HEAD', cwd=core)}")


def step(name: str, argv: list[str]) -> bool:
    print(f"\nlocal-ci: {name}")
    return subprocess.run(argv, cwd=ROOT, check=False).returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--core-repo",
        type=Path,
        default=ROOT.parent / "core",
        help="sibling checkout of makoto-project/makoto (default: ../core)",
    )
    parser.add_argument(
        "--probe",
        action="store_true",
        help="also verify that the deployed site serves the pinned bytes",
    )
    args = parser.parse_args()

    try:
        mode, commit = read_pin()
        core = args.core_repo.resolve()
        sync_core(core, commit)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        return fail(str(error))

    checks = [
        ("uv sync --locked --dev", ["uv", "sync", "--locked", "--dev"]),
        ("ruff check scripts tests", ["uv", "run", "ruff", "check", "scripts", "tests"]),
        ("pytest", ["uv", "run", "pytest", "-q"]),
        (
            f"check_site --{mode}",
            ["uv", "run", "scripts/check_site.py", f"--{mode}", "--core-repo", str(core)],
        ),
    ]
    if args.probe:
        checks.append(
            (
                f"probe_hosted --{mode}",
                ["uv", "run", "scripts/probe_hosted.py", f"--{mode}"],
            )
        )

    failed = [name for name, argv in checks if not step(name, argv)]
    if failed:
        print(f"\nlocal-ci: FAILED: {', '.join(failed)}")
        return 1
    print(f"\nlocal-ci: all {len(checks)} checks passed against core {commit[:12]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
