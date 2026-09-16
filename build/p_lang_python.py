import sys; sys.path.insert(0, 'build')
import shell

BODY = r"""
<span class="kicker">Python binding</span>
<h1>Hold the boundary the CLI defines.</h1>
<p class="lead">The core implementation is Python, which makes it tempting to import its internals. Don&rsquo;t. <code>makoto.*</code> modules are not a stable published SDK; the command and its report schema are the tested contract. This page builds a real client on that contract: install, validate, attest, verify, branch on a denial, and read the report as typed Python.</p>
<p class="editorial-note"><strong>Two layers, named plainly.</strong> Everything from section 1 to 6 is Makoto v0.2 through the reference CLI. Section 7 covers <code>sdk/python/</code> on this site: a historical v0.1 DBOM experiment that is not wire-compatible with v0.2, and that shares a name with an unrelated PyPI project. Read it for the API study, not as a supported install.</p>

<section aria-labelledby="install"><h2 id="install">1. Install</h2><p>No distribution is published. The supported install is a pinned checkout with a locked environment.</p>
<pre><code class="language-bash">git clone https://github.com/makoto-project/makoto.git
cd makoto
git checkout "$MAKOTO_REV"          # pin a reviewed revision
uv sync --locked --dev
uv run makoto --help

# Fixtures: one allowed bundle and seven denial cases.
./scripts/demo-v0.2.sh --acceptance</code></pre>
<p>Your own application needs only a JSON Schema validator for the structural layer:</p>
<pre><code class="language-bash">uv add jsonschema        # or: pip install "jsonschema[format-nongpl]"</code></pre></section>

<section aria-labelledby="validate"><h2 id="validate">2. Validate structure against the hosted schemas</h2><p>The hosted schemas are ordinary Draft 2020-12 documents served with CORS. Fetch once, cache by digest, and validate as many resources as you like.</p>
<pre><code class="language-python">"""makoto_schemas.py — structural validation against the hosted catalog."""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from urllib.request import urlopen

from jsonschema import Draft202012Validator

CATALOG_URL = "https://usemakoto.dev/schema/v0.2/catalog.json"
BASE = "https://usemakoto.dev/schema/v0.2/"


@lru_cache(maxsize=None)
def _fetch(url: str) -> bytes:
    with urlopen(url, timeout=10) as response:
        return response.read()


@lru_cache(maxsize=None)
def load_schema(name: str) -> dict:
    """Fetch one core schema and check it against the catalog's digest.

    The catalog pins a SHA-256 for every resource. Verifying it here is what
    turns a mutable network response into something you can reason about.
    """
    catalog = json.loads(_fetch(CATALOG_URL))
    expected = {
        entry["path"]: entry["digest"]["sha256"]
        for entry in catalog["resources"]
    }
    raw = _fetch(BASE + name)
    actual = hashlib.sha256(raw).hexdigest()
    if name in expected and actual != expected[name]:
        raise ValueError(f"{name}: digest {actual} does not match catalog {expected[name]}")
    return json.loads(raw)


def validate(instance: dict, schema_name: str) -> list[str]:
    """Return human-readable structural errors. Empty list means well-formed."""
    schema = load_schema(schema_name)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    return [
        f"{' / '.join(str(p) for p in error.absolute_path) or 'root'}: {error.message}"
        for error in sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path))
    ]


if __name__ == "__main__":
    policy = json.loads(Path("receiver/policy.json").read_text(encoding="utf-8"))
    problems = validate(policy, "trust-policy.schema.json")
    for problem in problems:
        print(f"x {problem}")
    raise SystemExit(1 if problems else 0)</code></pre>
<p class="editorial-note"><strong>This is not verification.</strong> Structure is step 4 of fourteen. It says nothing about whether a signature is valid, whether the signer was authorized, or whether the bytes that arrived are the bytes that were signed. See <a href="/verify/#pipeline">the ordered checks</a>.</p></section>

<section aria-labelledby="attest"><h2 id="attest">3. Generate an attestation</h2><p>Signing happens in the CLI so that the private key never enters your process and the signed payload bytes are produced by the tested implementation.</p>
<pre><code class="language-python">"""makoto_attest.py — produce origin and transformation statements."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

CORE = Path(os.environ["MAKOTO_CORE"])   # the pinned core checkout


