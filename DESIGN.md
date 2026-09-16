# Design system: the evidence docket

The site files real exhibits (configuration, commands, captured output) and
frames them with prose. It never describes code it could show.

All styling lives in `assets/v02.css`; code-block behaviour lives in
`assets/code.js`. There is no build step.

## Surfaces

| Surface | Role | Theme |
|---|---|---|
| Docket (page) | Carbon-form paper with faint printed rules | Light and dark from the same tokens |
| Sheet | Raised panels: callouts, cards, schema entries | Follows page theme |
| File exhibit | Configuration and source (`yaml`, `json`, `python`, ...) | Follows page theme |
| Terminal exhibit | Every `language-bash` block | Always the night slab |

## Tokens

Colours are tokens on `:root`, redefined under
`@media (prefers-color-scheme: dark)` and `:root[data-theme="dark"]`. Never
write a colour literal in a rule; add or reuse a token.

- Page: `--paper`, `--sheet`, `--ink`, `--ink-soft`, `--muted`, `--line`,
  `--line-strong`
- Form ink (labels, section marks): `--form`; seal (the one warm colour):
  `--seal`
- Verdicts: `--allow` / `--allow-wash`, `--deny` / `--deny-wash`
- Syntax roles: `--tok-key`, `--tok-string`, `--tok-number`, `--tok-boolean`,
  `--tok-comment`, `--tok-punct`, `--tok-anchor`, `--tok-keyword`,
  `--tok-function`, `--tok-deleted`; the night slab uses the `--night-*` set

Every text and token colour meets WCAG AA (4.5:1) on the surface it sits on;
the lowest measured pair is comments on the file zebra at 5.33:1. Re-measure
when changing any colour.

## Type

Self-hosted in `assets/fonts/` (OFL, licences alongside): Archivo (variable
weight and width) for everything readable, JetBrains Mono for code, labels,
and identifiers. Mono is for code, data, and labels only, never decoration.
Functional text stays at or above 11px.

## Code blocks

Write `<pre><code class="language-x">` and load, in this order,
`<script defer src="/assets/prism.js"></script><script defer src="/assets/code.js"></script>`.
`code.js` adds the exhibit tab (optional `data-filename` on the `<pre>`,
language label, copy button) and re-classes shell blocks before Prism runs:
blocks with `$ ` prompts become `terminal` (copy takes commands only), the
rest `shell-plain`. Verdict lines (`PASS`, `FAIL`, `DENY`, `ALLOW`,
`REFUSED`) and `E_*` codes are coloured. Never edit the text inside a block
for presentation; long lines scroll inside the block, never the page.

A page about code opens with a `figure.lead-exhibit` repeating its decisive
block verbatim, captioned with a link to where it appears.

## Generated pages

`scripts/render_spec.py` owns `spec/text/`, `spec/schemas/`, every
`spec/schemas/<name>/` field reference, and `schema/latest.json`. Rerun it
after changing a schema, the specification, or the shell in `spec/index.html`;
`tests/test_render_spec.py` fails on drift. Reference prose comes only from
the specification's field tables, and example values only from repository
documents that validate.

## Refused

Cream-and-serif editorial styling, gradient text, glow shadows, wide soft
shadows under bordered panels, bounce easing, icon glyphs standing in for
icons, and hiding or shortening content for layout.
