#!/usr/bin/env python3
"""Verify that a hosted Makoto candidate or release serves exact reviewed bytes."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE_URL = "https://usemakoto.dev"
HOME_PATH = "/"
LINEAGE_PATH = "/why-lineage/"
WALKTHROUGH_PATH = "/demos/v0.2-end-to-end/"
SITE_REVIEW_SURFACES = {
    HOME_PATH: "index.html",
    LINEAGE_PATH: "why-lineage/index.html",
    "/community/": "community/index.html",
    "/examples/v0.2/": "examples/v0.2/index.html",
    "/integrations/v0.2/": "integrations/v0.2/index.html",
    "/tooling/": "tooling/index.html",
}
CANDIDATE_DISCLOSURE = b"v0.2 candidate \xc2\xb7 not yet released"


class ProbeError(ValueError):
    """The hosted site does not match the reviewed candidate or release tree."""


class NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> None:
        del req, fp, code, msg, headers, newurl


@dataclass(frozen=True)
class ExpectedResource:
    path: str
    sha256: str
    media_types: tuple[str, ...]
    require_cors: bool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--attempts", type=int, default=1)
    parser.add_argument("--retry-delay", type=float, default=10.0)
    parser.add_argument("--timeout", type=float, default=15.0)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--candidate",
        action="store_true",
        help="probe a hosted review candidate",
    )
    mode.add_argument("--release", action="store_true", help="probe a tagged release")
    args = parser.parse_args()
    parsed = urlsplit(args.base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        parser.error("--base-url must be an absolute HTTP(S) origin")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        parser.error("--base-url must not include a path, query, or fragment")
    if args.attempts < 1:
        parser.error("--attempts must be at least 1")
    if args.retry_delay < 0 or args.timeout <= 0:
        parser.error("retry delay must be nonnegative and timeout must be positive")
    return args


def strict_json(path: Path) -> Any:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ProbeError(f"{path}: UTF-8 BOM is forbidden")

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ProbeError(f"{path}: duplicate JSON key {key!r}")
            result[key] = value
        return result

    try:
        return json.loads(raw, object_pairs_hook=pairs)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ProbeError(f"{path}: invalid strict JSON: {error}") from error


def load_expectations(
    root: Path, *, candidate: bool = False
) -> tuple[list[ExpectedResource], str | None]:
    mode = "candidate" if candidate else "release"
    pin_path = root / f"schema/core-{mode}.json"
    forbidden_pin = root / f"schema/core-{'release' if candidate else 'candidate'}.json"
    if not pin_path.is_file():
        raise ProbeError(f"hosted {mode} probing requires schema/core-{mode}.json")
    if forbidden_pin.exists():
        raise ProbeError("candidate and release pins cannot coexist")
    pin = strict_json(pin_path)
    schema_path = root / f"schema/core-{mode}.schema.json"
    try:
        schema = strict_json(schema_path)
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(pin)
    except (OSError, ProbeError, SchemaError, ValidationError) as error:
        raise ProbeError(f"invalid local {mode} pin: {error}") from error
    canonical = (
        json.dumps(pin, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode() + b"\n"
    )
    if pin_path.read_bytes() != canonical:
        raise ProbeError(f"local {mode} pin is not canonical JSON plus one LF")
    expected_tag = None if candidate else "v0.2.0"
    if pin.get("tag") != expected_tag:
        raise ProbeError(f"hosted {mode} probing requires tag {expected_tag!r}")
    documentation_paths = [item["path"] for item in pin["documentation"]]
    if any(not path.endswith("/") for path in documentation_paths):
        raise ProbeError("documentation pin paths must use canonical trailing slashes")
    resources = [
        ExpectedResource(
            path=f"/schema/core-{mode}.json",
            sha256=hashlib.sha256(pin_path.read_bytes()).hexdigest(),
            media_types=("application/json",),
            require_cors=True,
        ),
        ExpectedResource(
            path=f"/schema/core-{mode}.schema.json",
            sha256=hashlib.sha256(schema_path.read_bytes()).hexdigest(),
            media_types=("application/json", "application/schema+json"),
            require_cors=True,
        ),
    ]
    resources.extend(
        ExpectedResource(
            path=public_path,
            sha256=hashlib.sha256((root / relative).read_bytes()).hexdigest(),
            media_types=("text/html",),
            require_cors=False,
        )
        for public_path, relative in SITE_REVIEW_SURFACES.items()
    )
    resources.extend(
        ExpectedResource(
            path=item["path"],
            sha256=item["digest"]["sha256"],
            media_types=("application/json", "application/schema+json"),
            require_cors=True,
        )
        for item in pin["schemas"]
    )
    resources.extend(
        ExpectedResource(
            path=item["path"],
            sha256=item["digest"]["sha256"],
            media_types=("text/html",),
            require_cors=False,
        )
        for item in pin["documentation"]
    )
    resources.extend(
        ExpectedResource(
            path=item["path"],
            sha256=item["digest"]["sha256"],
            media_types=(item["mediaType"],),
            require_cors=item["cors"],
        )
        for item in pin["resources"]
    )
    paths = [resource.path for resource in resources]
    if len(paths) != len(set(paths)):
        raise ProbeError(f"{mode} pin resource paths must be globally unique")
    if paths.count(WALKTHROUGH_PATH) != 1:
        raise ProbeError(f"{mode} pin must contain the exact walkthrough path once")
    revision = pin["commit"] if candidate else pin["tag"]
    source_link = f"https://github.com/makoto-project/makoto/tree/{revision}/demos/v0.2-end-to-end"
    return resources, source_link


def fetch_exact(
    opener: urllib.request.OpenerDirector,
    base_url: str,
    resource: ExpectedResource,
    *,
    timeout: float,
) -> bytes:
    url = base_url.rstrip("/") + resource.path
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "*/*",
            "User-Agent": "makoto-release-probe/0.2",
        },
    )
    try:
        with opener.open(request, timeout=timeout) as response:
            status = response.getcode()
            body = response.read()
            content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            cors = response.headers.get("Access-Control-Allow-Origin")
            final_url = response.geturl()
    except urllib.error.HTTPError as error:
        if 300 <= error.code < 400:
            raise ProbeError(
                f"redirect forbidden for {resource.path}: HTTP {error.code} to "
                f"{error.headers.get('Location', '')!r}"
            ) from error
        raise ProbeError(f"HTTP {error.code} for {resource.path}") from error
    except urllib.error.URLError as error:
        raise ProbeError(f"request failed for {resource.path}: {error.reason}") from error
    if status != 200:
        raise ProbeError(f"expected HTTP 200 for {resource.path}, got {status}")
    if final_url != url:
        raise ProbeError(f"redirect forbidden for {resource.path}: final URL is {final_url}")
    if content_type not in resource.media_types:
        raise ProbeError(
            f"wrong Content-Type for {resource.path}: expected one of "
            f"{resource.media_types!r}, got {content_type!r}"
        )
    if resource.require_cors and cors != "*":
        raise ProbeError(f"schema CORS must be '*' for {resource.path}, got {cors!r}")
    actual_digest = hashlib.sha256(body).hexdigest()
    if actual_digest != resource.sha256:
        raise ProbeError(
            f"body digest differs for {resource.path}: expected {resource.sha256}, got {actual_digest}"
        )
    return body


def probe_once(root: Path, base_url: str, *, timeout: float, candidate: bool = False) -> None:
    resources, source_link = load_expectations(root, candidate=candidate)
    opener = urllib.request.build_opener(NoRedirects())
    walkthrough: bytes | None = None
    homepage: bytes | None = None
    for resource in resources:
        body = fetch_exact(opener, base_url, resource, timeout=timeout)
        if resource.path == WALKTHROUGH_PATH:
            walkthrough = body
        elif resource.path == HOME_PATH:
            homepage = body
    if walkthrough is None:
        raise ProbeError("walkthrough was not included in the hosted expectations")
    if source_link.encode() not in walkthrough:
        raise ProbeError(f"walkthrough does not link to exact source revision: {source_link}")
    if candidate and (homepage is None or CANDIDATE_DISCLOSURE not in homepage):
        raise ProbeError("hosted candidate homepage does not disclose its unreleased status")


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    last_error: ProbeError | None = None
    for attempt in range(1, args.attempts + 1):
        try:
            probe_once(root, args.base_url, timeout=args.timeout, candidate=args.candidate)
        except ProbeError as error:
            last_error = error
            if attempt == args.attempts:
                break
            print(f"probe attempt {attempt}/{args.attempts} failed: {error}")
            time.sleep(args.retry_delay)
        else:
            mode = "candidate" if args.candidate else "release"
            count = len(load_expectations(root, candidate=args.candidate)[0])
            print(f"hosted {mode} probe passed: {count} exact resources")
            return 0
    assert last_error is not None
    raise last_error


if __name__ == "__main__":
    raise SystemExit(main())
