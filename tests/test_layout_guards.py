"""Static guards for presentation rules that have regressed before.

* Nothing scrolls sideways: no stylesheet in the repository, linked or not,
  and no inline <style> block may set overflow-x (or the overflow shorthand)
  to auto or scroll.
* No coloured side stripes: no border-left / border-inline-start wider than
  1px with a visible colour, and no inset box-shadow drawn as a vertical rail.
* JSON reads vertically: every JSON code block's default view, as laid out by
  assets/code.js, keeps every line within 100 characters and parses to the
  same value as the published bytes.
* Light by default: dark mode is reachable only through the theme toggle.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MAX_JSON_LINE = 100


def site_pages() -> list[Path]:
    return sorted(
        path
        for path in ROOT.rglob("*.html")
        if ".git" not in path.parts and "node_modules" not in path.parts
    )


def linked_stylesheets() -> dict[str, str]:
    """Every stylesheet a page links, plus every inline <style> block."""
    sheets: dict[str, str] = {}
    for page in site_pages():
        text = page.read_text(encoding="utf-8")
        for href in re.findall(r'<link[^>]+rel="stylesheet"[^>]+href="(/[^"]+)"', text):
            path = ROOT / href.lstrip("/")
            if path.is_file():
                sheets[href] = path.read_text(encoding="utf-8")
        for index, block in enumerate(re.findall(r"<style[^>]*>(.*?)</style>", text, re.DOTALL)):
            sheets[f"{page.relative_to(ROOT)}#style{index}"] = block
    return sheets


def all_stylesheets() -> dict[str, str]:
    """Every .css file in the repository plus every inline <style> block.

    Scanning unlinked files too means a stylesheet cannot slip past the guard
    today and reintroduce sideways scroll the day someone links it.
    """
    sheets = linked_stylesheets()
    for path in sorted(ROOT.rglob("*.css")):
        if {".git", ".venv", "node_modules"}.intersection(path.relative_to(ROOT).parts):
            continue
        sheets[f"/{path.relative_to(ROOT).as_posix()}"] = path.read_text(encoding="utf-8")
    return sheets


def rules(css: str) -> list[tuple[str, str]]:
    """(selector, declarations) for every innermost rule, @media included."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    return [
        (selector.strip(), body) for selector, body in re.findall(r"([^{}@;]+)\{([^{}]*)\}", css)
    ]


def declarations(body: str) -> list[tuple[str, str]]:
    out = []
    for item in body.split(";"):
        if ":" in item:
            name, value = item.split(":", 1)
            out.append((name.strip().lower(), value.strip().lower()))
    return out


def test_pages_load_at_least_one_stylesheet() -> None:
    assert "/assets/v02.css" in linked_stylesheets()


def test_sideways_scroll_guard_scans_unlinked_stylesheets() -> None:
    names = all_stylesheets()
    on_disk = {
        f"/{path.relative_to(ROOT).as_posix()}"
        for path in ROOT.rglob("*.css")
        if not {".git", ".venv", "node_modules"}.intersection(path.relative_to(ROOT).parts)
    }
    assert on_disk and on_disk <= set(names)


def test_no_stylesheet_scrolls_content_sideways() -> None:
    offenders = []
    for name, css in all_stylesheets().items():
        for selector, body in rules(css):
            for prop, value in declarations(body):
                if prop == "overflow-x" and re.search(r"\b(auto|scroll)\b", value):
                    offenders.append(f"{name}: {selector} {{{prop}: {value}}}")
                if prop == "overflow" and re.match(r"(auto|scroll)\b", value):
                    offenders.append(f"{name}: {selector} {{{prop}: {value}}}")
    assert offenders == []


TRANSPARENT = re.compile(r"\b(transparent|none|hidden)\b|rgba\([^)]*,\s*0\)")


def _width_px(value: str) -> float:
    match = re.search(r"(\d*\.?\d+)(px|rem|em)\b", value)
    if not match:
        return (
            1.0
            if re.search(r"\bthin\b", value)
            else (3.0 if re.search(r"\b(medium|thick)\b", value) else 0.0)
        )
    number, unit = float(match.group(1)), match.group(2)
    return number * (16 if unit in {"rem", "em"} else 1)


def test_no_coloured_side_stripe_accents() -> None:
    offenders = []
    for name, css in linked_stylesheets().items():
        for selector, body in rules(css):
            for prop, value in declarations(body):
                if (
                    prop in {"border-left", "border-inline-start"}
                    and _width_px(value) > 1
                    and not TRANSPARENT.search(value)
                ):
                    offenders.append(f"{name}: {selector} {{{prop}: {value}}}")
                if (
                    prop in {"border-left-width", "border-inline-start-width"}
                    and _width_px(value) > 1
                ):
                    offenders.append(f"{name}: {selector} {{{prop}: {value}}}")
                if prop == "box-shadow":
                    for shadow in re.split(r",(?![^(]*\))", value):
                        match = re.match(r"\s*inset\s+(-?\d*\.?\d+)px\s+0\s+0(\s|$)", shadow)
                        if match and abs(float(match.group(1))) >= 2:
                            offenders.append(f"{name}: {selector} {{box-shadow: {shadow.strip()}}}")
    assert offenders == []


