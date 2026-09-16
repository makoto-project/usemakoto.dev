import sys; sys.path.insert(0, 'build')
import shell

BODY = r"""
<span class="kicker">Receiver verification</span>
<h1>A signature is one check, not the verdict.</h1>
<p class="lead">A receiver should be able to verify the evidence without access to the producer&rsquo;s platform: parse the resources, authenticate each signed claim, decide whether each signer was authorized, reconstruct the source-to-handoff graph, resolve exact schemas, and hash the bytes that actually arrived.</p>

<section aria-labelledby="bindings"><div class="section-intro"><h2 id="bindings">Verify from your language</h2><a class="text-link" href="/sdk/">All language interfaces &rarr;</a></div><p>Each page below is a complete working path: install, validate structure against the hosted schemas, produce an attestation, verify a bundle, branch on a failed verdict, and read the report the verifier returns.</p>
<div class="grid">
<a class="card-v02 card-link" href="/verify/bash.html"><span class="tag">Bash</span><h3>Shell and CI</h3><p>Verify in a pipeline step with the reference CLI, <code>jq</code>, and a non-zero exit that stops the job.</p></a>
<a class="card-v02 card-link" href="/verify/python.html"><span class="tag">Python</span><h3>Ingestion gates</h3><p>Validate with <code>jsonschema</code>, drive the CLI through <code>subprocess</code>, and raise on any decision other than <code>allow</code>.</p></a>
<a class="card-v02 card-link" href="/verify/nodejs.html"><span class="tag">JavaScript</span><h3>Node services</h3><p>Compile hosted schemas with AJV 2020, spawn the verifier, and surface the primary error to the caller.</p></a>
<a class="card-v02 card-link" href="/verify/typescript.html"><span class="tag">TypeScript</span><h3>Typed report contract</h3><p>Declared types for the decision, check statuses, diagnostic codes, and a narrowing guard over the parsed report.</p></a>
<a class="card-v02 card-link" href="/verify/go.html"><span class="tag">Go</span><h3>Services and sidecars</h3><p>Struct-decode the report, run the verifier with <code>os/exec</code>, and fail closed on a malformed document.</p></a>
<a class="card-v02 card-link" href="/validate/"><span class="tag">Any language</span><h3>Structure only</h3><p><code>jq</code>, <code>check-jsonschema</code>, pydantic, AJV, and Go against the hosted Draft 2020-12 schemas.</p></a>
</div></section>

<section aria-labelledby="verdict"><h2 id="verdict">What a real verdict checks</h2><table class="stack-table verification-table"><thead><tr><th>Check</th><th>Question answered</th><th>What failure means</th></tr></thead><tbody>
<tr><td>Structure</td><td>Do the statements, envelopes, profiles, policy, and handoff match their JSON Schemas?</td><td>The evidence is malformed or violates a required profile.</td></tr>
<tr id="signatures"><td>Cryptography</td><td>Do the DSSE signatures authenticate the exact payload bytes?</td><td>The metadata changed, the signature is invalid, or the key does not match.</td></tr>
<tr><td>Authorization</td><td>Does receiver-owned policy trust each key for this source, operation, profile, and handoff?</td><td>A mathematically valid signature was made by the wrong party.</td></tr>
<tr><td>Graph</td><td>Does every transformation point to the exact predecessor statement and input artifact?</td><td>A step is missing, rewired, duplicated, or disconnected from an origin.</td></tr>
<tr><td>Handoff</td><td>Does the signed manifest commit to the exact roots, heads, profiles, statements, and final artifacts?</td><td>The presented graph may be continuous but incomplete.</td></tr>
<tr><td>Freshness</td><td>Does an independent expected manifest, head, nonce, artifact, or age bound match?</td><td>An older valid handoff may have been replayed.</td></tr>
<tr><td>Data bytes</td><td>Do the bytes received by the consumer match the signed artifact digest?</td><td>The data changed after the claim was made.</td></tr>
</tbody></table></section>

<section aria-labelledby="run"><h2 id="run">Run the reference verifier</h2><p>Start with the deterministic handoff fixture. It produces one allowed bundle and seven denial cases, so the first experience includes the failure boundary as well as the happy path.</p><pre><code class="language-bash">git clone https://github.com/makoto-project/makoto.git
cd makoto
uv sync --locked --dev
./scripts/demo-v0.2.sh --acceptance</code></pre><p>To inspect the receiver command directly:</p><pre><code class="language-bash">uv run makoto verify bundle demos/v0.2-end-to-end/generated/positive-bundle \
  --policy demos/v0.2-end-to-end/generated/receiver/policy.json \
  --schema-catalog demos/v0.2-end-to-end/generated/receiver/catalog.json \
  --expected-artifact demos/v0.2-end-to-end/generated/receiver/expected-artifact.json \
  --evaluation-time 2026-09-16T16:00:00Z \
  --json</code></pre><p>The report keeps schema, signature, authorization, profile, graph, completeness, freshness, and artifact checks separate. A single boolean would hide which trust boundary failed.</p><p><a href="/demos/v0.2-end-to-end/"><strong>Open the complete walkthrough and exact denial reports &rarr;</strong></a></p></section>

<section aria-labelledby="pipeline"><h2 id="pipeline">The fourteen ordered checks</h2><p>Verification is a fixed sequence, and the order is part of the contract. A later check reports <code>skipped</code> when an earlier one did not establish its prerequisite, so a report never implies more was proven than actually was. Every entry in <code>checks[]</code> carries an <code>id</code>, a <code>status</code> of <code>pass</code>, <code>fail</code>, <code>indeterminate</code>, <code>not_checked</code>, or <code>skipped</code>, and the <code>prerequisiteChecks</code> that caused a skip.</p>
<table class="wide-table"><caption>Scroll horizontally to see the diagnostic codes for each step.</caption><thead><tr><th>Step</th><th>Check <code>id</code></th><th>What it establishes</th><th>Diagnostic codes</th></tr></thead><tbody>
<tr><td>1</td><td><code>load-safely</code></td><td>The bundle unpacks inside its own root, within resource limits.</td><td><code>E_BUNDLE_UNSAFE_PATH</code>, <code>E_HANDOFF_REQUIRED</code>, <code>E_RESOURCE_LIMIT</code></td></tr>
<tr><td>2</td><td><code>parse-strictly</code></td><td>Every resource is well-formed JSON with no duplicate keys, and each envelope carries the expected payload type.</td><td><code>E_JSON_INVALID</code>, <code>E_JSON_DUPLICATE_KEY</code>, <code>E_ENVELOPE_MALFORMED</code>, <code>E_PAYLOAD_TYPE</code></td></tr>
<tr><td>3</td><td><code>index-payloads</code></td><td>Each payload is addressed by its own digest, so later steps reference exact bytes.</td><td><code>E_STATEMENT_DIGEST</code>, <code>E_JSON_INVALID</code>, <code>E_JSON_DUPLICATE_KEY</code></td></tr>
<tr><td>4</td><td><code>core-schemas</code></td><td>Statements, predicates, handoff, policy, and catalog match the pinned core schemas.</td><td><code>E_CORE_SCHEMA</code>, <code>E_CATALOG_INVALID</code>, <code>E_PREDICATE_SEMANTICS_UNSUPPORTED</code>, <code>E_PROFILE_TARGET_MISSING</code></td></tr>
<tr><td>5</td><td><code>signatures</code></td><td>Each DSSE signature authenticates the exact payload bytes that were signed.</td><td><code>E_SIGNATURE_INVALID</code></td></tr>
<tr><td>6</td><td><code>authorization-thresholds</code></td><td>Signer counts and thresholds satisfy receiver policy.</td><td><code>E_SIGNER_UNAUTHORIZED</code></td></tr>
<tr><td>7</td><td><code>metadata-profiles</code>, <code>authorization</code></td><td>Declared profiles resolve to pinned digests, and each key is authorized for this source, operation, and profile.</td><td><code>E_PROFILE_UNRESOLVED</code>, <code>E_PROFILE_INVALID</code></td></tr>
<tr><td>8</td><td><code>graph-dependency-artifacts</code></td><td>The artifacts a transformation claims as inputs match their declared digests and manifests.</td><td><code>E_ARTIFACT_DIGEST</code>, <code>E_DATASET_MANIFEST_INVALID</code>, <code>E_DATASET_MANIFEST_REQUIRED</code></td></tr>
<tr><td>9</td><td><code>graph</code></td><td>Every step binds a real predecessor and its exact subject, with no cycles or duplicated event identifiers.</td><td><code>E_PREDECESSOR_MISSING</code>, <code>E_PREDECESSOR_SUBJECT</code>, <code>E_INPUT_DIGEST</code>, <code>E_GRAPH_CYCLE</code>, <code>E_EVENT_ID_DUPLICATE</code></td></tr>
<tr><td>10</td><td><code>roots-and-heads</code></td><td>Each chain terminates at a valid origin.</td><td><code>E_ROOT_INVALID</code></td></tr>
<tr><td>11</td><td><code>completeness-anchor</code>, <code>freshness-anchors</code></td><td>The signed manifest set is complete, and the receiver&rsquo;s independent expectations for manifest, heads, artifacts, recipient, nonce, and age hold.</td><td><code>E_MANIFEST_SET</code>, <code>E_EXPECTED_MANIFEST</code>, <code>E_EXPECTED_HEAD</code>, <code>E_EXPECTED_ARTIFACT</code>, <code>E_HANDOFF_RECIPIENT</code>, <code>E_HANDOFF_NONCE</code>, <code>E_HANDOFF_STALE</code>, <code>E_FRESHNESS_REQUIRED</code>, <code>E_REQUIRED_PROFILE_MISSING</code></td></tr>
<tr><td>12</td><td><code>artifact-bytes</code></td><td>The bytes on disk hash to the signed artifact digest at the declared size.</td><td><code>E_ARTIFACT_MISSING</code>, <code>E_ARTIFACT_DIGEST</code>, <code>E_ARTIFACT_SIZE</code></td></tr>
<tr><td>13</td><td><code>artifact-profiles</code></td><td>The structured artifact satisfies the content rules its profile declares.</td><td><code>E_ARTIFACT_FORMAT</code>, <code>E_PROFILE_INVALID</code>, <code>E_REQUIRED_PROFILE_MISSING</code></td></tr>
<tr><td>14</td><td><code>decision</code></td><td>The single <code>allow</code>, <code>deny</code>, or <code>indeterminate</code> outcome derived from everything above.</td><td><code>E_RESOURCE_LIMIT</code></td></tr>
</tbody></table>
<p class="editorial-note"><strong>Why the order is published.</strong> A receiver that reruns these checks in a different order can reach a different answer from the same bundle. The sequence, the skip semantics, and the diagnostic codes are the interoperability surface, not an implementation detail.</p></section>

<section aria-labelledby="report"><h2 id="report">Reading the report</h2><p>Every run emits one document against <a href="/schema/v0.2/verification-report.schema.json">the verification-report schema</a>. Read <code>decision</code> first, then <code>primaryError</code> to learn which boundary failed, then <code>checks[]</code> to see what was actually established.</p>
<pre><code class="language-json">{
  "reportVersion": "0.2",
  "decision": "deny",
  "reportTruncated": false,
  "primaryError": "E_ARTIFACT_DIGEST",
  "bundleId": "handoff-2026-09-16",
  "evaluationTime": "2026-09-16T16:00:00Z",
  "policyDigest": { "sha256": "9f2c..." },
  "policyDigestEncoding": "exact-input-bytes",
  "coreCatalogDigest": { "sha256": "30b4..." },
  "summary": {
    "statementsTotal": 3,
    "statementsReachable": 3,
    "statementsValid": 3,
    "statementsAuthorized": 3,
    "signaturesTotal": 3,
    "signaturesValid": 3,
    "artifactsDeclared": 1,
    "artifactsChecked": 1,
    "roots": 1,
    "heads": 1
  },
  "checks": [
    { "id": "load-safely",     "status": "pass",  "prerequisiteChecks": [] },
    { "id": "parse-strictly",  "status": "pass",  "prerequisiteChecks": [] },
    { "id": "signatures",      "status": "pass",  "prerequisiteChecks": [] },
    { "id": "authorization",   "status": "pass",  "prerequisiteChecks": [] },
    { "id": "graph",           "status": "pass",  "prerequisiteChecks": [] },
    { "id": "artifact-bytes",  "status": "fail",  "prerequisiteChecks": [] },
    { "id": "artifact-profiles", "status": "skipped",
      "prerequisiteChecks": ["artifact-bytes"] }
  ],
  "errors": [
    {
      "code": "E_ARTIFACT_DIGEST",
      "step": 12,
      "causedByCheck": "artifact-bytes",
      "message": "artifact bytes do not match the signed digest",
      "context": { "artifact": "data/orders-2026-09-16.parquet" }
    }
  ],
  "warnings": [],
  "tool": { "name": "makoto", "version": "0.2.0" }
}</code></pre>
<ul class="evidence-trail">
<li><span>decision</span><strong>allow, deny, or indeterminate</strong>Treat anything other than <code>allow</code> as a refusal. <code>indeterminate</code> means the verifier could not establish the answer, which is not the same as proving the evidence good.</li>
<li><span>primaryError</span><strong>The one code that explains the outcome</strong>Route on this before reading the array. It is <code>null</code> on an allow.</li>
<li><span>checks</span><strong>What was actually established</strong>A <code>skipped</code> status with a non-empty <code>prerequisiteChecks</code> is the verifier saying it did not test this, rather than that it passed.</li>
<li><span>errors</span><strong>Ordered diagnostics</strong>Each carries <code>code</code>, <code>step</code>, <code>causedByCheck</code>, a human <code>message</code>, and a typed <code>context</code>.</li>
<li><span>warnings</span><strong>Non-fatal gaps</strong>Codes such as <code>W_FRESHNESS_NOT_CHECKED</code> or <code>W_ARTIFACT_UNPROFILED</code> mark evidence the run did not cover. An allow with warnings is a narrower claim than an allow without them.</li>
<li><span>reportTruncated</span><strong>Completeness of the document itself</strong>When true, the arrays were cut at a resource limit. Do not infer absence of a finding from a truncated report.</li>
</ul></section>

<section id="structural-validation" aria-labelledby="structure"><h2 id="structure">Use hosted schemas for structural validation</h2><p>The hosted schemas are ordinary Draft 2020-12 JSON Schemas. Any conforming validator can check an individual resource. This is useful at editors, CI gates, and ingestion boundaries, but it does not validate signatures, signer authorization, graph completeness, freshness, or data bytes.</p><pre><code class="language-bash">uvx --from check-jsonschema check-jsonschema \
  --schemafile https://usemakoto.dev/schema/v0.2/trust-policy.schema.json \
  policy.json</code></pre><p>The <a href="/schema/v0.2/catalog.json">hosted catalog</a> publishes every core schema and its SHA-256 digest. Private organizational profiles can use their own URI and remain unpublished; the signed profile reference pins the exact root and closure digests so a receiver can resolve them from an authenticated local catalog.</p><p><a href="/validate/"><strong>See every external validator, command by command &rarr;</strong></a></p><h3 id="render-safe">Content rules remain separate from integrity</h3><p>A digest can prove that invisible Unicode or another dangerous string has not changed. It cannot make that string safe. Put normalization, control-character, field, or bounded-pattern rules in an organizational profile and require the receiver to validate the actual structured artifact against that profile.</p></section>

<section aria-labelledby="limits"><h2 id="limits">What verification still cannot prove</h2><p>Passing every check proves that exact bytes match authorized signed claims and the receiver&rsquo;s independent expectations. It does not prove that a source told the truth, that a claimed transformation actually ran, that the data is safe or high quality, or that signed metadata is confidential. Those are separate controls and evidence.</p></section>

<section class="community-band" aria-labelledby="implement"><span class="kicker">Implement another verifier</span><h2 id="implement">Match the report contract, not just the JSON shape.</h2><p>A useful implementation must preserve the distinctions between authenticity and authorization, continuity and completeness, and completeness and freshness. Start from the public schemas, conformance fixtures, denial reports, and reference implementation.</p><div class="actions"><a class="button" href="https://github.com/makoto-project/makoto">Read the source on GitHub</a><a class="button secondary" href="https://github.com/makoto-project/makoto/issues/new">Propose a verifier</a></div></section>
"""

shell.write('verify/index.html', BODY)
print("verify/index.html written")
