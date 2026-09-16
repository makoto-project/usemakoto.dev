# Demo 06: Invisible Unicode Guardrails

Analyzes text artifacts for invisible Unicode characters that hide content from
human reviewers while remaining present in the bytes.

## What it does

1. Loads two fixture files: `safe-visible.js` and `flagged-invisible.js`
2. Scans each for invisible/non-rendering Unicode codepoints
3. Emits the rendering analysis for each
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

### v0.2 evidence fixtures

The earlier `attestation.*.json` and `dbom.*.json` fixtures were hand-written
v0.1 DBOM documents. They are back, regenerated as real v0.2 artifacts produced
by the reference CLI rather than written by hand:

| File | Description |
|------|-------------|
| `fixtures/render-safe-origin-v1.schema.json` | Private profile schema: an origin claim must carry an NFC render-safety scan whose verdict is `pass` |
| `fixtures/render-safe.profile.json` | Digest-pinned profile reference produced by `makoto profile create` |
| `fixtures/receiver-policy.json` | Receiver trust policy; its one origin rule carries the profile as a `profileConstraints` entry |
| `fixtures/attestation.safe.json` | Signed DSSE origin envelope for `safe-visible.js`, carrying the scan and the profile |
| `fixtures/attestation.flagged.json` | Signed DSSE origin envelope for `flagged-invisible.js` with the profile **dropped** — the producer could not sign the claim with it attached |
| `fixtures/dbom.safe.json` | Signed v0.2 handoff manifest, the successor of the v0.1 DBOM roll-up |
| `fixtures/dbom.flagged.json` | Signed v0.2 handoff manifest for the flagged bundle |
| `fixtures/report.safe.json` | Receiver verification report — `"decision": "allow"` |
| `fixtures/report.flagged.json` | Receiver verification report — `"decision": "deny"`, `E_SIGNER_UNAUTHORIZED` |

Regenerate them against a Makoto core checkout:

```bash
uv run regenerate_v02_fixtures.py \
  /path/to/makoto /path/to/usemakoto.dev /tmp/demo06
```

Statement, manifest, and artifact digests are deterministic across runs; the
demo-only signing keys are generated fresh each time, so only the `signatures`
arrays and the policy digest change.

## Learn more

- [Invisible Unicode example](https://usemakoto.dev/examples/invisible-unicode/) — visual walkthrough
- [Demo 06 page](https://usemakoto.dev/demos/06/) — full narrative
- [D9: Display-Layer Obfuscation](https://usemakoto.dev/threats/#d9) — threat model entry
- [Render-safe verification](https://usemakoto.dev/verify/#render-safe) — spec guidance
