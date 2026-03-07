# Prompt: Generate a DBOM for a Hugging Face Dataset

You are generating a Data Bill of Materials (DBOM) for a public dataset hosted on Hugging Face.

A DBOM is a machine-readable, signed JSON document that captures three things:

1. **Source**: Where did this data come from? Who produced it? What version?
2. **Signature**: A hash that unambiguously identifies this dataset at this point in time.
3. **Lineage**: Every transformation applied between the raw source and the published dataset, in order, with input and output hashes at each step.

The goal is a document that any downstream consumer can use to verify the dataset's integrity, trace its full transformation history, and confirm the identity of the producer.

---

## Instructions

Given a Hugging Face dataset, produce a valid DBOM JSON document following the schema below.

### Rules

- `id` must follow the pattern `dbom:{huggingface_owner}/{dataset_name}@{version}`
- `created_by.identity` should point to a verifiable public key, preferably `https://github.com/{username}.keys`
- `signature.digest` must be a real SHA256 hash of the published dataset artifact. If you cannot compute it, use the placeholder format `sha256:COMPUTE_FROM_{artifact_description}` and note it clearly.
- `lineage` must be an ordered array of steps from raw source to final published artifact. Each step must include:
  - `step` (integer, 1-indexed)
  - `description` (plain English, one sentence)
  - `tool` and `tool_version` (use `null` if not versioned or unknown)
  - `inputs` (array of named inputs with URIs and digests where available)
  - `operations` (array of plain-English strings describing what was done)
  - `output_digest` (SHA256 of the output of this step, or placeholder)
- If a step involved human annotation, include `annotator_count` and note the annotation methodology.
- `attestations` is an array for third-party certifications or claims (leave empty `[]` if none exist yet).
- Do not invent facts. If provenance information is not publicly documented, use `null` and add a `"provenance_gap": true` flag on that field.
- Digests for intermediate steps that were never published should be marked `sha256:NOT_PUBLISHED` with a note.

### Schema

```json
{
  "dbom_version": "0.1.0",
  "id": "dbom:{owner}/{dataset}@{version}",
  "created_at": "{ISO8601 timestamp}",
  "created_by": {
    "name": "{author name}",
    "identity": "{public key URL or identifier}",
    "affiliation": "{institution or organization}"
  },

  "source": {
    "name": "{dataset name}",
    "uri": "{canonical URI on Hugging Face}",
    "version": "{version or commit SHA}",
    "license": "{SPDX license identifier}",
    "homepage": "{dataset homepage or paper URL}"
  },

  "signature": {
    "algorithm": "sha256",
    "digest": "{SHA256 of published artifact}",
    "signed_at": "{ISO8601 timestamp}",
    "signed_by": "{public key URL}"
  },

  "lineage": [
    {
      "step": 1,
      "description": "{one sentence description}",
      "tool": "{tool name}",
      "tool_version": "{version or null}",
      "repository": "{source repo URL if available, else omit}",
      "inputs": [
        {
          "name": "{input name}",
          "uri": "{URI if available}",
          "snapshot": "{date or version if applicable}",
          "digest": "{SHA256 or placeholder}"
        }
      ],
      "operations": [
        "{plain English description of operation 1}",
        "{plain English description of operation 2}"
      ],
      "output_digest": "{SHA256 or placeholder}"
    }
  ],

  "attestations": []
}
```

---

## What to research before generating

Before writing the DBOM, look up the following for the dataset:

1. The dataset card on Hugging Face (`https://huggingface.co/datasets/{owner}/{name}`)
2. The original paper or technical report if one exists
3. The GitHub repository for any processing or annotation scripts
4. The license and any known data governance documentation
5. Whether intermediate dataset versions or snapshots are publicly archived

Document any gaps where provenance information is not publicly available. These gaps are themselves useful signal — they show exactly where a DBOM would have required the producer to be more rigorous.

---

## Output format

Return only the JSON document. Do not include any preamble, explanation, or markdown code fences. The output should be valid, parseable JSON.

After the JSON, on a new line, add a section titled `## Provenance Gaps` that lists any fields where you used placeholders or `null`, and explains what information would be needed to fill them.
