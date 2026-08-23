# usemakoto.dev

This repository is the public documentation and hosted-schema candidate for Makoto v0.2: a
source-first, SLSA-like framework for data provenance and integrity.

Makoto lets a recipient answer three concrete questions:

1. Where did these data bytes originate?
2. Which append-only, hash-linked transformations produced the handed-off result?
3. Which receiver-authorized identities attested those claims, and do the metadata and data
   bytes still match their signed digests?

## Release status

v0.2 is an unreleased candidate. The deployed pages and schema files are public review
artifacts, not proof of a tagged release or an immutable release contract. The candidate pin
identifies the exact core commit used for the hosted schemas and demo; it does not make that
commit a v0.2.0 release.

The normative specification is [`spec/v0.2/spec.md`](spec/v0.2/spec.md), and the
[adversarial review record](docs/v0.2-adversarial-review.md) preserves completed findings and
excluded timeouts without claiming convergence. The runnable narrative is
[`demos/v0.2-end-to-end/`](demos/v0.2-end-to-end/), and the candidate hosted schemas are in
[`schema/v0.2/`](schema/v0.2/).

The older v0.1 SDK, verifier, examples, integration sketches, Makoto Levels, and L1-L3 pages are
historical design material. They are not wire-compatible with v0.2 and do not describe shipped
v0.2 packages or adapters.

## Repository layout

| Path | Contents |
|---|---|
| `index.html` | v0.2 candidate landing page |
| `spec/v0.2/` | normative v0.2 specification and reading page |
| `schema/v0.2/` | byte-for-byte copies of the core v0.2 schemas and catalog |
| `predicate/v0.2/` | origin and transformation predicate documentation |
| `vocab/v0.2/` | bounded extension-vocabulary documentation |
| `demos/v0.2-end-to-end/` | public producer-to-receiver proof and generated artifacts |
| `integrations/` | conceptual integration sketches; no packaged v0.2 adapters |
| `sdk/`, `verify/`, `levels/`, `examples/` | historical v0.1 material |

## Local review

The site has no production build step. Python tooling is managed with `uv`:

```bash
git clone https://github.com/makoto-project/usemakoto.dev
cd usemakoto.dev
uv sync --locked --dev
uv run python -m http.server 8080
```

Run the complete local gate before proposing a change:

```bash
uv run scripts/check_site.py --working-tree ../core
```

Working-tree mode is for local review against the sibling core checkout. A deployable review
candidate must pin an exact core commit; a release must pin the approved `v0.2.0` tag. Both must
pass their corresponding deployment-mode gate.

## Integration boundary

Airflow, Databricks, dbt, Kafka, Prefect, Spark, Dagster, Snowflake, Expanso, and Docling can
produce or consume Makoto evidence. They are not protocol dependencies. The inherited adapter
pages are conceptual examples only; packages such as `makoto-prefect`, `makoto-databricks`,
`@makoto/sdk`, and the unrelated PyPI project named `makoto` are not v0.2 distributions.

Docling is complementary: a document-processing pipeline could emit Makoto statements and
artifact profiles for its outputs, but Docling is not part of the Makoto protocol.

## Publication boundary

Merging source, tagging core, copying release artifacts, hosting schemas, and successfully
deploying `usemakoto.dev` are separate evidence lanes. A hosted candidate is explicitly a
review surface. Only a release pin tied to the approved `v0.2.0` tag is release evidence.

## License

Apache License 2.0. See [`LICENSE`](LICENSE).
