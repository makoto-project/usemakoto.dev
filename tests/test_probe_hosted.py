from __future__ import annotations

import hashlib
import json
import urllib.error
from email.message import Message
from pathlib import Path
from typing import Self

import pytest

from scripts import probe_hosted

HOME_BYTES = b"<main>source-first data provenance</main>\n"
STATUS_BYTES = b"<main>not yet an immutable tagged release</main>\n"
LINEAGE_BYTES = b"<main>why lineage</main>\n"
REVIEW_BYTES = b"<main>review surface</main>\n"


def canonical(value: object) -> bytes:
    return (json.dumps(value, separators=(",", ":"), sort_keys=True) + "\n").encode()


def write_release_pin(root: Path, *, schema_body: bytes, walkthrough: bytes) -> bytes:
    pin = {
        "version": "0.2",
        "repository": "https://github.com/makoto-project/makoto",
        "commit": "a" * 40,
        "tag": "v0.2.0",
        "schemas": [
            {
                "path": "/schema/v0.2/origin.schema.json",
                "digest": {"sha256": hashlib.sha256(schema_body).hexdigest()},
            }
        ],
        "documentation": [
            {
                "path": probe_hosted.WALKTHROUGH_PATH,
                "digest": {"sha256": hashlib.sha256(walkthrough).hexdigest()},
            }
        ],
        "resources": [],
    }
    path = root / "schema/core-release.json"
    path.parent.mkdir(parents=True)
    pin_bytes = canonical(pin)
    path.write_bytes(pin_bytes)
    (root / "schema/core-release.schema.json").write_bytes(
        (probe_hosted.ROOT / "schema/core-release.schema.json").read_bytes()
    )
    for public_path, relative in probe_hosted.SITE_REVIEW_SURFACES.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        body = HOME_BYTES if public_path == probe_hosted.HOME_PATH else REVIEW_BYTES
        if public_path == probe_hosted.LINEAGE_PATH:
            body = LINEAGE_BYTES
        elif public_path == probe_hosted.STATUS_PATH:
            body = STATUS_BYTES
        path.write_bytes(body)
    return pin_bytes


def write_candidate_pin(root: Path, *, schema_body: bytes, walkthrough: bytes) -> bytes:
    release_bytes = write_release_pin(root, schema_body=schema_body, walkthrough=walkthrough)
    release_path = root / "schema/core-release.json"
    pin = json.loads(release_bytes)
    pin["tag"] = None
    candidate_path = root / "schema/core-candidate.json"
    candidate_bytes = canonical(pin)
    candidate_path.write_bytes(candidate_bytes)
    (root / "schema/core-candidate.schema.json").write_bytes(
        (probe_hosted.ROOT / "schema/core-candidate.schema.json").read_bytes()
    )
    release_path.unlink()
    return candidate_bytes


class Response:
    def __init__(self, url: str, body: bytes, content_type: str, cors: str | None = None) -> None:
        self.url = url
        self.body = body
        self.headers = Message()
        self.headers["Content-Type"] = content_type
        if cors is not None:
            self.headers["Access-Control-Allow-Origin"] = cors

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def getcode(self) -> int:
        return 200

    def geturl(self) -> str:
        return self.url

    def read(self) -> bytes:
        return self.body


class Opener:
    def __init__(self, responses: dict[str, Response]) -> None:
        self.responses = responses

    def open(self, request: object, timeout: float) -> Response:
        del timeout
        return self.responses[request.full_url]  # type: ignore[attr-defined]


def site_surface_responses(
    root: Path, base: str, *, homepage: bytes = HOME_BYTES
) -> dict[str, Response]:
    responses: dict[str, Response] = {}
    for public_path, relative in probe_hosted.SITE_REVIEW_SURFACES.items():
        body = (root / relative).read_bytes()
        if public_path == probe_hosted.HOME_PATH:
            body = homepage
        responses[f"{base}{public_path}"] = Response(f"{base}{public_path}", body, "text/html")
    return responses