def test_stripe_guard_catches_the_old_sidebar_rail() -> None:
    css = '.docs-nav a[aria-current="page"] { box-shadow: inset 2px 0 0 var(--seal); }\n.callout { border-left: 3px solid var(--seal); }'
    found = []
    for selector, body in rules(css):
        for prop, value in declarations(body):
            if prop == "border-left" and _width_px(value) > 1 and not TRANSPARENT.search(value):
                found.append(selector)
            if prop == "box-shadow" and re.match(r"\s*inset\s+2px\s+0\s+0", value):
                found.append(selector)
    assert found == ['.docs-nav a[aria-current="page"]', ".callout"]


def layout_json(text: str) -> str | None:
    """Mirror of layoutJson in assets/code.js: a lexical two-space re-indent."""
    try:
        json.loads(text)
    except ValueError:
        return None
    out: list[str] = []
    depth, i, n = 0, 0, len(text)

    def newline() -> None:
        out.append("\n" + "  " * depth)

    while i < n:
        ch = text[i]
        if ch == '"':
            j = i + 1
            while j < n:
                if text[j] == "\\":
                    j += 2
                    continue
                if text[j] == '"':
                    break
                j += 1
            out.append(text[i : j + 1])
            i = j + 1
        elif ch in "{[":
            k = i + 1
            while k < n and text[k].isspace():
                k += 1
            close = "}" if ch == "{" else "]"
            if k < n and text[k] == close:
                out.append(ch + close)
                i = k + 1
                continue
            out.append(ch)
            depth += 1
            newline()
            i += 1
        elif ch in "}]":
            depth -= 1
            newline()
            out.append(ch)
            i += 1
        elif ch == ",":
            out.append(",")
            newline()
            i += 1
        elif ch == ":":
            out.append(": ")
            i += 1
        elif ch.isspace():
            i += 1
        else:
            out.append(ch)
            i += 1
    return "".join(out)


JSON_BLOCK = re.compile(
    r'<pre[^>]*>\s*<code[^>]*class="[^"]*\blanguage-json\b[^"]*"[^>]*>(.*?)</code>\s*</pre>',
    re.DOTALL,
)


def json_blocks() -> list[tuple[str, str]]:
    blocks = []
    for page in site_pages():
        for match in JSON_BLOCK.finditer(page.read_text(encoding="utf-8")):
            text = html.unescape(re.sub(r"<[^>]+>", "", match.group(1)))
            blocks.append((str(page.relative_to(ROOT)), text))
    return blocks


def test_site_has_json_code_blocks() -> None:
    assert len(json_blocks()) > 50


STRING_LITERAL = re.compile(r'"(?:[^"\\]|\\.)*"')


def unsplittable(line: str) -> bool:
    """A line over the limit only because one string literal is long.

    JSON strings cannot span lines without changing their value, so a single
    member such as a base64 payload stays on one source line and the frame
    wraps it visually. Anything else wider than the limit could be split.
    """
    literals = STRING_LITERAL.findall(line)
    if len(literals) > 2:
        return False
    skeleton = STRING_LITERAL.sub('""', line)
    longest = max((len(item) for item in literals), default=0)
    return len(skeleton) <= MAX_JSON_LINE and len(line) - longest + 2 <= MAX_JSON_LINE


def test_json_blocks_render_vertically_within_100_columns() -> None:
    offenders = []
    for page, original in json_blocks():
        shown = layout_json(original)
        view = original if shown is None else shown
        for line in view.split("\n"):
            if len(line) > MAX_JSON_LINE and not unsplittable(line):
                offenders.append(f"{page}: {len(line)} columns: {line.strip()[:60]!r}")
    assert offenders == []


def test_json_width_guard_rejects_a_minified_line() -> None:
    minified = '[{"age":34,"customer_id":"C-1001","email":" Alice@Example.COM ","marketing_consent":" YES ","region":"us"}]'
    assert len(minified) > MAX_JSON_LINE and not unsplittable(minified)
    assert unsplittable('  "payload": "' + "A" * 400 + '"')


def test_json_layout_preserves_the_parsed_value() -> None:
    for page, original in json_blocks():
        shown = layout_json(original)
        if shown is not None:
            assert json.loads(shown) == json.loads(original), page


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ('{"a":1,"b":[]}', '{\n  "a": 1,\n  "b": []\n}'),
        ('[{"s":"x,y:{z}"}]', '[\n  {\n    "s": "x,y:{z}"\n  }\n]'),
        ('{"n":1.50e+3,"q":"\\"}"}', '{\n  "n": 1.50e+3,\n  "q": "\\"}"\n}'),
        ("not json", None),
    ],
)
def test_json_layout_copies_literals_verbatim(source: str, expected: str | None) -> None:
    assert layout_json(source) == expected


def test_light_is_the_default_and_dark_is_opt_in() -> None:
    css = (ROOT / "assets/v02.css").read_text(encoding="utf-8")
    assert "prefers-color-scheme: dark" not in css
    assert ':root[data-theme="dark"]' in css
    script = (ROOT / "assets/theme.js").read_text(encoding="utf-8")
    assert "prefers-color-scheme" not in script
    assert "localStorage" in script and "catch" in script


def test_every_styled_page_sets_the_theme_before_first_paint() -> None:
    link = '<link rel="stylesheet" href="/assets/v02.css">'
    missing = []
    for page in site_pages():
        text = page.read_text(encoding="utf-8")
        if link not in text:
            continue
        head = text.split("</head>", 1)[0]
        after = head.split(link, 1)[1]
        if not re.match(r'\s*<script src="/assets/theme.js"></script>', after):
            missing.append(str(page.relative_to(ROOT)))
    assert missing == []
