# The Makoto adopter framework

Makoto is a source-first, SLSA-like framework for data provenance and integrity. It gives a
recipient portable evidence for five questions:

1. Where did these exact data bytes begin?
2. What changed, in what dependency order?
3. Which receiver-authorized keys attested the source, each change, and the handoff?
4. Do the received metadata and artifact bytes still match those attestations?
5. Does the received structured data satisfy the recipient's own rules?

Makoto records claims. A valid bundle does not prove that a source told the truth, that a claimed
operation actually ran, that pseudonymized data is anonymous, or that the data is safe, high
quality, confidential, or legally compliant.

## The portable evidence model

- An origin statement binds a source claim to exact subject bytes.
- Every change adds an immutable transformation statement. It points to exact predecessor
  statements and predecessor subjects instead of editing history.
- A transformation has a nonempty set of inputs, so the same model supports linear histories,
  joins, fan-out, and multiple roots or heads. Array order never defines lineage.
- DSSE envelopes carry Ed25519 signatures. Statement identity is the digest of the decoded
  payload, not the outer envelope.
- Public or private JSON Schema profiles can validate statement metadata or supported JSON and
  NDJSON artifacts. Profile references pin the root and complete schema closure by digest.
- A separately signed handoff manifest commits to the exact roots, heads, statements, final
  artifacts, recipient, issued-at claim, and required artifact profiles.
- The unsigned bundle index maps logical identities to local files. It is never authoritative:
  paths remain inside the bundle, duplicates and unsafe paths fail, and identities are recomputed
  from bytes.

The signed handoff manifest is the summary record. Human views should render that exact payload
rather than inventing a second normative summary that can drift from it.

## Extending Makoto privately

A team can keep its JSON Schemas private. The producer signs a profile reference containing the
schema identifier, root digest, closure digest, target, and criticality. The receiver provisions
the exact schema closure separately into an offline catalog.

Catalog membership resolves schema bytes; it does not authorize the rule. Receiver policy or an
independent expectation must approve the exact profile. A digest identifies bytes, not quality,
confidentiality, ownership, or safety. A required or critical profile that cannot be resolved or
validated fails closed.

Makoto's profile dialect fixes validator behavior, disables network retrieval, bounds evaluation,
and defines deterministic reference resolution. That matters because pinning a schema without
pinning its dialect and closure would not produce portable validation.

## What “who attested” means

A key ID is not inherently a person or organization. A receiver-owned trust policy maps keys to
operator labels and authorizes them for specific sources, operation types, profiles, or handoffs.
Signature validity and signer authorization remain separate results, and receiver policy may
require more than one distinct authorized signature.

Key authorization is evaluated at the receiver-controlled evaluation time against optional key
validity windows. Makoto does not provide public revocation or trustworthy signing time. Offline
verification is therefore only as current as the receiver's trust-policy snapshot.

## Completeness, freshness, and replay

A valid hash-linked graph proves continuity among the statements presented. The signed handoff
manifest proves completeness relative to the exact set its authorized signer selected. Neither
property proves that the recipient received the newest valid handoff.

Independent receiver values provide the missing anchor. Expected manifest, head, artifact,
recipient, and nonce values must arrive through a receiver-controlled channel or lockfile, never
from the bundle under test. An expected digest can provide selection or rollback resistance when
its channel resists rollback. A maximum-age policy evaluates the signed `issuedAt` claim against
the receiver's clock. A receiver-generated, single-use nonce can provide replay resistance.

The runnable proof models that boundary with `receiver-inputs/accepted-handoff.json`. The receiver
approves that lock outside the transferred bundle; the demo fails if a newly generated sender
candidate differs. Verification then supplies its manifest, head, artifact, recipient, and
evaluation-time expectations explicitly.

Offline Makoto cannot reveal equivocation when an authorized sender gives different valid heads
to different recipients. It is not a transparency log.

## Verification stays layered

The reference verifier reports these checks separately:

- core and organizational schema validity;
- signature validity and signer authorization;
- metadata profile validity;
- graph continuity, roots, and heads;
- handoff completeness and independent anchors;
- artifact-byte integrity; and
- artifact-content profile validity.

It collects every failure that remains safe to evaluate and also designates one deterministic
primary error for automation. Artifact bytes that fail their signed digest are not parsed as
trusted structured data for a later profile pass.

## The checked walkthrough

[`demos/v0.2-end-to-end/generated/walkthrough/`](../demos/v0.2-end-to-end/artifacts/walkthrough/)
contains readable projections derived from the signed runnable demo:

1. the receiver-approved JSON Schema for the final public dataset;
2. the decoded origin statement;
3. the first change, which normalizes the source;
4. the second change, which removes a direct identifier, creates linkable pseudonyms, and buckets
   ages;
5. the decoded signed handoff payload;
6. receiver-policy labels for the keys that signed each claim; and
7. a compact positive verification report.

Tests prove these files still match the full signed envelopes and report. They are teaching views,
not another wire format. The same demo includes denials for altered bytes, altered metadata,
missing or rewired steps, an unauthorized signer, and a receiver-schema violation in a fresh,
internally consistent candidate.

For partitioned real-world datasets, the dataset-manifest schema commits to exact members and
supports partition-level verification. Re-serialization is a transformation: if a warehouse,
notebook, or export changes byte encoding, it should emit a new statement rather than pretend the
artifact stayed identical. Reproducibility may also require optional code, parameter, container,
and environment digests; a lineage edge alone is not execution proof.

## Metadata is durable

Do not place secrets, raw personal data, row samples, salts, or sensitive error text in signed
metadata. Opaque identifiers reduce disclosure, but low-entropy identifiers and schema digests can
still fingerprint private facts. Encrypt transport where required. Deleting an artifact does not
erase evidence that has already been distributed.
