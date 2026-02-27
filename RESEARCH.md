# Makoto (誠): Data Integrity Framework

## Research Analysis & Framework Proposal

**Version:** 0.1.0-draft
**Date:** December 2025
**Status:** Initial Research & Discussion Draft

---

## Executive Summary

This document proposes **Makoto** with its **Makoto Levels** specification—a framework that brings SLSA-style assurance levels to data supply chains. While SLSA addresses "where, when, and how software artifacts were produced," Makoto addresses **"where, when, how, and through what transformations data was produced and processed."**

Makoto is not an extension of SLSA, but a sibling framework that shares its philosophy, level structure, and attestation format while addressing the fundamentally different challenges of data pipelines. The framework produces DBOMs (Data Bills of Materials)—signed records of a dataset's origin, transformations, and chain of custody.

### Why This Matters Now

1. **AI/ML Governance**: EU AI Act, US Executive Order on AI, and emerging regulations require transparency about training data provenance
2. **Data Marketplace Trust**: Organizations sharing data need verifiable claims about origin and processing
3. **Compliance & Audit**: Financial services, healthcare, and government need immutable audit trails
4. **Supply Chain Attacks on Data**: The same threats that plague software supply chains now target data pipelines

### Core Insight

> SLSA proves software wasn't tampered with. Makoto proves data wasn't tampered with AND explains what happened to it.

---

## Part 1: Analysis of SLSA Framework

### What SLSA Gets Right (That We Must Preserve)

| SLSA Principle | Why It Works | Data Adaptation |
|----------------|--------------|-----------------|
| **Progressive Levels (L1-L3)** | Organizations adopt incrementally | Essential - data maturity varies widely |
| **Attestation Model** | Separates envelope/statement/predicate | Reuse directly via in-toto |
| **Threat-Focused Design** | Each level mitigates specific attacks | Need data-specific threat model |
| **Producer/Consumer Split** | Clear responsibilities | Map to data producers/consumers |
| **Unforgeable Provenance** | Cryptographic guarantees | Critical for data integrity |

### SLSA Build Levels Summary

| Level | Provenance | Isolation | Key Guarantee |
|-------|------------|-----------|---------------|
| L1 | Exists | Hosted | Documentation exists |
| L2 | Authentic | Hosted | Signed, tamper-evident |
| L3 | Unforgeable | Isolated | Cannot be forged by tenants |

### SLSA Attestation Structure (We Build On This)

```json
{
  "_type": "https://in-toto.io/Statement/v1",
  "subject": [{ "name": "artifact.tar.gz", "digest": {"sha256": "..."} }],
  "predicateType": "https://slsa.dev/provenance/v1",
  "predicate": {
    "buildDefinition": { "buildType": "...", "externalParameters": {...} },
    "runDetails": { "builder": {"id": "..."}, "metadata": {...} }
  }
}
```

---

## Part 2: The Data Provenance Problem

### How Data Differs from Software Artifacts

| Dimension | Software Artifacts | Data |
|-----------|-------------------|------|
| **Cardinality** | Discrete builds | Continuous streams OR large batches |
| **Transformation** | One build step | Many ETL/processing stages |
| **Granularity** | File/package | Record/row/window/table/dataset |
| **Privacy** | Generally public | May contain PII/sensitive data |
| **Velocity** | Build-per-release | Millions of events/second |
| **Lineage Depth** | Source → Binary | Source → Transform₁ → Transform₂ → ... → TransformN |

### Data-Specific Threats (Extending SLSA Threat Model)

| Threat | Description | SLSA Parallel | Makoto Mitigation |
|--------|-------------|---------------|-----------------|
| **D1: Source Falsification** | Claiming data came from authoritative source when it didn't | (A) Producer | Origin attestation with verifiable source binding |
| **D2: Collection Tampering** | Modifying data during collection/ingestion | (B) Source Modification | Signed collection attestations |
| **D3: Transform Opacity** | Hiding what transformations were applied | (E) Build Process | Transform-level attestations |
| **D4: Lineage Forgery** | Fabricating data lineage/history | (F) Artifact Publication | Chained attestations with hash linking |
| **D5: Stream Injection** | Inserting unauthorized records into streams | (D) External Parameters | Window-based integrity verification |
| **D6: Aggregation Manipulation** | Tampering with aggregate statistics | (E) Build Process | Verifiable computation attestations |
| **D7: Privacy Leakage** | Provenance metadata exposing sensitive data | N/A (new) | Privacy-preserving attestation techniques |
| **D8: Time Manipulation** | Backdating or falsifying timestamps | N/A (new) | Trusted timestamping services |

### Existing Standards Landscape

