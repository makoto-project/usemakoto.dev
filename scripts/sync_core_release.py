#!/usr/bin/env python3
"""Atomically mirror a reviewed Makoto core candidate or release into the website."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
import unicodedata
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "https://github.com/makoto-project/makoto"
SCHEMA_NAMES = (
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
DOCUMENTATION = {
    "/demos/v0.2-end-to-end/": "demos/v0.2-end-to-end/index.html",
    "/predicate/v0.2/origin/": "predicate/v0.2/origin/index.html",
    "/predicate/v0.2/transform/": "predicate/v0.2/transform/index.html",
    "/source/file/": "source/file/index.html",
    "/spec/v0.2/": "spec/v0.2/index.html",
    "/vocab/v0.2/bounded-pattern/": "vocab/v0.2/bounded-pattern/index.html",
}
STATIC_RESOURCES = {
    "docs/adopter-framework.md": ("docs/adopter-framework.md", "text/markdown"),
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
    "docs/adopter-framework.md": (
        (
            "(../demos/v0.2-end-to-end/generated/walkthrough/)",
            "(../demos/v0.2-end-to-end/artifacts/walkthrough/)",
        ),
    ),
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
CHECKSUM_PREFIXES = (
    "demos/v0.2-end-to-end",
    "docs",
    "schemas/v0.2",
    "scripts",
    "src/makoto",
    "testdata/v0.2",
    "tests",
)
CHECKSUM_EXACT_PATHS = (
    "LICENSE",
    "README.md",
    "pyproject.toml",
    "release/checksums.schema.json",
    "spec/v0.2.md",
    "uv.lock",
)
CHECKSUM_FORBIDDEN_SEGMENTS = {
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".work",
    "__pycache__",
}


class SyncError(ValueError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--commit")
    selection.add_argument("--tag")
    selection.add_argument(
        "--working-tree",
        action="store_true",
        help="mirror reviewed local core bytes without creating or replacing a release pin",
    )
    parser.add_argument("--candidate", action="store_true")
    parser.add_argument("--core-repo", type=Path, default=ROOT.parent / "core")
    args = parser.parse_args()
    if args.working_tree:
        if args.candidate:
            parser.error("--working-tree cannot be combined with --candidate")
    elif args.commit is not None:
        if not args.candidate:
            parser.error("--commit requires --candidate")
        if len(args.commit) != 40 or any(
            character not in "0123456789abcdef" for character in args.commit
        ):
            parser.error("--commit must be exactly 40 lowercase hexadecimal digits")
    else:
        if args.candidate or args.tag != "v0.2.0":
            parser.error("release mode requires exactly --tag v0.2.0")
    return args


def git(core: Path, *arguments: str, check: bool = True) -> bytes:
    result = subprocess.run(["git", *arguments], cwd=core, check=check, capture_output=True)
    return result.stdout


def git_blob(core: Path, revision: str, path: str) -> bytes:
    try:
        return git(core, "show", f"{revision}:{path}")
    except subprocess.CalledProcessError as error:
        raise SyncError(f"missing core blob {path!r} at {revision}") from error


def git_tree(core: Path, revision: str, prefix: str) -> tuple[str, ...]:
    try:
        output = git(core, "ls-tree", "-r", "--name-only", revision, "--", prefix)
    except subprocess.CalledProcessError as error:
        raise SyncError(f"cannot list core tree {prefix!r} at {revision}") from error
    return tuple(line for line in output.decode().splitlines() if line)


def filesystem_blob(core: Path, path: str) -> bytes:
    target = (core / path).resolve()
    try:
        target.relative_to(core.resolve())
    except ValueError as error:
        raise SyncError(f"core path escapes repository: {path!r}") from error
    try:
        return target.read_bytes()
    except OSError as error:
        raise SyncError(f"missing core file {path!r} in working tree") from error


def filesystem_tree(core: Path, prefix: str) -> tuple[str, ...]:
    directory = (core / prefix).resolve()
    try:
        directory.relative_to(core.resolve())
    except ValueError as error:
        raise SyncError(f"core prefix escapes repository: {prefix!r}") from error
    if not directory.is_dir():
        return ()
    return tuple(
        sorted(
            (
                path.relative_to(core).as_posix()
                for path in directory.rglob("*")
                if path.is_file()
                and not CHECKSUM_FORBIDDEN_SEGMENTS.intersection(path.relative_to(core).parts)
            ),
            key=str.encode,
        )
    )


def source_blob(core: Path, revision: str | None, path: str) -> bytes:
    return filesystem_blob(core, path) if revision is None else git_blob(core, revision, path)


def source_tree(core: Path, revision: str | None, prefix: str) -> tuple[str, ...]:
    return filesystem_tree(core, prefix) if revision is None else git_tree(core, revision, prefix)


def public_resource_bytes(source_path: str, data: bytes) -> bytes:
    rewrites = PUBLIC_TEXT_REWRITES.get(source_path, ())
    if not rewrites:
        return data
    text = data.decode("utf-8")
    for original, replacement in rewrites:
        if text.count(original) != 1:
            raise SyncError(
                f"public-link rewrite source is absent or duplicated in {source_path}: {original}"
            )
        text = text.replace(original, replacement)
    return text.encode("utf-8")


def digest(data: bytes) -> dict[str, str]:
    return {"sha256": hashlib.sha256(data).hexdigest()}


def jcs(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
        + b"\n"
    )


def write_pin(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(jcs(value))


def strict_json_bytes(data: bytes, *, label: str) -> Any:
    if data.startswith(b"\xef\xbb\xbf"):
        raise SyncError(f"{label}: UTF-8 BOM is forbidden")

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise SyncError(f"{label}: duplicate JSON key {key!r}")
            result[key] = value
        return result

    try:
        return json.loads(data, object_pairs_hook=pairs)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise SyncError(f"{label}: invalid strict JSON: {error}") from error


def checksum_paths(core: Path, revision: str | None) -> tuple[str, ...]:
    paths = set(CHECKSUM_EXACT_PATHS)
    for prefix in CHECKSUM_PREFIXES:
        paths.update(source_tree(core, revision, prefix))
    paths.discard("release/v0.2/checksums.json")
    return tuple(sorted(paths, key=str.encode))


def load_core_checksums(core: Path, revision: str | None) -> dict[str, str]:
    manifest_bytes = source_blob(core, revision, "release/v0.2/checksums.json")
    schema_bytes = source_blob(core, revision, "release/checksums.schema.json")
    manifest = strict_json_bytes(manifest_bytes, label="core checksum manifest")
    schema = strict_json_bytes(schema_bytes, label="core checksum schema")
    Draft202012Validator.check_schema(schema)
    errors = sorted(
        Draft202012Validator(schema).iter_errors(manifest),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        raise SyncError("invalid core checksum manifest: " + "; ".join(e.message for e in errors))
    if manifest_bytes != jcs(manifest):
        raise SyncError("core checksum manifest is not canonical JSON plus one LF")
    paths = [item["path"] for item in manifest["files"]]
    if paths != sorted(paths, key=str.encode) or len(paths) != len(set(paths)):
        raise SyncError("core checksum paths are not sorted and unique")
    if any(path != unicodedata.normalize("NFC", path) for path in paths):
        raise SyncError("core checksum paths are not NFC")
    expected_paths = checksum_paths(core, revision)
    if tuple(paths) != expected_paths:
        raise SyncError("core checksum inclusion set is not exact")
    digests = {item["path"]: item["digest"]["sha256"] for item in manifest["files"]}
    for path, expected_digest in sorted(digests.items()):
        if digest(source_blob(core, revision, path))["sha256"] != expected_digest:
            raise SyncError(f"core checksum digest mismatch: {path}")
    return digests


def copy_release_content(
    core: Path,
    revision: str | None,
    staging: Path,
    checksum_digests: dict[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    schema_entries: list[dict[str, Any]] = []
    resource_entries: list[dict[str, Any]] = []
    schema_target = staging / "schema/v0.2"
    schema_target.mkdir(parents=True)
    core_schema_paths = source_tree(core, revision, "schemas/v0.2")
    expected_schema_paths = tuple(f"schemas/v0.2/{name}" for name in SCHEMA_NAMES)
    if core_schema_paths != expected_schema_paths:
        raise SyncError(
            f"core schema set differs: expected={expected_schema_paths!r} actual={core_schema_paths!r}"
        )
    for name in SCHEMA_NAMES:
        data = source_blob(core, revision, f"schemas/v0.2/{name}")
        if digest(data)["sha256"] != checksum_digests.get(f"schemas/v0.2/{name}"):
            raise SyncError(f"schema does not match core checksum manifest: {name}")
        if name.endswith(".schema.json"):
            schema = strict_json_bytes(data, label=f"core schema {name}")
            try:
                Draft202012Validator.check_schema(schema)
            except SchemaError as error:
                raise SyncError(f"invalid core JSON Schema {name}: {error}") from error
            expected_id = f"https://usemakoto.dev/schema/v0.2/{name}"
            if schema.get("$id") != expected_id:
                raise SyncError(f"core schema $id differs from hosted URL: {name}")
        (schema_target / name).write_bytes(data)
        schema_entries.append({"path": f"/schema/v0.2/{name}", "digest": digest(data)})
    for source_path, (relative, media_type) in STATIC_RESOURCES.items():
        data = source_blob(core, revision, source_path)
        if source_path != "release/v0.2/checksums.json" and digest(data)[
            "sha256"
        ] != checksum_digests.get(source_path):
            raise SyncError(f"resource does not match core checksum manifest: {source_path}")
        data = public_resource_bytes(source_path, data)
        target = staging / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        resource_entries.append(
            {
                "path": f"/{relative}",
                "digest": digest(data),
                "mediaType": media_type,
                "cors": True,
            }
        )
    demo_paths = source_tree(core, revision, "demos/v0.2-end-to-end/generated")
    if not demo_paths:
        raise SyncError("core candidate has no generated v0.2 demo artifacts")
    demo_target = staging / "demos/v0.2-end-to-end/artifacts"
    for source_path in demo_paths:
        relative = Path(source_path).relative_to("demos/v0.2-end-to-end/generated")
        target = demo_target / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        data = source_blob(core, revision, source_path)
        target.write_bytes(data)
        media_type = "application/octet-stream" if target.suffix == ".bin" else "application/json"
        resource_entries.append(
            {
                "path": f"/demos/v0.2-end-to-end/artifacts/{relative.as_posix()}",
                "digest": digest(data),
                "mediaType": media_type,
                "cors": True,
            }
        )
    return (
        sorted(schema_entries, key=lambda item: item["path"].encode()),
        sorted(resource_entries, key=lambda item: item["path"].encode()),
    )


def documentation_entries() -> list[dict[str, Any]]:
    entries = []
    for public_path, relative in sorted(DOCUMENTATION.items(), key=lambda item: item[0].encode()):
        source = ROOT / relative
        if not source.is_file():
            raise SyncError(f"documentation page is absent: {relative}")
        entries.append({"path": public_path, "digest": digest(source.read_bytes())})
    return entries


def promote(staging: Path, pin_name: str | None, remove_name: str | None) -> None:
    replacements = [
        (staging / "schema/v0.2", ROOT / "schema/v0.2"),
        (staging / "spec/v0.2/spec.md", ROOT / "spec/v0.2/spec.md"),
        (
            staging / "demos/v0.2-end-to-end/artifacts",
            ROOT / "demos/v0.2-end-to-end/artifacts",
        ),
    ]
    if pin_name is not None:
        replacements.append((staging / pin_name, ROOT / pin_name))
    for relative, _ in STATIC_RESOURCES.values():
        if relative != "spec/v0.2/spec.md":
            replacements.append((staging / relative, ROOT / relative))
    backups: list[tuple[Path, Path]] = []
    installed: list[Path] = []
    try:
        for source, target in replacements:
            target.parent.mkdir(parents=True, exist_ok=True)
            backup = staging / "backups" / target.relative_to(ROOT)
            if target.exists():
                backup.parent.mkdir(parents=True, exist_ok=True)
                target.replace(backup)
                backups.append((backup, target))
            source.replace(target)
            installed.append(target)
        remove_target = ROOT / remove_name if remove_name is not None else None
        if remove_target is not None and remove_target.exists():
            backup = staging / "backups" / remove_target.relative_to(ROOT)
            backup.parent.mkdir(parents=True, exist_ok=True)
            remove_target.replace(backup)
            backups.append((backup, remove_target))
    except Exception:
        for target in reversed(installed):
            if target.exists():
                if target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink()
        for backup, target in reversed(backups):
            backup.replace(target)
        raise


def main() -> int:
    args = parse_args()
    core = args.core_repo.resolve()
    if not (core / ".git").exists():
        raise SyncError(f"core repository is invalid: {core}")
    if args.working_tree:
        with tempfile.TemporaryDirectory(prefix=".makoto-sync-", dir=ROOT.parent) as temporary:
            staging = Path(temporary)
            checksum_digests = load_core_checksums(core, None)
            copy_release_content(core, None, staging, checksum_digests)
            promote(staging, None, None)
        print("synced reviewed core working tree without a candidate or release pin")
        return 0
    if args.commit is not None:
        revision = args.commit
        commit = git(core, "rev-parse", revision).decode().strip()
        if commit != revision:
            raise SyncError("candidate revision did not resolve to the exact requested commit")
        tag: str | None = None
        pin_name = "schema/core-candidate.json"
    else:
        if git(core, "status", "--porcelain").strip():
            raise SyncError("release source checkout must be clean")
        revision = "v0.2.0^{}"
        commit = git(core, "rev-parse", revision).decode().strip()
        candidate_path = ROOT / "schema/core-candidate.json"
        if not candidate_path.is_file():
            raise SyncError("release requires the reviewed candidate pin")
        candidate_bytes = candidate_path.read_bytes()
        candidate = strict_json_bytes(candidate_bytes, label="reviewed candidate pin")
        candidate_schema = strict_json_bytes(
            (ROOT / "schema/core-candidate.schema.json").read_bytes(),
            label="candidate pin schema",
        )
        errors = sorted(
            Draft202012Validator(candidate_schema).iter_errors(candidate),
            key=lambda error: list(error.absolute_path),
        )
        if errors or candidate_bytes != jcs(candidate):
            raise SyncError("reviewed candidate pin is invalid or not canonical")
        if candidate.get("commit") != commit:
            raise SyncError("release tag does not equal the reviewed candidate commit")
        tag = "v0.2.0"
        pin_name = "schema/core-release.json"
    with tempfile.TemporaryDirectory(prefix=".makoto-sync-", dir=ROOT.parent) as temporary:
        staging = Path(temporary)
        checksum_digests = load_core_checksums(core, revision)
        schemas, resources = copy_release_content(core, revision, staging, checksum_digests)
        pin = {
            "version": "0.2",
            "repository": REPOSITORY,
            "commit": commit,
            "tag": tag,
            "schemas": schemas,
            "documentation": documentation_entries(),
            "resources": resources,
        }
        pin_target = staging / pin_name
        write_pin(pin_target, pin)
        if tag is not None:
            reviewed_candidate = {**pin, "tag": None}
            if candidate != reviewed_candidate:
                raise SyncError("release content differs from the reviewed candidate pin")
        remove_name = "schema/core-release.json" if tag is None else "schema/core-candidate.json"
        promote(staging, pin_name, remove_name)
    print(f"synced core {commit} as {'candidate' if tag is None else tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
