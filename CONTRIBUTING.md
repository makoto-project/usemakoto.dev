# Contributing to Makoto

Makoto is an Apache-2.0 open-source project. The protocol is still a v0.2 review candidate, so
clear failure reports, real data-system requirements, schema critiques, interoperability tests,
documentation fixes, and implementation patches are all useful contributions.

## Pick the right repository

- [`makoto-project/makoto`](https://github.com/makoto-project/makoto) contains the protocol,
  schemas, reference CLI and library, verifier, tests, and runnable end-to-end demo.
- [`makoto-project/usemakoto.dev`](https://github.com/makoto-project/usemakoto.dev) contains the
  public website and the checked mirror of candidate schemas and demo evidence.

Open a GitHub issue before a large protocol or compatibility change so the intended behavior and
test evidence can be discussed first. Small corrections can go directly to a pull request.

## High-value ways to help

1. Run the [end-to-end proof](https://usemakoto.dev/demos/v0.2-end-to-end/) against the pinned
   candidate and report anything that is unclear or nondeterministic.
2. Describe a real producer-to-consumer data handoff and identify the claims, private rules, and
   trust decisions Makoto would need to carry.
3. Propose a failing conformance fixture for an ambiguity, attack, or interoperability edge case.
4. Review a JSON Schema for portability, closure pinning, bounded evaluation, and private-profile
   use.
5. Improve an example, integration sketch, or explanation without presenting an experiment as a
   released SDK or adapter.

## Local website checks

The website has no production build step. Python tooling is managed with `uv`.

```bash
git clone https://github.com/makoto-project/usemakoto.dev.git
cd usemakoto.dev
uv sync --locked --dev
uv run scripts/check_site.py --working-tree ../core
```

Before a pull request, run the repository checks documented in `README.md`. Changes to the hosted
v0.2 schemas, mirrored specification, or demo evidence must originate in the core repository and
be synchronized through the repository script; do not hand-edit those public mirrors.

## Review expectations

- Preserve the candidate-versus-release boundary. Do not describe v0.2 as tagged, released, or
  fully conformant until those facts are independently true.
- Add a test for new validation behavior, navigation contracts, or failure cases.
- Keep private organizational profiles separate from the portable protocol core.
- Do not commit credentials, private data, generated caches, or dependency directories.
- Keep changes attributable to the human contributor; do not add AI co-author boilerplate.

Formal governance has not been established yet. Repository history, issue discussion, reviewable
tests, and explicit technical evidence are the current decision record.
