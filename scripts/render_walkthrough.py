#!/usr/bin/env python3
"""Render the checked demo projections as readable JSON on the walkthrough page."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "demos/v0.2-end-to-end/index.html"
ARTIFACTS = ROOT / "demos/v0.2-end-to-end/artifacts/walkthrough"
START = "<!-- GENERATED WALKTHROUGH START -->"
END = "<!-- GENERATED WALKTHROUGH END -->"

SCENES = (
    (
        "00",
        "The receiver's rule",
        "One JSON Schema for the final dataset",
        (
            "This private profile rejects direct identifiers, fixes allowed fields, and constrains "
            "their types and lengths. The full proof also uses a separate metadata profile for the "
            "privacy transformation."
        ),
        "00-customer-public.schema.json",
    ),
    (
        "01",
        "Begin at the source",
        "Bind the origin claim to exact bytes",
        (
            "The first statement names the source and hashes customers.raw.json before anything "
            "changes."
        ),
        "01-origin.statement.json",
    ),
    (
        "02",
        "First change",
        "Normalize the customer records",
        (
            "The new statement points to the origin statement and raw artifact, then hashes the "
            "normalized output. Nothing edits the origin in place."
        ),
        "02-normalize.statement.json",
    ),
    (
        "03",
        "Second change",
        "Remove direct identifiers and bucket ages",
        (
            "The next statement points to the normalized predecessor, records the operation, and "
            "pins both the metadata rule and final-data rule by digest."
        ),
        "03-public-safe.statement.json",
    ),
    (
        "04",
        "Summary record",
        "Commit to the complete handoff",
        (
            "This decoded payload is the signed handoff manifest: the only normative summary. It "
            "commits to the root, head, complete statement set, recipient, and final artifact."
        ),
        "04-handoff.json",
    ),
    (
        "05",
        "Who attested",
        "Interpret keys through receiver policy",
        (
            "Key IDs are not identities by themselves. This teaching view joins each signed "
            "envelope to the labels and roles authorized by the receiver's policy."
        ),
        "05-attesters.json",
    ),
    (
        "06",
        "Receiver test",
        "Validate the history, rules, signatures, and bytes",
        (
            "The verifier separately passes core schemas, private profiles, signatures, "
            "authorization, graph continuity, completeness, freshness anchors, and the final data "
            "digest before returning allow."
        ),
        "06-verification-summary.json",
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if the rendered block is stale")
    return parser.parse_args()


def pretty_json(path: Path) -> str:
    value = json.loads(path.read_bytes())
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def render() -> str:
    items = []
    for number, eyebrow, title, description, name in SCENES:
        source = ARTIFACTS / name
        if not source.is_file():
            raise FileNotFoundError(f"walkthrough artifact is absent: {source.relative_to(ROOT)}")
        code = html.escape(pretty_json(source))
        href = f"artifacts/walkthrough/{name}"
        items.append(
            '<li class="evidence-step">'
            f'<div class="evidence-step-copy"><span>{number}</span><div>'
            f'<p class="evidence-step-eyebrow">{html.escape(eyebrow)}</p>'
            f"<h3>{html.escape(title)}</h3><p>{html.escape(description)}</p>"
            f'<a href="{href}">Open the exact JSON</a></div></div>'
            f'<pre class="walkthrough-json"><code class="language-json" '
            f'data-walkthrough-file="{html.escape(name, quote=True)}">{code}</code></pre>'
            "</li>"
        )
    return f'{START}\n<ol class="evidence-sequence">{"".join(items)}</ol>\n{END}'


def update(*, check: bool) -> bool:
    source = PAGE.read_text(encoding="utf-8")
    if source.count(START) != 1 or source.count(END) != 1:
        raise ValueError("walkthrough page must contain one generated-block marker pair")
    before, remainder = source.split(START, 1)
    _, after = remainder.split(END, 1)
    rendered = f"{before}{render()}{after}"
    if rendered == source:
        return False
    if check:
        raise SystemExit("rendered walkthrough block is stale")
    PAGE.write_text(rendered, encoding="utf-8")
    return True


def main() -> int:
    args = parse_args()
    changed = update(check=args.check)
    print("walkthrough block " + ("updated" if changed else "is current"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
