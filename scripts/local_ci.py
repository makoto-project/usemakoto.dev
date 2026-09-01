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
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE_URL = "https://github.com/makoto-project/makoto"
USES_PATTERN = re.compile(
    r"^\s*-?\s*uses:\s*([\w.-]+/[\w.-]+)@(\S+)(?:[ \t]*#[ \t]*(\S+))?", re.MULTILINE
)
SHA_PATTERN = re.compile(r"[0-9a-f]{40}")


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


def _remote_tag_shas(remote: str, tag: str) -> set[str]:
    """Every SHA that `tag` names on `remote`: the tag object and its commit."""
    result = subprocess.run(
        ["git", "ls-remote", "--tags", remote, f"refs/tags/{tag}", f"refs/tags/{tag}^{{}}"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return set()
    return {line.split()[0] for line in result.stdout.splitlines() if line.strip()}


def check_action_refs() -> list[str]:
    """Confirm every `uses:` reference in every workflow points where it claims.

    Two failures are only visible here. A tag that does not exist fails the
    hosted run before any project code executes, and nothing in the checkout
    can catch it because GitHub resolves the reference — not every project
    publishes a floating major tag, so `@v10` can be unresolvable while
    `v10.0.1` is real. And a digest pin carries its human-readable version in a
    trailing comment, which nothing enforces: the comment can say v4.1.0 while
    the digest is something else entirely.
    """
    problems: list[str] = []
    seen: set[tuple[str, str]] = set()
    for workflow in sorted((ROOT / ".github/workflows").glob("*.y*ml")):
        for action, ref, comment in USES_PATTERN.findall(workflow.read_text()):
            if (action, ref) in seen:
                continue
            seen.add((action, ref))
            remote = f"https://github.com/{action}"
            claimed = comment.strip() if comment else ""

            if SHA_PATTERN.fullmatch(ref):
                if not claimed:
                    continue  # a digest with no version claim is already immutable
                shas = _remote_tag_shas(remote, claimed)
                if not shas:
                    problems.append(f"{workflow.name}: {action} claims {claimed}, which does not exist")
                elif ref not in shas:
                    problems.append(
                        f"{workflow.name}: {action}@{ref[:12]} is not {claimed} "
                        f"(that tag is {min(shas)[:12]})"
                    )
                continue

            result = subprocess.run(
                ["git", "ls-remote", "--tags", "--heads", remote, ref, f"refs/tags/{ref}"],
                check=False,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0 or not result.stdout.strip():
                problems.append(f"{workflow.name}: {action}@{ref} does not resolve")
    return problems


def find_actionlint() -> str | None:
    """Locate actionlint, tolerating a PATH that omits the Homebrew prefix.

    A silent skip is the worst outcome here: it reads as "checked and fine"
    when nothing ran. Restricted shells routinely drop /opt/homebrew/bin.
    """
    located = shutil.which("actionlint")
    if located:
        return located
    for candidate in ("/opt/homebrew/bin/actionlint", "/usr/local/bin/actionlint"):
        if Path(candidate).is_file():
            return candidate
    return None


def check_actionlint() -> tuple[str, str]:
    """Run actionlint over the workflows. Returns (status, detail)."""
    binary = find_actionlint()
    if binary is None:
        return "skip", "actionlint is not installed (brew install actionlint)"
    result = subprocess.run(
        [binary], cwd=ROOT, check=False, capture_output=True, text=True
    )
    if result.returncode == 0:
        return "pass", "workflows lint clean"
    return "fail", ((result.stdout or "") + (result.stderr or "")).strip()


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

    print("\nlocal-ci: workflow lint")
    lint_status, lint_detail = check_actionlint()
    print(f"  {lint_status}: {lint_detail}")

    print("\nlocal-ci: workflow action references")
    problems = check_action_refs()
    for problem in problems:
        print(f"  {problem}")
    if not problems:
        print("  every uses: reference resolves and matches its version comment")

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

    failed = ["workflow lint"] if lint_status == "fail" else []
    failed += ["workflow action references"] if problems else []
    failed += [name for name, argv in checks if not step(name, argv)]
    if failed:
        print(f"\nlocal-ci: FAILED: {', '.join(failed)}")
        return 1
    print(f"\nlocal-ci: all {len(checks) + 2} checks passed against core {commit[:12]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
