# Makoto (誠) Implementation TODO

## Overview

This document tracks implementation tasks for Makoto and its Makoto Levels specification, organized into phases.

---

## Phase 1: Foundation & Research (Current)

### 1.1 Research Completion
- [x] Analyze SLSA v1.2 specification structure
- [x] Document SLSA levels and requirements
- [x] Analyze in-toto attestation framework
- [x] Review D&TA Data Provenance Standards v1.0.0
- [x] Document data-specific threat model
- [x] Draft Makoto level definitions (L1, L2, L3)
- [x] Design attestation schema (origin, transform, stream-window)
- [x] Design Data Bill of Materials (DBOM) format
- [ ] Review with SLSA framework creator - **PENDING MEETING**
- [ ] Incorporate feedback from review

### 1.2 Demo Site Scaffold
- [x] Create `signed-data` demo directory
- [ ] Create landing page with framework overview
- [ ] Create framework documentation pages:
  - [ ] Levels explanation with visual diagrams
  - [ ] Attestation format documentation
  - [ ] Threat model visualization
  - [ ] SLSA vs Makoto comparison page
- [ ] Add sample attestation JSON files
- [ ] Create interactive attestation explorer

---

## Phase 2: Specification Refinement

### 2.1 Predicate Type Specifications
- [ ] Finalize `https://makoto.dev/origin/v1` predicate spec
  - [ ] Required fields
  - [ ] Optional fields
  - [ ] Field validation rules
  - [ ] Examples for each field
- [ ] Finalize `https://makoto.dev/transform/v1` predicate spec
- [ ] Finalize `https://makoto.dev/stream-window/v1` predicate spec
- [ ] Define DBOM specification
- [ ] Create JSON Schema files for validation
- [ ] Create Protocol Buffer definitions

### 2.2 Level Requirements Document
- [ ] Write formal L1 requirements
  - [ ] Producer requirements
  - [ ] Platform requirements
  - [ ] Verification requirements
- [ ] Write formal L2 requirements
- [ ] Write formal L3 requirements
- [ ] Define conformance testing criteria

### 2.3 Threat Model Document
- [ ] Expand threat descriptions (D1-D8)
- [ ] Document attack scenarios for each threat
- [ ] Map mitigations to specific requirements
- [ ] Create threat/level matrix

---

## Phase 3: Expanso Prototype Implementation

### 3.1 Core Components

#### Attestation Data Types
- [ ] Implement `MakotoOriginAttestation` struct
- [ ] Implement `MakotoTransformAttestation` struct
- [ ] Implement `MakotoStreamWindowAttestation` struct
- [ ] Implement attestation serialization (JSON)
- [ ] Implement attestation validation

#### Signing Infrastructure
- [ ] Implement in-memory signing (development)
- [ ] Implement file-based key loading
- [ ] Implement ECDSA P-256 signing
- [ ] Implement signature verification
- [ ] (Future) HSM integration for L3

#### Hashing & Merkle Trees
- [ ] Implement streaming hash computation
- [ ] Implement Merkle tree builder
- [ ] Implement Merkle proof generation
- [ ] Implement Merkle proof verification
- [ ] Implement hash chaining for windows

### 3.2 Bloblang Processor Extension

```yaml
# Target configuration format
pipeline:
  processors:
    - makoto_attest:
        type: transform
        level: L2
        signing_key: ${SIGNING_KEY}
```

- [ ] Design processor configuration schema
- [ ] Implement `makoto_attest` processor
- [ ] Implement input hash computation
- [ ] Implement output hash computation
- [ ] Implement attestation generation
- [ ] Implement attestation signing (L2+)
- [ ] Add processor to Expanso CLI

### 3.3 Output Component

```yaml
output:
  makoto_attestation:
    level: L2
    destination: file:///attestations/
```

- [ ] Design output configuration schema
- [ ] Implement `makoto_attestation` output
- [ ] Implement file output backend
- [ ] Implement HTTP output backend (registry)
- [ ] Implement Kafka output backend
- [ ] Add output to Expanso CLI

### 3.4 Stream Window Attestation

```yaml
pipeline:
  processors:
    - makoto_window:
        window_type: tumbling
        window_duration: 1m
        merkle_algorithm: sha256
```

- [ ] Design window configuration schema
- [ ] Implement tumbling window attestation
- [ ] Implement sliding window attestation
- [ ] Implement session window attestation
- [ ] Implement window hash chaining
- [ ] Implement watermark handling
- [ ] Implement late data handling

---

## Phase 4: Demo Pipelines

### 4.1 Batch Attestation Demo
- [ ] Create sample input dataset (CSV/JSON)
- [ ] Create origin attestation pipeline
- [ ] Create transform attestation pipeline
- [ ] Create lineage visualization
- [ ] Document the demo

### 4.2 Streaming Attestation Demo
- [ ] Create sample stream generator
- [ ] Create stream ingestion pipeline with window attestation
- [ ] Create stream transformation pipeline
- [ ] Create attestation chain visualization
- [ ] Document the demo

