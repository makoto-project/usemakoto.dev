# Design system: the evidence docket

The site files real exhibits (configuration, commands, captured output) and
frames them with prose. It never describes code it could show.

All styling lives in `assets/v02.css`. Behaviour lives in three small scripts:
`assets/theme.js` (theme and table labels, every page), `assets/code.js` (code
frames), and `assets/flow.js` (drawn connectors on flow diagrams). There is no
build step.

## Surfaces

| Surface | Role | Theme |
|---|---|---|
| Docket (page) | A plain, cool sheet; no ruled lines, washes or glows | Light by default; dark on request |
| Sheet | Raised panels: callouts, cards, schema entries | Follows page theme |
| File exhibit | Configuration and source (`yaml`, `json`, `python`, ...) | Follows page theme |
| Terminal exhibit | Every `language-bash` block | Always the soft slate slab |

## Tokens

Colours are tokens on `:root` (light) and `:root[data-theme="dark"]`. Light is
the default for every visitor, whatever their OS prefers; dark exists only as
the visitor's explicit choice through the top-bar toggle, which `theme.js`
persists (storage failures fall back to light) and applies from `<head>`
before first paint. Every styled page loads
`<script src="/assets/theme.js"></script>` directly after the stylesheet.
Never write a colour literal in a rule; add or reuse a token.

- Page: `--paper`, `--sheet`, `--ink`, `--ink-soft`, `--muted`, `--line`,
  `--line-strong`
- Form ink (labels, section marks): `--form`; seal (the one warm colour):
  `--seal`
- Verdicts: `--allow` / `--allow-wash`, `--deny` / `--deny-wash`
- Syntax roles: `--tok-key`, `--tok-string`, `--tok-number`, `--tok-boolean`,
  `--tok-comment`, `--tok-punct`, `--tok-anchor`, `--tok-keyword`,
  `--tok-function`, `--tok-deleted`; the slate slab uses the `--night-*` set
- Flow diagrams: `--flow-line`, `--flow-spark`

Every text and token colour meets WCAG AA (4.5:1) on the surface it sits on.
Lowest measured pairs: light, muted on `--paper-deep` at 5.27:1; dark, deny on
its wash at 6.27:1. Re-measure when changing any colour.

## Spacing

Rhythm comes from tokens, never one-off values: `--space-1` to `--space-9`,
`--section-gap` (above every section heading), `--block-gap`, `--page-pad-*`,
`--hero-pad-*`, `--frame-pad-x/y` (inside code frames), `--card-pad`, and
`--grid-gap`. Narrow screens retune the tokens, not the rules.

Corners come from three tokens by role: `--radius` (frames, cards, callouts,
buttons), `--radius-sm` (inline code, chips) and `--radius-lg` (the dark
band and full-width panels). Nothing is rounder than `--radius-lg`.

Prose measure is set with zero specificity (`:where(.page) :is(p, li)`), so
any component class (a record row, a jump list, a grid cell) overrides it
without a specificity fight.

## Type

Self-hosted in `assets/fonts/` (OFL, licences alongside): Archivo (variable
weight and width) for everything readable, JetBrains Mono for code, labels,
and identifiers. Mono is for code, data, and labels only, never decoration.
Functional text stays at or above 11px.

One scale for the whole site: every page title, in a hero or at the top of a
document, is `--t-display`; every section heading `--t-h2`; card and record
headings `--t-h3`; leads `--t-lead`; captions and footer `--t-small`; table
headers and record labels `--t-meta`; code `--t-code`. Narrow screens retune
`--t-display` and `--t-h2` in the 560px query, nothing else.

## Records

Lists that are registers (the casebook, the provenance spine, the consequence
index, a schema's metadata, a definition block) are ruled: a strong rule
opens them, hairlines separate rows, the first column sits flush with the
heading above, numerals are tabular, and nothing lights up under the pointer.
Tables follow the same rule: no cell inset on the first column, no row hover.

## Shell

Every styled page carries the same footer: the page's own closing line
(`.footer-line`), the site's fixed points (`.footer-nav`: specification,
hosted schemas, runnable proof, examples, community, privacy) and the licence
line. Generated pages take it from `spec/index.html`.

Every page's `<head>` carries a canonical URL and Open Graph and Twitter
metadata with its own title and description; the card is
`/assets/og-card.png` (1200 × 630), rendered from `scripts/og_card.html`
with the site's own type and tokens. The generated pages get the block from
`STYLE_HEAD` in `scripts/render_spec.py`.

## Code blocks

Write `<pre><code class="language-x">` and load, in this order,
`<script defer src="/assets/prism.js"></script><script defer src="/assets/code.js"></script>`.
`code.js` adds the exhibit tab (optional `data-filename` on the `<pre>`,
language label, copy button) and re-classes shell blocks before Prism runs:
blocks with `$ ` prompts become `terminal` (copy takes commands only), the
rest `shell-plain`. Verdict lines (`PASS`, `FAIL`, `DENY`, `ALLOW`,
`REFUSED`) and `E_*` codes are coloured. Never edit the text inside a block
for presentation.

Nothing on the site scrolls sideways, at any width. Code wraps: `code.js`
wraps each source line in `.line`, and wrapped continuations hang past the
line's own indentation. Long digests wrap too; they are never truncated to
fit. JSON is laid out one member per line with two-space indentation by a
lexical re-indent that copies every literal verbatim; the frame says it is
formatted, Copy takes the published bytes, and an Exact bytes toggle shows
them. Tables fit their column and, below 720px, reflow into stacked label and
value rows. `tests/test_layout_guards.py` fails on `overflow-x` scrolling, on
coloured side stripes, and on JSON lines that could be split but are not.

A page about code opens with a `figure.lead-exhibit` repeating its decisive
block verbatim, captioned with a link to where it appears.

## Flow diagrams

Where content describes a flow, chain, graph or handoff, draw it. A host with
`data-flow` gets connector lines and small travelling points from `flow.js`,
in an `aria-hidden` SVG layer beneath opaque nodes: `chain` joins consecutive
`.dag-node`s, `spread` fans `.spread-source` out to every `.spread-node`
(`data-copies="3"` draws three lines; stacked in one column the copies share
one trunk down the gutter and branch off at their node), and `handoff` /
`lifecycle` / `overwrite` use the edge lists in `flow.js` over
`[data-flow-id]` nodes. The homepage hero is a `handoff`: the gate's frame to
the run's frame. Geometry is measured and redrawn on resize, and under
reduced motion the lines stay and nothing moves. Load
`<script defer src="/assets/flow.js"></script>` on those pages.

## Generated pages

`scripts/render_spec.py` owns `spec/text/`, `spec/schemas/`, every
`spec/schemas/<name>/` field reference, and `schema/latest.json`. Rerun it
after changing a schema, the specification, or the shell in `spec/index.html`;
`tests/test_render_spec.py` fails on drift. Reference prose comes only from
the specification's field tables, and example values only from repository
documents that validate.

## Refused

Cream-and-serif editorial styling, gradient text, glow shadows, wide soft
shadows under bordered panels, bounce easing, icon glyphs or emoji standing
in for icons, and hiding or shortening content for layout. Also refused:
coloured side stripes or rails on nav items, cards and callouts; uppercase,
letter-spaced mono eyebrow labels; decorative glyph prefixes such as `§`;
number badges on every item; stat cards; ruled or grid-line backgrounds;
pills used as ornament; watermarks as filler; hover lifts; and any sideways
scrolling.