| Standard | Focus | Relationship to Makoto |
|----------|-------|---------------------|
| [SLSA](https://slsa.dev/spec/v1.2/) | Software supply chain | Foundation framework |
| [in-toto](https://github.com/in-toto/attestation) | Attestation format | Direct adoption for attestation layer |
| [D&TA Data Provenance Standards](https://www.dtaalliance.org/work/data-provenance-standards) | Metadata fields | Incorporate as predicate content |
| [W3C PROV](https://www.w3.org/TR/prov-overview/) | Provenance data model | Inform lineage graph structure |
| [SPDX](https://spdx.dev/) | Software bill of materials | Model for Data Bill of Materials |

---

## Part 3: Makoto Framework Proposal

### Core Philosophy

1. **Build on SLSA, don't reinvent** - Use in-toto attestation format, SLSA level philosophy
2. **Data has lineage, not just provenance** - Track transformations, not just origin
3. **Scale to streams** - Solutions must work at millions of events/second
4. **Privacy by design** - Attestations must not leak sensitive data
5. **Progressive adoption** - L1 is achievable by anyone with a spreadsheet

### Makoto Level Definitions

#### Makoto L1: Provenance Exists
> "The data pipeline produces attestations that document data origin and processing."

| Requirement | Description |
|-------------|-------------|
| **Attestation Exists** | Machine-readable attestation accompanies data |
| **Origin Documented** | Source of data is recorded (may be self-attested) |
| **Transform Documented** | Processing steps are listed (best-effort) |
| **Format Compliance** | Uses Makoto attestation schema |

**Threats Mitigated:** D1 (partial), D3 (partial)
**Adoption Difficulty:** Low - can be manual/semi-automated

#### Makoto L2: Provenance is Authentic
> "Attestations are cryptographically signed by the data processor and cannot be tampered with after creation."

| Requirement | Description |
|-------------|-------------|
| **All L1 requirements** | Plus additional controls |
| **Signed Attestations** | Digital signatures from data processor |
| **Tamper-Evident** | Consumers can verify signature validity |
| **Timestamp Binding** | Attestations include verifiable timestamps |
| **Hash Chaining** | Each transform attestation references input hashes |

**Threats Mitigated:** D1, D2, D3, D4 (partial), D8
**Adoption Difficulty:** Medium - requires key management, signing infrastructure

#### Makoto L3: Provenance is Unforgeable
> "Attestations are generated by isolated infrastructure that data processing logic cannot influence."

| Requirement | Description |
|-------------|-------------|
| **All L2 requirements** | Plus additional controls |
| **Isolated Signing** | Signing keys inaccessible to data processing code |
| **Platform-Generated** | Attestations created by trusted control plane |
| **Deterministic Hashing** | Data hashes computed by platform, not user code |
| **Audit Trail** | All attestation operations logged immutably |

**Threats Mitigated:** D1-D6, D8
**Adoption Difficulty:** High - requires trusted execution environment or platform support

---

### Makoto Attestation Schema

Building on in-toto Statement format with data-specific predicates:

#### Data Origin Attestation

```json
{
  "_type": "https://in-toto.io/Statement/v1",
  "subject": [{
    "name": "dataset:customer_transactions_2025",
    "digest": {
      "sha256": "abc123...",
      "recordCount": "1000000",
      "merkleRoot": "def456..."
    }
  }],
  "predicateType": "https://makoto.dev/origin/v1",
  "predicate": {
    "origin": {
      "source": "https://api.partner.com/transactions",
      "sourceType": "api",
      "collectionMethod": "pull",
      "collectionTimestamp": "2025-12-20T10:00:00Z",
      "geography": "US-WEST",
      "consent": {
        "type": "contractual",
        "reference": "https://legal.example.com/dpa/2025"
      }
    },
    "collector": {
      "id": "https://expanso.io/collectors/prod-west-1",
      "version": {"expanso-cli": "1.2.3"}
    },
    "schema": {
      "format": "json-lines",
      "schemaRef": "https://schemas.example.com/transactions/v2"
    }
  }
}
```

#### Data Transform Attestation

```json
{
  "_type": "https://in-toto.io/Statement/v1",
  "subject": [{
    "name": "dataset:customer_transactions_anonymized",
    "digest": {
      "sha256": "xyz789...",
      "recordCount": "1000000",
      "merkleRoot": "ghi012..."
    }
  }],
  "predicateType": "https://makoto.dev/transform/v1",
  "predicate": {
    "inputs": [{
      "name": "dataset:customer_transactions_2025",
      "digest": {"sha256": "abc123..."},
      "attestationRef": "https://attestations.example.com/abc123"
    }],
    "transform": {
      "type": "https://makoto.dev/transforms/anonymization",
      "name": "PII Removal Pipeline",
      "version": "1.0.0",
      "parameters": {
        "fields_removed": ["email", "phone", "ssn"],
        "fields_hashed": ["customer_id"],
        "k_anonymity": 5
      },
      "codeRef": {
        "uri": "git+https://github.com/example/pipelines@v1.0.0",
        "digest": {"sha256": "..."}
      }
    },
    "executor": {
      "id": "https://expanso.io/pipelines/prod-1",
      "platform": "expanso",
      "version": {"expanso-runtime": "2.1.0"}
    },
    "metadata": {
      "startedOn": "2025-12-20T10:05:00Z",
      "finishedOn": "2025-12-20T10:15:00Z",
      "recordsProcessed": 1000000,
      "recordsDropped": 0
    }
  }
}
```

#### Stream Window Attestation (For High-Throughput)

```json
{
  "_type": "https://in-toto.io/Statement/v1",
  "subject": [{
    "name": "stream:sensor_readings:window_20251220_1000",
    "digest": {
      "merkleRoot": "window_merkle_root_here",
      "windowStart": "2025-12-20T10:00:00Z",
      "windowEnd": "2025-12-20T10:01:00Z",
      "recordCount": "50000"
    }
  }],
  "predicateType": "https://makoto.dev/stream-window/v1",
  "predicate": {
    "stream": {
      "id": "sensor_readings",
      "partitions": ["partition_0", "partition_1", "partition_2"]
    },
    "window": {
      "type": "tumbling",
      "duration": "PT1M",
      "watermark": "2025-12-20T09:59:55Z"
    },
    "integrity": {
      "merkleTree": {
        "algorithm": "sha256",
        "leafCount": 50000,
        "root": "..."
      },
      "previousWindow": {
        "windowId": "window_20251220_0959",
        "merkleRoot": "previous_root_here"
      }
    },
    "aggregates": {
      "checksum": "aggregate_checksum",
      "statistics": {
        "min_timestamp": "...",
        "max_timestamp": "...",
        "avg_value": 42.5
      }
    }
  }
}
```

---

### Data Bill of Materials (DBOM)

Analogous to SBOM for software, DBOM documents all data sources and transformations:

```json
{
  "dbomVersion": "1.0.0",
  "dataset": {
    "name": "ml_training_dataset_v3",
    "version": "3.0.0",
    "created": "2025-12-20T12:00:00Z"
  },
  "sources": [
    {
      "name": "customer_transactions",
      "attestationRef": "https://attestations.example.com/txn_origin",
      "makotoLevel": "L2",
      "geography": "US",
      "consentType": "contractual"
    },
    {
      "name": "public_weather_data",
      "attestationRef": "https://attestations.example.com/weather_origin",
      "makotoLevel": "L1",
      "geography": "GLOBAL",
      "license": "CC-BY-4.0"
    }
  ],
  "transformations": [
    {
      "order": 1,
      "name": "Join transactions with weather",
      "attestationRef": "https://attestations.example.com/join_transform"
    },
    {
      "order": 2,
      "name": "Anonymize PII",
      "attestationRef": "https://attestations.example.com/anon_transform"
    },
    {
      "order": 3,
      "name": "Feature engineering",
      "attestationRef": "https://attestations.example.com/feature_transform"
    }
  ],
  "lineageGraph": {
    "format": "graphviz-dot",
    "content": "digraph { A -> B -> C -> D }"
  }
}
```

---

## Part 4: Streaming Data Considerations

### The High-Throughput Challenge

At 1M events/second, we cannot:
- Sign every individual record (cryptographic overhead)
- Store attestations per-record (storage explosion)
- Wait for batches to complete (latency requirements)

### Proposed Solutions

#### 1. Merkle Tree Windows

```
Window: 1 minute of data (60M records at 1M/sec)

                 [Root Hash] ← This gets signed
                  /        \
           [Hash AB]      [Hash CD]
            /    \         /    \
        [A]    [B]     [C]    [D]   ← Leaf hashes (batches of 15M records)
```

**Tradeoffs:**
- ✅ Single signature per window
- ✅ Can verify any record with O(log n) proof
- ⚠️ Must wait for window to close
- ⚠️ Verification requires merkle proof

#### 2. Hash Chains (Blockchain-lite)

```
Window₁ → Window₂ → Window₃ → Window₄
  ↓          ↓          ↓          ↓
 H(W₁)    H(W₂|H₁)   H(W₃|H₂)   H(W₄|H₃)
```

Each window's attestation includes hash of previous window, creating tamper-evident chain.

#### 3. Probabilistic Attestation

For ultra-high-throughput where even windowing is too slow:

- Sample N% of records for full attestation
- Use statistical techniques to detect tampering
- Provide probabilistic guarantees, not absolute

**Use case:** IoT sensor streams where individual record integrity matters less than aggregate integrity.

---

## Part 5: Privacy-Preserving Provenance

### The Problem

Data attestations shouldn't leak sensitive information:
- Record counts may reveal business metrics
- Schema details may expose data structure
- Transformation parameters may reveal logic

### Proposed Techniques

#### 1. Commitment Schemes

Attest to a commitment (hash) that can be revealed later if needed:

```json
{
  "origin": {
    "source_commitment": "sha256(actual_source_uri + salt)",
    "reveal_policy": "court_order_only"
  }
}
```

#### 2. Zero-Knowledge Proofs

Prove properties without revealing data:
- "This dataset has ≥ 1M records" without revealing exact count
- "This data is from geography X" without revealing source

#### 3. Differential Privacy for Aggregates

When attesting to aggregate statistics, add calibrated noise:

```json
{
  "aggregates": {
    "record_count_range": "1M-2M",
    "privacy_budget_used": 0.1
  }
}
```

---

## Part 6: Integration with D&TA Data Provenance Standards

The [Data & Trust Alliance Data Provenance Standards v1.0.0](https://www.dtaalliance.org/work/data-provenance-standards) define 22 metadata fields. Makoto should incorporate these in the predicate:

### Mapping D&TA Fields to Makoto

| D&TA Category | D&TA Field | Makoto Location |
|---------------|------------|---------------|
| **Source** | Dataset title | `subject.name` |
| **Source** | Unique identifier | `subject.digest` |
| **Source** | Dataset issuer | `predicate.origin.issuer` |
| **Provenance** | Source | `predicate.origin.source` |
| **Provenance** | Data origin geography | `predicate.origin.geography` |
| **Provenance** | Method | `predicate.origin.collectionMethod` |
| **Provenance** | Data format | `predicate.schema.format` |
| **Use** | Consent documentation | `predicate.origin.consent.reference` |
| **Use** | License to use | `predicate.license` |
| **Use** | Intended data use | `predicate.intendedUse` |

---

## Part 7: Expanso as Makoto Platform

### Why Expanso Is Ideal for Makoto Implementation

Expanso's architecture aligns well with Makoto requirements:

| Expanso Feature | Makoto Requirement | Fit |
|-----------------|------------------|-----|
| Pipeline-based processing | Transform attestation | Natural fit - each pipeline step can emit attestation |
| Edge deployment | Distributed provenance | Attestations at point of collection |
| Bloblang transformations | Documented transforms | Transform code is the attestation content |
| Built-in observability | Audit logging | Existing infrastructure |

### Proposed Expanso Makoto Integration

#### Level 1: Attestation Output Component

Add a new output type `attestation` that emits Makoto attestations:

```yaml
name: customer-etl-pipeline
type: pipeline
config:
  input:
    kafka:
      addresses: ["broker:9092"]
      topics: ["raw_customers"]

  pipeline:
    processors:
      - mapping: |
          root = this
          root.email = deleted()  # Remove PII

  output:
    broker:
      outputs:
        - kafka:
            addresses: ["broker:9092"]
            topic: "processed_customers"

        # New: Makoto attestation output
        - makoto_attestation:
            level: L1
            output_type: transform
            origin_attestation: "${ORIGIN_ATTESTATION_URL}"
            signing: none  # L1 doesn't require signing
```

#### Level 2: Signed Attestations

```yaml
output:
  makoto_attestation:
    level: L2
    signing:
      method: ecdsa-p256
      key_source: env:SIGNING_KEY
    timestamp:
      service: https://timestamp.example.com
```

#### Level 3: Platform-Managed Signing

```yaml
output:
  makoto_attestation:
    level: L3
    signing:
      method: platform  # Expanso platform manages keys
      isolation: hardware  # HSM-backed
```

### Stream Attestation Pipeline

```yaml
name: sensor-ingestion
type: pipeline
config:
  input:
    mqtt:
      urls: ["tcp://sensors:1883"]
      topics: ["sensor/#"]

  pipeline:
    processors:
      # Existing processing
      - mapping: |
          root = this

      # Window-based attestation
      - makoto_window:
          window_type: tumbling
          window_duration: 1m
          merkle_algorithm: sha256

  output:
    broker:
      outputs:
        - kafka:
            topic: processed_sensors
        - makoto_attestation:
            level: L2
            attestation_type: stream_window
            chain_previous: true
```

---

## Part 8: Demo Site Architecture

### Proposed Demo Structure

```
demos/signed-data/
├── public/
│   ├── index.html           # Landing page with framework overview
│   ├── framework/           # Interactive framework documentation
│   │   ├── levels.html      # Makoto levels explained
│   │   ├── attestations.html # Attestation format deep-dive
│   │   └── threats.html     # Threat model visualization
│   ├── explorer/            # Live attestation explorer
│   │   └── index.html       # View/verify sample attestations
│   ├── demos/               # Interactive demonstrations
│   │   ├── batch.html       # Batch data attestation demo
│   │   ├── stream.html      # Streaming attestation demo
│   │   └── lineage.html     # Lineage graph visualization
│   └── compare/             # SLSA vs Makoto comparison
│       └── index.html
├── pipelines/               # Expanso pipeline examples
│   ├── batch-attestation-CLI.yaml
│   ├── stream-attestation-CLI.yaml
│   └── lineage-demo-CLI.yaml
└── attestations/            # Sample attestation files
    ├── origin-example.json
    ├── transform-example.json
    └── stream-window-example.json
```

---

## Part 9: Open Questions for Discussion

### Framework Design Questions

1. **Granularity**: What is the "artifact" in Makoto?
   - Individual record?
   - Batch/window?
   - Entire dataset?
   - Configurable per use case?

2. **Level Progression**: Should there be an L4?
   - L4 could require formal verification of transforms
   - L4 could require reproducible transformations

3. **Privacy Attestations**: How do we attest to PII handling?
   - Separate "privacy attestation" predicate type?
   - Integrated into transform attestations?

4. **Schema Evolution**: How do we handle schema changes in lineage?
   - Schema diffs in attestations?
   - Separate schema evolution attestations?

### Ecosystem Questions

1. **Attestation Storage**: Where do attestations live?
   - Alongside data?
   - Separate attestation registry?
   - Distributed ledger?

2. **Verification Tooling**: What tools are needed?
   - CLI for verification (like `cosign` for containers)
   - CI/CD integration
   - Visualization tools

3. **Key Management**: How do organizations manage signing keys?
   - Per-pipeline keys?
   - Per-organization keys?
   - Hardware security modules?

### Integration Questions

1. **SLSA Alignment**: How formally do we align with SLSA?
   - Same organization (OpenSSF)?
   - Separate but compatible?
   - Extension of SLSA spec?

2. **in-toto Compatibility**: Do we propose new predicate types to in-toto?

3. **D&TA Relationship**: How do we align with OASIS DPS TC?

---

## References

### Primary Sources

- [SLSA Specification v1.2](https://slsa.dev/spec/v1.2/) - Foundation framework
- [in-toto Attestation Framework](https://github.com/in-toto/attestation) - Attestation format
- [D&TA Data Provenance Standards](https://www.dtaalliance.org/work/data-provenance-standards) - Metadata fields
- [OASIS Data Provenance Standards TC](https://www.oasis-open.org/2025/03/06/oasis-to-advance-data-provenance-standards/) - Standardization effort

### Related Work

- [W3C PROV Ontology](https://www.w3.org/TR/prov-overview/) - Provenance data model
- [SPDX Specification](https://spdx.dev/) - Software bill of materials
- [Sigstore](https://sigstore.dev/) - Keyless signing infrastructure

---

## Appendix A: Glossary

| Term | Definition |
|------|------------|
| **Attestation** | A cryptographically signed statement about data or a data operation |
| **DBOM** | Data Bill of Materials - complete lineage documentation |
| **Makoto** | Data Supply-chain Levels for Attestation |
| **Lineage** | The complete chain of transformations data has undergone |
| **Merkle Root** | Root hash of a Merkle tree, enabling efficient integrity verification |
| **Origin** | The original source from which data was collected |
| **Predicate** | The metadata payload in an in-toto attestation |
| **Provenance** | Verifiable information about where data came from and how it was processed |
| **Transform** | Any operation that modifies, filters, or combines data |
| **Window** | A bounded subset of a data stream for attestation purposes |

---

## Appendix B: Example Attestation Verification Flow

```
1. Consumer receives dataset + attestation bundle

2. Verify attestation signature
   └── Check signer is trusted data processor

3. Verify subject binding
   └── Hash dataset, compare to attestation subject.digest

4. Verify lineage chain
   └── For each input attestation:
       └── Recursively verify (steps 2-4)

5. Verify transform compliance
   └── Check transform type is acceptable
   └── Check parameters meet policy

6. Verify Makoto level claims
   └── Check attestation meets claimed level requirements
```
