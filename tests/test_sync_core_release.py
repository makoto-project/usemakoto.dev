from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from scripts import sync_core_release

CHECKSUM_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["version", "tag", "files"],
    "properties": {
        "version": {"const": "1"},
        "tag": {"const": "v0.2.0"},
        "files": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["path", "digest"],
                "properties": {
                    "path": {"type": "string"},
                    "digest": {
                        "type": "object",
                        "required": ["sha256"],
                        "properties": {"sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"}},
                        "additionalProperties": False,
                    },
                },
                "additionalProperties": False,
            },
        },
    },
    "additionalProperties": False,
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def make_checksum_core(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    manifest_bytes: bytes | None = None,
    include_manifest: bool = True,
) -> tuple[Path, str]:
    core = tmp_path / "core"
    core.mkdir()
    readme = b"core\n"
    schema = sync_core_release.jcs(CHECKSUM_SCHEMA)
    write(core / "README.md", readme)
    write(core / "release/checksums.schema.json", schema)
    if manifest_bytes is None:
        manifest_bytes = sync_core_release.jcs(
            {
                "version": "1",
                "tag": "v0.2.0",
                "files": [
                    {"path": "README.md", "digest": {"sha256": sha256(readme)}},
                    {
                        "path": "release/checksums.schema.json",
                        "digest": {"sha256": sha256(schema)},
                    },
                ],
            }
        )
    if include_manifest:
        write(core / "release/v0.2/checksums.json", manifest_bytes)
    subprocess.run(["git", "init", "-q"], cwd=core, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=core, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=core, check=True)
    subprocess.run(["git", "add", "."], cwd=core, check=True)
    subprocess.run(["git", "commit", "-qm", "fixture"], cwd=core, check=True)
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=core,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    monkeypatch.setattr(
        sync_core_release, "CHECKSUM_EXACT_PATHS", ("README.md", "release/checksums.schema.json")
    )
    monkeypatch.setattr(sync_core_release, "CHECKSUM_PREFIXES", ())
    return core, revision


def test_release_pin_serialization_is_deterministic_jcs_plus_lf() -> None:
    value = {"z": 1, "a": {"sha256": "0" * 64}}

    encoded = sync_core_release.jcs(value)

    assert encoded == (json.dumps(value, separators=(",", ":"), sort_keys=True) + "\n").encode()


def test_write_pin_accepts_preexisting_schema_directory(tmp_path: Path) -> None:
    schema_directory = tmp_path / "schema"
    schema_directory.mkdir()
    path = schema_directory / "core-candidate.json"
    value = {"commit": "a" * 40, "tag": None}

    sync_core_release.write_pin(path, value)

    assert path.read_bytes() == sync_core_release.jcs(value)


def test_documentation_pin_paths_are_exact_sorted_and_digest_pinned() -> None:
    entries = sync_core_release.documentation_entries()

    assert [entry["path"] for entry in entries] == sorted(sync_core_release.DOCUMENTATION)
    assert all(len(entry["digest"]["sha256"]) == 64 for entry in entries)
    assert all(entry["path"].endswith("/") for entry in entries)


def test_filesystem_tree_ignores_runtime_caches(tmp_path: Path) -> None:
    write(tmp_path / "tests/kept.py", b"kept\n")
    write(tmp_path / "tests/__pycache__/ignored.pyc", b"ignored\n")

    paths = sync_core_release.filesystem_tree(tmp_path, "tests")

    assert paths == ("tests/kept.py",)


def test_load_core_checksums_accepts_exact_canonical_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    core, revision = make_checksum_core(tmp_path, monkeypatch)

    result = sync_core_release.load_core_checksums(core, revision)

    assert set(result) == {"README.md", "release/checksums.schema.json"}


def test_load_core_checksums_rejects_missing_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    core, revision = make_checksum_core(tmp_path, monkeypatch, include_manifest=False)

    with pytest.raises(sync_core_release.SyncError, match="missing core blob"):
        sync_core_release.load_core_checksums(core, revision)


def test_load_core_checksums_rejects_duplicate_json_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    duplicate = b'{"files":[],"tag":"v0.2.0","version":"1","version":"1"}\n'
    core, revision = make_checksum_core(tmp_path, monkeypatch, manifest_bytes=duplicate)

    with pytest.raises(sync_core_release.SyncError, match="duplicate JSON key"):
        sync_core_release.load_core_checksums(core, revision)


def test_load_core_checksums_rejects_noncanonical_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    readme = b"core\n"
    schema = sync_core_release.jcs(CHECKSUM_SCHEMA)
    noncanonical = json.dumps(
        {
            "version": "1",
            "tag": "v0.2.0",
            "files": [
                {"path": "README.md", "digest": {"sha256": sha256(readme)}},
                {
                    "path": "release/checksums.schema.json",
                    "digest": {"sha256": sha256(schema)},
                },
            ],
        },
        indent=2,
    ).encode()
    core, revision = make_checksum_core(tmp_path, monkeypatch, manifest_bytes=noncanonical)

    with pytest.raises(sync_core_release.SyncError, match="not canonical"):
        sync_core_release.load_core_checksums(core, revision)


