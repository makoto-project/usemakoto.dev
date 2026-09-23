"""The sharded-corpus guide shows exactly what scripts/corpus_example.py generates.

Every block on the three /examples/corpus/ pages is compared with the file it
claims to show, every JSON block that is a Makoto document is validated against
the published schemas, and the generator's own check re-signs and re-verifies the
whole record under the pinned core.
"""

from __future__ import annotations

import base64
import hashlib
import html
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/corpus"
REPO = EXAMPLE / "repo"
BUILD = EXAMPLE / "build"
RECORD = REPO / "text/letters/makoto"
PAGES = ("index.html", "licenses/index.html", "maintenance/index.html")
BLOCK = re.compile(
    r'<pre(?P<attrs>[^>]*)><code class="language-(?P<lang>[\w-]+)">(?P<body>.*?)</code></pre>',
    re.DOTALL,
)
FILENAME = re.compile(r'data-filename="([^"]*)"')


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def payload(envelope: Path) -> bytes:
    return base64.b64decode(json.loads(envelope.read_bytes())["payload"])


def statements() -> dict[str, bytes]:
    """Signed statement payloads in the record, by predicate kind."""
    found = {}
    for path in (RECORD / "attestations").glob("*.dsse.json"):
        data = payload(path)
        assert path.name == f"{sha256(data)}.dsse.json"
        found[json.loads(data)["predicateType"].rsplit("/", 1)[1]] = data
    return found


def material(subject: str) -> bytes:
    index = json.loads((RECORD / "bundle.json").read_bytes())
    (entry,) = [item for item in index["artifacts"] if item["subjectName"] == subject]
    return (RECORD / entry["path"]).read_bytes()


def sources() -> dict[str, bytes]:
    """What each titled exhibit on the guide claims to show."""
    signed = statements()
    files = {
        "index.yaml": REPO / "index.yaml",
        "text/index.yaml": REPO / "text/index.yaml",
        "text/letters/letters.yaml": REPO / "text/letters/letters.yaml",
        "lookaside · shards/letters-00001.ndjson": EXAMPLE
        / "lookaside/shards/letters-00001.ndjson",
        "../expected-letters.json": BUILD / "expected-letters.json",
        "../downloads/letters-00001.json": BUILD / "shard-binding.json",
        "report · datasetEntries": BUILD / "shard-entries.json",
        "lineage/policy.json · the ingest rule": BUILD / "ingest-rule.json",
        "extensions for the ingest statement": BUILD / "license-extension.json",
        "lineage/schemas/license-v1.schema.json": REPO / "lineage/schemas/license-v1.schema.json",
        "lineage/license.profile.json": REPO / "lineage/license.profile.json",
        ".github/workflows/lineage.yml": REPO / ".github/workflows/lineage.yml",
        "lineage/check_lineage.py": REPO / "lineage/check_lineage.py",
    }
    shown = {name: path.read_bytes() for name, path in files.items()}
    shown["letters.raw.json"] = material("letters.raw.json")
    shown["letters.shards.json"] = material("letters.shards.json")
    shown["origin statement · signed payload"] = signed["origin"]
    shown["ingest statement · signed payload"] = signed["transform"]
    shown["handoff manifest · signed payload"] = payload(RECORD / "manifest.dsse.json")
    return shown


# Exhibits that are Makoto documents, and the published schema each must satisfy.
SCHEMAS = {
    "letters.raw.json": "dataset-manifest.schema.json",
    "letters.shards.json": "dataset-manifest.schema.json",
    "origin statement · signed payload": "statement.schema.json",
    "ingest statement · signed payload": "statement.schema.json",
    "handoff manifest · signed payload": "handoff.schema.json",
    "lineage/schemas/license-v1.schema.json": "profile-dialect.schema.json",
    "lineage/license.profile.json": "profile-reference.schema.json",
}


def blocks() -> list[tuple[str, str, str | None, str]]:
    found = []
    for page in PAGES:
        text = (EXAMPLE / page).read_text(encoding="utf-8")
        for match in BLOCK.finditer(text):
            name = FILENAME.search(match["attrs"])
            found.append(
                (page, match["lang"], name[1] if name else None, html.unescape(match["body"]))
            )
    return found


def validator(schema_name: str) -> Draft202012Validator:
    resources = []
    for path in sorted((ROOT / "schema/v0.2").glob("*.schema.json")):
        schema = json.loads(path.read_bytes())
        resources.append((schema["$id"], Resource.from_contents(schema)))
    schema = json.loads((ROOT / "schema/v0.2" / schema_name).read_bytes())
    return Draft202012Validator(schema, registry=Registry().with_resources(resources))


