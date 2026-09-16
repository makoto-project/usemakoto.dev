"""Regenerate demo-06 fixtures as real Makoto v0.2 artifacts.

Usage: uv run regenerate_v02_fixtures.py <makoto-core-checkout> <site-root> <workdir>
Run from inside the core checkout so `uv run` resolves the makoto package.

Produces, for the safe and the flagged JavaScript fixture:
  attestation.<name>.json  signed DSSE origin envelope
  dbom.<name>.json         signed handoff manifest envelope (the v0.2 roll-up)
  report.<name>.json       receiver verification report
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

CORE = Path(sys.argv[1])
SITE = Path(sys.argv[2])
WORK = Path(sys.argv[3])
OUT = WORK / "out"
TIME = "2026-09-16T16:00:00Z"
FIX = SITE / "demos/06-invisible-unicode-guardrails/fixtures"

sys.path.insert(0, str(CORE / "src"))
from makoto.dsse import canonical_b64encode, keyid_from_spki  # noqa: E402


def run(*args: str, expect: int = 0) -> str:
    print("$ makoto " + " ".join(args))
    done = subprocess.run(
        [sys.executable, "-m", "makoto.cli", *args],
        cwd=CORE, capture_output=True, text=True,
    )
    if done.returncode != expect:
        raise SystemExit(f"exit {done.returncode}: {done.stdout}{done.stderr}")
    return (done.stdout + done.stderr).strip()


def write(path: Path, obj) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")
    return path


def spki_keyid(pem: Path) -> tuple[str, str]:
    from cryptography.hazmat.primitives import serialization
    pub = serialization.load_pem_public_key(pem.read_bytes())
    spki = pub.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return keyid_from_spki(spki), canonical_b64encode(spki)


shutil.rmtree(WORK, ignore_errors=True)
for sub in ("keys", "receiver/resources", "out"):
    (WORK / sub).mkdir(parents=True, exist_ok=True)

# ---- catalog: the receiver's own pinned copy of the render-safety schema ----
schema_bytes = (FIX / "render-safe-origin-v1.schema.json").read_bytes()
schema_digest = hashlib.sha256(schema_bytes).hexdigest()
(WORK / "receiver/resources" / f"{schema_digest}.schema.json").write_bytes(schema_bytes)
write(WORK / "receiver/catalog.json", {
    "version": "0.2",
    "resources": [{
        "digest": {"sha256": schema_digest},
        "id": "https://schemas.example.internal/makoto/render-safe-origin-v1.schema.json",
        "path": f"resources/{schema_digest}.schema.json",
    }],
})
catalog = str(WORK / "receiver/catalog.json")

run("profile", "create",
    "--schema-root", str(WORK / "receiver/resources" / f"{schema_digest}.schema.json"),
    "--target", "predicate", "--critical", "true",
    "--schema-catalog", catalog,
    "--out", str(WORK / "receiver/render-safe.profile.json"))
profile = json.loads((WORK / "receiver/render-safe.profile.json").read_text())

keys = {}
for name in ("scanner", "handoff"):
    priv = WORK / f"keys/{name}.private.pem"
    pub = WORK / f"keys/{name}.public.pem"
    run("key", "generate", "--private-out", str(priv), "--public-out", str(pub))
    keys[name] = (priv, *spki_keyid(pub))

# ---- receiver trust policy: the scan profile is required, not optional ----
policy = {
    "version": "0.2",
    "keys": {
        keys[n][1]: {"type": "ed25519", "publicKey": keys[n][2],
                     "label": f"insecure demo-only {n} key"}
        for n in ("scanner", "handoff")
    },
    "rules": [{
        "id": "urn:makoto:demo:rule:render-safe-origin",
        "predicateTypes": ["https://usemakoto.dev/predicate/v0.2/origin"],
        "authorizedKeyIds": [keys["scanner"][1]],
        "minimumSignatures": 1,
        "sourceKinds": ["urn:makoto:demo:source:repository-file"],
        "profileConstraints": [{
            "id": profile["id"],
            "digest": profile["digest"],
            "closureDigest": profile["closureDigest"],
            "target": "predicate",
        }],
    }],
    "handoff": {
        "authorizedKeyIds": [keys["handoff"][1]],
        "minimumSignatures": 1,
        "requireExpectedManifest": True,
        "requireExpectedHead": True,
        "requireExpectedArtifacts": True,
        "requireRecipient": False,
        "requireNonce": False,
        "allowReplayableHandoff": False,
    },
    "requiredProfiles": [],
    "limits": json.loads((SITE / "demos/v0.2-end-to-end/artifacts/receiver/policy.json")
                         .read_text())["limits"],
}
policy_path = write(WORK / "receiver/policy.json", policy)
run("policy", "check", "--policy", str(policy_path))

cases = {
    "safe": ("safe-visible.js", "analysis.safe.json",
             "urn:makoto:demo:v0.2:source:safe-visible-js",
             "urn:uuid:06000001-0600-4600-8600-060000000001", True),
    "flagged": ("flagged-invisible.js", "analysis.flagged.json",
                "urn:makoto:demo:v0.2:source:flagged-invisible-js",
                "urn:uuid:06000002-0600-4600-8600-060000000002", False),
}
transcript: dict[str, object] = {}

for name, (js, analysis_file, source_uri, event_id, attach_profile) in cases.items():
    case = WORK / name
    (case / "data").mkdir(parents=True, exist_ok=True)
    shutil.copy(FIX / js, case / "data" / js)
    analysis = json.loads((FIX / analysis_file).read_text())["analysis"]["rendering"]
    ext = write(case / "extensions.json", {"urn:makoto:demo:render-safe": analysis})

    attest = [
        "attest", "origin",
        "--subject", f"{js}={case / 'data' / js}",
        "--source-kind", "urn:makoto:demo:source:repository-file",
        "--source-uri", source_uri,
        "--extensions", str(ext),
        "--event-id", event_id,
        "--occurred-at", TIME,
        "--key", str(keys["scanner"][0]),
        "--out", str(case / "attestations/origin.dsse.json"),
    ]
    with_profile = attest + ["--profile", str(WORK / "receiver/render-safe.profile.json"),
                             "--schema-catalog", catalog]

    if attach_profile:
        run(*with_profile)
    else:
        # The producer cannot sign a render-safety claim it does not meet.
        transcript["producer_refusal"] = run(*with_profile, expect=2)
        # So the attacker drops the profile and signs the raw claim instead.
        run(*attest)

    write(case / "bindings/final-artifact.json", {
        "head": "../attestations/origin.dsse.json",
        "subjectName": js,
        "path": f"../data/{js}",
        "mediaType": "application/javascript",
    })
    run("handoff", "create",
        "--head", str(case / "attestations/origin.dsse.json"),
        "--attestations", str(case / "attestations"),
        "--artifact-binding", str(case / "bindings/final-artifact.json"),
        "--schema-catalog", catalog,
        "--bundle-id", f"urn:makoto:demo:06:{name}",
        "--issued-at", TIME,
        "--recipient", "example:review-team",
        "--key", str(keys["handoff"][0]),
        "--out", str(case / "bundle"))

    bundle = json.loads((case / "bundle/bundle.json").read_text())
    head = json.loads((case / "attestations/origin.dsse.json").read_text())
    head_digest = hashlib.sha256(
        __import__("base64").b64decode(head["payload"])).hexdigest()
    artifact_digest = hashlib.sha256((case / "data" / js).read_bytes()).hexdigest()
    manifest_digest = hashlib.sha256(
        __import__("base64").b64decode(
            json.loads((case / "bundle/manifest.dsse.json").read_text())["payload"])
    ).hexdigest()
    expected = write(case / "expected-artifact.json", {
        "subjectName": js,
        "digest": {"sha256": artifact_digest},
        "head": {"sha256": head_digest},
    })

    report_text = run(
        "verify", "bundle", str(case / "bundle"),
        "--policy", str(policy_path),
        "--schema-catalog", catalog,
        "--expected-manifest", f"sha256:{manifest_digest}",
        "--expected-head", f"sha256:{head_digest}",
        "--expected-artifact", str(expected),
        "--evaluation-time", TIME,
        "--json",
        expect=0 if attach_profile else 1,
    )
    report = json.loads(report_text)
    write(OUT / f"attestation.{name}.json", head)
    write(OUT / f"dbom.{name}.json",
          json.loads((case / "bundle/manifest.dsse.json").read_text()))
    write(OUT / f"report.{name}.json", report)
    transcript[name] = {
        "decision": report["decision"],
        "primaryError": report.get("primaryError"),
        "errors": report.get("errors", []),
        "artifactDigest": artifact_digest,
        "headDigest": head_digest,
        "manifestDigest": manifest_digest,
        "bundleId": bundle.get("bundleId"),
    }

transcript["schemaDigest"] = schema_digest
transcript["profile"] = profile
transcript["policyDigest"] = hashlib.sha256(policy_path.read_bytes()).hexdigest()
transcript["keyids"] = {n: keys[n][1] for n in keys}
write(OUT / "transcript.json", transcript)
print(json.dumps(transcript, indent=2)[:4000])
