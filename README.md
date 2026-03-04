# usemakoto.dev

The specification website for **Makoto (誠)** — a data integrity framework that brings SLSA-style assurance levels to data pipelines.

**Live site:** [https://usemakoto.dev](https://usemakoto.dev)

---

## What's Here

This repo is the source for `usemakoto.dev`. It contains:

| Path | Contents |
|------|----------|
| `index.html` | Landing page |
| `spec/` | Makoto Levels specification (L1/L2/L3) |
| `threats/` | Data supply chain threat model |
| `examples/` | Sample attestation JSON files |
| `levels/` | Per-level requirements detail |
| `privacy/` | Privacy-preserving attestation techniques |
| `comparison/` | Makoto vs SLSA vs DVC vs checksums |
| `attestations/` | Live attestation format examples |
| `assets/` | CSS, JS, images |
| `expanso/` | Expanso integration notes |

---

## How Deploys Work

Pushes to `main` auto-deploy to GitHub Pages via the [deploy workflow](.github/workflows/deploy.yml):

```
main → GitHub Actions → gh-pages branch → GitHub Pages → usemakoto.dev
```

DNS is managed via Cloudflare (proxied). HTTPS is handled by Cloudflare — no certificate configuration needed at the GitHub level.

**Deploy time:** ~30 seconds after merging to `main`.

---

## Local Development

No build step — it's static HTML/CSS/JS.

```bash
git clone https://github.com/makoto-project/usemakoto.dev
cd usemakoto.dev

# Serve locally (Python)
python3 -m http.server 8080
# → open http://localhost:8080

# Or with Node
npx serve .
```

---

## Contributing

Spec corrections, new examples, and clarifications welcome.

1. Fork the repo
2. Edit the relevant HTML or JSON files
3. Test locally (`python3 -m http.server`)
4. PR against `main` — deploy is automatic on merge

For large spec changes (new levels, new attestation types), open an issue first.

---

## Related

- **Demo repo:** [makoto-project/makoto](https://github.com/makoto-project/makoto) — 5 runnable demos, GitHub Action, DBOM generator
- **Full spec:** [usemakoto.dev/spec/](https://usemakoto.dev/spec/)
- **JSON Schema:** [dbom_schema.json](https://github.com/makoto-project/makoto/blob/main/dbom_schema.json)

---

## License

Apache 2.0
