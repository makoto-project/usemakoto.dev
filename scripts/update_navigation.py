#!/usr/bin/env python3
"""Render one canonical navigation shell into every substantive HTML page."""

from __future__ import annotations

import argparse
import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PRIMARY = (
    ("Examples", "/examples/", False),
    ("Specification", "/spec/", False),
    ("Tooling & SDKs", "/tooling/", False),
    ("Integrations", "/integrations/", False),
    ("Community", "/community/", False),
    ("GitHub ↗", "https://github.com/makoto-project/makoto", True),
)

GROUPS = (
    (
        "Start",
        (
            ("Overview", "/", False),
            ("Why lineage matters", "/why-lineage/", False),
            ("Specification", "/spec/", False),
            ("Runnable proof", "/demos/v0.2-end-to-end/", False),
        ),
    ),
    (
        "Learn",
        (
            ("Real-world examples", "/examples/", False),
            ("Assurance model", "/levels/", False),
            ("Threat model", "/threats/", False),
            ("Comparisons", "/comparison/", False),
            ("Demos", "/demos/", False),
        ),
    ),
    (
        "Build",
        (
            ("Hosted schemas", "/schema/v0.2/catalog.json", False),
            ("Verification", "/verify/", False),
            ("Origin predicate", "/predicate/v0.2/origin/", False),
            ("Transform predicate", "/predicate/v0.2/transform/", False),
            ("File source kind", "/source/file/", False),
            ("Bounded-pattern vocabulary", "/vocab/v0.2/bounded-pattern/", False),
            ("Tooling & SDKs", "/tooling/", False),
            ("Integrations", "/integrations/", False),
        ),
    ),
    (
        "Community",
        (
            ("Get involved", "/community/", False),
            ("GitHub repository ↗", "https://github.com/makoto-project/makoto", True),
            ("Issues ↗", "https://github.com/makoto-project/makoto/issues", True),
        ),
    ),
)

TOPBAR_PATTERN = re.compile(r'<nav class="nav" aria-label="Primary">.*?</nav>', re.DOTALL)
MOBILE_PATTERN = re.compile(r'<details class="mobile-menu">.*?</details>', re.DOTALL)
SIDEBAR_PATTERN = re.compile(
    r'<aside class="docs-sidebar" aria-label="Documentation">.*?</aside>', re.DOTALL
)
NAV_SCRIPT = '<script src="/assets/nav.js" defer></script>'


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if any shell is not canonical")
    return parser.parse_args()


def route_for(path: Path) -> str:
    relative = path.relative_to(ROOT).as_posix()
    if relative == "index.html":
        return "/"
    if relative.endswith("/index.html"):
        return f"/{relative.removesuffix('index.html')}"
    return f"/{relative}"


def owner_for(route: str) -> str:
    exact = {
        "/": "/",
        "/why-lineage/": "/why-lineage/",
        "/demos/v0.2-end-to-end/": "/demos/v0.2-end-to-end/",
        "/levels/": "/levels/",
        "/threats/": "/threats/",
        "/comparison/": "/comparison/",
        "/predicate/v0.2/origin/": "/predicate/v0.2/origin/",
        "/predicate/v0.2/transform/": "/predicate/v0.2/transform/",
        "/source/file/": "/source/file/",
        "/vocab/v0.2/bounded-pattern/": "/vocab/v0.2/bounded-pattern/",
        "/tooling/": "/tooling/",
        "/integrations/": "/integrations/",
        "/examples/": "/examples/",
        "/verify/": "/verify/",
        "/spec/": "/spec/",
        "/community/": "/community/",
    }
    if route in exact:
        return exact[route]
    prefixes = (
        ("/integrations/", "/integrations/"),
        ("/examples/", "/examples/"),
        ("/demos/", "/demos/"),
        ("/verify/", "/verify/"),
        ("/sdk/", "/tooling/"),
        ("/validate/", "/verify/"),
        ("/privacy/", "/threats/"),
        ("/spec/", "/spec/"),
    )
    for prefix, owner in prefixes:
        if route.startswith(prefix):
            return owner
    raise ValueError(f"no canonical navigation owner for {route}")


def link(label: str, href: str, external: bool, current: str, *, sidebar: bool) -> str:
    attributes = [f'href="{html.escape(href, quote=True)}"']
    if external and sidebar:
        attributes.insert(0, 'class="external"')
    if href == current:
        attributes.append('aria-current="page"')
    return f"<a {' '.join(attributes)}>{html.escape(label)}</a>"


def primary(current: str) -> str:
    links = "".join(link(*item, current, sidebar=False) for item in PRIMARY)
    return f'<nav class="nav" aria-label="Primary">{links}</nav>'


def mobile(current: str) -> str:
    groups = []
    for title, items in GROUPS:
        links = "".join(link(*item, current, sidebar=False) for item in items)
        groups.append(f'<p class="mobile-section">{html.escape(title)}</p>{links}')
    return (
        '<details class="mobile-menu"><summary>Menu</summary>'
        f'<nav aria-label="Mobile">{"".join(groups)}</nav></details>'
    )


def sidebar(current: str) -> str:
    groups = []
    for title, items in GROUPS:
        links = "".join(link(*item, current, sidebar=True) for item in items)
        groups.append(
            '<div class="docs-nav-group">'
            f'<p class="docs-nav-title">{html.escape(title)}</p>{links}</div>'
        )
    return (
        '<aside class="docs-sidebar" aria-label="Documentation">'
        f'<nav class="docs-nav">{"".join(groups)}</nav></aside>'
    )


def render(path: Path, source: str) -> str:
    current = owner_for(route_for(path))
    result, topbar_count = TOPBAR_PATTERN.subn(primary(current), source)
    result, mobile_count = MOBILE_PATTERN.subn(mobile(current), result)
    result, sidebar_count = SIDEBAR_PATTERN.subn(sidebar(current), result)
    if (topbar_count, mobile_count, sidebar_count) != (1, 1, 1):
        raise ValueError(
            f"{path.relative_to(ROOT)} has invalid shell counts "
            f"primary={topbar_count} mobile={mobile_count} sidebar={sidebar_count}"
        )
    if NAV_SCRIPT not in result:
        if result.count("</head>") != 1:
            raise ValueError(f"{path.relative_to(ROOT)} has no unique closing head")
        result = result.replace("</head>", f"{NAV_SCRIPT}</head>")
    return result


def shell_pages() -> tuple[Path, ...]:
    pages = []
    for path in sorted(ROOT.rglob("*.html")):
        source = path.read_text(encoding="utf-8")
        markers = (
            'class="nav" aria-label="Primary"' in source,
            'class="mobile-menu"' in source,
            'class="docs-sidebar"' in source,
        )
        if any(markers):
            if not all(markers):
                raise ValueError(f"{path.relative_to(ROOT)} has a partial navigation shell")
            pages.append(path)
    return tuple(pages)


def main() -> int:
    args = parse_args()
    changed = []
    for path in shell_pages():
        source = path.read_text(encoding="utf-8")
        rendered = render(path, source)
        if rendered == source:
            continue
        changed.append(path.relative_to(ROOT).as_posix())
        if not args.check:
            path.write_text(rendered, encoding="utf-8")
    if args.check and changed:
        raise SystemExit(f"navigation is not canonical: {', '.join(changed)}")
    print(f"{'checked' if args.check else 'updated'} {len(shell_pages())} page shells")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
