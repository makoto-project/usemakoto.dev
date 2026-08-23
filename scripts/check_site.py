#!/usr/bin/env python3
"""Fail-closed local validation for the Makoto documentation and release mirror."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import unicodedata
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
CORE_SCHEMA_NAMES = (
    "bundle.schema.json",
    "catalog.json",
    "catalog.schema.json",
    "dataset-manifest.schema.json",
    "envelope.schema.json",
    "handoff.schema.json",
    "origin.schema.json",
    "profile-dialect.schema.json",
    "profile-reference.schema.json",
    "statement.schema.json",
    "transform.schema.json",
    "trust-policy.schema.json",
    "verification-report.schema.json",
)
LEGACY_PAGES = (
    "comparison/decision-guide.html",
    "comparison/index.html",
    "comparison/open-lineage.html",
    "comparison/w3c-prov.html",
    "demos/01/index.html",
    "demos/02/index.html",
    "demos/03/index.html",
    "demos/04/index.html",
    "demos/05/index.html",
    "demos/06/index.html",
    "demos/index.html",
    "demos/setup/index.html",
    "examples/index.html",
    "examples/invisible-unicode/index.html",
    "levels/index.html",
    "privacy/index.html",
    "spec/index.html",
    "spec/l1-requirements.html",
    "spec/l2-requirements.html",
    "spec/l3-requirements.html",
    "spec/signature-guide.html",
    "threats/index.html",
    "validate/index.html",
    "verify/bash.html",
    "verify/go.html",
    "verify/index.html",
    "verify/nodejs.html",
    "verify/python.html",
)
INTEGRATION_PAGES = (
    "expanso/index.html",
    "integrations/airflow/index.html",
    "integrations/databricks/index.html",
    "integrations/dagster/index.html",
    "integrations/dbt/index.html",
    "integrations/expanso/index.html",
    "integrations/index.html",
    "integrations/kafka/index.html",
    "integrations/prefect/index.html",
    "integrations/snowflake/index.html",
    "integrations/spark/index.html",
)
LINEAGE_PAGE = "why-lineage/index.html"
CURRENT_SHELL_PAGES = (
    "community/index.html",
    "demos/v0.2-end-to-end/index.html",
    "examples/v0.2/index.html",
    "index.html",
    "integrations/v0.2/index.html",
    "predicate/v0.2/origin/index.html",
    "predicate/v0.2/transform/index.html",
    "source/file/index.html",
    "spec/v0.2/index.html",
    "tooling/index.html",
    "vocab/v0.2/bounded-pattern/index.html",
    "why-lineage/index.html",
)
CURRENT_SHELL_MARKERS = (
    'class="docs-sidebar"',
    'class="mobile-menu"',
    'href="/why-lineage/"',
    'href="/examples/v0.2/"',
    'href="/source/file/"',
    'href="/vocab/v0.2/bounded-pattern/"',
    'href="/tooling/"',
    'href="/integrations/v0.2/"',
    'href="/community/"',
    'href="https://github.com/makoto-project/makoto"',
    'href="https://github.com/makoto-project/makoto/issues"',
)
LINEAGE_REQUIRED_TEXT = (
    "One file becomes ten copies. Its history usually doesn’t.",
    "Now let it move.",
    (
        "It lands in object storage, gets picked up into a warehouse, gets denormalized into three "
        "marts because three teams wanted different grain, gets a feature-store copy for the model, "
        "gets a nightly backup with a 90-day cycle, gets replicated to a second region for durability, "
        "gets pulled into a vendor's SaaS for enrichment, and gets exported once into a notebook by an "
        "analyst who left in March."
    ),
    (
        "Call that eight to ten locations, and I am being conservative, because I have not counted "
        "the CI fixture somebody generated from prod or the Slack thread with the screenshot."
    ),
    "A checksum is necessary. It is not lineage.",
    "Makoto does not discover an unrecorded notebook export or Slack screenshot.",
    "/demos/v0.2-end-to-end/",
    "/spec/v0.2/",
)
CANDIDATE_STATUS_TEXT = {
    "README.md": (
        "v0.2 is an unreleased candidate.",
        "artifacts, not proof of a tagged release or an immutable release contract.",
    ),
    "index.html": (
        "v0.2 candidate · not yet released",
        "These versioned URLs are mutable public review routes",
    ),
    "spec/v0.2/index.html": ("v0.2 candidate · not released",),
    "demos/v0.2-end-to-end/index.html": ("tested v0.2 candidate implementation · not released",),
}
DOCUMENTATION_FILES = {
    "/demos/v0.2-end-to-end/": "demos/v0.2-end-to-end/index.html",
    "/predicate/v0.2/origin/": "predicate/v0.2/origin/index.html",
    "/predicate/v0.2/transform/": "predicate/v0.2/transform/index.html",
    "/source/file/": "source/file/index.html",
    "/spec/v0.2/": "spec/v0.2/index.html",
    "/vocab/v0.2/bounded-pattern/": "vocab/v0.2/bounded-pattern/index.html",
}
STATIC_RESOURCES = {
    "docs/v0.2-adversarial-review.md": (
        "docs/v0.2-adversarial-review.md",
        "text/markdown",
    ),
    "docs/v0.2-architecture.md": ("docs/v0.2-architecture.md", "text/markdown"),
    "docs/v0.2-integrations.md": ("docs/v0.2-integrations.md", "text/markdown"),
    "docs/v0.2-migration.md": ("docs/v0.2-migration.md", "text/markdown"),
    "release/checksums.schema.json": (
        "tooling/release/checksums.schema.json",
        "application/json",
    ),
    "release/v0.2/checksums.json": ("release/v0.2/checksums.json", "application/json"),
    "spec/v0.2.md": ("spec/v0.2/spec.md", "text/markdown"),
    "testdata/v0.2/diagnostic-map.json": (
        "spec/v0.2/diagnostic-map.json",
        "application/json",
    ),
}
PUBLIC_TEXT_REWRITES = {
    "docs/v0.2-adversarial-review.md": (("(../spec/v0.2.md)", "(../spec/v0.2/spec.md)"),),
    "docs/v0.2-architecture.md": (
        (
            "[`testdata/v0.2/diagnostic-map.json`](../testdata/v0.2/diagnostic-map.json)",
            "[`spec/v0.2/diagnostic-map.json`](../spec/v0.2/diagnostic-map.json)",
        ),
        ("(../spec/v0.2.md)", "(../spec/v0.2/spec.md)"),
    ),
    "docs/v0.2-migration.md": (
        ("(../demos/v0.2-end-to-end/README.md)", "(../demos/v0.2-end-to-end/)"),
    ),
}
JSON_EXAMPLE_SCHEMAS = {
    "demos/v0.2-end-to-end/artifacts/positive-bundle/attestations/1f28b72bcd4c1e9b7df71403ac6bb1670c2f2b09628ca6d76a2fa384db9a0848.dsse.json": "envelope.schema.json",
    "demos/v0.2-end-to-end/artifacts/positive-bundle/attestations/56b7be4394fe09c62ec7a3d5763cecc251e9696f267f35b2acc717b0d170a27a.dsse.json": "envelope.schema.json",
    "demos/v0.2-end-to-end/artifacts/positive-bundle/attestations/962be71738a0146642d27c87fba3c7338b0f2bb764b113b16867bb4808b11977.dsse.json": "envelope.schema.json",
    "demos/v0.2-end-to-end/artifacts/positive-bundle/bundle.json": "bundle.schema.json",
    "demos/v0.2-end-to-end/artifacts/positive-bundle/manifest.dsse.json": "envelope.schema.json",
    "demos/v0.2-end-to-end/artifacts/receiver/attacker-known-policy.json": "trust-policy.schema.json",
    "demos/v0.2-end-to-end/artifacts/receiver/catalog.json": "catalog.schema.json",
    "demos/v0.2-end-to-end/artifacts/receiver/customer-public.profile.json": "profile-reference.schema.json",
    "demos/v0.2-end-to-end/artifacts/receiver/policy.json": "trust-policy.schema.json",
    "demos/v0.2-end-to-end/artifacts/receiver/public-transform-metadata.profile.json": "profile-reference.schema.json",
    "demos/v0.2-end-to-end/artifacts/receiver/resources/31934d2cf8fa7b5af2f8e4cf591d96278c4f59ddb6bb190afccb93701244f9eb.schema.json": "profile-dialect.schema.json",
    "demos/v0.2-end-to-end/artifacts/receiver/resources/68169d043c628fda5435cbd7845b02ea3e0d850b7a509c0b35fd304463fffacb.schema.json": "profile-dialect.schema.json",
    "demos/v0.2-end-to-end/artifacts/reports/edited-signed-metadata.json": "verification-report.schema.json",
    "demos/v0.2-end-to-end/artifacts/reports/mutated-final-data.json": "verification-report.schema.json",
    "demos/v0.2-end-to-end/artifacts/reports/positive.json": "verification-report.schema.json",
    "demos/v0.2-end-to-end/artifacts/reports/private-schema-violation.json": "verification-report.schema.json",
    "demos/v0.2-end-to-end/artifacts/reports/removed-predecessor.json": "verification-report.schema.json",
    "demos/v0.2-end-to-end/artifacts/reports/rewired-step.json": "verification-report.schema.json",
    "demos/v0.2-end-to-end/artifacts/reports/statement-digest-mismatch.json": "verification-report.schema.json",
    "demos/v0.2-end-to-end/artifacts/reports/unauthorized-signer.json": "verification-report.schema.json",
}
FORBIDDEN_TRACKED_SEGMENTS = {
    ".codex-work",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".specstory",
    ".venv",
    "__pycache__",
    "node_modules",
}
CORE_CHECKSUM_PREFIXES = (
    "demos/v0.2-end-to-end",
    "docs",
    "schemas/v0.2",
    "scripts",
    "src/makoto",
    "testdata/v0.2",
    "tests",
)
CORE_CHECKSUM_EXACT_PATHS = (
    "LICENSE",
    "README.md",
    "pyproject.toml",
    "release/checksums.schema.json",
    "spec/v0.2.md",
    "uv.lock",
)
CORE_CHECKSUM_FORBIDDEN_SEGMENTS = {
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".work",
    "__pycache__",
}


class DuplicateKeyError(ValueError):
    pass


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: list[str] = []
        self.references: list[str] = []
        self.in_mobile_nav = False
        self.mobile_current_hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "nav" and values.get("aria-label") == "Mobile":
            self.in_mobile_nav = True
        if (
            self.in_mobile_nav
            and tag == "a"
            and values.get("aria-current") == "page"
            and values.get("href")
        ):
            self.mobile_current_hrefs.append(str(values["href"]))
        if values.get("id") is not None:
            self.ids.append(str(values["id"]))
        for name in ("href", "src"):
            if values.get(name):
                self.references.append(str(values[name]))
        if values.get("srcset"):
            for candidate in str(values["srcset"]).split(","):
                url = candidate.strip().split(" ", 1)[0]
                if url:
                    self.references.append(url)

    def handle_endtag(self, tag: str) -> None:
        if tag == "nav" and self.in_mobile_nav:
            self.in_mobile_nav = False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--working-tree", type=Path)
    mode.add_argument("--candidate", action="store_true")
    mode.add_argument("--release", action="store_true")
    parser.add_argument("--core-repo", type=Path)
    return parser.parse_args()


def strict_json(path: Path) -> Any:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError(f"{path}: UTF-8 BOM is forbidden")

    def pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in values:
            if key in result:
                raise DuplicateKeyError(f"{path}: duplicate JSON key {key!r}")
            result[key] = value
        return result

    return json.loads(raw, object_pairs_hook=pairs)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def public_resource_bytes(source_path: str, data: bytes) -> bytes:
    rewrites = PUBLIC_TEXT_REWRITES.get(source_path, ())
    if not rewrites:
        return data
    text = data.decode("utf-8")
    for original, replacement in rewrites:
        if text.count(original) != 1:
            raise ValueError(
                f"public-link rewrite source is absent or duplicated in {source_path}: {original}"
            )
        text = text.replace(original, replacement)
    return text.encode("utf-8")


def exact_files(root: Path) -> dict[str, Path]:
    return {
        path.relative_to(root).as_posix(): path
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def compare_trees(left: Path, right: Path, label: str, errors: list[str]) -> None:
    left_files = exact_files(left)
    right_files = exact_files(right)
    if set(left_files) != set(right_files):
        missing = sorted(set(right_files) - set(left_files))
        extra = sorted(set(left_files) - set(right_files))
        errors.append(f"{label} path set differs: missing={missing!r} extra={extra!r}")
    for relative in sorted(set(left_files) & set(right_files)):
        if left_files[relative].read_bytes() != right_files[relative].read_bytes():
            errors.append(f"{label} bytes differ: {relative}")


def expected_resource_files() -> dict[str, tuple[Path, str, bool]]:
    resources = {
        f"/{relative}": (ROOT / relative, media_type, True)
        for _, (relative, media_type) in STATIC_RESOURCES.items()
    }
    demo_root = ROOT / "demos/v0.2-end-to-end/artifacts"
    for relative, path in exact_files(demo_root).items():
        media_type = "application/octet-stream" if path.suffix == ".bin" else "application/json"
        resources[f"/demos/v0.2-end-to-end/artifacts/{relative}"] = (
            path,
            media_type,
            True,
        )
    return resources


def validate_pin(mode: str, core_repo: Path | None, errors: list[str]) -> Path | None:
    candidate = ROOT / "schema/core-candidate.json"
    release = ROOT / "schema/core-release.json"
    expected = candidate if mode == "candidate" else release
    forbidden = release if mode == "candidate" else candidate
    if not expected.is_file():
        errors.append(f"{mode} pin is absent: {expected.relative_to(ROOT)}")
        return core_repo
    if forbidden.exists():
        errors.append(f"candidate and release pins cannot coexist: {forbidden.relative_to(ROOT)}")
    schema_path = ROOT / f"schema/core-{mode}.schema.json"
    try:
        pin = strict_json(expected)
        schema = strict_json(schema_path)
        Draft202012Validator(schema).validate(pin)
    except (OSError, ValueError, SchemaError, ValidationError) as error:
        errors.append(f"invalid {mode} pin: {error}")
        return core_repo
    canonical = (
        json.dumps(pin, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode() + b"\n"
    )
    if expected.read_bytes() != canonical:
        errors.append(f"{mode} pin is not canonical JSON plus one LF")
    for collection in ("schemas", "documentation", "resources"):
        paths = [item["path"] for item in pin[collection]]
        if paths != sorted(paths, key=str.encode) or len(paths) != len(set(paths)):
            errors.append(f"{mode} pin {collection} paths are not sorted and unique")
    expected_schema_paths = {f"/schema/v0.2/{name}" for name in CORE_SCHEMA_NAMES}
    schema_entries = {item["path"]: item for item in pin["schemas"]}
    if set(schema_entries) != expected_schema_paths:
        errors.append(f"{mode} pin schema path set is not exact")
    for public_path, item in sorted(schema_entries.items()):
        local_path = ROOT / public_path.lstrip("/")
        if not local_path.is_file():
            errors.append(f"{mode} pin schema is absent: {public_path}")
        elif sha256(local_path) != item["digest"]["sha256"]:
            errors.append(f"{mode} pin schema digest differs: {public_path}")
    documentation_entries = {item["path"]: item for item in pin["documentation"]}
    if set(documentation_entries) != set(DOCUMENTATION_FILES):
        errors.append(f"{mode} pin documentation path set is not exact")
    for public_path, relative in sorted(DOCUMENTATION_FILES.items()):
        item = documentation_entries.get(public_path)
        if item is not None and sha256(ROOT / relative) != item["digest"]["sha256"]:
            errors.append(f"{mode} pin documentation digest differs: {public_path}")
    resource_entries = {item["path"]: item for item in pin["resources"]}
    expected_resources = expected_resource_files()
    if set(resource_entries) != set(expected_resources):
        errors.append(f"{mode} pin resource path set is not exact")
    for public_path, (local_path, media_type, cors) in sorted(expected_resources.items()):
        item = resource_entries.get(public_path)
        if item is None:
            continue
        if not local_path.is_file():
            errors.append(f"{mode} pin resource is absent: {public_path}")
        elif sha256(local_path) != item["digest"]["sha256"]:
            errors.append(f"{mode} pin resource digest differs: {public_path}")
        if item["mediaType"] != media_type or item["cors"] is not cors:
            errors.append(f"{mode} pin resource metadata differs: {public_path}")
    if core_repo is None:
        core_repo = ROOT.parent / "core"
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=core_repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as error:
        errors.append(f"cannot inspect core repository: {error}")
    else:
        if head != pin["commit"]:
            errors.append(f"core HEAD {head} does not equal pinned commit {pin['commit']}")
        if mode == "release":
            tag = subprocess.run(
                ["git", "rev-parse", "v0.2.0^{}"],
                cwd=core_repo,
                check=False,
                capture_output=True,
                text=True,
            ).stdout.strip()
            if tag != pin["commit"]:
                errors.append("v0.2.0 does not resolve to the pinned release commit")
    return core_repo


def expected_core_checksum_paths(core: Path) -> tuple[str, ...]:
    paths = set(CORE_CHECKSUM_EXACT_PATHS)
    for prefix in CORE_CHECKSUM_PREFIXES:
        directory = core / prefix
        if not directory.is_dir():
            continue
        for path in directory.rglob("*"):
            if path.is_file() and not CORE_CHECKSUM_FORBIDDEN_SEGMENTS.intersection(path.parts):
                paths.add(path.relative_to(core).as_posix())
    return tuple(sorted(paths, key=str.encode))


def validate_core_checksums(core: Path, errors: list[str]) -> dict[str, str]:
    manifest_path = core / "release/v0.2/checksums.json"
    schema_path = core / "release/checksums.schema.json"
    try:
        manifest = strict_json(manifest_path)
        schema = strict_json(schema_path)
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(manifest)
    except (OSError, ValueError, SchemaError, ValidationError) as error:
        errors.append(f"invalid core checksum manifest: {error}")
        return {}
    canonical = (
        json.dumps(manifest, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
        + b"\n"
    )
    if manifest_path.read_bytes() != canonical:
        errors.append("core checksum manifest is not canonical JSON plus one LF")
    paths = [item["path"] for item in manifest["files"]]
    if paths != sorted(paths, key=str.encode) or len(paths) != len(set(paths)):
        errors.append("core checksum paths are not sorted and unique")
    if any(path != unicodedata.normalize("NFC", path) for path in paths):
        errors.append("core checksum paths are not NFC")
    expected_paths = expected_core_checksum_paths(core)
    if tuple(paths) != expected_paths:
        errors.append("core checksum inclusion set is not exact")
    digests = {item["path"]: item["digest"]["sha256"] for item in manifest["files"]}
    for relative, expected_digest in sorted(digests.items()):
        path = core / relative
        if not path.is_file() or sha256(path) != expected_digest:
            errors.append(f"core checksum digest differs: {relative}")
    return digests


def check_core_parity(core: Path, errors: list[str]) -> None:
    checksum_digests = validate_core_checksums(core, errors)
    website_schema = ROOT / "schema/v0.2"
    core_schema = core / "schemas/v0.2"
    actual_names = tuple(sorted(path.name for path in website_schema.iterdir() if path.is_file()))
    if actual_names != tuple(sorted(CORE_SCHEMA_NAMES)):
        errors.append(f"website v0.2 schema set is wrong: {actual_names!r}")
    for name in CORE_SCHEMA_NAMES:
        website_path = website_schema / name
        core_path = core_schema / name
        if not website_path.is_file() or not core_path.is_file():
            errors.append(f"missing v0.2 schema resource: {name}")
            continue
        if website_path.read_bytes() != core_path.read_bytes():
            errors.append(f"schema bytes differ from core: {name}")
        checksum_digest = checksum_digests.get(f"schemas/v0.2/{name}")
        if checksum_digest is not None and sha256(website_path) != checksum_digest:
            errors.append(f"website schema differs from core checksum manifest: {name}")
        if name.endswith(".schema.json"):
            try:
                value = strict_json(website_path)
                Draft202012Validator.check_schema(value)
            except (OSError, ValueError, SchemaError) as error:
                errors.append(f"invalid JSON Schema {name}: {error}")
            else:
                expected_id = f"https://usemakoto.dev/schema/v0.2/{name}"
                if value.get("$id") != expected_id:
                    errors.append(f"schema $id differs from hosted URL: {name}")
    catalog_path = website_schema / "catalog.json"
    try:
        catalog = strict_json(catalog_path)
    except (OSError, ValueError) as error:
        errors.append(f"invalid core catalog: {error}")
    else:
        for resource in catalog.get("resources", []):
            resource_path = website_schema / resource["path"]
            if not resource_path.is_file() or sha256(resource_path) != resource["digest"]["sha256"]:
                errors.append(f"catalog digest mismatch: {resource.get('path')}")
    core_spec = core / "spec/v0.2.md"
    website_spec = ROOT / "spec/v0.2/spec.md"
    if core_spec.read_bytes() != website_spec.read_bytes():
        errors.append("spec/v0.2/spec.md differs from core spec/v0.2.md")
    legacy_spec_copy = ROOT / "docs/specs/makoto-v0.2-project-spec.md"
    if legacy_spec_copy.is_file() and legacy_spec_copy.read_bytes() != core_spec.read_bytes():
        errors.append("docs/specs/makoto-v0.2-project-spec.md differs from canonical core spec")
    for core_relative, (site_relative, _) in STATIC_RESOURCES.items():
        core_path = core / core_relative
        site_path = ROOT / site_relative
        try:
            expected_site_bytes = public_resource_bytes(core_relative, core_path.read_bytes())
        except (OSError, UnicodeError, ValueError) as error:
            errors.append(f"cannot derive website resource {site_relative}: {error}")
            continue
        if not site_path.is_file() or site_path.read_bytes() != expected_site_bytes:
            errors.append(f"website resource differs from core: {site_relative}")
        checksum_digest = checksum_digests.get(core_relative)
        if (
            core_path.is_file()
            and checksum_digest is not None
            and sha256(core_path) != checksum_digest
        ):
            errors.append(f"core resource differs from checksum manifest: {core_relative}")
    compare_trees(
        ROOT / "demos/v0.2-end-to-end/artifacts",
        core / "demos/v0.2-end-to-end/generated",
        "v0.2 demo artifacts",
        errors,
    )
    check_demo_manifest(errors)


def check_demo_manifest(errors: list[str]) -> None:
    root = ROOT / "demos/v0.2-end-to-end/artifacts"
    manifest_path = root / "manifest.json"
    try:
        manifest = strict_json(manifest_path)
    except (OSError, ValueError) as error:
        errors.append(f"invalid demo artifact manifest: {error}")
        return
    items = manifest.get("files")
    if not isinstance(items, list):
        errors.append("demo artifact manifest files must be an array")
        return
    paths = [item.get("path") for item in items if isinstance(item, dict)]
    if len(paths) != len(items) or any(not isinstance(path, str) for path in paths):
        errors.append("demo artifact manifest contains an invalid path")
        return
    if paths != sorted(paths, key=str.encode) or len(paths) != len(set(paths)):
        errors.append("demo artifact manifest paths are not sorted and unique")
    actual = set(exact_files(root)) - {"manifest.json"}
    if set(paths) != actual:
        errors.append("demo artifact manifest path set is not exact")
    for item in items:
        relative = item["path"]
        path = root / relative
        expected = item.get("digest", {}).get("sha256")
        if not path.is_file() or sha256(path) != expected:
            errors.append(f"demo artifact manifest digest differs: {relative}")


def resolve_local_reference(page: Path, reference: str) -> tuple[Path, str] | None:
    parsed = urlsplit(reference)
    if parsed.scheme in {"data", "mailto", "tel", "javascript"}:
        return None
    if parsed.scheme in {"http", "https"}:
        if parsed.netloc not in {"usemakoto.dev", "www.usemakoto.dev"}:
            return None
        raw_path = parsed.path
    elif parsed.scheme or parsed.netloc:
        return None
    else:
        raw_path = parsed.path
    if not raw_path:
        target = page
    elif raw_path.startswith("/"):
        target = ROOT / unquote(raw_path.lstrip("/"))
    else:
        target = page.parent / unquote(raw_path)
    try:
        resolved = target.resolve()
        resolved.relative_to(ROOT.resolve())
    except (OSError, ValueError):
        return ROOT / "__path_escape__", parsed.fragment
    if resolved.is_dir() or raw_path.endswith("/"):
        resolved /= "index.html"
    return resolved, unquote(parsed.fragment)


def check_links(errors: list[str]) -> None:
    parsed_pages: dict[Path, PageParser] = {}
    for page in sorted(ROOT.rglob("*.html")):
        parser = PageParser()
        try:
            parser.feed(page.read_text(encoding="utf-8"))
            parser.close()
        except (OSError, UnicodeError) as error:
            errors.append(f"HTML parse failed for {page.relative_to(ROOT)}: {error}")
            continue
        duplicates = sorted({value for value in parser.ids if parser.ids.count(value) > 1})
        if duplicates:
            errors.append(f"duplicate fragment IDs in {page.relative_to(ROOT)}: {duplicates!r}")
        parsed_pages[page.resolve()] = parser
    for page, parser in sorted(parsed_pages.items(), key=lambda item: str(item[0])):
        for reference in parser.references:
            resolved = resolve_local_reference(page, reference)
            if resolved is None:
                continue
            target, fragment = resolved
            if not target.is_file():
                errors.append(f"broken local reference in {page.relative_to(ROOT)}: {reference}")
                continue
            if fragment and target.suffix.lower() in {".html", ""}:
                target_parser = parsed_pages.get(target.resolve())
                if target_parser is None or fragment not in target_parser.ids:
                    errors.append(f"broken fragment in {page.relative_to(ROOT)}: {reference}")


def check_json_examples(errors: list[str]) -> None:
    schemas: dict[str, Any] = {}
    resources: list[tuple[str, Resource[Any]]] = []
    for name in CORE_SCHEMA_NAMES:
        if not name.endswith(".schema.json"):
            continue
        path = ROOT / "schema/v0.2" / name
        try:
            schema = strict_json(path)
            resource = Resource.from_contents(schema)
        except (OSError, ValueError) as error:
            errors.append(f"cannot load example schema {name}: {error}")
            continue
        schemas[name] = schema
        resources.append((schema["$id"], resource))
    registry = Registry().with_resources(resources)
    for relative, schema_name in sorted(JSON_EXAMPLE_SCHEMAS.items(), key=lambda item: item[0]):
        path = ROOT / relative
        schema = schemas.get(schema_name)
        if schema is None:
            errors.append(f"example schema unavailable for {relative}: {schema_name}")
            continue
        try:
            value = strict_json(path)
        except (OSError, ValueError) as error:
            errors.append(f"invalid JSON example {relative}: {error}")
            continue
        validation_errors = sorted(
            Draft202012Validator(schema, registry=registry).iter_errors(value),
            key=lambda error: list(error.absolute_path),
        )
        if validation_errors:
            detail = "; ".join(error.message for error in validation_errors[:3])
            errors.append(f"JSON example violates {schema_name}: {relative}: {detail}")


def check_tracked_files(errors: list[str]) -> None:
    result = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True)
    tracked = [Path(value.decode()) for value in result.stdout.split(b"\0") if value]
    forbidden = [
        path.as_posix() for path in tracked if FORBIDDEN_TRACKED_SEGMENTS.intersection(path.parts)
    ]
    if forbidden:
        errors.append(f"forbidden tracked dependencies/caches: {forbidden[:10]!r}")


def check_truthfulness(errors: list[str], *, mode: str = "working-tree") -> None:
    for relative in LEGACY_PAGES:
        if "Historical v0.1 material." not in (ROOT / relative).read_text(encoding="utf-8"):
            errors.append(f"historical v0.1 banner missing: {relative}")
    for relative in ("sdk/index.html", "sdk/javascript/examples/browser-example.html"):
        if "Historical v0.1 experiment" not in (ROOT / relative).read_text(encoding="utf-8"):
            errors.append(f"historical SDK banner missing: {relative}")
    for relative in INTEGRATION_PAGES:
        if "Conceptual integration only." not in (ROOT / relative).read_text(encoding="utf-8"):
            errors.append(f"conceptual integration banner missing: {relative}")
    for relative in CURRENT_SHELL_PAGES:
        path = ROOT / relative
        if not path.is_file():
            errors.append(f"current documentation page missing: {relative}")
            continue
        content = path.read_text(encoding="utf-8")
        for marker in CURRENT_SHELL_MARKERS:
            if marker not in content:
                errors.append(f"current documentation shell is incomplete in {relative}: {marker}")
        parser = PageParser()
        parser.feed(content)
        expected_current = (
            "/" if relative == "index.html" else f"/{relative.removesuffix('index.html')}"
        )
        if parser.mobile_current_hrefs != [expected_current]:
            errors.append(
                "mobile navigation current page differs in "
                f"{relative}: expected={[expected_current]!r} actual={parser.mobile_current_hrefs!r}"
            )
    community = ROOT / "community/index.html"
    contributing = ROOT / "CONTRIBUTING.md"
    if not contributing.is_file():
        errors.append("CONTRIBUTING.md is missing")
    if community.is_file():
        content = community.read_text(encoding="utf-8")
        for marker in (
            "Makoto is developed in public.",
            "Formal governance is not established yet",
            "makoto-project/makoto/issues/new",
            "makoto-project/usemakoto.dev/issues/new",
            "CONTRIBUTING.md",
        ):
            if marker not in content:
                errors.append(f"community participation path is incomplete: {marker}")
    tooling = ROOT / "tooling/index.html"
    if tooling.is_file():
        content = tooling.read_text(encoding="utf-8")
        for marker in (
            "package publication pending",
            "Historical v0.1 experiments",
            "not a published Makoto distribution",
            "no maintained v0.2 adapter packages are claimed",
        ):
            if marker not in content:
                errors.append(f"tooling status boundary is incomplete: {marker}")
    lineage_path = ROOT / LINEAGE_PAGE
    if not lineage_path.is_file():
        errors.append(f"lineage explanation page missing: {LINEAGE_PAGE}")
    else:
        lineage = lineage_path.read_text(encoding="utf-8")
        for required_text in LINEAGE_REQUIRED_TEXT:
            if required_text not in lineage:
                errors.append(f"lineage explanation is incomplete: {required_text}")
    combined = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in sorted(ROOT.rglob("*"))
        if path.is_file() and path.suffix in {".html", ".md"}
    )
    for false_command in (
        "uv add makoto",
        "pip install makoto",
        "npm install @makoto/sdk",
        "https://unpkg.com/@makoto/sdk",
        "https://api.makoto.dev/sign",
        "usemakoto.dev/demos/06-invisible-unicode-guardrails",
        "makoto/demos/06-invisible-unicode-guardrails",
        "Official libraries for Python and JavaScript",
    ):
        if false_command in combined:
            errors.append(f"false install/service claim remains: {false_command}")
    for page in sorted(ROOT.rglob("*.html")):
        if 'href="https://github.com"' in page.read_text(encoding="utf-8", errors="replace"):
            errors.append(f"bare GitHub link remains: {page.relative_to(ROOT)}")
    demo = (ROOT / "demos/v0.2-end-to-end/index.html").read_text(encoding="utf-8")
    if "artifact 4e90181e…" not in demo:
        errors.append("v0.2 demo does not display the verified source digest prefix")
    for required_demo_text in (
        "MAKOTO_RECEIVER_DIR",
        "--expected-manifest sha256:b83a5cd1",
        "--expected-artifact demos/v0.2-end-to-end/generated/receiver/expected-artifact.json",
        "artifacts/data/customers.public.json",
        "artifacts/receiver/expected-artifact.json",
    ):
        if required_demo_text not in demo:
            errors.append(f"v0.2 demo receiver story is incomplete: {required_demo_text}")
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    if "Apache License" not in license_text or "Version 2.0" not in license_text:
        errors.append("LICENSE is not Apache-2.0 text")
    if mode in {"working-tree", "candidate"}:
        for relative, markers in CANDIDATE_STATUS_TEXT.items():
            content = (ROOT / relative).read_text(encoding="utf-8")
            for marker in markers:
                if marker not in content:
                    errors.append(f"{mode} status marker is missing from {relative}: {marker}")
    elif mode == "release":
        for relative, markers in CANDIDATE_STATUS_TEXT.items():
            content = (ROOT / relative).read_text(encoding="utf-8")
            if any(marker in content for marker in markers):
                errors.append(f"release surface still has candidate status: {relative}")
    else:
        raise ValueError(f"unknown truthfulness mode: {mode}")


def main() -> int:
    args = parse_args()
    errors: list[str] = []
    if args.working_tree is not None:
        core = args.working_tree.resolve()
        validation_mode = "working-tree"
        if args.core_repo is not None:
            print("--core-repo cannot be combined with --working-tree", file=sys.stderr)
            return 2
    else:
        validation_mode = "candidate" if args.candidate else "release"
        core = validate_pin(validation_mode, args.core_repo, errors)
        if core is None:
            core = Path("/__missing_core__")
    if not (core / "schemas/v0.2/catalog.json").is_file():
        errors.append(f"core repository is invalid: {core}")
    else:
        check_core_parity(core, errors)
    check_links(errors)
    check_json_examples(errors)
    check_tracked_files(errors)
    check_truthfulness(errors, mode=validation_mode)
    if errors:
        for error in sorted(set(errors), key=str.encode):
            print(f"FAIL: {error}")
        return 1
    print("site check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
