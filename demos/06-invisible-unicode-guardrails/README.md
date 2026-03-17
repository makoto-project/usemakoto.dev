# Demo 06: Invisible Unicode Guardrails

Analyzes text artifacts for invisible Unicode characters that hide content from
human reviewers while remaining present in the bytes.

## What it does

1. Loads two fixture files: `safe-visible.js` and `flagged-invisible.js`
2. Scans each for invisible/non-rendering Unicode codepoints
3. Emits Makoto artifacts (analysis, attestation, DBOM) for each
4. Applies policy: safe sample passes, flagged sample fails
5. Prints human-readable explanations

## Run it

```bash
uv run run.py
```

## Expected output

```
safe-visible.js:      PASS  (0 invisible codepoints)
flagged-invisible.js: FAIL  (128 invisible variation selectors)
```

Generated artifacts are written to `output/`.

## Safety

This demo never evaluates or executes hidden content. The flagged fixture
contains actual invisible Unicode variation selectors, but the encoded content
decodes only to an inert explanation string.

## Fixtures

| File | Description |
|------|-------------|
| `fixtures/safe-visible.js` | Clean JS utility, no invisible characters |
| `fixtures/flagged-invisible.js` | Same-looking JS with 128 hidden variation selectors |
| `fixtures/flagged-revealed.txt` | Annotated view showing what the invisible characters contain |
| `fixtures/analysis.*.json` | Pre-computed rendering analysis |
| `fixtures/attestation.*.json` | Pre-computed Makoto attestations |
| `fixtures/dbom.*.json` | Pre-computed Data Bills of Materials |

## Learn more

- [Invisible Unicode example](https://usemakoto.dev/examples/#invisible-unicode) — visual walkthrough
- [Demo 06 page](https://usemakoto.dev/demos/06/) — full narrative
- [D9: Display-Layer Obfuscation](https://usemakoto.dev/threats/#d9) — threat model entry
- [Render-safe verification](https://usemakoto.dev/verify/#render-safe) — spec guidance
