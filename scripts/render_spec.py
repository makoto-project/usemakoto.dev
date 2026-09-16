#!/usr/bin/env python3
"""Generate the rendered specification and schema pages from canonical sources.

Two pages and one pointer are generated, never hand-edited:

* ``spec/text/index.html``    — the full normative text of ``spec/v0.2/spec.md``.
* ``spec/schemas/index.html`` — every hosted schema under ``schema/v0.2/``.
* ``schema/latest.json``      — the convenience pointer to the current catalog.

Both are derived, so the published prose and JSON cannot drift from the bytes
the pin and the catalog digest. ``tests/test_render_spec.py`` runs the ``--check`` comparison so a stale page
fails the suite rather than the reader.

The page shell (topbar, docs sidebar, footer) is lifted verbatim from
``spec/index.html`` rather than duplicated here: the navigation link sets have a
single owner, and a generated page can never fall behind them.

Usage: uv run scripts/render_spec.py [--check]
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.markdown_lite import render

SHELL_SOURCE = ROOT / "spec/index.html"
SPEC_SOURCE = ROOT / "spec/v0.2/spec.md"
SCHEMA_DIR = ROOT / "schema/v0.2"
TEXT_PAGE = ROOT / "spec/text/index.html"
SCHEMA_PAGE = ROOT / "spec/schemas/index.html"
LATEST_POINTER = ROOT / "schema/latest.json"

# One sentence per hosted resource, describing what the schema constrains.
# Kept here rather than derived from the schema's own description so the index
# reads as a guide; the authoritative text stays in the resource itself.
SCHEMA_NOTES = {
    "bundle.schema.json": "The on-disk bundle layout a sender transfers: statements, attestations, schema closure, and final artifacts.",
    "catalog.json": "The index of hosted resources and their digests. Not a schema itself; the document a resolver pins against.",
    "catalog.schema.json": "The shape of that catalog, so a resolver can validate an index before trusting any entry in it.",
    "dataset-manifest.schema.json": "A partitioned dataset described as one subject: member parts, their digests, and the manifest that binds them.",
    "envelope.schema.json": "The DSSE envelope. Signatures authenticate exact payload bytes and nothing about authorization.",
    "handoff.schema.json": "The completeness anchor: roots, heads, statement set, required profiles, final artifacts, and named recipients.",
    "origin.schema.json": "The origin predicate. Source claims, event identity and time, and the exact subjects first observed.",
    "profile-dialect.schema.json": "The restricted JSON Schema dialect a private profile may use, bounded so resolution stays offline and terminating.",
    "profile-reference.schema.json": "A profile reference: the schema root URI plus its complete digest-pinned closure.",
    "statement.schema.json": "The common in-toto statement wrapper every Makoto predicate is carried in.",
    "transform.schema.json": "The transformation predicate. Operation metadata, exact predecessors, input artifacts, and output subjects.",
    "trust-policy.schema.json": "The receiver-owned policy: which keys may make which claims, under which thresholds and resource limits.",
    "verification-report.schema.json": "The report contract. Separate outcomes per check, never a single collapsed verdict.",
}

STYLE_HEAD = """  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="description" content="{description}">
  <title>{title}</title>
  <link rel="canonical" href="https://usemakoto.dev{canonical}">
  <link rel="stylesheet" href="/assets/v02.css">
