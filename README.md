# usemakoto.dev

This repository contains Makoto's public documentation and hosted schemas. Makoto is a
source-first, SLSA-like framework for data provenance and integrity.

Makoto lets a recipient answer three concrete questions:

1. Where did these data bytes originate?
2. Which append-only, hash-linked transformations produced the handed-off result?
3. Which receiver-authorized identities attested those claims, and do the metadata and data
   bytes still match their signed digests?

## Release status

The current protocol is under review and has not been released. The deployed pages and schema
files are public review artifacts, not proof of a tagged release or an immutable release
contract. The checked core pin identifies the exact commit used for the hosted schemas and demo.

The normative specification is [`spec/v0.2/spec.md`](spec/v0.2/spec.md), and the
[adversarial review record](docs/v0.2-adversarial-review.md) preserves completed findings and
excluded timeouts without claiming convergence. The runnable narrative is
[`demos/v0.2-end-to-end/`](demos/v0.2-end-to-end/), and the hosted schemas are in
[`schema/v0.2/`](schema/v0.2/).

Earlier SDK, verifier, example, integration, and assurance concepts have been rewritten onto the
current protocol model. The public pages do not present a parallel legacy site or imply shipped
packages and adapters. Retired wire examples remain incompatible and are excluded from the
current documentation and deployment contract.

## Open-source project

Makoto is developed in public under Apache-2.0. The core specification, schemas, reference CLI,
verifier, demos, fixtures, and tests live in
[`makoto-project/makoto`](https://github.com/makoto-project/makoto). This website and checked
schema mirror live in
[`makoto-project/usemakoto.dev`](https://github.com/makoto-project/usemakoto.dev).

Read [`CONTRIBUTING.md`](CONTRIBUTING.md) for contribution paths. Useful contributions include
running the proof, bringing a real producer-to-consumer handoff, adding a denial fixture,
reviewing a schema, improving documentation, or submitting a tested implementation patch.

## Repository layout

| Path | Contents |
|---|---|
| `index.html` | public project overview |
| `spec/` | canonical, versionless specification reading page |
| `spec/v0.2/` | normative protocol text and technical identifier route |
| `schema/v0.2/` | byte-for-byte copies of the core v0.2 schemas and catalog |
| `predicate/v0.2/` | origin and transformation predicate documentation |
| `vocab/v0.2/` | bounded extension-vocabulary documentation |
| `demos/v0.2-end-to-end/` | public producer-to-receiver proof and generated artifacts |
| `examples/` | current proof and real-world scenario library |
| `tooling/` | truthful status of the reference CLI, hosted schemas, and SDK experiments |
| `integrations/` | current integration contract and platform-specific field notes |
| `community/`, `CONTRIBUTING.md` | public participation and contribution paths |
| `sdk/`, `verify/`, `validate/` | truthful implementation status and language recipes |
| `levels/` | assurance dimensions; no numbered security badge |

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
./scripts/check.sh --working-tree ../core
actionlint .github/workflows/deploy.yml
```

Working-tree mode is for local review against the sibling core checkout. Deployment pins an exact
core commit; release publication pins the approved tag. Both pass their corresponding gate. The
script runs the same formatting, lint, test, generated-navigation, rendered-walkthrough, and site
contract checks used by CI. `actionlint` is the additional local parser for workflow changes;
install it before editing `.github/workflows/`.

## Integration boundary

Orchestrators, warehouses, stream processors, catalogs, and other data tools can produce or
consume Makoto evidence. They are not protocol dependencies. The inherited adapter pages are
conceptual examples only; packages such as `makoto-prefect`, `makoto-databricks`, `@makoto/sdk`,
and the unrelated PyPI project named `makoto` are not v0.2 distributions.

## Publication boundary

Merging source, tagging core, copying release artifacts, hosting schemas, and successfully
deploying `usemakoto.dev` are separate evidence lanes. Only a release pin tied to the approved tag
is release evidence.

## License

Apache License 2.0. See [`LICENSE`](LICENSE).
