from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from scripts import local_ci

CHECKOUT = "actions/checkout"
SHA = "3d3c42e5aac5ba805825da76410c181273ba90b1"
OTHER_SHA = "1" * 40


def write_pin(root: Path, name: str, commit: str) -> None:
    path = root / "schema" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"commit": commit, "version": "0.2"}))


def write_workflow(root: Path, body: str) -> None:
    path = root / ".github/workflows/deploy.yml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)


def test_read_pin_prefers_the_candidate_when_it_is_the_only_pin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(local_ci, "ROOT", tmp_path)
    write_pin(tmp_path, "core-candidate.json", "b" * 40)

    assert local_ci.read_pin() == ("candidate", "b" * 40)


def test_read_pin_reports_the_release_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(local_ci, "ROOT", tmp_path)
    write_pin(tmp_path, "core-release.json", "c" * 40)

    assert local_ci.read_pin() == ("release", "c" * 40)


def test_read_pin_refuses_two_coexisting_pins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(local_ci, "ROOT", tmp_path)
    write_pin(tmp_path, "core-candidate.json", "b" * 40)
    write_pin(tmp_path, "core-release.json", "c" * 40)

    with pytest.raises(ValueError, match="cannot coexist"):
        local_ci.read_pin()


def test_read_pin_refuses_a_missing_pin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(local_ci, "ROOT", tmp_path)

    with pytest.raises(ValueError, match="no candidate or release pin"):
        local_ci.read_pin()


def test_uses_pattern_reads_the_action_ref_and_version_comment() -> None:
    found = local_ci.USES_PATTERN.findall(
        "      - uses: actions/checkout@abc # v7.0.1\n"
        "        uses: astral-sh/setup-uv@v10.0.1\n"
    )

    assert found == [
        ("actions/checkout", "abc", "v7.0.1"),
        ("astral-sh/setup-uv", "v10.0.1", ""),
    ]


def test_digest_pin_matching_its_version_comment_is_accepted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(local_ci, "ROOT", tmp_path)
    monkeypatch.setattr(local_ci, "_remote_tag_shas", lambda remote, tag: {SHA})
    write_workflow(tmp_path, f"      - uses: {CHECKOUT}@{SHA} # v7.0.1\n")

    assert local_ci.check_action_refs() == []


def test_digest_pin_contradicting_its_version_comment_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(local_ci, "ROOT", tmp_path)
    monkeypatch.setattr(local_ci, "_remote_tag_shas", lambda remote, tag: {OTHER_SHA})
    write_workflow(tmp_path, f"      - uses: {CHECKOUT}@{SHA} # v7.0.1\n")

    problems = local_ci.check_action_refs()

    assert len(problems) == 1
    assert "is not v7.0.1" in problems[0]


def test_digest_pin_claiming_a_nonexistent_tag_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(local_ci, "ROOT", tmp_path)
    monkeypatch.setattr(local_ci, "_remote_tag_shas", lambda remote, tag: set())
    write_workflow(tmp_path, f"      - uses: {CHECKOUT}@{SHA} # v99.0.0\n")

    problems = local_ci.check_action_refs()

    assert len(problems) == 1
    assert "does not exist" in problems[0]


def test_digest_pin_without_a_version_comment_is_left_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(local_ci, "ROOT", tmp_path)
    write_workflow(tmp_path, f"      - uses: {CHECKOUT}@{SHA}\n")

    assert local_ci.check_action_refs() == []


def test_unresolvable_tag_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(local_ci, "ROOT", tmp_path)
    monkeypatch.setattr(
        local_ci.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout="", stderr=""),
    )
    write_workflow(tmp_path, "      - uses: astral-sh/setup-uv@v10\n")

    problems = local_ci.check_action_refs()

    assert len(problems) == 1
    assert "does not resolve" in problems[0]


def test_resolvable_tag_is_accepted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(local_ci, "ROOT", tmp_path)
    monkeypatch.setattr(
        local_ci.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(
            a, 0, stdout=f"{SHA}\trefs/tags/v7\n", stderr=""
        ),
    )
    write_workflow(tmp_path, "      - uses: actions/checkout@v7\n")

    assert local_ci.check_action_refs() == []


def test_actionlint_absence_is_a_skip_not_a_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(local_ci, "find_actionlint", lambda: None)

    status, detail = local_ci.check_actionlint()

    assert status == "skip"
    assert "not installed" in detail


def test_actionlint_is_found_outside_path_in_the_homebrew_prefix(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(local_ci.shutil, "which", lambda name: None)
    monkeypatch.setattr(
        local_ci.Path, "is_file", lambda self: str(self) == "/opt/homebrew/bin/actionlint"
    )

    assert local_ci.find_actionlint() == "/opt/homebrew/bin/actionlint"


def test_actionlint_findings_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(local_ci, "find_actionlint", lambda: "/usr/bin/actionlint")
    monkeypatch.setattr(
        local_ci.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a, 1, stdout="deploy.yml:1:1: oops", stderr=""),
    )

    status, detail = local_ci.check_actionlint()

    assert status == "fail"
    assert "oops" in detail


def test_sync_core_refuses_a_dirty_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    core = tmp_path / "core"
    (core / ".git").mkdir(parents=True)
    calls = {"rev-parse": "d" * 40, "status": " M file.txt"}
    monkeypatch.setattr(local_ci, "git", lambda *a, **k: calls[a[0]])

    with pytest.raises(ValueError, match="local changes"):
        local_ci.sync_core(core, "e" * 40)