def _run(*args: str) -> str:
    completed = subprocess.run(
        ["uv", "run", "makoto", *args],
        cwd=CORE, check=False, capture_output=True, text=True, timeout=300,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"makoto {' '.join(args)} failed ({completed.returncode}): "
            f"{completed.stderr.strip()}"
        )
    return completed.stdout


def attest_origin(subject: Path, key: Path, out: Path) -> Path:
    """Claim where an artifact entered the system."""
    _run("attest", "origin",
         "--subject", str(subject.resolve()),
         "--source-kind", "file",
         "--key", str(key),
         "--out", str(out))
    return out


def attest_transform(subject: Path, input_artifact: Path,
                     predecessor: Path, key: Path, out: Path) -> Path:
    """Bind an output to the exact input artifact and predecessor statement.

    Both bindings matter. The predecessor digest proves which claim this step
    continues; the input digest proves which bytes it actually consumed.
    """
    _run("attest", "transform",
         "--subject", str(subject.resolve()),
         "--input", str(input_artifact.resolve()),
         "--predecessor", str(predecessor),
         "--key", str(key),
         "--out", str(out))
    return out


if __name__ == "__main__":
    keys, evidence = Path("keys/producer.json"), Path("evidence")
    evidence.mkdir(exist_ok=True)

    origin = attest_origin(Path("data/orders-2026-09-16.parquet"),
                           keys, evidence / "origin.dsse.json")
    attest_transform(Path("data/orders-redacted.parquet"),
                     Path("data/orders-2026-09-16.parquet"),
                     origin, keys, evidence / "transform.dsse.json")</code></pre>
<p>Keep the private key inside the job&rsquo;s secret boundary. Never place it in a dict you log, an exception you re-raise, or a value you pass between tasks. Run <code>uv run makoto attest transform --help</code> against your pinned revision for the authoritative flag set.</p></section>

<section aria-labelledby="verify"><h2 id="verify">4. Verify a bundle</h2><p>The receiver&rsquo;s policy, catalog, and expectations are inputs you supply, not values the bundle carries. That separation is the whole point of the design.</p>
<pre><code class="language-python">"""makoto_verify.py — run the reference verifier and parse its report."""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

CORE = Path(os.environ["MAKOTO_CORE"])


