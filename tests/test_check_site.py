from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from scripts import check_site


def canonical(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
        + b"\n"
    )


def write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def checksum_schema() -> dict[str, object]:
    return {
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
                            "properties": {"sha256": {"type": "string"}},
                        },
                    },
                },
            },
        },
    }


def write_checksum_manifest(core: Path, paths: tuple[str, ...]) -> None:
    files = [
        {"path": relative, "digest": {"sha256": digest((core / relative).read_bytes())}}
        for relative in sorted(paths, key=str.encode)
    ]
    write(
        core / "release/v0.2/checksums.json",
        canonical({"version": "1", "tag": "v0.2.0", "files": files}),
    )


def make_parity_trees(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    site = tmp_path / "site"
    core = tmp_path / "core"
    checksum_paths: list[str] = []
    for name in check_site.CORE_SCHEMA_NAMES:
        if name == "catalog.json":
            data = canonical({"resources": []})
        else:
            data = canonical(
                {
                    "$schema": "https://json-schema.org/draft/2020-12/schema",
                    "$id": f"https://usemakoto.dev/schema/v0.2/{name}",
                    "type": "object",
                }
            )
        write(site / f"schema/v0.2/{name}", data)
        write(core / f"schemas/v0.2/{name}", data)
        checksum_paths.append(f"schemas/v0.2/{name}")
    write(site / "spec/v0.2/spec.md", b"spec\n")
    write(core / "spec/v0.2.md", b"spec\n")
    write(site / "demos/v0.2-end-to-end/artifacts/.keep", b"")
    write(core / "demos/v0.2-end-to-end/generated/.keep", b"")
    schema_bytes = canonical(checksum_schema())
    write(core / "release/checksums.schema.json", schema_bytes)
    checksum_paths.extend(("release/checksums.schema.json", "spec/v0.2.md"))
    write_checksum_manifest(core, tuple(checksum_paths))
    monkeypatch.setattr(check_site, "ROOT", site)
    monkeypatch.setattr(check_site, "CORE_CHECKSUM_PREFIXES", ())
    monkeypatch.setattr(check_site, "CORE_CHECKSUM_EXACT_PATHS", tuple(checksum_paths))
    return site, core


def test_strict_json_rejects_duplicate_keys(tmp_path: Path) -> None:
    value = tmp_path / "duplicate.json"
    value.write_text('{"version":"0.2","version":"0.2"}', encoding="utf-8")

    with pytest.raises(check_site.DuplicateKeyError):
        check_site.strict_json(value)


def test_local_reference_resolution_is_root_bounded() -> None:
    page = check_site.ROOT / "spec/v0.2/index.html"

    resolved = check_site.resolve_local_reference(page, "/schema/v0.2/catalog.json")
    assert resolved is not None
    assert resolved[0] == check_site.ROOT / "schema/v0.2/catalog.json"

    escaped = check_site.resolve_local_reference(page, "../../../outside")
    assert escaped is not None
    assert escaped[0].name == "__path_escape__"


def test_current_site_truthfulness_contract_passes() -> None:
    errors: list[str] = []

    check_site.check_truthfulness(errors)

    assert errors == []


def test_lineage_story_is_a_first_class_linked_route() -> None:
    page = check_site.ROOT / check_site.LINEAGE_PAGE
    home = (check_site.ROOT / "index.html").read_text(encoding="utf-8")

    assert page.is_file()
    assert 'href="/why-lineage/"' in home
    content = page.read_text(encoding="utf-8")
    assert all(required in content for required in check_site.LINEAGE_REQUIRED_TEXT)


def test_current_pages_share_persistent_navigation_and_mobile_menu() -> None:
    for relative in check_site.CURRENT_SHELL_PAGES:
        content = (check_site.ROOT / relative).read_text(encoding="utf-8")
        assert all(marker in content for marker in check_site.CURRENT_SHELL_MARKERS), relative

        parser = check_site.PageParser()
        parser.feed(content)
        expected = "/" if relative == "index.html" else f"/{relative.removesuffix('index.html')}"
        assert parser.mobile_current_hrefs == [expected], relative


def test_home_restores_examples_tooling_and_open_source_discovery() -> None:
    home = (check_site.ROOT / "index.html").read_text(encoding="utf-8")

    assert "Poisoned pipeline" in home
    assert "Scientific reproducibility" in home
    assert "Configuration postmortem" in home
    assert "Invisible Unicode" in home
    assert "Tooling &amp; SDKs" in home
    assert "Build with us on GitHub" in home
    assert "Contributions welcome" in home


def test_tooling_page_keeps_current_and_historical_status_separate() -> None:
    content = (check_site.ROOT / "tooling/index.html").read_text(encoding="utf-8")

    assert "Reference CLI and Python library" in content
    assert "Current v0.2 source" in content
    assert "Historical v0.1 experiments" in content
    assert "not a published Makoto distribution" in content
    assert "no maintained v0.2 adapter packages are claimed" in content


def test_community_page_links_real_public_participation_paths() -> None:
    content = (check_site.ROOT / "community/index.html").read_text(encoding="utf-8")

    assert (check_site.ROOT / "CONTRIBUTING.md").is_file()
    assert "Makoto is developed in public." in content
    assert "Formal governance is not established yet" in content
    assert "https://github.com/makoto-project/makoto/issues/new" in content
    assert "https://github.com/makoto-project/usemakoto.dev/issues/new" in content
    assert "CONTRIBUTING.md" in content


def test_current_site_matches_sibling_core_working_tree() -> None:
    errors: list[str] = []
    core = check_site.ROOT.parent / "core"

    check_site.check_core_parity(core, errors)

    assert errors == []


def test_current_local_link_graph_is_closed() -> None:
    errors: list[str] = []

    check_site.check_links(errors)

    assert errors == []


def test_current_v02_json_examples_match_explicit_schemas() -> None:
    errors: list[str] = []

    check_site.check_json_examples(errors)

    assert errors == []


def test_public_documentation_pin_paths_are_canonical_directory_urls() -> None:
    assert all(path.endswith("/") for path in check_site.DOCUMENTATION_FILES)


def test_release_resources_cover_diagnostic_contract_and_receiver_handoff() -> None:
    resources = check_site.expected_resource_files()

    assert resources["/spec/v0.2/diagnostic-map.json"][1:] == ("application/json", True)
    assert resources["/demos/v0.2-end-to-end/artifacts/receiver/expected-artifact.json"][1:] == (
        "application/json",
        True,
    )


def test_compare_trees_reports_path_and_shared_byte_drift(
    tmp_path: Path,
) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    write(left / "shared.json", b"left\n")
    write(right / "shared.json", b"right\n")
    write(right / "missing.json", b"missing\n")
    errors: list[str] = []

    check_site.compare_trees(left, right, "fixture", errors)

    assert any("path set differs" in error for error in errors)
    assert "fixture bytes differ: shared.json" in errors


def test_validate_core_checksums_rejects_missing_manifest(tmp_path: Path) -> None:
    core = tmp_path / "core"
    write(core / "release/checksums.schema.json", canonical(checksum_schema()))
    errors: list[str] = []

    result = check_site.validate_core_checksums(core, errors)

    assert result == {}
    assert any("invalid core checksum manifest" in error for error in errors)


def test_validate_core_checksums_rejects_mutated_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    core = tmp_path / "core"
    write(core / "README.md", b"before\n")
    write(core / "release/checksums.schema.json", canonical(checksum_schema()))
    paths = ("README.md", "release/checksums.schema.json")
    write_checksum_manifest(core, paths)
    write(core / "README.md", b"after\n")
    monkeypatch.setattr(check_site, "CORE_CHECKSUM_PREFIXES", ())
    monkeypatch.setattr(check_site, "CORE_CHECKSUM_EXACT_PATHS", paths)
    errors: list[str] = []

    check_site.validate_core_checksums(core, errors)

    assert "core checksum digest differs: README.md" in errors


def test_validate_core_checksums_rejects_extra_inclusion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    core = tmp_path / "core"
    write(core / "README.md", b"core\n")
    write(core / "extra.txt", b"extra\n")
    write(core / "release/checksums.schema.json", canonical(checksum_schema()))
    paths = ("README.md", "extra.txt", "release/checksums.schema.json")
    write_checksum_manifest(core, paths)
    monkeypatch.setattr(check_site, "CORE_CHECKSUM_PREFIXES", ())
    monkeypatch.setattr(
        check_site,
        "CORE_CHECKSUM_EXACT_PATHS",
        ("README.md", "release/checksums.schema.json"),
    )
    errors: list[str] = []

    check_site.validate_core_checksums(core, errors)

    assert "core checksum inclusion set is not exact" in errors


def test_core_parity_rejects_schema_id_that_differs_from_hosted_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    site, core = make_parity_trees(tmp_path, monkeypatch)
    name = "origin.schema.json"
    value = json.loads((core / f"schemas/v0.2/{name}").read_bytes())
    value["$id"] = "https://example.invalid/wrong.json"
    data = canonical(value)
    write(core / f"schemas/v0.2/{name}", data)
    write(site / f"schema/v0.2/{name}", data)
    checksum_paths = check_site.CORE_CHECKSUM_EXACT_PATHS
    write_checksum_manifest(core, checksum_paths)
    errors: list[str] = []

    check_site.check_core_parity(core, errors)

    assert f"schema $id differs from hosted URL: {name}" in errors


def test_validate_pin_defaults_to_sibling_core(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    site = tmp_path / "site"
    core = tmp_path / "core"
    core.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=core, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=core, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=core, check=True)
    write(core / "README.md", b"core\n")
    subprocess.run(["git", "add", "."], cwd=core, check=True)
    subprocess.run(["git", "commit", "-qm", "fixture"], cwd=core, check=True)
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=core,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    pin_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": ["commit", "schemas", "documentation", "resources"],
        "properties": {
            "commit": {"type": "string"},
            "schemas": {"type": "array"},
            "documentation": {"type": "array"},
            "resources": {"type": "array"},
        },
    }
    write(site / "schema/core-candidate.schema.json", canonical(pin_schema))
    write(
        site / "schema/core-candidate.json",
        canonical({"commit": commit, "schemas": [], "documentation": [], "resources": []}),
    )
    monkeypatch.setattr(check_site, "ROOT", site)
    errors: list[str] = []

    resolved = check_site.validate_pin("candidate", None, errors)

    assert resolved == core


def test_validate_pin_rejects_noncanonical_candidate_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    site = tmp_path / "site"
    core = tmp_path / "core"
    core.mkdir()
    pin_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": ["commit", "schemas", "documentation", "resources"],
        "properties": {
            "commit": {"type": "string"},
            "schemas": {"type": "array"},
            "documentation": {"type": "array"},
            "resources": {"type": "array"},
        },
    }
    pin = {"commit": "a" * 40, "schemas": [], "documentation": [], "resources": []}
    write(site / "schema/core-candidate.schema.json", canonical(pin_schema))
    write(
        site / "schema/core-candidate.json",
        (json.dumps(pin, indent=2) + "\n").encode(),
    )
    monkeypatch.setattr(check_site, "ROOT", site)

    class Result:
        stdout = "a" * 40 + "\n"

    monkeypatch.setattr(check_site.subprocess, "run", lambda *args, **kwargs: Result())
    errors: list[str] = []

    check_site.validate_pin("candidate", core, errors)

    assert "candidate pin is not canonical JSON plus one LF" in errors
