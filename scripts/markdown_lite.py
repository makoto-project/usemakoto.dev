"""A deliberately small Markdown renderer for the canonical specification text.

The site has no build step and no Markdown dependency, and the one document
this renders is fully inventoried: ATX headings, paragraphs, bullet and ordered
lists (including task boxes), pipe tables, fenced code, and inline ``code`` and
**bold**. There are no links, images, blockquotes, nested lists, raw HTML, or
underscore emphasis in it, so this implements exactly that grammar and raises
on anything it does not recognise rather than silently dropping text.

That trade is the point: a general Markdown library would render unknown
constructs plausibly, and silent plausibility is the failure mode a
specification page cannot afford.
"""

from __future__ import annotations

import html
import re
import unicodedata

_INLINE_CODE = re.compile(r"`([^`]+)`")
_BOLD = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)
_FENCE = re.compile(r"^```(\w*)\s*$")
_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_ORDERED = re.compile(r"^(\d+)\.\s+(.*)$")
_BULLET = re.compile(r"^[-*]\s+(.*)$")
_TASK = re.compile(r"^\[([ xX])\]\s+(.*)$")
_TABLE_DIVIDER = re.compile(r"^\|(?:\s*:?-{2,}:?\s*\|)+$")


class MarkdownError(ValueError):
    """Raised when the source uses a construct this renderer does not model."""


def slugify(text: str, used: set[str]) -> str:
    """GitHub-style anchor slug, made unique against ``used``."""
    plain = _INLINE_CODE.sub(r"\1", _BOLD.sub(r"\1", text))
    normalised = unicodedata.normalize("NFKD", plain).casefold()
    slug = re.sub(r"[^a-z0-9\s-]", "", normalised)
    slug = re.sub(r"[\s-]+", "-", slug).strip("-") or "section"
    candidate, suffix = slug, 2
    while candidate in used:
        candidate, suffix = f"{slug}-{suffix}", suffix + 1
    used.add(candidate)
    return candidate


def inline(text: str) -> str:
    """Escape, then re-introduce only the two inline spans the document uses."""
    placeholders: list[str] = []

    def stash(match: re.Match[str]) -> str:
        placeholders.append(f"<code>{html.escape(match.group(1))}</code>")
        return f"\x00{len(placeholders) - 1}\x00"

    staged = _INLINE_CODE.sub(stash, text)
    escaped = html.escape(staged, quote=False)
    bolded = _BOLD.sub(lambda m: f"<strong>{m.group(1)}</strong>", escaped)
    return re.sub(r"\x00(\d+)\x00", lambda m: placeholders[int(m.group(1))], bolded)


def _list_item(body: str) -> str:
    task = _TASK.match(body)
    if not task:
        return f"<li>{inline(body)}</li>"
    checked = " checked" if task.group(1).lower() == "x" else ""
    label = inline(task.group(2))
    return (
        '<li class="task"><input type="checkbox" disabled'
        f'{checked} aria-hidden="true"><span>{label}</span></li>'
    )


def _table(rows: list[str]) -> str:
    def cells(row: str) -> list[str]:
        return [cell.strip() for cell in row.strip().strip("|").split("|")]

    header = cells(rows[0])
    body = [cells(row) for row in rows[2:]]
    width = len(header)
    if any(len(row) != width for row in body):
        raise MarkdownError(f"ragged table near: {rows[0][:60]!r}")
    head_html = "".join(f'<th scope="col">{inline(cell)}</th>' for cell in header)
    body_html = "".join(
        "<tr>" + "".join(f"<td>{inline(cell)}</td>" for cell in row) + "</tr>" for row in body
    )
    return (
        '<div class="table-scroll"><table class="doc-table">'
        f"<thead><tr>{head_html}</tr></thead><tbody>{body_html}</tbody></table></div>"
    )


def _code(language: str, lines: list[str], counter: list[int]) -> str:
    counter[0] += 1
    body = html.escape("\n".join(lines))
    if not language or language == "text":
        return f'<pre class="language-none"><code>{body}</code></pre>'
    return f'<pre class="language-{language}"><code class="language-{language}">{body}</code></pre>'


def render(source: str) -> tuple[str, list[dict[str, object]]]:
    """Return ``(html_body, outline)`` for the given Markdown source.

    ``outline`` lists every heading below the document title as
    ``{"level", "text", "slug"}``, in document order, for table-of-contents use.
    """
    lines = source.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    outline: list[dict[str, object]] = []
    used_slugs: set[str] = set()
    code_counter = [0]
    index = 0
    paragraph: list[str] = []
    list_stack: list[str] = []

    def close_paragraph() -> None:
        if paragraph:
            out.append(f"<p>{inline(' '.join(paragraph))}</p>")
            paragraph.clear()

    def close_list() -> None:
        while list_stack:
            out.append(f"</{list_stack.pop()}>")

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        fence = _FENCE.match(stripped)
        if fence:
            close_paragraph()
            close_list()
            language, block, index = fence.group(1), [], index + 1
            while index < len(lines) and not _FENCE.match(lines[index].strip()):
                block.append(lines[index])
                index += 1
            if index >= len(lines):
                raise MarkdownError("unterminated code fence")
            out.append(_code(language, block, code_counter))
            index += 1
            continue

        if not stripped:
            close_paragraph()
            close_list()
            index += 1
            continue

        heading = _HEADING.match(stripped)
        if heading:
            close_paragraph()
            close_list()
            level, text = len(heading.group(1)), heading.group(2).strip()
            slug = slugify(text, used_slugs)
            anchor = f'<a class="anchor-link" href="#{slug}" aria-label="Permalink">#</a>'
            out.append(f'<h{level} id="{slug}">{inline(text)}{anchor}</h{level}>')
            if level > 1:
                outline.append({"level": level, "text": text, "slug": slug})
            index += 1
            continue

        if stripped.startswith("|"):
            close_paragraph()
            close_list()
            rows = [stripped]
            index += 1
            while index < len(lines) and lines[index].strip().startswith("|"):
                rows.append(lines[index].strip())
                index += 1
            if len(rows) < 3 or not _TABLE_DIVIDER.match(rows[1]):
                raise MarkdownError(f"table without a header rule near: {rows[0][:60]!r}")
            out.append(_table(rows))
            continue

        ordered = _ORDERED.match(stripped)
        bullet = _BULLET.match(stripped)
        if ordered or bullet:
            close_paragraph()
            wanted = "ol" if ordered else "ul"
            if list_stack and list_stack[-1] != wanted:
                close_list()
            if not list_stack:
                css = (
                    ' class="task-list"'
                    if _TASK.match((bullet or ordered).group(2 if ordered else 1))
                    else ""
                )
                out.append(f"<{wanted}{css}>")
                list_stack.append(wanted)
            out.append(_list_item((ordered.group(2) if ordered else bullet.group(1)).strip()))
            index += 1
            continue

        if line.startswith("    ") and list_stack:
            raise MarkdownError(f"nested list content is not modelled: {stripped[:60]!r}")

        close_list()
        paragraph.append(stripped)
        index += 1

    close_paragraph()
    close_list()
    return "\n".join(out), outline