class VerificationError(RuntimeError):
    """Raised for any outcome that is not an explicit allow."""

    def __init__(self, message: str, report: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.report = report


@dataclass(frozen=True)
class Receiver:
    """Everything the receiver owns, kept outside the bundle on purpose."""

    policy: Path
    catalog: Path
    expected_artifact: Path


def verify_bundle(bundle: Path, receiver: Receiver,
                  evaluation_time: datetime | None = None) -> dict[str, Any]:
    """Verify one handoff bundle. Returns the report, or raises.

    Any outcome other than a parseable report saying "allow" is a refusal,
    including a crash, a timeout, or output we cannot read.
    """
    when = (evaluation_time or datetime.now(UTC)).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        completed = subprocess.run(
            ["uv", "run", "makoto", "verify", "bundle", str(bundle.resolve()),
             "--policy", str(receiver.policy.resolve()),
             "--schema-catalog", str(receiver.catalog.resolve()),
             "--expected-artifact", str(receiver.expected_artifact.resolve()),
             "--evaluation-time", when,
             "--json"],
            cwd=CORE, check=False, capture_output=True, text=True, timeout=600,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise VerificationError(f"verifier did not run: {error}") from error

    try:
        report = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise VerificationError(
            f"no usable report (exit {completed.returncode}): "
            f"{completed.stderr.strip()[:500]}"
        ) from error

    if not isinstance(report, dict) or "decision" not in report:
        raise VerificationError("report is not a verification report", report)

    return report</code></pre></section>

<section aria-labelledby="fail"><h2 id="fail">5. Handle a failed verdict</h2><p>A denial is structured data, not a string. Route on <code>primaryError</code>, because that single code says which trust boundary gave way, and different boundaries deserve different responses.</p>
<pre><code class="language-python">def require_allow(report: dict[str, Any]) -> dict[str, Any]:
    """Return the report on allow, otherwise raise with the diagnostics."""
    decision = report.get("decision")

    if decision != "allow":
        failed = [c["id"] for c in report.get("checks", []) if c["status"] == "fail"]
        detail = "; ".join(
            f"[{e['code']}] step {e['step']} {e['causedByCheck']}: {e['message']}"
            for e in report.get("errors", [])
        )
        raise VerificationError(
            f"decision={decision} primaryError={report.get('primaryError')} "
            f"failed={failed or ['-']} :: {detail}",
            report,
        )

    if report.get("reportTruncated"):
        # An allow from a truncated report is a claim about a partial document.
        raise VerificationError("report was truncated at a resource limit", report)

    return report


# Different boundaries fail for different reasons, so route on the code.
RETRYABLE = {"E_RESOURCE_LIMIT"}
TAMPERING = {"E_ARTIFACT_DIGEST", "E_SIGNATURE_INVALID", "E_STATEMENT_DIGEST"}
TRUST     = {"E_SIGNER_UNAUTHORIZED", "E_HANDOFF_RECIPIENT"}
STALE     = {"E_HANDOFF_STALE", "E_EXPECTED_HEAD", "E_EXPECTED_MANIFEST",
             "E_HANDOFF_NONCE", "E_EXPECTED_ARTIFACT"}

try:
    report = require_allow(verify_bundle(Path("bundle/"), receiver))
except VerificationError as error:
    code = (error.report or {}).get("primaryError")
    if code in RETRYABLE:
        raise                       # a limit, not a verdict: retry with headroom
    if code in STALE:
        request_fresh_handoff()     # valid evidence, but not for this delivery
    elif code in TRUST:
        alert_security(error)       # a real signature from the wrong party
    elif code in TAMPERING:
        quarantine(error)           # the bytes are not the bytes that were signed
    raise
else:
    ingest(report)</code></pre>
<p>Three rules keep a gate honest:</p>
<ul class="evidence-trail">
<li><span>fail</span><strong>Default to denial</strong>Only an explicit <code>"allow"</code> continues. A crash, a timeout, empty stdout, or an unparseable document is a refusal.</li>
<li><span>hold</span><strong>Never swallow the exception to keep a pipeline green</strong>A bare <code>except</code> around verification converts a security control into a log line.</li>
<li><span>keep</span><strong>Persist the report</strong><code>policyDigest</code> and <code>coreCatalogDigest</code> record which policy and which schemas produced the verdict. That is what an auditor asks for months later.</li>
</ul></section>

<section aria-labelledby="report"><h2 id="report">6. Read the verification report</h2><p>The report deliberately keeps the boundaries apart. Model it that way in your own code rather than flattening it to a boolean.</p>
<pre><code class="language-python">"""makoto_report.py — a typed read over the verification report."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

Status = Literal["pass", "fail", "indeterminate", "not_checked", "skipped"]
Decision = Literal["allow", "deny", "indeterminate"]


@dataclass(frozen=True)
class Check:
    id: str
    status: Status
    prerequisite_checks: tuple[str, ...]

    @property
    def proven(self) -> bool:
        """A skipped check is not a passing check."""
        return self.status == "pass"


@dataclass(frozen=True)
class Report:
    decision: Decision
    primary_error: str | None
    truncated: bool
    checks: tuple[Check, ...]
    errors: tuple[dict[str, Any], ...]
    warnings: tuple[dict[str, Any], ...]
    summary: dict[str, Any]
    tool: dict[str, str]

    @classmethod
    def parse(cls, raw: dict[str, Any]) -> "Report":
        return cls(
            decision=raw["decision"],
            primary_error=raw.get("primaryError"),
            truncated=bool(raw.get("reportTruncated")),
            checks=tuple(
                Check(c["id"], c["status"], tuple(c.get("prerequisiteChecks", ())))
                for c in raw.get("checks", ())
            ),
            errors=tuple(raw.get("errors", ())),
            warnings=tuple(raw.get("warnings", ())),
            summary=raw.get("summary", {}),
            tool=raw.get("tool", {}),
        )

    def failed(self) -> tuple[Check, ...]:
        return tuple(c for c in self.checks if c.status == "fail")

    def untested(self) -> tuple[Check, ...]:
        """Checks that never ran. Absence of a failure here is not evidence."""
        return tuple(c for c in self.checks
                     if c.status in ("skipped", "not_checked", "indeterminate"))


report = Report.parse(raw)

print(f"{report.decision}  {report.primary_error or '-'}")
for check in report.checks:
    blocked = f"  (needs {', '.join(check.prerequisite_checks)})" if check.prerequisite_checks else ""
    print(f"  {check.status.upper():<13} {check.id}{blocked}")
for warning in report.warnings:
    print(f"  warning [{warning['code']}] {warning['message']}")

print(report.summary["statementsAuthorized"], "of",
      report.summary["statementsTotal"], "statements authorized")</code></pre>
<p>On a bundle whose data file was edited after signing, that prints:</p>
<pre><code class="language-bash">deny  E_ARTIFACT_DIGEST
  PASS          load-safely
  PASS          parse-strictly
  PASS          core-schemas
  PASS          signatures
  PASS          authorization
  PASS          graph
  FAIL          artifact-bytes
  SKIPPED       artifact-profiles  (needs artifact-bytes)
3 of 3 statements authorized</code></pre>
<p>Every signature was valid and every signer authorized. The failure is narrower and more useful than &ldquo;invalid&rdquo;: the bytes that arrived are not the bytes that were signed. Because <code>artifact-bytes</code> failed, the profile check reports <code>skipped</code> instead of claiming a pass it did not earn. <a href="/verify/#pipeline">Every code and the step that raises it &rarr;</a></p></section>

<section aria-labelledby="dbom"><span class="kicker">Historical</span><h2 id="dbom">7. The v0.1 DBOM study in <code>sdk/python/</code></h2><p>Before v0.2, this site carried a small Python module that produced a flat DBOM document: one source, one signature, a list of lineage steps. It is <strong>not</strong> wire-compatible with v0.2, it is not published to PyPI, and the PyPI project named <code>makoto</code> is unrelated. It is preserved because its API shape is a useful reference for anyone designing a language SDK, and because the code is real and runs.</p>
<pre><code class="language-bash">git clone https://github.com/makoto-project/usemakoto.dev.git
cd usemakoto.dev/sdk/python
uv run --with jsonschema --with requests python -c "import makoto; print(makoto.__version__)"</code></pre>
<pre><code class="language-python">import json

from makoto import generate, verify

# generate(file_path, signer, uri=None, lineage_steps=None, format=None) -> dict
dbom = generate(
    file_path="data/sales.csv",
    signer="github:your-username",
    uri="s3://my-bucket/sales.csv",   # optional; defaults to the file:// path
    format="csv",                      # optional; inferred from the extension
)
print(json.dumps(dbom, indent=2))

# verify(dbom_path_or_dict, file_path=None) -> VerifyResult
result = verify(dbom, file_path="data/sales.csv")
if result.valid:
    print("DBOM is internally consistent")
else:
    for error in result.errors:
        print(f"x {error}")</code></pre>
<p><code>VerifyResult</code> is a dataclass with <code>.valid</code> and <code>.errors</code>, and it is truthy when valid. Supply custom provenance with <code>lineage_steps</code>, and check the chain yourself &mdash; the v0.1 verifier validates structure and the source digest, not step-to-step continuity:</p>
<pre><code class="language-python">steps = dbom["lineage"]
problems = [
    f"step {steps[i]['step']} input_hash does not match step {steps[i - 1]['step']} output_hash"
    for i in range(1, len(steps))
    if steps[i]["input_hash"] != steps[i - 1]["output_hash"]
]
if steps[-1]["output_hash"] != dbom["source"]["hash"]["value"]:
    problems.append("final output_hash does not match source.hash.value")</code></pre>
<p class="editorial-note"><strong>What v0.2 changed, and why.</strong> The v0.1 signature is <code>sha256(file_hash + signer)</code>, which is a checksum of an identity string rather than a signature anyone can authenticate. It proves nothing about who produced the document. v0.2 replaces it with DSSE over exact payload bytes, receiver-owned authorization policy separate from signature validity, and a graph in which every step pins its predecessor statement. Use sections 1 to 6 for anything real.</p></section>

<section class="community-band"><h2>Contribute a Python fixture.</h2><p>The useful contribution is a client paired with the exact denial report it must refuse, not another wrapper around the happy path.</p><div class="actions"><a class="button" href="/verify/">Back to verification</a><a class="button secondary" href="/sdk/">All language interfaces</a></div></section>
"""

shell.write('verify/python.html', BODY)
print("ok")
