"""Fail a pull request whose corpus manifests and lineage records disagree.

The policy and schema catalog come from the base commit, never from the pull
request, so a contribution cannot authorize its own key. A policy change is a
separate pull request that merges first.

Every leaf directory (one holding an `ingest.yaml`) must have a `makoto/`
lineage record, and every record is checked three ways:

1. If the pull request changed a file the record hands off (the leaf manifest)
   but changed nothing under that record, the contributor edited the corpus
   without re-running the ingest that updates its lineage.
2. `makoto verify bundle` must allow the record under the base policy, with the
   handed-off file's current bytes as the expected artifact. A stale,
   hand-edited or wrongly signed record is denied.
3. Once the record verifies, the ingest statement's `parametersDigest` must
   match the `ingest.yaml` in the pull request.

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

POLICY = "lineage/policy.json"
CATALOG = "lineage/catalog.json"
SKIPPED = {".git", ".venv", "node_modules"}


def git(*arguments: str) -> bytes:
    return subprocess.run(["git", *arguments], check=True, capture_output=True).stdout


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def decode(envelope: Path) -> dict:
    return json.loads(base64.b64decode(json.loads(envelope.read_bytes())["payload"]))


def directories_holding(pattern: str) -> list[Path]:
    return sorted(
        path.parent for path in Path(".").glob(f"**/{pattern}") if not SKIPPED & set(path.parts)
    )


def base_config(base: str, scratch: Path) -> tuple[Path, Path]:
    """The base commit's policy and catalog, with every schema the catalog names."""
    names = [POLICY, CATALOG]
    catalog = json.loads(git("show", f"{base}:{CATALOG}"))
    names += [f"{Path(CATALOG).parent.as_posix()}/{item['path']}" for item in catalog["resources"]]
    for name in names:
        target = scratch / "base" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(git("show", f"{base}:{name}"))
    return scratch / "base" / POLICY, scratch / "base" / CATALOG


def verify(record: Path, artifacts: list[dict], config: tuple[Path, Path], scratch: Path):
    policy, catalog = config
    command = [
        "makoto", "verify", "bundle", str(record),
        "--policy", str(policy),
        "--schema-catalog", str(catalog),
        "--json",
    ]  # fmt: skip
    for index, artifact in enumerate(artifacts):
        current = record.parent / artifact["name"]
        data = current.read_bytes() if current.is_file() else b""
        binding = scratch / f"expected-{sha256(str(record).encode())[:12]}-{index}.json"
        binding.write_text(
            json.dumps(
                {
                    "head": artifact["head"],
                    "subjectName": artifact["name"],
                    "digest": {"sha256": sha256(data)},
                }
            )
        )
        command += ["--expected-artifact", str(binding)]
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError:
        return "error", [result.stderr.strip() or f"makoto exited {result.returncode}"]
    return report["decision"], sorted({item["code"] for item in report.get("errors", [])})


def pinned_parameters(record: Path) -> set[str]:
    """The parametersDigest of each head statement, read after the record verified."""
    index = json.loads((record / "bundle.json").read_bytes())
    paths = {item["statementDigest"]["sha256"]: item["path"] for item in index["attestations"]}
    pinned = set()
    for head in decode(record / "manifest.dsse.json")["heads"]:
        operation = decode(record / paths[head["sha256"]])["predicate"].get("operation", {})
        pinned.add(operation.get("parametersDigest", {}).get("sha256", ""))
    return pinned


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", required=True, help="Git ref the pull request targets")
    args = parser.parse_args()
    changed = set(git("diff", "--name-only", f"{args.base}...HEAD").decode().splitlines())
    failures = 0
    for leaf in directories_holding("ingest.yaml"):
        if not (leaf / "makoto/bundle.json").is_file():
            print(f"FAIL {leaf.as_posix()}/ has ingest.yaml but no makoto/ lineage record")
            failures += 1
    with tempfile.TemporaryDirectory() as scratch_name:
        scratch = Path(scratch_name)
        config = base_config(args.base, scratch)
        for record in directories_holding("makoto/bundle.json"):
            # Read only to learn which files to expect; the verifier checks the signature.
            artifacts = decode(record / "manifest.dsse.json")["artifacts"]
            record_changed = any(path.startswith(f"{record.as_posix()}/") for path in changed)
            for artifact in artifacts:
                name = (record.parent / artifact["name"]).as_posix()
                if name in changed and not record_changed:
                    print(f"FAIL {name} changed but {record.as_posix()}/ did not")
                    print("     re-run the ingest so the lineage record describes the new bytes")
                    failures += 1
            decision, codes = verify(record, artifacts, config, scratch)
            if decision != "allow":
                print(f"FAIL {record.as_posix()} {decision}: {', '.join(codes)}")
                failures += 1
                continue
            parameters = record.parent / "ingest.yaml"
            if parameters.is_file() and sha256(parameters.read_bytes()) not in pinned_parameters(
                record
            ):
                print(f"FAIL {parameters.as_posix()} differs from the parameters the record pins")
                failures += 1
                continue
            print(f"PASS {record.as_posix()} verifies against the current files")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