def test_every_titled_exhibit_shows_its_file_verbatim() -> None:
    shown = sources()
    titled = [(page, name, body) for page, _, name, body in blocks() if name]
    assert {name for _, name, _ in titled} - {"repository layout"} == set(shown)
    for page, name, body in titled:
        if name != "repository layout":
            assert body == shown[name].decode().rstrip("\n"), f"{page}: {name}"


def test_every_json_exhibit_is_titled_and_every_makoto_document_validates() -> None:
    for page, lang, name, body in blocks():
        if lang != "json":
            continue
        assert name is not None, f"{page}: untitled JSON block"
        if name in SCHEMAS:
            errors = [
                error.message for error in validator(SCHEMAS[name]).iter_errors(json.loads(body))
            ]
            assert errors == [], f"{page}: {name} violates {SCHEMAS[name]}: {errors[:3]}"


def test_repository_policy_and_catalog_validate() -> None:
    policy = json.loads((REPO / "lineage/policy.json").read_bytes())
    assert list(validator("trust-policy.schema.json").iter_errors(policy)) == []
    catalog = json.loads((REPO / "lineage/catalog.json").read_bytes())
    assert list(validator("catalog.schema.json").iter_errors(catalog)) == []
    rule = json.loads((BUILD / "ingest-rule.json").read_bytes())
    assert rule in policy["rules"]


def test_every_transcript_is_a_captured_run() -> None:
    captured = {path.read_text().rstrip("\n") for path in BUILD.glob("*.txt")}
    for page, lang, _, body in blocks():
        if lang == "bash":
            assert body in captured, f"{page}: shell block is not a captured run"


def test_repository_layout_names_only_real_paths() -> None:
    (layout,) = {body for _, _, name, body in blocks() if name == "repository layout"}
    stack: list[str] = []
    for line in layout.splitlines():
        depth = (len(line) - len(line.lstrip(" "))) // 2
        name = line.split()[0]
        stack[depth:] = [name.rstrip("/")]
        assert (REPO / "/".join(stack)).exists(), "/".join(stack)


def test_record_digests_chain_from_raw_files_to_handoff() -> None:
    signed = statements()
    origin, ingest = json.loads(signed["origin"]), json.loads(signed["transform"])
    raw, shards = material("letters.raw.json"), material("letters.shards.json")
    assert origin["subject"] == [{"name": "letters.raw.json", "digest": {"sha256": sha256(raw)}}]
    for entry in json.loads(raw)["entries"]:
        data = (EXAMPLE / "lookaside/raw" / entry["name"]).read_bytes()
        assert (entry["digest"]["sha256"], entry["size"]) == (sha256(data), len(data))
    for entry in json.loads(shards)["entries"]:
        data = (EXAMPLE / "lookaside" / entry["name"]).read_bytes()
        assert (entry["digest"]["sha256"], entry["size"]) == (sha256(data), len(data))
    (edge,) = ingest["predicate"]["inputs"]
    assert edge["digest"]["sha256"] == sha256(raw)
    assert edge["provenance"]["statementDigest"]["sha256"] == sha256(signed["origin"])
    leaf = (REPO / "text/letters/letters.yaml").read_bytes()
    assert {item["name"]: item["digest"]["sha256"] for item in ingest["subject"]} == {
        "letters.yaml": sha256(leaf),
        "letters.shards.json": sha256(shards),
    }
    params = (REPO / "text/letters/ingest.yaml").read_bytes()
    assert ingest["predicate"]["operation"]["parametersDigest"]["sha256"] == sha256(params)
    extension: dict[str, Any] = json.loads((BUILD / "license-extension.json").read_bytes())
    assert ingest["predicate"]["extensions"] == extension
    handoff = json.loads(payload(RECORD / "manifest.dsse.json"))
    assert handoff["statements"] == sorted(
        ({"sha256": sha256(data)} for data in signed.values()), key=lambda item: item["sha256"]
    )
    assert handoff["artifacts"] == [
        {
            "name": "letters.yaml",
            "digest": {"sha256": sha256(leaf)},
            "head": {"sha256": sha256(signed["transform"])},
        }
    ]


def test_guide_is_linked_once_from_the_casebook_and_not_from_navigation() -> None:
    linking = [
        path.relative_to(ROOT).as_posix()
        for path in ROOT.rglob("*.html")
        if 'href="/examples/corpus/"' in path.read_text(encoding="utf-8")
        and EXAMPLE not in path.parents
    ]
    assert linking == ["examples/index.html"]


def test_generator_rebuilds_the_committed_example_and_every_run_it_shows() -> None:
    result = subprocess.run(
        ["uv", "run", "--project", "../core", "python", "scripts/corpus_example.py", "--check"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
