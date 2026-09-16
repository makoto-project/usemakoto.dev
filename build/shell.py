"""Replace only the inner content of <main>, keeping each page's shell verbatim.

The redesign's shell (head, topbar, mobile menu, docs sidebar, footer) is the
keeper. Restoring substance means rewriting <main> and nothing else, so the
three post-redesign design fixes and the shared nav link sets stay untouched.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAIN_OPEN = re.compile(r'(<main\b[^>]*>)', re.I)
MAIN_CLOSE = re.compile(r'(</main>)', re.I)


def split(path):
    text = (ROOT / path).read_text(encoding="utf-8")
    om = MAIN_OPEN.search(text)
    cm = MAIN_CLOSE.search(text, om.end())
    return text[:om.end()], text[cm.start():]


def write(path, body, head_edits=None):
    prefix, suffix = split(path)
    if head_edits:
        for old, new in head_edits:
            assert old in prefix, f"{path}: missing {old[:60]!r}"
            prefix = prefix.replace(old, new, 1)
    (ROOT / path).write_text(prefix + "\n" + body.strip() + "\n" + suffix,
                             encoding="utf-8")


def clone(src, dest, edits):
    """Create a new page from a sibling's shell (for verify/typescript.html)."""
    text = (ROOT / src).read_text(encoding="utf-8")
    for old, new in edits:
        assert old in text, f"{src}->{dest}: missing {old[:60]!r}"
        text = text.replace(old, new)
    out = ROOT / dest
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
