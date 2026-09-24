"""The v0.3 identifiers the core declares under usemakoto.dev resolve to pinned bytes."""

from __future__ import annotations

import hashlib
import json
import re

from scripts import check_site, sync_core_release

ROOT = check_site.ROOT
PROFILE_ID = "https://usemakoto.dev/profile/v0.3/license-claim-v1.schema.json"


def pinned_profile_values() -> tuple[str, int]:
    """The digest and byte length spec/v0.3.md fixes for the standard profile."""
    spec = (ROOT / "spec/v0.3/spec.md").read_text(encoding="utf-8")
    match = re.search(
        rf"has ID `{re.escape(PROFILE_ID)}`, SHA-256 `([0-9a-f]{{64}})`, byte length (\d+),",
        spec,
    )
    assert match is not None, "spec/v0.3.md no longer states the profile pin"
    return match.group(1), int(match.group(2))


def test_licence_profile_is_served_at_its_id_with_the_pinned_bytes() -> None:
    expected_digest, expected_length = pinned_profile_values()
    data = (ROOT / PROFILE_ID.removeprefix("https://usemakoto.dev/")).read_bytes()

    assert len(data) == expected_length
    assert hashlib.sha256(data).hexdigest() == expected_digest
    assert json.loads(data)["$id"] == PROFILE_ID


def test_candidate_pin_carries_the_profile_digest() -> None:
    expected_digest, _ = pinned_profile_values()
    pin = json.loads((ROOT / "schema/core-candidate.json").read_text(encoding="utf-8"))
    resources = {item["path"]: item for item in pin["resources"]}

    entry = resources["/profile/v0.3/license-claim-v1.schema.json"]
    assert entry["digest"]["sha256"] == expected_digest
    assert (entry["mediaType"], entry["cors"]) == ("application/json", True)


def test_every_v03_schema_is_hosted_at_its_id() -> None:
    for name in check_site.V03_CORE_SCHEMA_NAMES:
        document = json.loads((ROOT / "schema/v0.3" / name).read_text(encoding="utf-8"))
        if name.endswith(".schema.json"):
            assert document["$id"] == f"https://usemakoto.dev/schema/v0.3/{name}"


def test_every_declared_v03_identifier_resolves_to_a_page_or_file() -> None:
    spec = (ROOT / "spec/v0.3/spec.md").read_text(encoding="utf-8")
    declared = set(
        re.findall(r"https://usemakoto\.dev/[a-z]+/v0\.3/[A-Za-z0-9._/-]*[A-Za-z0-9]", spec)
    )
    assert PROFILE_ID in declared
    for url in sorted(declared):
        relative = url.removeprefix("https://usemakoto.dev/")
        target = ROOT / relative
        assert target.is_file() or (target / "index.html").is_file(), url


def test_v02_publication_is_unchanged_beside_v03() -> None:
    pin = json.loads((ROOT / "schema/core-candidate.json").read_text(encoding="utf-8"))
    schemas = {item["path"] for item in pin["schemas"]}
    documentation = {item["path"] for item in pin["documentation"]}

    assert {f"/schema/v0.2/{name}" for name in check_site.CORE_SCHEMA_NAMES} <= schemas
    assert {
        "/predicate/v0.2/origin/",
        "/predicate/v0.2/transform/",
        "/spec/v0.2/",
        "/vocab/v0.2/bounded-pattern/",
    } <= documentation
    # The site default and the latest pointer stay on the current family.
    latest = json.loads((ROOT / "schema/latest.json").read_text(encoding="utf-8"))
    assert "/v0.3/" not in json.dumps(latest)


def test_sync_and_check_agree_on_the_v03_publication() -> None:
    assert sync_core_release.V03_SCHEMA_NAMES == check_site.V03_CORE_SCHEMA_NAMES
    assert sync_core_release.STATIC_RESOURCES == check_site.STATIC_RESOURCES
    assert sync_core_release.DOCUMENTATION == check_site.DOCUMENTATION_FILES
    assert sync_core_release.CHECKSUM_MANIFEST == check_site.CORE_CHECKSUM_MANIFEST
