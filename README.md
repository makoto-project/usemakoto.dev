# usemakoto.dev

The specification website for **Makoto (誠)** — a data integrity framework that brings SLSA-style assurance levels to data pipelines.

**Live site:** [https://usemakoto.dev](https://usemakoto.dev)

> **100% Open Source.** Makoto is, and will always be, fully open source under the [MIT License](LICENSE) — an [OSI-approved](https://opensource.org/licenses/MIT) license. There is no "open core," no proprietary tier, no source-available trickery. The spec, the schema, the examples, and this site are all yours to read, fork, run, and ship.

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
| `integrations/` | Platform integration concepts (Airflow, dbt, Spark, Kafka, Snowflake, Databricks, Dagster, Prefect, Expanso) |
| `assets/` | CSS, JS, images |
| `expanso/` | Redirect → `integrations/expanso/` |

---

## Platform Integrations

Makoto is platform-agnostic — the same DBOM format works on any data pipeline. The `integrations/` directory contains conceptual integration pages for common platforms, each showing how Makoto attestations attach using that platform's native APIs:

| Platform | Category | Primary integration pattern |
|----------|----------|------------------------------|
| [Apache Airflow](https://usemakoto.dev/integrations/airflow/) | Orchestration | `MakotoOperator` + `on_success_callback` |
| [dbt](https://usemakoto.dev/integrations/dbt/) | Transformations | Post-hook macro + `on-run-end` |
| [Apache Spark](https://usemakoto.dev/integrations/spark/) | Distributed compute | `SparkListener` + UDF + writer wrapper |
| [Apache Kafka](https://usemakoto.dev/integrations/kafka/) | Streaming | Producer/Consumer Interceptor, Connect SMT |
| [Snowflake](https://usemakoto.dev/integrations/snowflake/) | Warehouse | Stored procedure + Task + External Function signing |
| [Databricks](https://usemakoto.dev/integrations/databricks/) | Lakehouse | Unity Catalog hooks + Job webhooks + DLT expectations |
| [Dagster](https://usemakoto.dev/integrations/dagster/) | Orchestration | `@makoto_asset` + materialization sensor + IO manager |
| [Prefect](https://usemakoto.dev/integrations/prefect/) | Orchestration | State hooks + `MakotoResult` serializer |
| [Expanso](https://usemakoto.dev/integrations/expanso/) | Edge pipelines | Bloblang mapping + custom processor plugin |

All integrations are **conceptual** — they use real platform APIs, but the Makoto-specific pieces (operators, hooks, processors, decorators) are illustrative sketches. To ship one for real, [open an issue](https://github.com/makoto-project/makoto/issues).

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

Licensed under the **MIT License** — see [LICENSE](LICENSE) for the full text.

This project is, and always will be, **100% open source**. MIT was chosen specifically because it is:

- **[OSI-approved](https://opensource.org/licenses/MIT)** — meets the Open Source Definition (free to use, modify, redistribute, and sublicense, including for commercial purposes)
- **Maximally permissive** — short, plain, and battle-tested; legal review takes minutes, not weeks, which lowers adoption friction for teams shipping Makoto-conformant pipelines
- **Universally compatible** — MIT-licensed work can be combined with virtually any other OSS license (GPL, Apache, BSD, etc.), so downstream tools and specs can ingest the schema and examples without conflict

If you need a different OSI-approved license for compatibility (e.g., Apache-2.0, BSD), open an issue and we'll discuss.