def test_load_core_checksums_rejects_incomplete_inclusion_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    incomplete = sync_core_release.jcs(
        {
            "version": "1",
            "tag": "v0.2.0",
            "files": [
                {"path": "README.md", "digest": {"sha256": sha256(b"core\n")}},
            ],
        }
    )
    core, revision = make_checksum_core(tmp_path, monkeypatch, manifest_bytes=incomplete)

    with pytest.raises(sync_core_release.SyncError, match="inclusion set is not exact"):
        sync_core_release.load_core_checksums(core, revision)


def test_load_core_checksums_rejects_mutated_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    schema = sync_core_release.jcs(CHECKSUM_SCHEMA)
    mutated = sync_core_release.jcs(
        {
            "version": "1",
            "tag": "v0.2.0",
            "files": [
                {"path": "README.md", "digest": {"sha256": "0" * 64}},
                {
                    "path": "release/checksums.schema.json",
                    "digest": {"sha256": sha256(schema)},
                },
            ],
        }
    )
    core, revision = make_checksum_core(tmp_path, monkeypatch, manifest_bytes=mutated)

    with pytest.raises(sync_core_release.SyncError, match="digest mismatch: README.md"):
        sync_core_release.load_core_checksums(core, revision)


def test_copy_release_content_rejects_schema_id_not_equal_hosted_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    blobs: dict[str, bytes] = {}
    checksum_digests: dict[str, str] = {}
    schema_paths: list[str] = []
    for name in sync_core_release.SCHEMA_NAMES:
        path = f"schemas/v0.2/{name}"
        schema_paths.append(path)
        if name == "catalog.json":
            data = sync_core_release.jcs({"resources": []})
        else:
            schema_id = f"https://usemakoto.dev/schema/v0.2/{name}"
            if name == "origin.schema.json":
                schema_id = "https://example.invalid/origin.schema.json"
            data = sync_core_release.jcs(
                {
                    "$schema": "https://json-schema.org/draft/2020-12/schema",
                    "$id": schema_id,
                    "type": "object",
                }
            )
        blobs[path] = data
        checksum_digests[path] = sha256(data)

    def fake_tree(core: Path, revision: str, prefix: str) -> tuple[str, ...]:
        del core, revision
        if prefix == "schemas/v0.2":
            return tuple(schema_paths)
        if prefix == "demos/v0.2-end-to-end/generated":
            return ("demos/v0.2-end-to-end/generated/manifest.json",)
        raise AssertionError(prefix)

    def fake_blob(core: Path, revision: str, path: str) -> bytes:
        del core, revision
        if path == "spec/v0.2.md":
            return b"spec\n"
        if path == "demos/v0.2-end-to-end/generated/manifest.json":
            return b"{}\n"
        return blobs[path]

    monkeypatch.setattr(sync_core_release, "git_tree", fake_tree)
    monkeypatch.setattr(sync_core_release, "git_blob", fake_blob)

    with pytest.raises(sync_core_release.SyncError, match=r"\$id differs from hosted URL"):
        sync_core_release.copy_release_content(
            tmp_path / "core", "a" * 40, tmp_path / "staging", checksum_digests
        )


def test_strict_json_bytes_rejects_duplicate_candidate_pin_key() -> None:
    with pytest.raises(sync_core_release.SyncError, match="duplicate JSON key 'commit'"):
        sync_core_release.strict_json_bytes(
            b'{"commit":"a","commit":"b"}\n', label="reviewed candidate pin"
        )


def test_release_candidate_comparison_is_exact() -> None:
    release_pin = {
        "version": "0.2",
        "repository": sync_core_release.REPOSITORY,
        "commit": "a" * 40,
        "tag": "v0.2.0",
        "schemas": [],
        "documentation": [],
        "resources": [],
    }
    reviewed_candidate = {**release_pin, "tag": None}
    changed_release = {
        **release_pin,
        "documentation": [{"path": "/spec/v0.2/", "digest": {"sha256": "0" * 64}}],
    }

    assert reviewed_candidate == {**release_pin, "tag": None}
    assert reviewed_candidate != {**changed_release, "tag": None}


def test_promote_rolls_back_every_replacement_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "site"
    staging = tmp_path / "staging"
    monkeypatch.setattr(sync_core_release, "ROOT", root)
    old_targets = {
        "schema/v0.2/old.json": b"old schema\n",
        "spec/v0.2/spec.md": b"old spec\n",
        "demos/v0.2-end-to-end/artifacts/old.json": b"old demo\n",
        "schema/core-candidate.json": b"old candidate\n",
        "schema/core-release.json": b"old release\n",
    }
    for relative, data in old_targets.items():
        write(root / relative, data)
    write(staging / "schema/v0.2/new.json", b"new schema\n")
    write(staging / "spec/v0.2/spec.md", b"new spec\n")
    write(staging / "demos/v0.2-end-to-end/artifacts/new.json", b"new demo\n")
    write(staging / "schema/core-candidate.json", b"new candidate\n")
    original_replace = Path.replace

    def fail_on_spec(source: Path, target: Path) -> Path:
        if source == staging / "spec/v0.2/spec.md":
            raise OSError("simulated promotion failure")
        return original_replace(source, target)

    monkeypatch.setattr(Path, "replace", fail_on_spec)

    with pytest.raises(OSError, match="simulated promotion failure"):
        sync_core_release.promote(staging, "schema/core-candidate.json", "schema/core-release.json")

    for relative, data in old_targets.items():
        assert (root / relative).read_bytes() == data
    assert not (root / "schema/v0.2/new.json").exists()
