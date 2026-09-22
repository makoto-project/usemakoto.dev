"""Generate the sharded-corpus guide's example repository and its Makoto lineage record.

The guide under /examples/corpus/ follows one small text corpus kept in Git: a
tree of directory index files, one leaf manifest listing two shards, and the
Makoto record that lives beside that manifest. Everything the guide shows is
produced here by the pinned core reference CLI, so every statement is signed,
every digest is computed, and the record verifies.

Keys are derived from fixed seeds, as in core's own demonstration, so the
signed bytes are reproducible. They are insecure example-only keys; no private
key is written into the site.

Run with the pinned core checkout's environment:

    uv run --project ../core python scripts/corpus_example.py
    uv run --project ../core python scripts/corpus_example.py --check

`--check` rebuilds everything in a scratch directory and fails when a committed
file differs, is missing, or is extra.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from makoto.canonical import canonical_json
from makoto.dsse import SigningKey, canonical_b64decode, canonical_b64encode
from makoto.schema import core_dataset_manifest_profile_reference, strict_json_loads

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/corpus"
# Generated trees. The corpus repository is what a maintainer would keep in Git; the
# lookaside holds the raw files and shards, which stay out of Git; build holds the
# decoded documents and captured command output the guide displays.
GENERATED = ("repo", "lookaside", "build")
# Hand-written files inside the generated repository tree; kept, never regenerated.
HAND_WRITTEN = ("repo/.github/workflows/lineage.yml", "repo/lineage/check_lineage.py")

LEAF = "text/letters"
LEAF_MANIFEST = "letters.yaml"
RAW_MANIFEST = "letters.raw.json"
SHARD_MANIFEST = "letters.shards.json"
DATASET_MEDIA_TYPE = "application/vnd.makoto.dataset-manifest.v0.2+json"
NDJSON = "application/x-ndjson"
LICENSE_KEY = "https://corpus.example/makoto/license/v1"
LICENSE_PROFILE_ID = "https://corpus.example/makoto/license/v1/predicate.schema.json"
SOURCE_KIND = "urn:makoto:example:source:archive-series"
SOURCE_URI = "https://archive.example/harbour-letters/"
INGEST_TYPE = "urn:makoto:example:operation:corpus-ingest"

RETRIEVED_AT = "2026-09-02T09:00:00Z"
ORIGIN_AT = "2026-09-02T09:05:00Z"
INGEST_AT = "2026-09-02T09:20:00Z"
HANDOFF_AT = "2026-09-02T09:30:00Z"
ORIGIN_EVENT = "urn:uuid:3c0e8a52-7f1d-4b2a-9d6e-1a5b7c9e0f21"
INGEST_EVENT = "urn:uuid:8d4f2b61-0a3c-4e7d-b1f9-6c2e5a8d3b47"
BUNDLE_ID = "urn:uuid:e2b7c4d9-5f0a-4c18-a36e-9b1d7f2c8e05"

# Five transcribed letters. Synthetic text; the archive and the society are fictional.
LETTERS = (
    (
        "letter-001.txt",
        (
            "Dear Ada,\nThe boats came in before noon and the harbour smelled of tar and rain.\n"
            "Father says the new pier will be finished by spring.\nYours, Tom\n"
        ),
    ),
    (
        "letter-002.txt",
        (
            "Dear Tom,\nThe school has a stove at last, and we read by it after lessons.\n"
            "Send word when the pier is done.\nAda\n"
        ),
    ),
    (
        "letter-003.txt",
        (
            "To the harbour master,\nThe east light was dark on the night of the ninth.\n"
            "Two fishing crews waited offshore until dawn.\nR. Hale\n"
        ),
    ),
    (
        "letter-004.txt",
        (
            "Dear Mrs Pryce,\nThank you for the loan of the ledger. I have copied the tide\n"
            "tables for the society and will return it by Friday.\nE. Marsh\n"
        ),
    ),
    (
        "letter-005.txt",
        (
            "Dear Society members,\nThe copied ledgers are now shelved in the reading room.\n"
            "Please sign the book when you borrow one.\nE. Marsh, secretary\n"
        ),
    ),
)
MAINTAINER = "letters-maintainers"
SET_LICENSE = "CC0-1.0"
SET_EVIDENCE = "https://archive.example/harbour-letters/rights"
SOCIETY_LICENSE = "CC-BY-4.0"
SOCIETY_ATTRIBUTION = "Transcribed by the Harbour Letters Society"
SOCIETY_EVIDENCE = "https://archive.example/harbour-letters/society-terms"
# (shard name, letters it holds, per-shard license override or None)
SHARDS = (
    ("shards/letters-00000.ndjson", ("letter-001.txt", "letter-002.txt", "letter-003.txt"), None),
    ("shards/letters-00001.ndjson", ("letter-004.txt", "letter-005.txt"), SOCIETY_LICENSE),
)
INGEST_PARAMETERS = (
    "# Parameters for corpus-ingest. The ingest statement pins these exact bytes\n"
    "# as operation.parametersDigest, so a reviewer can see which settings ran.\n"
    "source: https://archive.example/harbour-letters/\n"
    "records_per_shard: 3\n"
    "shard_format: ndjson\n"
    "text_normalization: none\n"
    "license_overrides:\n"
    "  - shard: shards/letters-00001.ndjson\n"
    "    license: CC-BY-4.0\n"
    '    attribution: "Transcribed by the Harbour Letters Society"\n'
    "    evidence: https://archive.example/harbour-letters/society-terms\n"
)

LIMITS = {
    "maxBundleFiles": 10000,
    "maxMetadataBytes": 104857600,
    "maxArtifactBytesPerFile": 10737418240,
    "maxAggregateArtifactBytes": 53687091200,
    "maxSnapshotBytes": 53687091200,
    "maxArtifactValidationBytes": 104857600,
    "maxJsonDepth": 128,
    "maxJsonNumberChars": 1024,
    "maxJsonExponentMagnitude": 10000,
    "maxSchemaBytes": 2097152,
    "maxSchemaResources": 256,
    "maxSchemaEvaluationDepth": 256,
    "maxSchemaOperations": 10000000,
    "maxRegexLength": 4096,
    "profileEvaluationTimeoutSeconds": 5,
    "profileWorkerMemoryBytes": 536870912,
    "maxNdjsonLineBytes": 1048576,
    "maxSignaturesTotal": 10000,
    "maxProfileEvaluations": 10000,
    "maxDiagnostics": 10000,
    "maxReportRecords": 20000,
    "maxReportBytes": 67108864,
}

LICENSE_TERMS: dict[str, Any] = {
    "type": "object",
    "required": ["license", "evidence"],
    "properties": {
        "license": {"type": "string", "minLength": 1},
        "attribution": {"type": "string", "minLength": 1},
        "evidence": {"type": "string", "minLength": 1},
    },
}
LICENSE_PROFILE: dict[str, Any] = {
    "$schema": "https://usemakoto.dev/schema/v0.2/profile-dialect.schema.json",
    "$id": LICENSE_PROFILE_ID,
    "type": "object",
    "required": ["extensions"],
    "properties": {
        "extensions": {
            "type": "object",
            "required": [LICENSE_KEY],
            "properties": {
                LICENSE_KEY: {
                    "type": "object",
                    "required": ["default", "overrides"],
                    "properties": {
                        "default": LICENSE_TERMS,
                        "overrides": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "required": ["subjectName", "entryName", "license", "evidence"],
                                "properties": {
                                    "subjectName": {"type": "string", "minLength": 1},
                                    "entryName": {"type": "string", "minLength": 1},
                                    **LICENSE_TERMS["properties"],
                                },
                            },
                        },
                    },
                }
            },
        }
    },
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def pretty(value: object) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode()


def write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def write_json(path: Path, value: object) -> None:
    write(path, canonical_json(value) + b"\n")


def makoto(*arguments: str, cwd: Path, expect: int = 0) -> str:
    completed = subprocess.run(
        [sys.executable, "-m", "makoto.cli", *arguments],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != expect:
        raise SystemExit(
            f"makoto {' '.join(arguments)} exited {completed.returncode}, expected {expect}\n"
            f"{completed.stdout}{completed.stderr}"
        )
    return completed.stdout


def keys() -> dict[str, SigningKey]:
    # Insecure, example-only seeds, in the style of core's demonstration keys.
    return {
        "letters-maintainer": SigningKey.from_seed(b"\x41" * 32),
        "index-maintainer": SigningKey.from_seed(b"\x42" * 32),
    }


def dataset_manifest(entries: list[tuple[str, bytes, str]]) -> bytes:
    rows = [
        {"name": name, "digest": {"sha256": sha256(data)}, "size": len(data), "mediaType": media}
        for name, data, media in sorted(entries, key=lambda item: item[0].encode())
    ]
    return canonical_json({"version": "0.2", "entries": rows}) + b"\n"


def shard_bytes(letters: tuple[str, ...], license_id: str | None) -> bytes:
    text = dict(LETTERS)
    lines = []
    for name in letters:
        row: dict[str, Any] = {
            "id": name.removesuffix(".txt"),
            "text": text[name],
            "source": SOURCE_URI + name,
            "license": license_id or SET_LICENSE,
            "maintainer": MAINTAINER,
            "language": "en",
        }
        if license_id == SOCIETY_LICENSE:
            row["attribution"] = SOCIETY_ATTRIBUTION
        lines.append(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
    return ("\n".join(lines) + "\n").encode()


def leaf_manifest(shards: list[tuple[str, bytes, int, str | None]]) -> bytes:
    lines = [
        "# Leaf manifest, written by corpus-ingest. Edit ingest.yaml and re-run the",
        "# ingest instead of editing this file: the lineage record pins its bytes.",
        "name: harbour-letters",
        "title: Harbour Letters",
        "languages: [en]",
        f"license: {SET_LICENSE}",
        f"license_evidence: {SET_EVIDENCE}",
        "sources:",
        "  - name: Harbour town archive, letters series",
        f"    uri: {SOURCE_URI}",
        '    version: "2026-09-01"',
        f'    retrieved_at: "{RETRIEVED_AT}"',
        "shards:",
    ]
    for name, data, records, override in shards:
        lines += [
            f"  - name: {name}",
            f"    sha256: {sha256(data)}",
            f"    bytes: {len(data)}",
            f"    records: {records}",
        ]
        if override is not None:
            lines += [
                f"    license: {override}",
                f'    attribution: "{SOCIETY_ATTRIBUTION}"',
                f"    license_evidence: {SOCIETY_EVIDENCE}",
            ]
    return ("\n".join(lines) + "\n").encode()


def license_extension() -> dict[str, Any]:
    return {
        LICENSE_KEY: {
            "default": {"license": SET_LICENSE, "evidence": SET_EVIDENCE},
            "overrides": [
                {
                    "subjectName": SHARD_MANIFEST,
                    "entryName": "shards/letters-00001.ndjson",
                    "license": SOCIETY_LICENSE,
                    "attribution": SOCIETY_ATTRIBUTION,
                    "evidence": SOCIETY_EVIDENCE,
                }
            ],
        }
    }


def policy(signing: dict[str, SigningKey], license_profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "version": "0.2",
        "keys": {
            key.keyid(): {
                "type": "ed25519",
                "publicKey": canonical_b64encode(key.public_spki()),
                "label": f"insecure example-only {name} key",
            }
            for name, key in signing.items()
        },
        "rules": [
            {
                "id": "urn:makoto:example:rule:letters-ingest",
                "predicateTypes": ["https://usemakoto.dev/predicate/v0.2/transform"],
                "authorizedKeyIds": [signing["letters-maintainer"].keyid()],
                "minimumSignatures": 1,
                "operationTypes": [INGEST_TYPE],
                "profileConstraints": [
                    {
                        "id": license_profile["id"],
                        "digest": license_profile["digest"],
                        "closureDigest": license_profile["closureDigest"],
                        "target": "predicate",
                    }
                ],
            },
            {
                "id": "urn:makoto:example:rule:letters-origin",
                "predicateTypes": ["https://usemakoto.dev/predicate/v0.2/origin"],
                "authorizedKeyIds": [signing["letters-maintainer"].keyid()],
                "minimumSignatures": 1,
                "sourceKinds": [SOURCE_KIND],
                "sourceUris": [SOURCE_URI],
            },
        ],
        "handoff": {
            "authorizedKeyIds": [signing["index-maintainer"].keyid()],
            "minimumSignatures": 1,
            "requireExpectedManifest": False,
            "requireExpectedHead": False,
            "requireExpectedArtifacts": True,
            "requireRecipient": False,
            "requireNonce": False,
            "allowReplayableHandoff": False,
        },
        "requiredProfiles": [],
        "limits": LIMITS,
    }


def payload(envelope_path: Path) -> bytes:
    envelope = strict_json_loads(envelope_path.read_bytes())
    assert isinstance(envelope, dict)
    return canonical_b64decode(envelope["payload"])


def build(out: Path) -> None:
    """Write the repo, lookaside and build trees under `out`."""
    repo, lookaside, display = out / "repo", out / "lookaside", out / "build"
    leaf = repo / LEAF
    signing = keys()
    with tempfile.TemporaryDirectory() as scratch_name:
        work = Path(scratch_name)
        for name, key in signing.items():
            write(work / f"keys/{name}.pem", key.private_pkcs8_pem())

        # The corpus as the upstream archive serves it, and as the ingest writes it.
        raw_entries = []
        for name, text in LETTERS:
            write(lookaside / "raw" / name, text.encode())
            raw_entries.append((name, text.encode(), "text/plain"))
        shards = []
        for name, letters, override in SHARDS:
            data = shard_bytes(letters, override)
            write(lookaside / name, data)
            shards.append((name, data, len(letters), override))

        write(
            repo / "index.yaml",
            b"# Directories beneath this one that hold corpora.\nchildren:\n  - text/\n",
        )
        write(repo / "text/index.yaml", b"children:\n  - letters/\n")
        write(leaf / "ingest.yaml", INGEST_PARAMETERS.encode())
        write(leaf / LEAF_MANIFEST, leaf_manifest(shards))
        write(work / RAW_MANIFEST, dataset_manifest(raw_entries))
        write(work / SHARD_MANIFEST, dataset_manifest([(n, d, NDJSON) for n, d, _, _ in shards]))

        # The repository's receiver policy and the license profile it demands.
        lineage = repo / "lineage"
        write(lineage / "schemas/license-v1.schema.json", pretty(LICENSE_PROFILE))
        schema_bytes = (lineage / "schemas/license-v1.schema.json").read_bytes()
        write_json(
            lineage / "catalog.json",
            {
                "version": "0.2",
                "resources": [
                    {
                        "id": LICENSE_PROFILE_ID,
                        "digest": {"sha256": sha256(schema_bytes)},
                        "path": "schemas/license-v1.schema.json",
                    }
                ],
            },
        )
        makoto(
            "profile", "create",
            "--schema-root", str(lineage / "schemas/license-v1.schema.json"),
            "--target", "predicate",
            "--critical", "true",
            "--schema-catalog", str(lineage / "catalog.json"),
            "--out", str(work / "license.profile.json"),
            cwd=work,
        )  # fmt: skip
        license_profile = strict_json_loads((work / "license.profile.json").read_bytes())
        assert isinstance(license_profile, dict)
        write_json(lineage / "license.profile.json", license_profile)
        write_json(lineage / "policy.json", policy(signing, license_profile))
        for subject in (RAW_MANIFEST, SHARD_MANIFEST):
            write_json(
                work / f"{subject}.profile.json",
                core_dataset_manifest_profile_reference(subject),
            )
        write_json(
            work / "source.json",
            {
                "name": "Harbour town archive, letters series",
                "mediaType": "text/plain",
                "retrievedAt": RETRIEVED_AT,
                "version": "2026-09-01",
            },
        )
        write_json(
            work / "operation.json",
            {
                "tool": {
                    "name": "corpus-ingest",
                    "version": "1.4.0",
                    "uri": "https://tools.corpus.example/corpus-ingest",
                },
                "parametersDigest": {"sha256": sha256(INGEST_PARAMETERS.encode())},
            },
        )
        write_json(work / "license-extension.json", license_extension())

        attestations = work / "attestations"
        attestations.mkdir()
        makoto(
            "attest", "origin",
            "--subject", f"{RAW_MANIFEST}={work / RAW_MANIFEST}",
            "--source-kind", SOURCE_KIND,
            "--source-uri", SOURCE_URI,
            "--source-metadata", str(work / "source.json"),
            "--profile", str(work / f"{RAW_MANIFEST}.profile.json"),
            "--event-id", ORIGIN_EVENT,
            "--occurred-at", ORIGIN_AT,
            "--key", str(work / "keys/letters-maintainer.pem"),
            "--out", str(attestations / "01-origin.dsse.json"),
            cwd=work,
        )  # fmt: skip
        write_json(
            work / "ingest-input.json",
            {
                "name": "raw",
                "path": RAW_MANIFEST,
                "predecessor": "attestations/01-origin.dsse.json",
                "subjectName": RAW_MANIFEST,
            },
        )
        ingest = [
            "attest", "transform",
            "--subject", f"{LEAF_MANIFEST}={leaf / LEAF_MANIFEST}",
            "--subject", f"{SHARD_MANIFEST}={work / SHARD_MANIFEST}",
            "--input-binding", str(work / "ingest-input.json"),
            "--operation-type", INGEST_TYPE,
            "--operation-name", "Ingest the letters series into NDJSON shards",
            "--operation-metadata", str(work / "operation.json"),
            "--profile", str(work / f"{SHARD_MANIFEST}.profile.json"),
            "--event-id", INGEST_EVENT,
            "--occurred-at", INGEST_AT,
            "--key", str(work / "keys/letters-maintainer.pem"),
        ]  # fmt: skip
        makoto(
            *ingest,
            "--extensions", str(work / "license-extension.json"),
            "--profile", str(work / "license.profile.json"),
            "--schema-catalog", str(lineage / "catalog.json"),
            "--out", str(attestations / "02-ingest.dsse.json"),
            cwd=work,
        )  # fmt: skip
        handoff(work, attestations, leaf / "makoto", leaf / LEAF_MANIFEST, lineage)

        # Decoded documents for display, named by role rather than by digest.
        origin_payload = payload(attestations / "01-origin.dsse.json")
        ingest_payload = payload(attestations / "02-ingest.dsse.json")
        manifest_payload = payload(leaf / "makoto/manifest.dsse.json")
        for name, data in (
            ("origin.statement.json", origin_payload),
            ("ingest.statement.json", ingest_payload),
            ("handoff.json", manifest_payload),
            (RAW_MANIFEST, (work / RAW_MANIFEST).read_bytes()),
            (SHARD_MANIFEST, (work / SHARD_MANIFEST).read_bytes()),
            ("license-extension.json", (work / "license-extension.json").read_bytes()),
        ):
            write(display / name, pretty(json.loads(data)))

        record = leaf / "makoto"
        write(
            display / "verify.txt",
            transcript(*verify_bundle(record, repo, leaf / LEAF_MANIFEST)).encode(),
        )
        expected_artifact(record, leaf / LEAF_MANIFEST, display / "expected-letters.json")
        rules = json.loads((lineage / "policy.json").read_bytes())["rules"]
        (ingest_rule,) = [rule for rule in rules if rule.get("operationTypes") == [INGEST_TYPE]]
        write(display / "ingest-rule.json", pretty(ingest_rule))

        # A reader fetched one shard from the lookaside and checks it against the record.
        shard_name = SHARDS[1][0]
        shard = (lookaside / shard_name).read_bytes()
        shard_binding = {
            "manifestStatementDigest": {"sha256": sha256(ingest_payload)},
            "manifestSubjectName": SHARD_MANIFEST,
            "entryName": shard_name,
            "digest": {"sha256": sha256(shard)},
            "path": "letters-00001.ndjson",
        }
        write(display / "shard-binding.json", pretty(shard_binding))
        entry = ("--dataset-entry-binding", "../downloads/letters-00001.json")

        def downloads(data: bytes) -> dict[str, bytes]:
            return {
                "downloads/letters-00001.json": canonical_json(shard_binding) + b"\n",
                "downloads/letters-00001.ndjson": data,
            }

        fetched = verify_bundle(record, repo, leaf / LEAF_MANIFEST, entry, beside=downloads(shard))
        write(display / "shard-verify.txt", transcript(*fetched).encode())
        _, as_json = verify_bundle(
            record, repo, leaf / LEAF_MANIFEST, entry, ("--json", ""), beside=downloads(shard)
        )
        report = json.loads(as_json)
        assert report["decision"] == "allow", report["errors"]
        write(display / "shard-entries.json", pretty(report["datasetEntries"]))
        tampered = verify_bundle(
            record,
            repo,
            leaf / LEAF_MANIFEST,
            entry,
            beside=downloads(shard.replace(b"Friday", b"Monday")),
            expect=1,
        )
        write(display / "shard-tampered.txt", transcript(*tampered).encode())

        # Negative case for the licensing page: the same ingest, signed without the
        # license claim, is refused by the rule that demands the license profile.
        bare = work / "bare"
        (bare / "attestations").mkdir(parents=True)
        shutil.copy(attestations / "01-origin.dsse.json", bare / "attestations")
        makoto(*ingest, "--out", str(bare / "attestations/02-ingest.dsse.json"), cwd=work)
        bare_repo = work / "bare-repo/repo"
        shutil.copytree(repo, bare_repo)
        shutil.rmtree(bare_repo / LEAF / "makoto")
        handoff(
            work, bare / "attestations", bare_repo / LEAF / "makoto", leaf / LEAF_MANIFEST, lineage
        )
        refused = verify_bundle(
            bare_repo / LEAF / "makoto", bare_repo, bare_repo / LEAF / LEAF_MANIFEST, expect=1
        )
        write(display / "verify-without-license.txt", transcript(*refused).encode())

        # The check a pull request runs, on a change it accepts and one it refuses.
        write(display / "check-current.txt", check_lineage(repo, work, edit=False).encode())
        write(display / "check-stale.txt", check_lineage(repo, work, edit=True).encode())


def handoff(work: Path, attestations: Path, out: Path, leaf_manifest: Path, lineage: Path) -> None:
    bindings = work / "handoff-bindings"
    if bindings.exists():
        shutil.rmtree(bindings)
    bindings.mkdir()
    head = attestations / "02-ingest.dsse.json"
    write_json(
        bindings / "leaf.json",
        {"head": str(head), "subjectName": LEAF_MANIFEST, "path": str(leaf_manifest)},
    )
    for statement, subject in (("01-origin", RAW_MANIFEST), ("02-ingest", SHARD_MANIFEST)):
        write_json(
            bindings / f"{subject}.material.json",
            {
                "statement": str(attestations / f"{statement}.dsse.json"),
                "subjectName": subject,
                "path": str(work / subject),
            },
        )
    makoto(
        "handoff", "create",
        "--head", str(head),
        "--attestations", str(attestations),
        "--artifact-binding", str(bindings / "leaf.json"),
        "--artifact-material", str(bindings / f"{RAW_MANIFEST}.material.json"),
        "--artifact-material", str(bindings / f"{SHARD_MANIFEST}.material.json"),
        "--schema-catalog", str(lineage / "catalog.json"),
        "--bundle-id", BUNDLE_ID,
        "--issued-at", HANDOFF_AT,
        "--key", str(work / "keys/index-maintainer.pem"),
        "--out", str(out),
        cwd=work,
    )  # fmt: skip


def expected_artifact(bundle: Path, leaf_manifest: Path, path: Path) -> None:
    handoff_payload = json.loads(payload(bundle / "manifest.dsse.json"))
    (artifact,) = handoff_payload["artifacts"]
    write_json(
        path,
        {
            "head": artifact["head"],
            "subjectName": artifact["name"],
            "digest": {"sha256": sha256(leaf_manifest.read_bytes())},
        },
    )


def transcript(lines: list[str], output: str) -> str:
    """A shell transcript: the command as a reader would type it, then what it printed."""
    return "$ " + " \\\n  ".join(lines) + "\n" + output


def verify_bundle(
    bundle: Path,
    repo: Path,
    leaf_manifest: Path,
    *options: tuple[str, str],
    beside: dict[str, bytes] | None = None,
    expect: int = 0,
) -> tuple[list[str], str]:
    """Run the receiver's command from the repository root.

    Returns the command, one option per line, and what it printed. The
    consumer's own files (the expected-artifact binding and anything in
    `beside`) sit next to the repository, outside the bundle, as the CLI requires.
    """
    staged = {"expected-letters.json": b""} | (beside or {})
    for name, data in staged.items():
        write(repo.parent / name, data)
    expected_artifact(bundle, leaf_manifest, repo.parent / "expected-letters.json")
    lines = [
        f"makoto verify bundle {os.path.relpath(bundle, repo)}",
        "--policy lineage/policy.json",
        "--schema-catalog lineage/catalog.json",
        "--expected-artifact ../expected-letters.json",
        *(f"{flag} {value}".rstrip() for flag, value in options),
    ]
    try:
        tokens = [token for line in lines for token in line.split()]
        output = makoto(*tokens[1:], cwd=repo, expect=expect)
    finally:
        for name in staged:
            (repo.parent / name).unlink()
        shutil.rmtree(repo.parent / "downloads", ignore_errors=True)
    return lines, output


def check_lineage(repo: Path, work: Path, *, edit: bool) -> str:
    """Run the repository's pull-request check on a throwaway Git copy of the corpus."""
    clone = work / ("check-stale" if edit else "check-current")
    shutil.copytree(repo, clone)
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Example Contributor",
        "GIT_AUTHOR_EMAIL": "contributor@corpus.example",
        "GIT_COMMITTER_NAME": "Example Contributor",
        "GIT_COMMITTER_EMAIL": "contributor@corpus.example",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
    }

    def git(*arguments: str) -> None:
        subprocess.run(["git", *arguments], cwd=clone, env=env, check=True, capture_output=True)

    git("init", "--quiet", "--initial-branch=main")
    git("add", "-A")
    git("commit", "--quiet", "-s", "-m", "Add the letters corpus")
    git("checkout", "--quiet", "-b", "contribution")
    manifest = clone / LEAF / LEAF_MANIFEST
    if edit:
        # A contributor adds a shard to the manifest by hand and leaves the record alone.
        manifest.write_bytes(
            manifest.read_bytes()
            + b"  - name: shards/letters-00002.ndjson\n"
            + f"    sha256: {sha256(b'extra')}\n".encode()
            + b"    bytes: 5\n    records: 1\n"
        )
    else:
        # A contributor changes a file the record does not cover.
        (clone / "README.md").write_bytes(b"Harbour Letters corpus.\n")
    git("add", "-A")
    git("commit", "--quiet", "-s", "-m", "Update the letters corpus")
    command = ["uv", "run", "--no-project", "lineage/check_lineage.py", "--base", "main"]
    completed = subprocess.run(
        command, cwd=clone, env=env, check=False, capture_output=True, text=True
    )
    if completed.returncode != (1 if edit else 0):
        raise SystemExit(
            f"check_lineage exited {completed.returncode}\n{completed.stdout}{completed.stderr}"
        )
    return transcript([" ".join(command)], completed.stdout)


def tree(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def generated_files(root: Path) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    for name in GENERATED:
        for relative, data in tree(root / name).items():
            files[f"{name}/{relative}"] = data
    for relative in HAND_WRITTEN:
        files.pop(relative, None)
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail on any drift")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as scratch_name:
        fresh = Path(scratch_name)
        for relative in HAND_WRITTEN:
            write(fresh / relative, (EXAMPLE / relative).read_bytes())
        build(fresh)
        expected = generated_files(fresh)
        committed = generated_files(EXAMPLE)
        if args.check:
            drift = sorted(
                name
                for name in expected.keys() | committed.keys()
                if expected.get(name) != committed.get(name)
            )
            if drift:
                print("corpus example drift:", *drift, sep="\n  ", file=sys.stderr)
                return 1
            print(f"corpus example matches ({len(expected)} files)")
            return 0
        for name in committed.keys() - expected.keys():
            (EXAMPLE / name).unlink()
        for name, data in expected.items():
            write(EXAMPLE / name, data)
        print(f"wrote {len(expected)} files under {EXAMPLE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
