"""Fail a pull request whose corpus manifests and lineage records disagree.

Every leaf directory with a `makoto/` lineage record is checked twice:

1. If the pull request changed a file the record hands off (the leaf manifest)
   but changed nothing under that record, the contributor edited the corpus
   without re-running the ingest that updates its lineage.
2. `makoto verify bundle` must allow the record under the repository's own
   policy, with the handed-off file's current bytes as the expected artifact.
   A stale, hand-edited or wrongly signed record is denied.

Usage, from the repository root:

    uv run --no-project lineage/check_lineage.py --base origin/main

Requires Git and the `makoto` command on PATH. Standard library only.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

POLICY = Path("lineage/policy.json")
CATALOG = Path("lineage/catalog.json")


def changed_files(base: str) -> set[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return {line for line in result.stdout.splitlines() if line}


def handed_off(record: Path) -> list[dict]:
    """The artifacts the record's signed handoff names, read from its payload."""
    envelope = json.loads((record / "manifest.dsse.json").read_bytes())
    return json.loads(base64.b64decode(envelope["payload"]))["artifacts"]


def verify(record: Path, artifacts: list[dict]) -> tuple[str, list[str]]:
    with tempfile.TemporaryDirectory() as scratch:
        command = [
            "makoto", "verify", "bundle", str(record),
            "--policy", str(POLICY),
            "--schema-catalog", str(CATALOG),
            "--json",
        ]  # fmt: skip
        for index, artifact in enumerate(artifacts):
            current = record.parent / artifact["name"]
            data = current.read_bytes() if current.is_file() else b""
            digest = hashlib.sha256(data).hexdigest()
            binding = Path(scratch) / f"expected-{index}.json"
            binding.write_text(
                json.dumps(
                    {
                        "head": artifact["head"],
                        "subjectName": artifact["name"],
                        "digest": {"sha256": digest},
                    }
                )
            )
            command += ["--expected-artifact", str(binding)]
        result = subprocess.run(command, check=False, capture_output=True, text=True)
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError:
        return "error", [result.stderr.strip() or f"makoto exited {result.returncode}"]
    codes = sorted({item["code"] for item in report.get("errors", [])})
    return report["decision"], codes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", required=True, help="Git ref the pull request targets")
    args = parser.parse_args()
    changed = changed_files(args.base)
    failures = 0
    for bundle_index in sorted(Path(".").glob("**/makoto/bundle.json")):
        record = bundle_index.parent
        artifacts = handed_off(record)
        record_changed = any(path.startswith(f"{record.as_posix()}/") for path in changed)
        for artifact in artifacts:
            name = (record.parent / artifact["name"]).as_posix()
            if name in changed and not record_changed:
                print(f"FAIL {name} changed but {record.as_posix()}/ did not")
                print("     re-run the ingest so the lineage record describes the new bytes")
                failures += 1
        decision, codes = verify(record, artifacts)
        if decision == "allow":
            print(f"PASS {record.as_posix()} verifies against the current files")
        else:
            print(f"FAIL {record.as_posix()} {decision}: {', '.join(codes)}")
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