def candidate_responses(
    root: Path,
    base: str,
    *,
    pin_bytes: bytes,
    schema: bytes,
    walkthrough: bytes,
    homepage: bytes = HOME_BYTES,
) -> dict[str, Response]:
    return {
        f"{base}/schema/core-candidate.json": Response(
            f"{base}/schema/core-candidate.json", pin_bytes, "application/json", "*"
        ),
        f"{base}/schema/core-candidate.schema.json": Response(
            f"{base}/schema/core-candidate.schema.json",
            (root / "schema/core-candidate.schema.json").read_bytes(),
            "application/json",
            "*",
        ),
        f"{base}/schema/v0.2/origin.schema.json": Response(
            f"{base}/schema/v0.2/origin.schema.json", schema, "application/json", "*"
        ),
        f"{base}{probe_hosted.WALKTHROUGH_PATH}": Response(
            f"{base}{probe_hosted.WALKTHROUGH_PATH}", walkthrough, "text/html"
        ),
        **site_surface_responses(root, base, homepage=homepage),
    }


def test_probe_once_accepts_exact_bytes_media_types_cors_and_tag_link(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = "https://example.test"
    schema = b'{"type":"object"}\n'
    tag_link = "https://github.com/makoto-project/makoto/tree/v0.2.0/demos/v0.2-end-to-end"
    walkthrough = f'<a href="{tag_link}">tag</a>\n'.encode()
    pin_bytes = write_release_pin(tmp_path, schema_body=schema, walkthrough=walkthrough)
    responses = {
        f"{base}/schema/core-release.json": Response(
            f"{base}/schema/core-release.json", pin_bytes, "application/json", "*"
        ),
        f"{base}/schema/v0.2/origin.schema.json": Response(
            f"{base}/schema/v0.2/origin.schema.json", schema, "application/json", "*"
        ),
        f"{base}/schema/core-release.schema.json": Response(
            f"{base}/schema/core-release.schema.json",
            (tmp_path / "schema/core-release.schema.json").read_bytes(),
            "application/json",
            "*",
        ),
        f"{base}{probe_hosted.WALKTHROUGH_PATH}": Response(
            f"{base}{probe_hosted.WALKTHROUGH_PATH}", walkthrough, "text/html"
        ),
        **site_surface_responses(tmp_path, base),
    }
    monkeypatch.setattr(
        probe_hosted.urllib.request, "build_opener", lambda *args: Opener(responses)
    )

    probe_hosted.probe_once(tmp_path, base, timeout=1)


def test_probe_once_accepts_exact_candidate_commit_link_and_disclosure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = "https://example.test"
    schema = b'{"type":"object"}\n'
    commit_link = f"https://github.com/makoto-project/makoto/tree/{'a' * 40}/demos/v0.2-end-to-end"
    walkthrough = f'<a href="{commit_link}">candidate source</a>\n'.encode()
    pin_bytes = write_candidate_pin(tmp_path, schema_body=schema, walkthrough=walkthrough)
    responses = candidate_responses(
        tmp_path, base, pin_bytes=pin_bytes, schema=schema, walkthrough=walkthrough
    )
    monkeypatch.setattr(
        probe_hosted.urllib.request, "build_opener", lambda *args: Opener(responses)
    )

    probe_hosted.probe_once(tmp_path, base, timeout=1, candidate=True)


def test_candidate_probe_rejects_missing_exact_commit_link(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = "https://example.test"
    schema = b'{"type":"object"}\n'
    walkthrough = b"<main>no exact source link</main>\n"
    pin_bytes = write_candidate_pin(tmp_path, schema_body=schema, walkthrough=walkthrough)
    responses = candidate_responses(
        tmp_path, base, pin_bytes=pin_bytes, schema=schema, walkthrough=walkthrough
    )
    monkeypatch.setattr(
        probe_hosted.urllib.request, "build_opener", lambda *args: Opener(responses)
    )

    with pytest.raises(probe_hosted.ProbeError, match="exact source revision"):
        probe_hosted.probe_once(tmp_path, base, timeout=1, candidate=True)


def test_candidate_probe_rejects_missing_specification_disclosure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = "https://example.test"
    schema = b'{"type":"object"}\n'
    commit_link = f"https://github.com/makoto-project/makoto/tree/{'a' * 40}/demos/v0.2-end-to-end"
    walkthrough = f'<a href="{commit_link}">candidate source</a>\n'.encode()
    pin_bytes = write_candidate_pin(tmp_path, schema_body=schema, walkthrough=walkthrough)
    status_page = b"<main>status omitted</main>\n"
    (tmp_path / "spec/index.html").write_bytes(status_page)
    responses = candidate_responses(
        tmp_path,
        base,
        pin_bytes=pin_bytes,
        schema=schema,
        walkthrough=walkthrough,
    )
    monkeypatch.setattr(
        probe_hosted.urllib.request, "build_opener", lambda *args: Opener(responses)
    )

    with pytest.raises(probe_hosted.ProbeError, match="unreleased status"):
        probe_hosted.probe_once(tmp_path, base, timeout=1, candidate=True)


def test_candidate_expectations_reject_coexisting_release_pin(tmp_path: Path) -> None:
    schema = b'{"type":"object"}\n'
    commit_link = f"https://github.com/makoto-project/makoto/tree/{'a' * 40}/demos/v0.2-end-to-end"
    walkthrough = f'<a href="{commit_link}">candidate source</a>\n'.encode()
    write_candidate_pin(tmp_path, schema_body=schema, walkthrough=walkthrough)
    (tmp_path / "schema/core-release.json").write_bytes(b"{}\n")

    with pytest.raises(probe_hosted.ProbeError, match="cannot coexist"):
        probe_hosted.load_expectations(tmp_path, candidate=True)


@pytest.mark.parametrize(
    ("body", "content_type", "cors", "message"),
    [
        (b"changed\n", "application/json", "*", "body digest differs"),
        (b'{"type":"object"}\n', "text/plain", "*", "wrong Content-Type"),
        (b'{"type":"object"}\n', "application/json", None, "schema CORS must be"),
    ],
)
def test_fetch_exact_rejects_bad_schema_response(
    body: bytes, content_type: str, cors: str | None, message: str
) -> None:
    base = "https://example.test"
    path = "/schema/v0.2/origin.schema.json"
    expected = b'{"type":"object"}\n'
    response = Response(base + path, body, content_type, cors)
    resource = probe_hosted.ExpectedResource(
        path,
        hashlib.sha256(expected).hexdigest(),
        ("application/json", "application/schema+json"),
        True,
    )

    with pytest.raises(probe_hosted.ProbeError, match=message):
        probe_hosted.fetch_exact(Opener({base + path: response}), base, resource, timeout=1)


def test_fetch_exact_sends_explicit_accept_header() -> None:
    base = "https://example.test"
    path = probe_hosted.HOME_PATH
    response = Response(base + path, HOME_BYTES, "text/html")
    resource = probe_hosted.ExpectedResource(
        path,
        hashlib.sha256(HOME_BYTES).hexdigest(),
        ("text/html",),
        False,
    )

    class RecordingOpener:
        def open(self, request: object, timeout: float) -> Response:
            del timeout
            assert request.get_header("Accept") == "*/*"  # type: ignore[attr-defined]
            return response

    assert probe_hosted.fetch_exact(RecordingOpener(), base, resource, timeout=1) == HOME_BYTES


def test_fetch_exact_rejects_redirect() -> None:
    base = "https://example.test"
    path = probe_hosted.WALKTHROUGH_PATH
    headers = Message()
    headers["Location"] = path.rstrip("/")
    resource = probe_hosted.ExpectedResource(path, "0" * 64, ("text/html",), False)

    class RedirectingOpener:
        def open(self, request: object, timeout: float) -> Response:
            del timeout
            raise urllib.error.HTTPError(
                request.full_url,
                301,
                "Moved",
                headers,
                None,  # type: ignore[attr-defined,arg-type]
            )

    with pytest.raises(probe_hosted.ProbeError, match="redirect forbidden"):
        probe_hosted.fetch_exact(RedirectingOpener(), base, resource, timeout=1)


def test_load_expectations_rejects_slashless_documentation_path(tmp_path: Path) -> None:
    schema = b'{"type":"object"}\n'
    walkthrough = b"walkthrough\n"
    write_release_pin(tmp_path, schema_body=schema, walkthrough=walkthrough)
    pin_path = tmp_path / "schema/core-release.json"
    pin = json.loads(pin_path.read_bytes())
    pin["documentation"][0]["path"] = probe_hosted.WALKTHROUGH_PATH.rstrip("/")
    pin_path.write_bytes(canonical(pin))

    with pytest.raises(probe_hosted.ProbeError, match="trailing slashes"):
        probe_hosted.load_expectations(tmp_path)
