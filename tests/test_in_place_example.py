"""The in-place walkthrough shows exactly what scripts/in_place_example.py generates."""

from __future__ import annotations

import hashlib
import html
import json
import re
from itertools import pairwise
from pathlib import Path

from scripts import in_place_example

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "examples/in-place/index.html"


def page_text() -> str:
    return html.unescape(PAGE.read_text(encoding="utf-8"))


def test_committed_files_match_a_fresh_run() -> None:
    outputs = in_place_example.build()
    in_place_example.validate(outputs)
    assert outputs, "the generator produced nothing"
    for path, data in outputs.items():
        assert path.read_bytes() == data, f"stale generated file: {path.relative_to(ROOT)}"


def test_every_state_digest_changes_and_chains() -> None:
    outputs = in_place_example.build()
    statements = [
        json.loads(data)
        for path, data in outputs.items()
        if path.suffix == ".json" and path.parent.name == "attestations"
    ]
    subjects = [s["subject"][0]["digest"]["sha256"] for s in statements]
    assert len(set(subjects)) == len(subjects) == 3
    names = {s["subject"][0]["name"] for s in statements}
    assert names == {in_place_example.SUBJECT_NAME}
    for previous, current in pairwise(statements):
        (link,) = current["predicate"]["inputs"]
        assert link["digest"]["sha256"] == previous["subject"][0]["digest"]["sha256"]
        assert link["provenance"]["statementDigest"]["sha256"] == (
            in_place_example.statement_digest(previous)
        )


def test_page_shows_generated_bytes_verbatim() -> None:
    text = page_text()
    for path, data in in_place_example.build().items():
        if path.parent.name == "states":
            assert data.decode().rstrip("\n") in text, path.name
            assert hashlib.sha256(data).hexdigest() in text, path.name
        else:
            assert data.decode().rstrip("\n") in text, path.name
            digest = in_place_example.statement_digest(json.loads(data))
            assert digest in text, path.name
    sql = ROOT / "examples/in-place/sql"
    for path in sorted(sql.glob("*.sql")):
        assert path.read_text(encoding="utf-8").rstrip("\n") in text, path.name
    # The digests a reader is asked to reproduce: both edit commands and the export.
    for name in ("02-normalize.sql", "03-withdraw-minor-consent.sql", "export.sql"):
        assert hashlib.sha256((sql / name).read_bytes()).hexdigest() in text, name


def test_walkthroughs_link_each_other() -> None:
    lifecycle = (ROOT / "examples/lifecycle/index.html").read_text(encoding="utf-8")
    index = (ROOT / "examples/index.html").read_text(encoding="utf-8")
    page = PAGE.read_text(encoding="utf-8")
    assert 'href="/examples/in-place/"' in lifecycle
    assert 'href="/examples/in-place/"' in index
    assert 'href="/examples/lifecycle/"' in page
    assert 'href="/examples/"' in page
    assert "overwrite-panel" not in lifecycle


def test_figure_is_drawn_and_decorative() -> None:
    page = PAGE.read_text(encoding="utf-8")
    assert 'data-flow="inplace"' in page
    assert '<script defer src="/assets/flow.js"></script>' in page
    assert re.search(r'class="ip-rows" aria-hidden="true"', page)
    css = (ROOT / "assets/v02.css").read_text(encoding="utf-8")
    motion = css.split("@media (prefers-reduced-motion: no-preference)", 1)[1]
    assert "ip-peel" in motion.split("@media", 1)[0], "in-place motion must be opt-in"
