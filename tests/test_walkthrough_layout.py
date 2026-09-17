"""The example walkthroughs borrow the Explorer's layout without becoming a stepper.

* Each data step is followed by the statement step it produced, so the two can
  sit side by side, and both exhibits carry the digest they show.
* The step index is plain in-page anchors (it must work without JavaScript),
  every anchor resolves, and every step on the page is reachable from it.
* The page links to the Explorer from the top.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PAGES = ["examples/lifecycle/index.html", "examples/in-place/index.html"]


def steps(text: str) -> list[tuple[str, str]]:
    """(id, class) for every step in the walkthrough's setup sequence."""
    sequence = text.split('<ol class="setup-sequence is-paired">', 1)[1].split("\n  </ol>", 1)[0]
    return re.findall(r'\n  <li id="([^"]+)"(?: class="([^"]+)")?>', sequence)


@pytest.mark.parametrize("page", PAGES)
def test_data_steps_sit_beside_their_statements(page: str) -> None:
    text = (ROOT / page).read_text(encoding="utf-8")
    found = steps(text)
    roles = [cls for _, cls in found]
    assert roles.count("pair-data") == roles.count("pair-statement") == 3
    for index, role in enumerate(roles):
        if role == "pair-data":
            assert roles[index + 1] == "pair-statement", found[index]
        if role == "pair-statement":
            assert roles[index - 1] == "pair-data", found[index]
    digests = re.findall(r'<pre data-filename="[^"]+" data-digest="sha256:([0-9a-f]{64})">', text)
    assert len(digests) == 6
    for digest in digests:
        assert text.count(digest) > 1, f"exhibit digest {digest} is not stated on the page"


@pytest.mark.parametrize("page", PAGES)
def test_step_index_is_static_anchors_covering_every_step(page: str) -> None:
    text = (ROOT / page).read_text(encoding="utf-8")
    nav = re.search(r'<nav class="step-index"[^>]*data-step-index>(.*?)</nav>', text).group(1)
    targets = re.findall(r'<a class="explorer-stage" href="#([^"]+)"', nav)
    ids = [step_id for step_id, _ in steps(text)]
    assert targets and targets[0] == ids[0]
    for target in targets:
        assert f'id="{target}"' in text, target
    # Every index entry starts a solo step or a pair; nothing else is skipped.
    starts = [step_id for step_id, cls in steps(text) if cls != "pair-statement"]
    assert targets == starts
    assert text.index("data-step-index") < text.index('<ol class="setup-sequence')
    assert '<script defer src="/assets/steps.js"></script>' in text


@pytest.mark.parametrize("page", PAGES)
def test_links_to_the_explorer_from_the_top(page: str) -> None:
    text = (ROOT / page).read_text(encoding="utf-8")
    link = '<p class="explorer-jump"><a href="/explorer/">Step through this in the Explorer</a>'
    assert link in text
    assert text.index(link) < text.index("<figure")