### 4.3 Full Lineage Demo
- [ ] Create multi-source data scenario
- [ ] Create multi-stage transformation pipeline
- [ ] Generate complete DBOM
- [ ] Create lineage graph visualization
- [ ] Document the demo

---

## Phase 5: Verification Tooling

### 5.1 CLI Verification Tool
- [ ] Design CLI interface
  ```bash
  makoto verify --attestation attestation.json --data dataset.json
  makoto verify-chain --attestation final.json
  makoto verify-level --attestation attestation.json --level L2
  ```
- [ ] Implement attestation parsing
- [ ] Implement signature verification
- [ ] Implement hash verification
- [ ] Implement level compliance checking
- [ ] Implement lineage chain verification
- [ ] Implement human-readable output
- [ ] Implement JSON output for automation

### 5.2 Web Explorer
- [ ] Create attestation upload/paste interface
- [ ] Create attestation visualization
- [ ] Create signature verification display
- [ ] Create lineage graph rendering
- [ ] Create level compliance indicator

---

## Phase 6: Documentation & Website

### 6.1 Specification Website
- [ ] Set up makoto.dev domain (or subdomain of expanso.io)
- [ ] Create specification landing page
- [ ] Create level requirements pages
- [ ] Create attestation format pages
- [ ] Create threat model page
- [ ] Create getting started guide

### 6.2 Integration Guides
- [ ] Expanso integration guide
- [ ] Generic Python integration guide
- [ ] Generic Go integration guide
- [ ] Kafka integration guide
- [ ] Cloud storage integration guide

### 6.3 Examples Repository
- [ ] Create makoto-examples repository
- [ ] Add batch processing examples
- [ ] Add stream processing examples
- [ ] Add verification examples
- [ ] Add CI/CD integration examples

---

## Phase 7: Community & Standardization

### 7.1 Community Engagement
- [ ] Publish blog post introducing Makoto
- [ ] Present at relevant conferences/meetups
- [ ] Create GitHub discussions
- [ ] Establish contribution guidelines

### 7.2 Standardization Path
- [ ] Engage with in-toto project for predicate type acceptance
- [ ] Engage with SLSA community for alignment
- [ ] Consider OASIS DPS TC alignment
- [ ] Consider OpenSSF involvement

---

## Immediate Next Steps (This Week)

### For Presentation to SLSA Creator

1. **Finalize RESEARCH.md** - Ensure comprehensive and well-organized
2. **Create Visual Diagrams**:
   - [ ] Makoto level comparison chart
   - [ ] Attestation flow diagram
   - [ ] Streaming window attestation diagram
   - [ ] SLSA → Makoto mapping diagram
3. **Prepare Discussion Points**:
   - [ ] Key differences from SLSA
   - [ ] Why data needs different treatment
   - [ ] Proposed collaboration model
   - [ ] Standardization path questions

### For Demo Site

4. **Create Landing Page** (`index.html`):
   - [ ] Executive summary
   - [ ] Key concepts
   - [ ] Level overview
   - [ ] Call to action

5. **Create Sample Attestations**:
   - [ ] `attestations/origin-example.json`
   - [ ] `attestations/transform-example.json`
   - [ ] `attestations/stream-window-example.json`
   - [ ] `attestations/dbom-example.json`

---

## Success Criteria

### Phase 1 Complete When:
- [ ] RESEARCH.md reviewed and approved
- [ ] Demo site accessible at demos.expanso.io/signed-data
- [ ] Feedback incorporated from SLSA creator meeting

### Phase 3 Complete When:
- [ ] Expanso CLI can generate L1 attestations
- [ ] Attestations validate against schema
- [ ] Demo pipeline produces working attestations

### Phase 5 Complete When:
- [ ] `makoto verify` CLI works end-to-end
- [ ] Web explorer can visualize attestations
- [ ] Verification documented and tested

### Phase 7 Complete When:
- [ ] Predicate types accepted by in-toto project
- [ ] Public specification published
- [ ] At least one external implementation

---

## Dependencies & Blockers

| Task | Depends On | Blocked By |
|------|------------|------------|
| Finalize predicate specs | SLSA creator feedback | Meeting scheduling |
| Expanso implementation | Predicate spec finalization | None |
| Standardization | Working implementation + adoption | Community engagement |

---

## Notes & Decisions Log

### 2025-12-20
- Initial research document created
- Decided to build on in-toto attestation format (not custom)
- Decided on three levels (L1, L2, L3) matching SLSA
- Identified streaming as key differentiator from SLSA
- Proposed Merkle tree approach for stream attestation

### Open Decisions
- [x] Name: Makoto (brand) + Data Provenance Levels / Makoto (spec) + DBOM (artifact) ✓
- [ ] Domain: makoto.dev vs expanso.io/makoto?
- [ ] Governance: Expanso-led vs community-led vs foundation?
