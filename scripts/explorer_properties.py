"""Write explorer/properties.json: the verified properties each published report supports.

The explorer never re-implements Makoto's rules in the browser. This script
applies core's own property rules to every published end-to-end report and the
policy whose digest that report records, and the explorer only displays the
result. Run it with the pinned core checkout's environment:

    uv run --project ../core python scripts/explorer_properties.py
    uv run --project ../core python scripts/explorer_properties.py --check
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from makoto.assurance import (
    _authorized,
    _freshness_anchored,
    _graph_complete,
    _schema_conformant,
)
from makoto.policy import TrustPolicy

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "demos/end-to-end/artifacts"
OUTPUT = ROOT / "explorer/properties.json"
# The unauthorized-signer report was verified against the policy that knows the
# attacker's key but authorizes it for nothing.
POLICIES = {"unauthorized-signer": "receiver/attacker-known-policy.json"}
REPORTS = (
    "positive",
    "mutated-final-data",
    "removed-predecessor",
    "rewired-step",
    "unauthorized-signer",
    "edited-signed-metadata",
    "statement-digest-mismatch",
    "private-schema-violation",
)


def properties(name: str, core: Path) -> dict[str, bool]:
    report = json.loads((ARTIFACTS / f"reports/{name}.json").read_text(encoding="utf-8"))
    policy = TrustPolicy.from_path(
        ARTIFACTS / POLICIES.get(name, "receiver/policy.json"), repository_root=core
    )
    if report["policyDigest"] != policy.digest():
        raise SystemExit(f"{name}: report policy digest does not match the policy")
    checks = {item["id"]: item["status"] for item in report["checks"]}
    return {
        "MAKOTO_AUTHORIZED": _authorized(report, checks),
        "MAKOTO_GRAPH_COMPLETE": _graph_complete(checks),
        "MAKOTO_FRESHNESS_ANCHORED": _freshness_anchored(report, checks),
        "MAKOTO_SCHEMA_CONFORMANT": _schema_conformant(report, policy, checks),
        # Needs a second allow report from an independent platform; none is published.
        "MAKOTO_REPRODUCED": False,
    }


def render(core: Path) -> bytes:
    value = {name: properties(name, core) for name in REPORTS}
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--core-repo", type=Path, default=ROOT.parent / "core")
    args = parser.parse_args()
    data = render(args.core_repo.resolve())
    if args.check:
        if not OUTPUT.is_file() or OUTPUT.read_bytes() != data:
            print(f"{OUTPUT.relative_to(ROOT)} is stale; rerun without --check", file=sys.stderr)
            return 1
        print("explorer properties are current")
        return 0
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(data)
    print(f"wrote {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
