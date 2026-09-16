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
import base64
import hashlib
import html
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.markdown_lite import inline, render

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
  <script src="/assets/theme.js"></script>
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
        '<script defer src="/assets/prism.js"></script><script defer src="/assets/code.js"></script>\n'
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
            f'<tr><td><a href="/spec/schemas/{reference_slug(path)}/"><code>{html.escape(path)}</code></a></td>'
            f'<td>{html.escape(note)} <a href="#{slug}">Published bytes</a></td></tr>'
        )
        entries.append(
            f'<article class="schema-entry" id="{slug}">'
            f'<h3>{html.escape(path)}<a class="anchor-link" href="#{slug}" aria-label="Permalink">#</a></h3>'
            f"<p>{html.escape(note)}</p>"
            '<dl class="schema-meta">'
            f"<dt>Identifier</dt><dd>{html.escape(identifier)}</dd>"
            f"<dt>Digest</dt><dd>sha256:{digest}</dd>"
            f'<dt>Raw</dt><dd><a href="/schema/v0.2/{html.escape(path)}">/schema/v0.2/{html.escape(path)}</a></dd>'
            f'<dt>Reference</dt><dd><a href="/spec/schemas/{reference_slug(path)}/">Every field, with types, rules, and real values</a></dd>'
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

  <p class="lead">Each resource has a field reference: every property and definition with its type, whether it is required, its constraints, the rules the specification states for it, and a value read from a real document that validates. The raw <a href="/schema/v0.2/catalog.json"><code>catalog.json</code></a> lists every resource with its digest.</p>

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


# ---------------------------------------------------------------------------
# Schema reference: one human-readable page per hosted resource.
#
# The raw schemas carry almost no prose, so every sentence on these pages comes
# from one of three places, and nothing is written freehand per field:
#
# * structure (type, required, constraints, variants) is read from the schema;
# * a field's "Rules" text is the matching row of a field table in the
#   specification section that defines that schema;
# * an example value is read from a real document in this repository that
#   validates against the schema.
#
# ``tests/test_render_spec.py`` fails when a page drifts from the schema bytes
# or from this renderer, so a schema change must be followed by a regeneration.
# ---------------------------------------------------------------------------

REFERENCE_ROOT = ROOT / "spec/schemas"
DEMO_ARTIFACTS = ROOT / "demos/v0.2-end-to-end/artifacts"
SCHEMA_BASE_URI = "https://usemakoto.dev/schema/v0.2/"


def reference_slug(name: str) -> str:
    """URL segment for a hosted resource's reference page."""
    if name == "catalog.json":
        return "catalog"
    if name == "catalog.schema.json":
        return "catalog-schema"
    return name.removesuffix(".schema.json")


# Specification sections whose field tables and prose define each resource.
SCHEMA_SECTIONS: dict[str, tuple[str, ...]] = {
    "bundle.schema.json": ("13.3",),
    "catalog.json": ("12.3", "17"),
    "catalog.schema.json": ("12.3",),
    "dataset-manifest.schema.json": ("12.5",),
    "envelope.schema.json": ("10.1",),
    "handoff.schema.json": ("13.2",),
    "origin.schema.json": ("11.2", "11.3"),
    "profile-dialect.schema.json": ("12.1", "12.4"),
    "profile-reference.schema.json": ("12.1",),
    "statement.schema.json": ("11.1",),
    "transform.schema.json": ("11.2", "11.4"),
    "trust-policy.schema.json": ("14",),
    "verification-report.schema.json": ("15", "16.3", "Appendix A", "Appendix C"),
}

# Where each document travels. Every statement here is checked against the
# demo artifacts and CLI invocations published on this site.
SCHEMA_CARRIERS: dict[str, str] = {
    "bundle.schema.json": "<code>bundle.json</code> at the root of every handoff bundle.",
    "catalog.json": 'The hosted core catalog. Every other resource on these pages is listed in it with its digest, and it is validated by <a href="/spec/schemas/catalog-schema/"><code>catalog.schema.json</code></a>.',
    "catalog.schema.json": "Validates every catalog document: the hosted core catalog, a bundle's <code>schemaCatalog</code>, and the receiver catalog passed to <code>makoto verify bundle --schema-catalog</code>.",
    "dataset-manifest.schema.json": "A partitioned dataset handed off as one subject (Section 12.5).",
    "envelope.schema.json": "Every signed file in a bundle: <code>attestations/&lt;digest&gt;.dsse.json</code> carries one statement, and <code>manifest.dsse.json</code> carries the handoff.",
    "handoff.schema.json": "The decoded payload of <code>manifest.dsse.json</code>, payload type <code>application/vnd.makoto.handoff.v0.2+json</code>.",
    "origin.schema.json": "The <code>predicate</code> of a statement whose <code>predicateType</code> is <code>https://usemakoto.dev/predicate/v0.2/origin</code>.",
    "profile-dialect.schema.json": "The <code>$schema</code> every private profile resource declares, such as the receiver resources in the runnable proof.",
    "profile-reference.schema.json": "Entries of <code>profiles</code> in origin and transformation predicates, and the receiver's profile references.",
    "statement.schema.json": "The decoded <code>payload</code> of each attestation envelope, payload type <code>application/vnd.in-toto+json</code>.",
    "transform.schema.json": "The <code>predicate</code> of a statement whose <code>predicateType</code> is <code>https://usemakoto.dev/predicate/v0.2/transform</code>.",
    "trust-policy.schema.json": "The receiver-owned policy passed to <code>makoto verify bundle --policy</code>.",
    "verification-report.schema.json": "The report <code>makoto verify bundle --json</code> writes, one per verification.",
}


def _decoded_payloads(pattern: str) -> list[tuple[str, dict[str, Any]]]:
    found = []
    for path in sorted(DEMO_ARTIFACTS.glob(pattern)):
        envelope = json.loads(path.read_text(encoding="utf-8"))
        payload = json.loads(base64.b64decode(envelope["payload"]))
        found.append((path.relative_to(ROOT).as_posix(), payload))
    return found


def _documents(pattern: str) -> list[tuple[str, Any]]:
    return [
        (path.relative_to(ROOT).as_posix(), json.loads(path.read_text(encoding="utf-8")))
        for path in sorted(DEMO_ARTIFACTS.glob(pattern))
    ]


def _spec_examples() -> list[tuple[str, Any]]:
    """Fenced JSON examples in the specification that parse as JSON."""
    found = []
    source = SPEC_SOURCE.read_text(encoding="utf-8")
    section = ""
    for match in re.finditer(
        r"^(#{2,3}) (.*)$|^```json\n(.*?)^```", source, re.MULTILINE | re.DOTALL
    ):
        if match.group(2):
            section = _section_number(match.group(2))
            continue
        try:
            value = json.loads(match.group(3))
        except ValueError:
            continue
        found.append((f"spec/v0.2/spec.md §{section}", value))
    return found


def example_sources(name: str) -> list[tuple[str, Any]]:
    """Candidate real documents for a resource, before validation."""
    statements = _decoded_payloads("positive-bundle/attestations/*.dsse.json")
    candidates: dict[str, list[tuple[str, Any]]] = {
        "bundle.schema.json": _documents("positive-bundle/bundle.json"),
        "catalog.json": [
            (
                "schema/v0.2/catalog.json",
                json.loads((SCHEMA_DIR / "catalog.json").read_text("utf-8")),
            )
        ],
        "catalog.schema.json": _documents("receiver/catalog.json")
        + _documents("positive-bundle/schemas/catalog.json"),
        "envelope.schema.json": _documents("positive-bundle/attestations/*.dsse.json")
        + _documents("positive-bundle/manifest.dsse.json"),
        "handoff.schema.json": _decoded_payloads("positive-bundle/manifest.dsse.json"),
        "origin.schema.json": [
            (f"{path} → predicate", doc["predicate"])
            for path, doc in statements
            if doc["predicateType"].endswith("/origin")
        ],
        "profile-dialect.schema.json": _documents("receiver/resources/*.schema.json"),
        "profile-reference.schema.json": _documents("receiver/*.profile.json"),
        "statement.schema.json": [(f"{path} → payload", doc) for path, doc in statements],
        "transform.schema.json": [
            (f"{path} → predicate", doc["predicate"])
            for path, doc in statements
            if doc["predicateType"].endswith("/transform")
        ],
        "trust-policy.schema.json": _documents("receiver/policy.json")
        + _documents("receiver/attacker-known-policy.json"),
        "verification-report.schema.json": _documents("reports/positive.json")
        + [d for d in _documents("reports/*.json") if not d[0].endswith("/positive.json")],
    }
    return candidates.get(name, []) + _spec_examples()


def _registry() -> Any:
    from referencing import Registry, Resource

    resources = []
    for path in sorted(SCHEMA_DIR.glob("*.schema.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        resources.append((document["$id"], Resource.from_contents(document)))
    return Registry().with_resources(resources)


def valid_examples(name: str) -> list[tuple[str, Any]]:
    """Real documents that validate against the resource. Invalid ones never render."""
    if name == "catalog.json":
        return example_sources(name)[:1]
    from jsonschema import Draft202012Validator
    from referencing.exceptions import Unresolvable

    schema = json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, registry=_registry())
    found = []
    for label, value in example_sources(name):
        try:
            if validator.is_valid(value):
                found.append((label, value))
        except Unresolvable:
            continue
    return found


def _section_number(heading: str) -> str:
    match = re.match(r"(Appendix [A-Z]|\d+(?:\.\d+)?)", heading)
    return match.group(1) if match else ""


def spec_field_rules() -> dict[str, dict[str, str]]:
    """Field-table rows by specification section: {section: {field: rules}}."""
    rules: dict[str, dict[str, str]] = {}
    section = ""
    header: list[str] = []
    for line in SPEC_SOURCE.read_text(encoding="utf-8").splitlines():
        heading = re.match(r"^#{2,3} (.*)$", line)
        if heading:
            section = _section_number(heading.group(1))
            header = []
            continue
        if not line.startswith("|"):
            header = []
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if not header:
            header = [cell.casefold() for cell in cells]
            continue
        if all(set(cell) <= set(":-") for cell in cells):
            continue
        key = re.fullmatch(r"`([^`]+)`", cells[0])
        if key and "field" in header[0] and len(cells) >= 2:
            rules.setdefault(section, {})[key.group(1)] = cells[-1]
    return rules


def spec_anchors() -> dict[str, str]:
    _, outline = render(SPEC_SOURCE.read_text(encoding="utf-8"))
    anchors: dict[str, str] = {}
    for entry in outline:
        number = _section_number(str(entry["text"]))
        if number and number not in anchors:
            anchors[number] = str(entry["slug"])
    return anchors


def spec_responsibility() -> dict[str, str]:
    """Section 17's fixed responsibility table, by resource name."""
    table: dict[str, str] = {}
    for line in SPEC_SOURCE.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^\| `([a-z-]+)` \| [^|]+ \| (.+) \|$", line)
        if match and (SCHEMA_DIR / f"{match.group(1)}.schema.json").is_file():
            table[f"{match.group(1)}.schema.json"] = match.group(2)
    return table


def _json_snippet(value: Any, limit: int = 96) -> str:
    text = json.dumps(value, ensure_ascii=False, separators=(", ", ": "))
    return text if len(text) <= limit else text[: limit - 1] + "…"


class SchemaReference:
    """Walks one schema, its $defs, and real instances in tandem."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.raw = (SCHEMA_DIR / name).read_bytes()
        self.document = json.loads(self.raw.decode("utf-8"))
        self.defs: dict[str, Any] = self.document.get("$defs", {})
        self.examples = valid_examples(name)
        self.instances: dict[str, list[Any]] = {"root": []}
        self.paths: dict[str, set[str]] = {"root": {""}}
        self.current = "root"
        self.section_node: Any = None
        self._walk(self.document, [value for _, value in self.examples], "", "root", 0)

    # -- instance collection ------------------------------------------------

    def _walk(self, node: Any, values: list[Any], path: str, section: str, depth: int) -> None:
        if not isinstance(node, dict) or depth > 14:
            return
        if section:
            bucket = self.instances.setdefault(section, [])
            for value in values:
                if all(value is not seen for seen in bucket):
                    bucket.append(value)
        reference = node.get("$ref")
        if isinstance(reference, str) and reference.startswith("#/$defs/"):
            target = reference.removeprefix("#/$defs/")
            self.paths.setdefault(target, set()).add(path)
            if target in self.defs:
                self._walk(self.defs[target], values, path, target, depth + 1)
        for key, child in (node.get("properties") or {}).items():
            children = [value[key] for value in values if isinstance(value, dict) and key in value]
            self._walk(child, children, f"{path}.{key}" if path else key, "", depth + 1)
        items = node.get("items")
        if isinstance(items, dict):
            children = [item for value in values if isinstance(value, list) for item in value]
            self._walk(items, children, f"{path}[]", "", depth + 1)
        extra = node.get("additionalProperties")
        if isinstance(extra, dict):
            declared = set(node.get("properties") or {})
            children = [
                item
                for value in values
                if isinstance(value, dict)
                for key, item in value.items()
                if key not in declared
            ]
            self._walk(extra, children, f"{path}.*" if path else "*", "", depth + 1)
        for keyword in ("allOf", "oneOf", "anyOf"):
            for branch in node.get(keyword) or []:
                self._walk(branch, values, path, "", depth + 1)
        for keyword in ("then", "else"):
            if isinstance(node.get(keyword), dict):
                self._walk(node[keyword], values, path, "", depth + 1)

    # -- rendering helpers -------------------------------------------------

    def link(self, reference: str) -> str:
        if reference.startswith("#/$defs/"):
            target = reference.removeprefix("#/$defs/")
            return f'<a href="#def-{html.escape(target)}">{html.escape(target)}</a>'
        if reference.startswith(SCHEMA_BASE_URI):
            resource = reference.removeprefix(SCHEMA_BASE_URI).split("#", 1)[0]
            if (SCHEMA_DIR / resource).is_file():
                return (
                    f'<a href="/spec/schemas/{reference_slug(resource)}/">'
                    f"{html.escape(resource)}</a>"
                )
        return f"<code>{html.escape(reference)}</code>"

    def type_label(self, node: Any) -> str:
        if node is True or node == {}:
            return "any"
        if node is False:
            return "never"
        if not isinstance(node, dict):
            return "any"
        parts: list[str] = []
        if "$ref" in node:
            parts.append(self.link(node["$ref"]))
        if "const" in node:
            parts.append(f"{type(node['const']).__name__.replace('str', 'string')} constant")
        declared = node.get("type")
        if isinstance(declared, list):
            parts.append(" | ".join(html.escape(str(item)) for item in declared))
        elif declared == "array":
            items = node.get("items")
            parts.append(
                f"array of {self.type_label(items)}" if isinstance(items, dict) else "array"
            )
        elif (
            declared == "object"
            and isinstance(node.get("additionalProperties"), dict)
            and not node.get("properties")
        ):
            parts.append(f"map of {self.type_label(node['additionalProperties'])}")
        elif isinstance(declared, str):
            parts.append(html.escape(declared))
        if "enum" in node and not declared:
            parts.append("enum")
        for keyword, word in (("oneOf", "one of"), ("anyOf", "any of")):
            if keyword not in node:
                continue
            if node is self.section_node:
                parts.append(
                    f'{word} {len(node[keyword])} <a href="#variants-{html.escape(self.current)}">variants</a>'
                )
            else:
                options = [self.type_label(branch) for branch in node[keyword][:6]]
                more = "…" if len(node[keyword]) > 6 else ""
                parts.append(f"{word}: " + " | ".join(options) + more)
        return ", ".join(parts) if parts else "any"

    def constraints(self, node: Any) -> list[str]:
        if not isinstance(node, dict):
            return []
        out: list[str] = []
        if "const" in node:
            out.append(f"= {json.dumps(node['const'], ensure_ascii=False)}")
        if "enum" in node:
            values = ", ".join(json.dumps(value, ensure_ascii=False) for value in node["enum"])
            out.append(f"one of: {values}")
        for keyword, label in (
            ("minLength", "min length"),
            ("maxLength", "max length"),
            ("minimum", "≥"),
            ("exclusiveMinimum", ">"),
            ("maximum", "≤"),
            ("exclusiveMaximum", "<"),
            ("multipleOf", "multiple of"),
            ("minItems", "min items"),
            ("maxItems", "max items"),
            ("minProperties", "min keys"),
            ("maxProperties", "max keys"),
            ("pattern", "pattern"),
            ("format", "format"),
            ("contentEncoding", "encoding"),
            ("contentMediaType", "media type"),
        ):
            if keyword in node:
                out.append(
                    f"{label} {json.dumps(node[keyword], ensure_ascii=False) if isinstance(node[keyword], str) else node[keyword]}"
                )
        if node.get("uniqueItems"):
            out.append("unique items")
        if node.get("additionalProperties") is False or node.get("unevaluatedProperties") is False:
            out.append("closed object")
        names = node.get("propertyNames")
        if isinstance(names, dict):
            inner = self.constraints(names)
            if inner:
                out.append("keys: " + "; ".join(inner))
        items = node.get("items")
        if node.get("type") == "array" and isinstance(items, dict):
            out.extend(
                f"each: {rule}" for rule in self.constraints(items) if rule != "closed object"
            )
        return out

    def rules_for(self, section: str, field: str, table: dict[str, str]) -> str:
        paths = self.paths.get(section, {""}) if section != "root" else {""}
        candidates = []
        for path in sorted(paths):
            base = re.sub(r"\.\*$", "", path)
            candidates.append(f"{base}.{field}" if base else field)
        candidates.append(field)
        for candidate in candidates:
            if candidate in table:
                return inline(table[candidate])
            for key, value in table.items():
                if key.endswith(f".{candidate}") or re.sub(r"\[\]", "", key) == candidate:
                    return inline(value)
        return ""

    def example_for(self, section: str, field: str) -> str:
        for value in self.instances.get(section, []):
            if isinstance(value, dict) and field in value:
                return _json_snippet(value[field])
        return ""

    def conditions(self, node: dict[str, Any]) -> list[str]:
        out = []
        for branch in node.get("allOf") or []:
            if not isinstance(branch, dict) or "if" not in branch:
                continue
            condition = self._describe(branch["if"])
            for keyword, word in (("then", "then"), ("else", "otherwise")):
                if isinstance(branch.get(keyword), dict):
                    out.append(
                        f"<li>When {condition}: {word} {self._describe(branch[keyword])}.</li>"
                        if keyword == "then"
                        else f"<li>When not {condition}: {self._describe(branch[keyword])}.</li>"
                    )
        if "if" in node:
            out.extend(self.conditions({"allOf": [node]}))
        return out

    def _describe(self, node: Any) -> str:
        if not isinstance(node, dict):
            return "any value"
        phrases = []
        for key, child in (node.get("properties") or {}).items():
            bits = (
                [self.type_label(child)]
                if isinstance(child, dict) and ("$ref" in child or "type" in child)
                else []
            )
            bits.extend(html.escape(rule) for rule in self.constraints(child))
            phrases.append(
                f"<code>{html.escape(key)}</code> {' '.join(bits) if bits else 'is present'}"
            )
        if node.get("required"):
            phrases.append(
                "requires " + ", ".join(f"<code>{html.escape(k)}</code>" for k in node["required"])
            )
        return "; ".join(phrases) or "the base shape applies"

    def variants(self, key: str, node: dict[str, Any]) -> str:
        blocks = []
        for keyword in ("oneOf", "anyOf"):
            branches = [b for b in node.get(keyword) or [] if isinstance(b, dict)]
            if not branches:
                continue
            const_columns: list[str] = []
            ref_columns: list[str] = []
            for branch in branches:
                for prop, child in (branch.get("properties") or {}).items():
                    if isinstance(child, dict) and "const" in child and prop not in const_columns:
                        const_columns.append(prop)
                    elif isinstance(child, dict) and "$ref" in child and prop not in ref_columns:
                        ref_columns.append(prop)
            head = "".join(
                f'<th scope="col">{html.escape(c)}</th>' for c in [*const_columns, *ref_columns]
            )
            rows = []
            for index, branch in enumerate(branches, start=1):
                props = branch.get("properties") or {}
                cells = [
                    f"<td>{index}</td>",
                    f'<td class="field-type">{self.type_label({k: v for k, v in branch.items() if k != "properties"})}</td>',
                ]
                for column in const_columns:
                    value = (
                        props.get(column, {}).get("const")
                        if isinstance(props.get(column), dict)
                        else None
                    )
                    cells.append(
                        f"<td><code>{html.escape(json.dumps(value, ensure_ascii=False))}</code></td>"
                        if column in props
                        else "<td></td>"
                    )
                for column in ref_columns:
                    cells.append(
                        f'<td class="field-type">{self.type_label(props[column])}</td>'
                        if column in props
                        else "<td></td>"
                    )
                rows.append(f"<tr>{''.join(cells)}</tr>")
            word = "Exactly one" if keyword == "oneOf" else "At least one"
            blocks.append(
                f'<h4 id="variants-{html.escape(key)}">Variants ({len(branches)})</h4>'
                f"<p>{word} of these shapes must match.</p>"
                '<div class="table-scroll"><table class="doc-table variant-table">'
                f'<thead><tr><th scope="col">#</th><th scope="col">Base</th>{head}</tr></thead>'
                f"<tbody>{''.join(rows)}</tbody></table></div>"
            )
        return "".join(blocks)

    def section(self, key: str, node: Any, table: dict[str, str]) -> str:
        self.current = key
        self.section_node = node
        label = "Top level" if key == "root" else key
        anchor = "def-root" if key == "root" else f"def-{key}"
        parts = [
            f'<section class="def-block" id="{html.escape(anchor)}" aria-labelledby="{html.escape(anchor)}-title">'
        ]
        parts.append(
            f'<h3 id="{html.escape(anchor)}-title">{html.escape(label)}<a class="anchor-link" href="#{html.escape(anchor)}" aria-label="Permalink">#</a></h3>'
        )
        if not isinstance(node, dict):
            parts.append("<p>Any JSON value.</p></section>")
            return "".join(parts)
        shape = self.type_label(node)
        rules = self.constraints(node)
        uses = sorted(p for p in self.paths.get(key, set()) if p) if key != "root" else []
        summary = [f'<strong>Shape</strong> <span class="field-type">{shape}</span>']
        if rules:
            summary.append(
                '<ul class="field-constraints">'
                + "".join(f"<li>{html.escape(r)}</li>" for r in rules)
                + "</ul>"
            )
        if uses:
            summary.append(
                '<p class="text-muted">Appears at '
                + ", ".join(f"<code>{html.escape(p)}</code>" for p in uses[:8])
                + ("…" if len(uses) > 8 else "")
                + "</p>"
            )
        parts.append(f'<div class="def-summary">{"".join(summary)}</div>')
        properties = node.get("properties") or {}
        if properties:
            required = set(node.get("required") or [])
            rows = []
            for field, child in properties.items():
                rule_text = self.rules_for(key, field, table)
                example = self.example_for(key, field)
                constraints = self.constraints(child)
                badge = (
                    '<span class="field-req is-required">required</span>'
                    if field in required
                    else '<span class="field-req is-optional">optional</span>'
                )
                cells = [
                    f'<td id="f-{html.escape(key)}-{html.escape(field)}"><span class="field-name">{html.escape(field)}</span><br>{badge}</td>',
                    f'<td class="field-type">{self.type_label(child)}</td>',
                    "<td>"
                    + (
                        '<ul class="field-constraints">'
                        + "".join(f"<li>{html.escape(c)}</li>" for c in constraints)
                        + "</ul>"
                        if constraints
                        else ""
                    )
                    + (f"<div>{rule_text}</div>" if rule_text else "")
                    + (
                        f'<div class="field-example"><code>{html.escape(example)}</code></div>'
                        if example
                        else ""
                    )
                    + "</td>",
                ]
                rows.append(f"<tr>{''.join(cells)}</tr>")
            parts.append(
                '<div class="table-scroll"><table class="doc-table field-table stack-table">'
                '<thead><tr><th scope="col">Field</th><th scope="col">Type</th><th scope="col">Constraints, rules, and a real value</th></tr></thead>'
                f"<tbody>{''.join(rows)}</tbody></table></div>"
            )
        extra = node.get("additionalProperties")
        if isinstance(extra, dict) and properties:
            parts.append(
                f'<p>Other keys: <span class="field-type">{self.type_label(extra)}</span>.</p>'
            )
        conditions = self.conditions(node)
        if conditions:
            parts.append(
                '<h4>Conditional rules</h4><ul class="variant-list">'
                + "".join(conditions)
                + "</ul>"
            )
        parts.append(self.variants(key, node))
        parts.append("</section>")
        return "".join(parts)


def referenced_by() -> dict[str, list[tuple[str, str]]]:
    """External $ref edges between hosted resources: {target: [(source, location)]}."""
    edges: dict[str, list[tuple[str, str]]] = {}

    def visit(node: Any, source: str, trail: list[str]) -> None:
        if isinstance(node, dict):
            reference = node.get("$ref")
            if isinstance(reference, str) and reference.startswith(SCHEMA_BASE_URI):
                target = reference.removeprefix(SCHEMA_BASE_URI).split("#", 1)[0]
                location = ".".join(
                    "[]" if part == "items" else part
                    for part in trail
                    if part not in {"properties", "allOf", "then", "else", "$defs"}
                    and not part.isdigit()
                ).replace(".[]", "[]")
                pair = (source, location or "(root)")
                if pair not in edges.setdefault(target, []):
                    edges[target].append(pair)
            for key, child in node.items():
                visit(child, source, [*trail, key])
        elif isinstance(node, list):
            for index, child in enumerate(node):
                visit(child, source, [*trail, str(index)])

    for path in sorted(SCHEMA_DIR.glob("*.json")):
        visit(json.loads(path.read_text(encoding="utf-8")), path.name, [])
    return edges


def _published_json(raw: bytes) -> tuple[str, bool]:
    text = raw.decode("utf-8").rstrip("\n")
    if "\n" in text:
        return text, False
    return json.dumps(json.loads(text), indent=2, ensure_ascii=False), True


def reference_page(name: str) -> str:
    reference = SchemaReference(name)
    slug = reference_slug(name)
    catalog = json.loads((SCHEMA_DIR / "catalog.json").read_text(encoding="utf-8"))
    listed = {entry["path"]: entry for entry in catalog["resources"]}
    digest = (
        listed.get(name, {}).get("digest", {}).get("sha256")
        or hashlib.sha256(reference.raw).hexdigest()
    )
    identifier = reference.document.get("$id", f"{SCHEMA_BASE_URI}{name}")
    title = reference.document.get("title", "Schema catalog")
    anchors = spec_anchors()
    sections = SCHEMA_SECTIONS.get(name, ())
    spec_links = "".join(
        f'<a href="/spec/text/#{anchors[number]}">§{html.escape(number)}</a>'
        for number in sections
        if number in anchors
    )
    responsibility = spec_responsibility().get(name)
    field_rules: dict[str, str] = {}
    all_rules = spec_field_rules()
    for number in sections:
        field_rules.update(all_rules.get(number, {}))

    used = referenced_by().get(name, [])
    used_html = "".join(
        f'<li><a href="/spec/schemas/{reference_slug(source)}/"><code>{html.escape(source)}</code> → {html.escape(location)}</a></li>'
        for source, location in used
    )
    example_list = "".join(
        f"<li><code>{html.escape(label)}</code></li>" for label, _ in reference.examples
    )
    if reference.examples:
        label, value = reference.examples[0]
        example_text = json.dumps(value, indent=2, ensure_ascii=False)
        example_block = (
            '<figure class="lead-exhibit">'
            f"<figcaption><strong>A real instance.</strong> Read from <code>{html.escape(label)}</code>, which validates against this schema.</figcaption>"
            f'<pre data-filename="{html.escape(label.split(" ")[0].rsplit("/", 1)[-1])}"><code class="language-json">{html.escape(example_text)}</code></pre>'
            "</figure>"
        )
        examples_section = (
            '<section aria-labelledby="examples"><h2 id="examples">Real documents that validate</h2>'
            f'<ul class="schema-list">{example_list}</ul></section>'
        )
    else:
        example_block = (
            '<p class="editorial-note"><strong>No real instance on hand.</strong> No document in this repository validates against this schema yet, so no example values are shown rather than inventing one. '
            '<a href="/community/">Contribute a fixture</a>.</p>'
        )
        examples_section = ""

    if name == "catalog.json":
        rows = "".join(
            f'<tr><td><a href="/spec/schemas/{reference_slug(entry["path"])}/"><code>{html.escape(entry["path"])}</code></a></td>'
            f'<td class="hash">{html.escape(entry["digest"]["sha256"])}</td></tr>'
            for entry in catalog["resources"]
        )
        fields = (
            '<section aria-labelledby="fields"><h2 id="fields">Resources</h2>'
            '<div class="table-scroll"><table class="doc-table">'
            '<thead><tr><th scope="col">Path</th><th scope="col">SHA-256</th></tr></thead>'
            f"<tbody>{rows}</tbody></table></div></section>"
        )
    else:
        blocks = [reference.section("root", reference.document, field_rules)]
        blocks.extend(
            reference.section(key, node, field_rules) for key, node in reference.defs.items()
        )
        index = "".join(
            f'<a href="#def-{html.escape(key)}">{html.escape(key)}</a>' for key in reference.defs
        )
        fields = (
            '<section aria-labelledby="fields"><h2 id="fields">Fields</h2>'
            + (
                f'<p class="spec-jump"><a href="#def-root">Top level</a>{index}</p>'
                if index
                else ""
            )
            + "".join(blocks)
            + "</section>"
        )

    published, formatted = _published_json(reference.raw)
    caption = (
        "Formatted for reading. The digested bytes are canonical single-line JSON; fetch the raw URL to compare them."
        if formatted
        else "The published bytes, unmodified."
    )
    main = f"""  <span class="kicker">Schema reference</span>
  <h1><code>{html.escape(name)}</code></h1>
  <p class="lead">{html.escape(SCHEMA_NOTES[name])}</p>
  <dl class="schema-meta">
    <dt>Title</dt><dd>{html.escape(title)}</dd>
    <dt>Identifier</dt><dd>{html.escape(identifier)}</dd>
    <dt>Digest</dt><dd>sha256:{digest}</dd>
    <dt>Raw</dt><dd><a href="/schema/v0.2/{html.escape(name)}">/schema/v0.2/{html.escape(name)}</a></dd>
    <dt>Carried in</dt><dd class="prose">{SCHEMA_CARRIERS[name]}</dd>
    {f'<dt>Responsibility</dt><dd class="prose">{inline(responsibility)}</dd>' if responsibility else ""}
  </dl>
  <p class="spec-jump"><a href="/spec/schemas/">All schemas</a>{spec_links}<a href="#fields">Fields</a><a href="#raw">Raw JSON</a></p>
  {example_block}
  {f'<section aria-labelledby="used-by"><h2 id="used-by">Referenced by</h2><ul class="used-by">{used_html}</ul></section>' if used_html else ""}
{fields}
  {examples_section}
  <section aria-labelledby="raw"><h2 id="raw">Raw JSON</h2>
    <details><summary>The published document ({len(reference.raw):,} bytes)</summary><div>
      <pre data-filename="{html.escape(name)}"><code class="language-json">{html.escape(published)}</code></pre>
      <p class="code-note">{caption}</p>
    </div></details>
  </section>"""
    return page(
        title=f"{name} reference — Makoto",
        description=f"Field-by-field reference for the hosted Makoto resource {name}: types, requirements, constraints, rules, and real example values.",
        canonical=f"/spec/schemas/{slug}/",
        main=main,
    )


def reference_pages() -> list[tuple[Path, str]]:
    return [
        (REFERENCE_ROOT / reference_slug(path.name) / "index.html", reference_page(path.name))
        for path in sorted(SCHEMA_DIR.iterdir())
        if path.is_file()
    ]


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
        *reference_pages(),
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
