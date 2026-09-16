from __future__ import annotations

import base64
import html
import json
import re
import shutil
import subprocess

import pytest

from scripts import check_site, render_spec

REQUIRED_LANGUAGES = ("json", "yaml", "python", "javascript", "typescript", "go", "bash", "sql")


def test_generated_specification_pages_are_current() -> None:
    targets = (
        (render_spec.TEXT_PAGE, render_spec.text_page()),
        (render_spec.SCHEMA_PAGE, render_spec.schema_page()),
        (render_spec.LATEST_POINTER, render_spec.latest_pointer()),
    )
    for path, expected in targets:
        assert path.read_text(encoding="utf-8") == expected, (
            f"{path.relative_to(check_site.ROOT)} is stale; run scripts/render_spec.py"
        )


def test_schema_page_shows_published_bytes() -> None:
    content = render_spec.SCHEMA_PAGE.read_text(encoding="utf-8")
    for path in sorted(render_spec.SCHEMA_DIR.iterdir()):
        text = path.read_text(encoding="utf-8").rstrip("\n")
        if "\n" in text:
            assert html.escape(text) in content, path.name


def test_hub_origin_example_is_the_published_envelope_payload() -> None:
    hub = (check_site.ROOT / "spec/index.html").read_text(encoding="utf-8")
    match = re.search(
        r'<a href="(/demos/[^"]+\.dsse\.json)">the published envelope</a>.*?'
        r'<code class="language-json">(.*?)</code>',
        hub,
        flags=re.DOTALL,
    )
    assert match is not None
    envelope = json.loads((check_site.ROOT / match.group(1).lstrip("/")).read_text("utf-8"))
    payload = json.loads(base64.b64decode(envelope["payload"]))

    assert json.loads(html.unescape(match.group(2))) == payload


def test_every_highlighted_page_loads_the_shared_bundle() -> None:
    for path in sorted(check_site.ROOT.rglob("*.html")):
        content = path.read_text(encoding="utf-8", errors="replace")
        if 'class="language-' in content:
            assert '<script defer src="/assets/prism.js"></script>' in content, path.relative_to(
                check_site.ROOT
            )


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_prism_bundle_registers_every_required_language() -> None:
    script = (
        "const vm=require('vm');const c={};vm.createContext(c);"
        "vm.runInContext(require('fs').readFileSync(process.argv[1],'utf8'),c);"
        "console.log(JSON.stringify(Object.keys(c.Prism.languages)));"
    )
    result = subprocess.run(
        ["node", "-e", script, str(check_site.ROOT / "assets/prism.js")],
        check=True,
        capture_output=True,
        text=True,
    )
    languages = set(json.loads(result.stdout))

    assert set(REQUIRED_LANGUAGES) <= languages
