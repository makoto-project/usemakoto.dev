import sys; sys.path.insert(0, 'build')
import shell

BODY = r"""
<span class="kicker">Bash binding</span>
<h1>Make the shell fail closed.</h1>
<p class="lead">In a pipeline step there is no object model, only an exit status and a JSON document. This page covers the whole loop from an empty shell: install the verifier, validate structure against the hosted schemas, attest an origin and a transformation, verify a bundle, branch on the verdict, and read the report that comes back.</p>
<p class="editorial-note"><strong>Two layers, named plainly.</strong> <code>makoto</code> in the core repository is the supported v0.2 implementation and the subject of everything below. The <code>sdk/</code> directory on this site holds a separate, historical v0.1 DBOM experiment that is not wire-compatible with v0.2 and was never published to a package registry.</p>

<section aria-labelledby="install"><h2 id="install">1. Install</h2><p>There is no published binary or package. The supported install is a reviewed checkout with a locked environment, which is also what makes a CI run reproducible.</p>
<pre><code class="language-bash">git clone https://github.com/makoto-project/makoto.git
cd makoto
git checkout "$MAKOTO_REV"          # pin a reviewed revision, never a moving branch
uv sync --locked --dev

uv run makoto --help
uv run makoto verify bundle --help</code></pre>
<p>Generate the fixture set once so every command below has something real to run against. It produces one allowed bundle and seven denial cases.</p>
<pre><code class="language-bash">./scripts/demo-v0.2.sh --acceptance
ls demos/v0.2-end-to-end/generated/</code></pre></section>

<section aria-labelledby="validate"><h2 id="validate">2. Validate structure against the hosted schemas</h2><p>Structural validation is cheap, needs no keys, and belongs at the editor and the ingestion boundary. It answers &ldquo;is this shaped correctly?&rdquo; and nothing else.</p>
<pre><code class="language-bash">uvx --from check-jsonschema check-jsonschema \
  --schemafile https://usemakoto.dev/schema/v0.2/trust-policy.schema.json \
  receiver/policy.json</code></pre>
<p>For a pre-flight that needs no network and no Python, <code>jq</code> can assert the fields a policy must carry before you spend time on a full run:</p>
<pre><code class="language-bash">jq --exit-status '
  has("policyVersion")
  and (.rules      | type == "array" and length >= 1)
  and (.rules      | all(has("id") and has("keys")))
  and (.trustedKeys| type == "array" and length >= 1)
' receiver/policy.json > /dev/null \
  || { echo "policy.json is missing required fields" >&2; exit 1; }</code></pre>
<p class="editorial-note"><strong>This is not verification.</strong> A schema-valid policy can still trust the wrong key, and a schema-valid bundle can carry an invalid signature. Structure is step 4 of fourteen. See <a href="/validate/">the full validator catalogue</a> and <a href="/verify/#pipeline">the ordered checks</a>.</p></section>

<section aria-labelledby="attest"><h2 id="attest">3. Generate an attestation</h2><p>An origin statement claims where data came from. A transformation statement binds an output to the exact predecessor statement and input artifact. Both are DSSE-signed over exact payload bytes.</p>
<pre><code class="language-bash"># A signing key. Keep the private half in the job's secret boundary,
# never in the repository, the log, or an environment dump.
uv run makoto key generate --out keys/producer.json

# Origin: this artifact entered the system here.
uv run makoto attest origin \
  --subject data/orders-2026-09-16.parquet \
  --source-kind file \
  --key keys/producer.json \
  --out evidence/origin.dsse.json

# Transformation: this output came from that exact input,
# under that exact predecessor statement.
uv run makoto attest transform \
  --subject data/orders-redacted.parquet \
  --input data/orders-2026-09-16.parquet \
  --predecessor evidence/origin.dsse.json \
  --key keys/producer.json \
  --out evidence/transform.dsse.json

# A handoff commits to the exact heads, artifacts, and recipient.
uv run makoto handoff create \
  --statement evidence/origin.dsse.json \
  --statement evidence/transform.dsse.json \
  --artifact data/orders-redacted.parquet \
  --recipient "receiver@example.org" \
  --key keys/producer.json \
  --out bundle/</code></pre>
<p>Run <code>uv run makoto attest origin --help</code> against your pinned revision for the exact flag set; the checked-out CLI is authoritative, not this page.</p></section>

<section aria-labelledby="verify"><h2 id="verify">4. Verify a bundle</h2><p>The receiver supplies its own policy, its own catalog, and its own independent expectations. None of those come from the bundle, which is the point.</p>
<pre><code class="language-bash">uv run makoto verify bundle bundle/ \
  --policy receiver/policy.json \
  --schema-catalog receiver/catalog.json \
  --expected-artifact receiver/expected-artifact.json \
  --evaluation-time "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --json > report.json</code></pre></section>

<section aria-labelledby="fail"><h2 id="fail">5. Handle a failed verdict</h2><p>Two things can go wrong, and a gate has to treat them the same way. The verifier can return a report that says <code>deny</code>, or it can fail to produce a usable report at all. Both must stop the pipeline.</p>
<pre><code class="language-bash">#!/usr/bin/env bash
# gate.sh — verify a handoff bundle, or stop the pipeline.
set -euo pipefail

BUNDLE="${1:?usage: gate.sh BUNDLE_DIR}"
CORE="${MAKOTO_CORE:?set MAKOTO_CORE to the pinned core checkout}"
REPORT="$(mktemp -t makoto-report.XXXXXX.json)"
trap 'rm -f "$REPORT"' EXIT

# `set -e` must not swallow the verifier's own non-zero exit: capture it.
status=0
( cd "$CORE" && uv run makoto verify bundle "$BUNDLE" \
    --policy "$PWD/receiver/policy.json" \
    --schema-catalog "$PWD/receiver/catalog.json" \
    --expected-artifact "$PWD/receiver/expected-artifact.json" \
    --evaluation-time "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --json ) > "$REPORT" || status=$?

# A report we cannot parse is a denial, not a pass.
if ! jq -e 'type == "object" and has("decision")' "$REPORT" > /dev/null 2>&1; then
  echo "makoto: no usable report (exit $status)" >&2
  exit 1
fi

decision=$(jq -r '.decision' "$REPORT")
primary=$(jq -r '.primaryError // "none"' "$REPORT")

if [ "$decision" != "allow" ]; then
  echo "makoto: DENIED ($decision), primary error: $primary" >&2
  jq -r '.errors[] | "  [\(.code)] step \(.step) \(.causedByCheck): \(.message)"' \
    "$REPORT" >&2
  exit 1
fi

# An allow with warnings is a narrower claim than a clean allow.
jq -r '.warnings[]? | "  warning [\(.code)] \(.message)"' "$REPORT" >&2

echo "makoto: allowed"</code></pre>
<p>Three habits make the difference between a gate and a decoration:</p>
<ul class="evidence-trail">
<li><span>fail</span><strong>Default to denial</strong>A crash, a timeout, an empty stdout, or a malformed document must exit non-zero. Only an explicit <code>"allow"</code> lets the job continue.</li>
<li><span>pin</span><strong>Pin the verifier</strong><code>MAKOTO_REV</code> is part of the security boundary. A gate that silently follows a moving branch can change its verdict without anyone changing the data.</li>
<li><span>keep</span><strong>Keep the report</strong>Archive <code>report.json</code> as a build artifact. <code>policyDigest</code> and <code>coreCatalogDigest</code> record which policy and which schemas produced the verdict, which is what an audit needs later.</li>
</ul></section>

<section aria-labelledby="report"><h2 id="report">6. Read the verification report</h2><p>The report separates the trust boundaries on purpose. These are the queries worth having in muscle memory.</p>
<pre><code class="language-bash"># The verdict and the one code that explains it.
jq -r '"\(.decision)  \(.primaryError // "-")"' report.json

# Which checks ran, which failed, and which were never tested.
jq -r '.checks[] | "\(.status | ascii_upcase)\t\(.id)"' report.json

# A skipped check is not a passing check: show what blocked it.
jq -r '.checks[]
  | select(.status == "skipped")
  | "\(.id) skipped, needs: \(.prerequisiteChecks | join(", "))"' report.json

# Every diagnostic, in pipeline order.
jq -r '.errors[] | "[\(.code)] step \(.step) (\(.causedByCheck)): \(.message)"' report.json

# What the run actually established.
jq '.summary | {statementsValid, statementsAuthorized, signaturesValid,
                artifactsChecked, roots, heads}' report.json

# Never read a truncated report as a complete one.
jq -e '.reportTruncated == false' report.json > /dev/null \
  || echo "report was truncated at a resource limit" >&2</code></pre>
<p>Sample output from a bundle whose data file was edited after signing:</p>
<pre><code class="language-bash">$ jq -r '"\(.decision)  \(.primaryError // "-")"' report.json
deny  E_ARTIFACT_DIGEST

$ jq -r '.checks[] | "\(.status | ascii_upcase)\t\(.id)"' report.json
PASS    load-safely
PASS    parse-strictly
PASS    core-schemas
PASS    signatures
PASS    authorization
PASS    graph
FAIL    artifact-bytes
SKIPPED artifact-profiles</code></pre>
<p>The signatures passed. The authorization passed. The graph was continuous. The bytes that arrived were not the bytes that were signed &mdash; and because <code>artifact-bytes</code> failed, the profile check never ran and reports <code>skipped</code> rather than claiming a pass it did not earn. A single boolean would have hidden all of that. See <a href="/verify/#pipeline">the fourteen ordered checks</a> for every code and the step that raises it.</p></section>

<section class="community-band"><h2>Contribute a shell fixture.</h2><p>The most useful contribution is a gate script paired with the exact denial report it must reject.</p><div class="actions"><a class="button" href="/verify/">Back to verification</a><a class="button secondary" href="/sdk/">All language interfaces</a></div></section>
"""

shell.write('verify/bash.html', BODY)
print("ok")