"""


def shell_fragments() -> tuple[str, str, str]:
    """Return the (topbar, sidebar, footer) blocks used by every current page."""
    source = SHELL_SOURCE.read_text(encoding="utf-8")

    def between(start: str, end: str) -> str:
        first = source.index(start)
        last = source.index(end, first) + len(end)
        return source[first:last]

    topbar = between('<header class="topbar">', "</header>")
    sidebar = between('<aside class="docs-sidebar"', "</aside>")
    footer = between('<footer class="footer">', "</footer>")
    return topbar, sidebar, footer


def page(*, title: str, description: str, canonical: str, main: str) -> str:
    topbar, sidebar, footer = shell_fragments()
    head = STYLE_HEAD.format(
        title=html.escape(title), description=html.escape(description), canonical=canonical
    )
    return (
        '<!doctype html>\n<html lang="en">\n<head>\n'
        f"{head}</head>\n<body>\n"
        '<a class="skip-link" href="#main">Skip to content</a>\n'
        f"{topbar}\n"
        '<div class="site-shell">\n'
        f"{sidebar}\n"
        '<div class="site-main"><main id="main" class="page wide">\n'
        f"{main}\n"
        f"</main>{footer}</div>\n"
        "</div>\n"
        '<script defer src="/assets/prism.js"></script>\n'
        "</body>\n</html>\n"
    )


def _close_part(part: list[str]) -> str:
    """Close one part, omitting the child list when the section has no subsections."""
    head, children = part[0], part[1:]
    body = f"<ul>{''.join(children)}</ul>" if children else ""
    return f"{head}{body}</div></li>"


def contents(outline: list[dict[str, object]]) -> str:
    """Build the part/section table of contents from the heading outline."""
    parts: list[str] = []
    current: list[str] | None = None
    for entry in outline:
        text, slug = str(entry["text"]), str(entry["slug"])
        if entry["level"] == 2:
            if current is not None:
                parts.append(_close_part(current))
            number, _, name = text.partition(". ")
            current = [f'<li><div><h3><a href="#{slug}">{html.escape(name or number)}</a></h3>']
        elif current is not None:
            label = text.split(" ", 1)[-1]
            current.append(f'<li><a href="#{slug}">{html.escape(label)}</a></li>')
    if current is not None:
        parts.append(_close_part(current))
    return '<ol class="spec-toc">' + "".join(parts) + "</ol>"


def text_page() -> str:
    source = SPEC_SOURCE.read_text(encoding="utf-8")
    body, outline = render(source)
    digest = hashlib.sha256(SPEC_SOURCE.read_bytes()).hexdigest()
    # The rendered <h1> repeats the document title the page header already
    # carries, so drop it and keep one level-one heading per page.
    body = re.sub(r"^<h1 id=\"[^\"]+\">.*?</h1>\n", "", body, count=1, flags=re.DOTALL)
    main = f"""  <span class="kicker">Normative text</span>
  <h1>The complete specification, as written.</h1>
  <p class="lead">This is the canonical normative text, rendered from the same file the release pin digests. Nothing here is a summary: algorithms, limits, diagnostic codes, and conformance obligations appear exactly as the specification states them.</p>
  <p class="editorial-note"><strong>Publication status.</strong> The normative text and implementation are available for public review. They are not yet an immutable tagged release.</p>
  <dl class="schema-meta">
    <dt>Source</dt><dd><a href="/spec/v0.2/spec.md">/spec/v0.2/spec.md</a></dd>
    <dt>Digest</dt><dd>sha256:{digest}</dd>
  </dl>
  <p class="spec-jump"><a href="#contents">Contents</a><a href="/spec/">Specification overview</a><a href="/spec/schemas/">Hosted schemas</a><a href="/spec/v0.2/spec.md">Raw text</a></p>

  <section aria-labelledby="contents"><h2 id="contents">Contents</h2>
{contents(outline)}
  </section>

  <article class="doc-body">
{body}
  </article>"""
    return page(
        title="Normative text — Makoto",
        description=(
            "The complete normative Makoto specification, rendered from the canonical "
            "source file with its digest."
        ),
        canonical="/spec/text/",
        main=main,
    )


def schema_page() -> str:
    catalog = json.loads((SCHEMA_DIR / "catalog.json").read_text(encoding="utf-8"))
    listed = {entry["path"]: entry for entry in catalog["resources"]}
    entries: list[str] = []
    index_rows: list[str] = []
    for path in sorted(p.name for p in SCHEMA_DIR.iterdir() if p.is_file()):
        raw = (SCHEMA_DIR / path).read_bytes()
        document = json.loads(raw.decode("utf-8"))
        note = SCHEMA_NOTES[path]
        slug = path.replace(".", "-")
        identifier = document.get("$id", f"https://usemakoto.dev/schema/v0.2/{path}")
        digest = (
            listed.get(path, {}).get("digest", {}).get("sha256") or hashlib.sha256(raw).hexdigest()
        )
        # Show the published bytes, not a re-serialisation, so the page shows what
        # is digested. The catalog is canonical single-line JSON, which nobody can
        # read in a code block, so that one is formatted and says so.
        text = raw.decode("utf-8").rstrip("\n")
        formatted = "\n" not in text
        if formatted:
            text = json.dumps(document, indent=2, ensure_ascii=False)
        published = html.escape(text)
        caption = (
            "Formatted for reading. The digested bytes are canonical single-line JSON; "
            "fetch the raw URL to compare them."
            if formatted
            else "The published bytes, unmodified."
        )
        index_rows.append(
            f'<tr><td><a href="#{slug}"><code>{html.escape(path)}</code></a></td>'
            f"<td>{html.escape(note)}</td></tr>"
        )
        entries.append(
            f'<article class="schema-entry" id="{slug}">'
            f'<h3>{html.escape(path)}<a class="anchor-link" href="#{slug}" aria-label="Permalink">#</a></h3>'
            f"<p>{html.escape(note)}</p>"
            '<dl class="schema-meta">'
            f"<dt>Identifier</dt><dd>{html.escape(identifier)}</dd>"
            f"<dt>Digest</dt><dd>sha256:{digest}</dd>"
            f'<dt>Raw</dt><dd><a href="/schema/v0.2/{html.escape(path)}">/schema/v0.2/{html.escape(path)}</a></dd>'
            "</dl>"
            f"<details><summary>Read the document ({len(raw):,} bytes)</summary><div>"
            f'<pre class="language-json"><code class="language-json">{published}</code></pre>'
            f'<p class="code-note">{caption}</p>'
            "</div></details></article>"
        )
    main = f"""  <span class="kicker">Machine-readable resources</span>
  <h1>Every hosted schema, with the bytes it is pinned by.</h1>
  <p class="lead">These are the resources a verifier resolves. Each one is served at a stable URL, digested in the catalog, and reproduced below exactly as published, so a reader can compare what a page claims against what the resolver will actually fetch.</p>
  <p class="spec-jump"><a href="/spec/">Specification overview</a><a href="/spec/text/">Normative text</a><a href="/schema/v0.2/catalog.json">Catalog</a><a href="/schema/latest.json">Current release pointer</a></p>

  <p class="editorial-note"><strong>Pin versioned URLs.</strong> <a href="/schema/latest.json"><code>/schema/latest.json</code></a> is a convenience pointer to the current catalog for people. It is not an immutable protocol identifier and changes when a new version is published; cite the versioned resource and its digest instead.</p>

  <section aria-labelledby="index"><h2 id="index">Resource index</h2>
    <table class="stack-table schema-table"><thead><tr><th scope="col">Resource</th><th scope="col">What it constrains</th></tr></thead><tbody>{"".join(index_rows)}</tbody></table>
  </section>

  <section aria-labelledby="resources"><h2 id="resources">The resources</h2>
    <p>Digests are the catalog's own values. A resolver pins these bytes; it does not trust a live lookup.</p>
{"".join(entries)}
  </section>"""
    return page(
        title="Hosted schemas — Makoto",
        description=(
            "Every hosted Makoto JSON Schema resource, with its identifier, digest, and "
            "complete published document."
        ),
        canonical="/spec/schemas/",
        main=main,
    )


def latest_pointer() -> str:
    """Resolve /schema/latest.json to the current catalog.

    This URL used to serve a byte-for-byte copy of the superseded single-document
    schema, so anything still polling it was being handed a retired format under a
    name that promised the opposite. The current schema set is thirteen resources
    indexed by a catalog, and there is no single document to alias, so the honest
    resolution is a pointer: it names the catalog, carries the catalog's own
    digest, states the publication status, and says where the superseded document
    still lives unchanged.

    It deliberately does not restate the resource list. Duplicating the catalog
    here is how a pointer goes stale without anybody noticing.
    """
    catalog_path = SCHEMA_DIR / "catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    status = "candidate" if (ROOT / "schema/core-candidate.json").is_file() else "release"
    document = {
        "catalog": {
            "digest": {"sha256": hashlib.sha256(catalog_path.read_bytes()).hexdigest()},
            "id": "https://usemakoto.dev/schema/v0.2/catalog.json",
            "resources": len(catalog["resources"]),
        },
        "note": (
            "This document resolves the name 'latest' to the current schema catalog, "
            "as a convenience for people. It is not an immutable protocol identifier: "
            "it changes when a new version is published, so never use it as a $id, "
            "$schema, or pinned reference. It is a pointer, not a schema: validate "
            "against the catalog's resources, each served at its own versioned URL "
            "and pinned by digest."
        ),
        "status": status,
        "supersedes": {
            "available": True,
            "id": "https://usemakoto.dev/schema/v0.1.json",
            "note": (
                "The superseded single-document schema remains published and "
                "unchanged at its own URL. It is not wire-compatible with the "
                "current version and must never be coerced into it."
            ),
        },
        "version": catalog["version"],
    }
    return json.dumps(document, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="compare without writing")
    args = parser.parse_args()
    targets = (
        (TEXT_PAGE, text_page()),
        (SCHEMA_PAGE, schema_page()),
        (LATEST_POINTER, latest_pointer()),
    )
    stale = []
    for path, content in targets:
        if args.check:
            if not path.is_file() or path.read_text(encoding="utf-8") != content:
                stale.append(path.relative_to(ROOT).as_posix())
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)} ({len(content.encode()):,} bytes)")
    if stale:
        print(f"FAIL: generated pages are stale: {stale}")
        return 1
    if args.check:
        print("generated specification pages are current")
    return 0


if __name__ == "__main__":
    sys.exit(main())
