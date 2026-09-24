#!/usr/bin/env python3
"""Fail-closed local validation for the Makoto documentation and release mirror."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
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
V03_CORE_SCHEMA_NAMES = tuple(
    sorted(
        (
            *CORE_SCHEMA_NAMES,
            "record-declaration.schema.json",
            "record-inclusion-proof.schema.json",
        ),
        key=str.encode,
    )
)
# Hosted schema families. v0.3 is published beside v0.2 and is not the default.
CORE_SCHEMA_FAMILIES = {"v0.2": CORE_SCHEMA_NAMES, "v0.3": V03_CORE_SCHEMA_NAMES}
# The core release inventory that authenticates both families' bytes.
CORE_CHECKSUM_MANIFEST = "release/v0.3/checksums.json"
LICENSE_PROFILE_SOURCE = "src/makoto/standard-profiles/v0.3/license-claim-v1.schema.json"
LICENSE_PROFILE_PATH = "profile/v0.3/license-claim-v1.schema.json"
LINEAGE_PAGE = "why-lineage/index.html"
WALKTHROUGH_PAGE = "demos/end-to-end/index.html"
# Learning content lives at permanent versionless URLs. The retired versioned
# addresses keep resolving forever: each one is a canonical-linked forwarding
# page, and the walkthrough artifacts stay byte-identical at the old path so
# published curl + shasum commands still verify. Protocol identifiers such as
# /spec/v0.2/ and /schema/v0.2/ are wire identifiers and deliberately keep
# their version.
DEMO_ARTIFACTS = "demos/end-to-end/artifacts"
LEGACY_DEMO_ARTIFACTS = "demos/v0.2-end-to-end/artifacts"
LEGACY_REDIRECTS = {
    "demos/v0.2-end-to-end/index.html": "/demos/end-to-end/",
    "examples/v0.2/index.html": "/examples/",
    "integrations/v0.2/index.html": "/integrations/",
}
VERSIONED_LEARNING_URL = re.compile(
    r"(?:usemakoto\.dev|href=\"|src=\"|\]\()/?(?:\.\./)*(?:demos/v0\.2-end-to-end|examples/v0\.2|integrations/v0\.2)/"
)
SOURCE_REVISION_PREFIX = "https://github.com/makoto-project/makoto/tree/"
CANONICAL_PRESENTATION_PAGES = (
    "community/index.html",
    "demos/index.html",
    "examples/index.html",
    "index.html",
    "integrations/index.html",
    "spec/index.html",
    "tooling/index.html",
    "verify/index.html",
    "why-lineage/index.html",
)
# Superseded-format pages. They stay reachable and labelled (sections 17 and 21),
# so the retired version string is expected here and its absence is the error.
# The L1-L3 pages are not in this set: they explain the current Section 8.3
# Origin and Transform track levels.
SUPERSEDED_FORMAT_PAGES = ("spec/signature-guide.html",)
LEVEL_PAGES = (
    "spec/l1-requirements.html",
    "spec/l2-requirements.html",
    "spec/l3-requirements.html",
)
# Section 21 also requires the superseded pages to state the incompatibility, so
# the banner has to carry both markers, inside the banner element itself.
SUPERSEDED_BANNER_CLASS = 'class="superseded-banner"'
SUPERSEDED_BANNER_TEXT = ("Historical v0.1 material.", "not wire-compatible")
# Pages that reproduce canonical source text verbatim. The retired version is
# discussed by the specification itself, so a faithful rendering has to contain
# it; scripts/render_spec.py --check is what keeps these honest.
VERBATIM_SOURCE_PAGES = ("spec/text/index.html", "spec/v0.3/index.html")
# Pages permitted to display a version label at all.
TECHNICAL_VERSION_PAGES = {
    "claim/v0.3/license/index.html",
    "predicate/v0.2/origin/index.html",
    "predicate/v0.2/transform/index.html",
    "predicate/v0.3/origin/index.html",
    "predicate/v0.3/transform/index.html",
    "source/file/index.html",
    "spec/schemas/index.html",
    "spec/text/index.html",
    "spec/v0.3/index.html",
    "vocab/v0.2/bounded-pattern/index.html",
    "vocab/v0.3/bounded-pattern/index.html",
    *SUPERSEDED_FORMAT_PAGES,
}
CURRENT_SHELL_PAGES = (
    "community/index.html",
    "demos/index.html",
    "demos/end-to-end/index.html",
    "examples/index.html",
    "index.html",
    "integrations/index.html",
    "predicate/v0.2/origin/index.html",
    "predicate/v0.2/transform/index.html",
    "source/file/index.html",
    "spec/index.html",
    "tooling/index.html",
    "verify/index.html",
    "vocab/v0.2/bounded-pattern/index.html",
    "why-lineage/index.html",
)
CURRENT_SHELL_MARKERS = (
    'class="docs-sidebar"',
    'class="mobile-menu"',
    'href="/why-lineage/"',
    'href="/examples/"',
    'href="/source/file/"',
    'href="/vocab/v0.2/bounded-pattern/"',
    'href="/tooling/"',
    'href="/integrations/"',
    'href="/community/"',
    'href="https://github.com/makoto-project/makoto"',
    'href="https://github.com/makoto-project/makoto/issues"',
)
CURRENT_INTEGRATION_PAGES = tuple(
    f"integrations/{name}/index.html"
    for name in (
        "airflow",
        "dagster",
        "databricks",
        "dbt",
        "expanso",
        "kafka",
        "prefect",
        "snowflake",
        "spark",
    )
)
CURRENT_SHELL_PAGES += CURRENT_INTEGRATION_PAGES
# Retired numeric-level constructs. These must not match the current track
# levels ("Origin L2", MAKOTO_TRANSFORM_LEVEL_3) defined by Section 8.3.
STALE_LEVEL_PATTERNS = (
    ("makoto.level", r"\bmakoto\.level\b"),
    # Tags and quotes may sit between the name and the number in highlighted markup.
    ("numeric level assignment", r"(?i)\blevel\s*=\s*(?:<[^>]*>|[\"'])*\s*[123]\b"),
)
STALE_JSON_PATTERNS = (
    r"makoto\.dev/(?:origin|transform)/v1",
    r'"makotoLevel"',
    r'"level"\s*:\s*[123](?:\s*[,}])',
)
STALE_INTEGRATION_MARKERS = (
    "origin/v1",
    "transform/v1",
    "makoto_airflow",
    "makoto_dagster",
    "makoto_databricks",
    "makoto_prefect",
    "MakotoOperator",
    "MakotoResult",
    "AttestationListener",
    "AttestationSMT",
    "@makoto_asset",
    "flow_dbom",
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
    "/demos/end-to-end/",
    "/spec/",
)
CANDIDATE_STATUS_TEXT = {
    "README.md": (
        "under review and has not been released.",
        "files are public review artifacts",
    ),
    "spec/index.html": ("not yet an immutable tagged release",),
    "demos/end-to-end/index.html": ("Runnable reference proof",),
}
DOCUMENTATION_FILES = {
    "/claim/v0.3/license/": "claim/v0.3/license/index.html",
    "/demos/end-to-end/": "demos/end-to-end/index.html",
    "/predicate/v0.2/origin/": "predicate/v0.2/origin/index.html",
    "/predicate/v0.2/transform/": "predicate/v0.2/transform/index.html",
    "/predicate/v0.3/origin/": "predicate/v0.3/origin/index.html",
    "/predicate/v0.3/transform/": "predicate/v0.3/transform/index.html",
    "/source/file/": "source/file/index.html",
    "/spec/v0.2/": "spec/v0.2/index.html",
    "/spec/v0.3/": "spec/v0.3/index.html",
    "/vocab/v0.2/bounded-pattern/": "vocab/v0.2/bounded-pattern/index.html",
    "/vocab/v0.3/bounded-pattern/": "vocab/v0.3/bounded-pattern/index.html",
}
STATIC_RESOURCES = {
    "docs/v0.2-adversarial-review.md": (
        "docs/v0.2-adversarial-review.md",
        "text/markdown",
    ),
    "docs/v0.2-architecture.md": ("docs/v0.2-architecture.md", "text/markdown"),
    "docs/v0.2-integrations.md": ("docs/v0.2-integrations.md", "text/markdown"),
    "docs/v0.2-migration.md": ("docs/v0.2-migration.md", "text/markdown"),
    "docs/v0.3-migration.md": ("docs/v0.3-migration.md", "text/markdown"),
    "release/checksums.schema.json": (
        "tooling/release/checksums.schema.json",
        "application/json",
    ),
    "release/v0.2/checksums.json": ("release/v0.2/checksums.json", "application/json"),
    "release/v0.3/checksums.json": ("release/v0.3/checksums.json", "application/json"),
    "spec/v0.2.md": ("spec/v0.2/spec.md", "text/markdown"),
    "spec/v0.3.md": ("spec/v0.3/spec.md", "text/markdown"),
    LICENSE_PROFILE_SOURCE: (LICENSE_PROFILE_PATH, "application/json"),
    "testdata/v0.2/diagnostic-map.json": (
        "spec/v0.2/diagnostic-map.json",
        "application/json",
    ),
    "testdata/v0.3/diagnostic-map.json": (
        "spec/v0.3/diagnostic-map.json",
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
    "docs/v0.2-migration.md": (("(../demos/v0.2-end-to-end/README.md)", "(../demos/end-to-end/)"),),
}
JSON_EXAMPLE_SCHEMAS = {
    "demos/end-to-end/artifacts/positive-bundle/attestations/1f28b72bcd4c1e9b7df71403ac6bb1670c2f2b09628ca6d76a2fa384db9a0848.dsse.json": "envelope.schema.json",
    "demos/end-to-end/artifacts/positive-bundle/attestations/56b7be4394fe09c62ec7a3d5763cecc251e9696f267f35b2acc717b0d170a27a.dsse.json": "envelope.schema.json",
    "demos/end-to-end/artifacts/positive-bundle/attestations/962be71738a0146642d27c87fba3c7338b0f2bb764b113b16867bb4808b11977.dsse.json": "envelope.schema.json",
    "demos/end-to-end/artifacts/positive-bundle/bundle.json": "bundle.schema.json",
    "demos/end-to-end/artifacts/positive-bundle/manifest.dsse.json": "envelope.schema.json",
    "demos/end-to-end/artifacts/receiver/attacker-known-policy.json": "trust-policy.schema.json",
    "demos/end-to-end/artifacts/receiver/catalog.json": "catalog.schema.json",
    "demos/end-to-end/artifacts/receiver/customer-public.profile.json": "profile-reference.schema.json",
    "demos/end-to-end/artifacts/receiver/policy.json": "trust-policy.schema.json",
    "demos/end-to-end/artifacts/receiver/public-transform-metadata.profile.json": "profile-reference.schema.json",
    "demos/end-to-end/artifacts/receiver/resources/31934d2cf8fa7b5af2f8e4cf591d96278c4f59ddb6bb190afccb93701244f9eb.schema.json": "profile-dialect.schema.json",
    "demos/end-to-end/artifacts/receiver/resources/68169d043c628fda5435cbd7845b02ea3e0d850b7a509c0b35fd304463fffacb.schema.json": "profile-dialect.schema.json",
    "demos/end-to-end/artifacts/reports/edited-signed-metadata.json": "verification-report.schema.json",
    "demos/end-to-end/artifacts/reports/mutated-final-data.json": "verification-report.schema.json",
    "demos/end-to-end/artifacts/reports/positive.json": "verification-report.schema.json",
    "demos/end-to-end/artifacts/reports/private-schema-violation.json": "verification-report.schema.json",
    "demos/end-to-end/artifacts/reports/removed-predecessor.json": "verification-report.schema.json",
    "demos/end-to-end/artifacts/reports/rewired-step.json": "verification-report.schema.json",
    "demos/end-to-end/artifacts/reports/statement-digest-mismatch.json": "verification-report.schema.json",
    "demos/end-to-end/artifacts/reports/unauthorized-signer.json": "verification-report.schema.json",
    "examples/corpus/repo/lineage/catalog.json": "catalog.schema.json",
    "examples/corpus/repo/lineage/license.profile.json": "profile-reference.schema.json",
    "examples/corpus/repo/lineage/policy.json": "trust-policy.schema.json",
    "examples/corpus/repo/lineage/schemas/license-v1.schema.json": "profile-dialect.schema.json",
    "examples/corpus/repo/text/letters/makoto/attestations/a4449e246f93d9a68a19481b2338590efe99e9b2f4e7614c2e80e8bd51bee031.dsse.json": "envelope.schema.json",
    "examples/corpus/repo/text/letters/makoto/attestations/cc674882b6f8d3ba63a076a2f39e476bebffb52c144ca96cf735044f101645d8.dsse.json": "envelope.schema.json",
    "examples/corpus/repo/text/letters/makoto/bundle.json": "bundle.schema.json",
    "examples/corpus/repo/text/letters/makoto/manifest.dsse.json": "envelope.schema.json",
    "examples/corpus/repo/text/letters/makoto/schemas/catalog.json": "catalog.schema.json",
    "examples/corpus/repo/text/letters/makoto/schemas/resources/ce30589e17abff371e461b6fd75723b055fdddef6e865bcc5fabcf327f07b9ab.schema.json": "profile-dialect.schema.json",
    "examples/in-place/attestations/state-1-origin.json": "statement.schema.json",
    "examples/in-place/attestations/state-2-normalize.json": "statement.schema.json",
    "examples/in-place/attestations/state-3-withdraw-minor-consent.json": "statement.schema.json",
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
    "examples/go",
    "schemas/v0.2",
    "schemas/v0.3",
    "scripts",
    "src/makoto",
    "testdata/v0.2",
    "testdata/v0.3",
    "tests",
)
CORE_CHECKSUM_EXACT_PATHS = (
    "LICENSE",
    "README.md",
    "pyproject.toml",
    "release/checksums.schema.json",
    "spec/v0.2.md",
    "spec/v0.3.md",
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
        self.ignored_text_depth = 0
        self.visible_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag in {"code", "pre", "script", "style"}:
            self.ignored_text_depth += 1
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
        if tag in {"code", "pre", "script", "style"} and self.ignored_text_depth:
            self.ignored_text_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self.ignored_text_depth and data.strip():
            self.visible_text.append(data.strip())


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
    demo_root = ROOT / DEMO_ARTIFACTS
    for relative, path in exact_files(demo_root).items():
        media_type = "application/octet-stream" if path.suffix == ".bin" else "application/json"
        resources[f"/{DEMO_ARTIFACTS}/{relative}"] = (
            path,
            media_type,
            True,
        )
    return resources


def validate_source_revision_link(pin: dict[str, Any], mode: str, errors: list[str]) -> None:
    revision = pin["commit"] if mode == "candidate" else pin["tag"]
    expected = f"{SOURCE_REVISION_PREFIX}{revision}/demos/v0.2-end-to-end"
    walkthrough = ROOT / WALKTHROUGH_PAGE
    try:
        text = walkthrough.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        errors.append(f"cannot inspect walkthrough source revision link: {error}")
        return
    links = re.findall(rf'{re.escape(SOURCE_REVISION_PREFIX)}[^"\s<]+/demos/v0\.2-end-to-end', text)
    if links != [expected]:
        errors.append(
            f"walkthrough source revision link is not exact: expected={expected!r} actual={links!r}"
        )


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
    validate_source_revision_link(pin, mode, errors)
    for collection in ("schemas", "documentation", "resources"):
        paths = [item["path"] for item in pin[collection]]
        if paths != sorted(paths, key=str.encode) or len(paths) != len(set(paths)):
            errors.append(f"{mode} pin {collection} paths are not sorted and unique")
    expected_schema_paths = {
        f"/schema/{family}/{name}"
        for family, names in CORE_SCHEMA_FAMILIES.items()
        for name in names
    }
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
    manifest_path = core / CORE_CHECKSUM_MANIFEST
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
    for family, names in CORE_SCHEMA_FAMILIES.items():
        check_schema_family_parity(core, family, names, checksum_digests, errors)
    core_spec = core / "spec/v0.2.md"
    for family in CORE_SCHEMA_FAMILIES:
        try:
            same = (core / f"spec/{family}.md").read_bytes() == (
                ROOT / f"spec/{family}/spec.md"
            ).read_bytes()
        except OSError as error:
            errors.append(f"cannot compare spec/{family}/spec.md with core: {error}")
            continue
        if not same:
            errors.append(f"spec/{family}/spec.md differs from core spec/{family}.md")
    check_license_profile(errors)
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
        ROOT / DEMO_ARTIFACTS,
        core / "demos/v0.2-end-to-end/generated",
        "v0.2 demo artifacts",
        errors,
    )
    check_legacy_demo_mirror(errors)
    check_demo_manifest(errors)


def check_schema_family_parity(
    core: Path,
    family: str,
    names: tuple[str, ...],
    checksum_digests: dict[str, str],
    errors: list[str],
) -> None:
    website_schema = ROOT / "schema" / family
    core_schema = core / "schemas" / family
    actual_names = (
        tuple(sorted(path.name for path in website_schema.iterdir() if path.is_file()))
        if website_schema.is_dir()
        else ()
    )
    if actual_names != tuple(sorted(names)):
        errors.append(f"website {family} schema set is wrong: {actual_names!r}")
    for name in names:
        website_path = website_schema / name
        core_path = core_schema / name
        if not website_path.is_file() or not core_path.is_file():
            errors.append(f"missing {family} schema resource: {name}")
            continue
        if website_path.read_bytes() != core_path.read_bytes():
            errors.append(f"schema bytes differ from core: {family}/{name}")
        checksum_digest = checksum_digests.get(f"schemas/{family}/{name}")
        if checksum_digest is not None and sha256(website_path) != checksum_digest:
            errors.append(f"website schema differs from core checksum manifest: {family}/{name}")
        if name.endswith(".schema.json"):
            try:
                value = strict_json(website_path)
                Draft202012Validator.check_schema(value)
            except (OSError, ValueError, SchemaError) as error:
                errors.append(f"invalid JSON Schema {family}/{name}: {error}")
            else:
                expected_id = f"https://usemakoto.dev/schema/{family}/{name}"
                if value.get("$id") != expected_id:
                    errors.append(f"schema $id differs from hosted URL: {family}/{name}")
    catalog_path = website_schema / "catalog.json"
    try:
        catalog = strict_json(catalog_path)
    except (OSError, ValueError) as error:
        errors.append(f"invalid {family} core catalog: {error}")
    else:
        for resource in catalog.get("resources", []):
            resource_path = website_schema / resource["path"]
            if not resource_path.is_file() or sha256(resource_path) != resource["digest"]["sha256"]:
                errors.append(f"{family} catalog digest mismatch: {resource.get('path')}")


def check_license_profile(errors: list[str]) -> None:
    """The standard profile is served at its own $id, as a valid JSON Schema."""
    path = ROOT / LICENSE_PROFILE_PATH
    try:
        profile = strict_json(path)
        Draft202012Validator.check_schema(profile)
    except (OSError, ValueError, SchemaError) as error:
        errors.append(f"invalid standard licence-claim profile: {error}")
        return
    if profile.get("$id") != f"https://usemakoto.dev/{LICENSE_PROFILE_PATH}":
        errors.append("standard licence-claim profile $id differs from its hosted URL")


def check_legacy_demo_mirror(errors: list[str]) -> None:
    """The retired artifact path must serve exactly the canonical bytes."""
    if not (ROOT / LEGACY_DEMO_ARTIFACTS).is_dir():
        errors.append(f"legacy demo artifact mirror is missing: {LEGACY_DEMO_ARTIFACTS}")
        return
    compare_trees(
        ROOT / LEGACY_DEMO_ARTIFACTS,
        ROOT / DEMO_ARTIFACTS,
        "legacy demo artifact mirror",
        errors,
    )


def check_legacy_redirects(errors: list[str]) -> None:
    """Retired learning URLs forward to their permanent home, and nothing links them."""
    for relative, target in sorted(LEGACY_REDIRECTS.items()):
        path = ROOT / relative
        if not path.is_file():
            errors.append(f"legacy forwarding page is missing: {relative}")
            continue
        content = path.read_text(encoding="utf-8")
        for marker in (
            f'<meta http-equiv="refresh" content="0;url={target}">',
            f'<link rel="canonical" href="https://usemakoto.dev{target}">',
            f'<a href="{target}">',
        ):
            if marker not in content:
                errors.append(f"legacy forwarding page is incomplete in {relative}: {marker}")
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path.suffix not in {".html", ".md"}:
            continue
        relative = path.relative_to(ROOT).as_posix()
        if relative in LEGACY_REDIRECTS or FORBIDDEN_TRACKED_SEGMENTS.intersection(path.parts):
            continue
        content = path.read_text(encoding="utf-8", errors="replace")
        for match in VERSIONED_LEARNING_URL.finditer(content):
            errors.append(f"versioned learning URL remains in {relative}: {match.group(0)}")


def check_demo_manifest(errors: list[str]) -> None:
    root = ROOT / DEMO_ARTIFACTS
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


def stale_integration_markers(content: str) -> list[str]:
    """Return the retired constructs an integration page still uses.

    The numeric-level guards target only the old forms: a ``makoto.level``
    attribute and a ``level = 1..3`` assignment. The current string levels
    (``"L1"``-``"L3"``, ``--require L2``) and the ``makoto.levels`` module pass.
    """
    found = [marker for marker in STALE_INTEGRATION_MARKERS if marker in content]
    found += [label for label, pattern in STALE_LEVEL_PATTERNS if re.search(pattern, content)]
    return found


def is_technical_version_page(relative: str) -> bool:
    """Pages allowed to display a version label.

    The generated schema field references under ``spec/schemas/`` quote schema
    identifiers and titles that carry the version by definition, like the
    schema index they hang off.
    """
    return relative in TECHNICAL_VERSION_PAGES or relative.startswith("spec/schemas/")


def retired_version_errors(relative: str, content: str) -> list[str]:
    """Apply the retired-version rule to one HTML page.

    The retired version may appear only where the specification requires it:
    on the superseded pages, which must carry the labelled banner, and on the
    verbatim rendering of the specification, which discusses it. Anywhere else
    it is a regression.
    """
    names_retired = re.search(r"v0\.1", content, flags=re.IGNORECASE) is not None
    if relative in SUPERSEDED_FORMAT_PAGES:
        if not names_retired:
            return [f"superseded-format page no longer names the retired version: {relative}"]
        _, has_banner, after = content.partition(SUPERSEDED_BANNER_CLASS)
        banner = after.split("</div>", 1)[0]
        if not has_banner or not all(text in banner for text in SUPERSEDED_BANNER_TEXT):
            return [f"superseded-format banner is missing or incomplete: {relative}"]
        return []
    if names_retired and relative not in VERBATIM_SOURCE_PAGES:
        return [f"retired protocol version remains in HTML: {relative}"]
    return []


def check_truthfulness(errors: list[str], *, mode: str = "working-tree") -> None:
    for path in sorted(ROOT.rglob("*.html")):
        relative = path.relative_to(ROOT).as_posix()
        content = path.read_text(encoding="utf-8", errors="replace")
        errors.extend(retired_version_errors(relative, content))
        if is_technical_version_page(relative):
            continue
        parser = PageParser()
        parser.feed(content)
        visible_text = " ".join(parser.visible_text).casefold()
        for forbidden in ("v0.1", "v0.2"):
            if re.search(rf"\b{re.escape(forbidden)}\b", visible_text):
                errors.append(
                    f"visible version label remains in narrative page {relative}: {forbidden}"
                )
    for path in sorted(ROOT.rglob("*.json")):
        if ".codex-work" in path.parts:
            continue
        content = path.read_text(encoding="utf-8", errors="replace")
        for pattern in STALE_JSON_PATTERNS:
            if re.search(pattern, content):
                errors.append(
                    "retired protocol construct remains in deployable JSON: "
                    f"{path.relative_to(ROOT)}"
                )
                break
    for relative in CANONICAL_PRESENTATION_PAGES:
        parser = PageParser()
        parser.feed((ROOT / relative).read_text(encoding="utf-8"))
        visible_text = " ".join(parser.visible_text).casefold()
        for forbidden in ("historical", "legacy", "archive"):
            if re.search(rf"\b{re.escape(forbidden)}\b", visible_text):
                errors.append(f"presentation version label remains in {relative}: {forbidden}")
    for relative in CURRENT_INTEGRATION_PAGES:
        content = (ROOT / relative).read_text(encoding="utf-8", errors="replace")
        errors.extend(
            f"stale integration construct remains in {relative}: {marker}"
            for marker in stale_integration_markers(content)
        )
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
            "No membership required.",
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
            "Source checkout",
            "API research",
            "not a published Makoto distribution",
            "No published SDK or adapter package is claimed",
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
    demo = (ROOT / "demos/end-to-end/index.html").read_text(encoding="utf-8")
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
    check_legacy_redirects(errors)
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
