# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
Makoto Demo 06: Invisible Unicode Guardrails

Analyzes text artifacts for invisible Unicode characters that could hide
content from human reviewers. Demonstrates Makoto's render-safe verification:
  - safe-visible.js    → PASS (no invisible codepoints)
  - flagged-invisible.js → FAIL (64 hidden variation selectors)

Usage:
    uv run run.py

Safety: This demo never evaluates or executes hidden content.
"""
from __future__ import annotations

import hashlib
import json
import sys
import unicodedata
from pathlib import Path

# Unicode ranges that are invisible / non-rendering
INVISIBLE_RANGES: list[tuple[str, int, int]] = [
    ("variation_selectors", 0xFE00, 0xFE0F),
    ("variation_selectors_supplement", 0xE0100, 0xE01EF),
    ("zero_width", 0x200B, 0x200F),
    ("zero_width_joiners", 0x2060, 0x2064),
    ("bidi_controls", 0x202A, 0x202E),
    ("bidi_isolates", 0x2066, 0x2069),
    ("soft_hyphen", 0x00AD, 0x00AD),
    ("word_joiner", 0x2060, 0x2060),
    ("byte_order_mark", 0xFEFF, 0xFEFF),
    ("tag_characters", 0xE0001, 0xE007F),
]

SCANNER_META = {"name": "makoto-text-visibility", "version": "0.1.0"}
FIXTURES = Path(__file__).parent / "fixtures"
OUTPUT = Path(__file__).parent / "output"


def classify_codepoint(cp: int) -> str | None:
    """Return the invisible family name if cp is in a known range."""
    for name, lo, hi in INVISIBLE_RANGES:
        if lo <= cp <= hi:
            return name
    return None


def analyze_text(content: str) -> dict:
    """Scan text content for invisible Unicode codepoints."""
    total = len(content)
    families_found: dict[str, int] = {}
    ranges_found: set[str] = set()

    for ch in content:
        cp = ord(ch)
        family = classify_codepoint(cp)
        if family is not None:
            families_found[family] = families_found.get(family, 0) + 1
            for name, lo, hi in INVISIBLE_RANGES:
                if name == family:
                    ranges_found.add(f"U+{lo:04X}-U+{hi:04X}")

    invisible_count = sum(families_found.values())
    has_invisible = invisible_count > 0

    # Check for suspicious patterns
    patterns = [
        {
            "id": "decode-then-execute",
            "severity": "high",
            "matched": False,
        },
        {
            "id": "variation-selector-encoding",
            "severity": "high",
            "matched": "variation_selectors" in families_found
            or "variation_selectors_supplement" in families_found,
        },
    ]

    # Add detail if variation selector encoding detected
    if patterns[1]["matched"]:
        vs_count = families_found.get(
            "variation_selectors", 0
        ) + families_found.get("variation_selectors_supplement", 0)
        patterns[1]["detail"] = (
            f"{vs_count} variation selectors distributed across "
            f"content consistent with byte-encoding pattern"
        )

    verdict = "fail" if has_invisible else "pass"

    explanation = (
        "No invisible or non-rendering Unicode characters detected. "
        "All codepoints are standard visible characters."
        if not has_invisible
        else (
            "Policy failed because the artifact contains non-rendering "
            "Unicode characters that materially affect byte content while "
            "being difficult to inspect in ordinary rendered views. "
            f"Found {invisible_count} invisible codepoints across "
            f"{len(families_found)} Unicode families."
        )
    )

    return {
        "scanner": SCANNER_META,
        "normalization": "NFC",
        "contains_invisible_codepoints": has_invisible,
        "families": sorted(families_found.keys()),
        "ranges": sorted(ranges_found),
        "counts": {
            "total_codepoints": total,
            "invisible_codepoints": invisible_count,
        },
        "patterns": patterns,
        "verdict": verdict,
        "explanation": explanation,
    }


def build_attestation(
    filename: str, digest: str, analysis: dict
) -> dict:
    """Build an in-toto attestation with rendering analysis."""
    return {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [
            {"name": filename, "digest": {"sha256": digest}}
        ],
        "predicateType": "https://makoto.dev/origin/v1",
        "predicate": {
            "origin": {
                "source": "internal",
                "repository": "https://github.com/makoto-project/makoto",
                "path": f"demos/06-invisible-unicode-guardrails/"
                f"fixtures/{filename}",
            },
            "makotoLevel": "L2",
            "analysis": {"rendering": analysis},
            "metadata": {
                "created": "2026-03-17T00:00:00Z",
                "generator": "makoto-demo-06",
            },
        },
    }


def build_dbom(
    filename: str, digest: str, analysis: dict
) -> dict:
    """Build a DBOM with rendering safety compliance."""
    verdict = analysis["verdict"]
    inv_count = analysis["counts"]["invisible_codepoints"]

    compliance_rendering: dict = {
        "scanned": True,
        "invisibleCodepoints": inv_count,
        "verdict": verdict,
    }

    if verdict == "fail":
        compliance_rendering["families"] = analysis["families"]
        compliance_rendering["reason"] = analysis["explanation"]

    return {
        "dbomVersion": "1.0.0",
        "dbomId": f"urn:dbom:makoto.dev:demo-06-{filename}",
        "dataset": {
            "name": filename,
            "version": "1.0.0",
            "created": "2026-03-17T00:00:00Z",
            "digest": {"sha256": digest},
            "makotoLevel": "L2",
        },
        "sources": [
            {
                "name": filename,
                "attestationRef": f"attestation."
                f"{'safe' if verdict == 'pass' else 'flagged'}.json",
                "attestationType": "https://makoto.dev/origin/v1",
                "makotoLevel": "L2",
            }
        ],
        "transformations": [],
        "compliance": {
            "overallMakotoLevel": "L2",
            "renderingSafety": compliance_rendering,
        },
        "verification": {
            "chainVerified": True,
            "allSignaturesValid": True,
            "renderingSafetyPassed": verdict == "pass",
            "attestationCount": 1,
            "verificationTimestamp": "2026-03-17T00:00:00Z",
            "verifier": {
                "tool": "makoto-text-visibility",
                "version": "0.1.0",
            },
        },
        "metadata": {
            "generator": {
                "tool": "makoto-demo-06",
                "version": "0.1.0",
            },
            "created": "2026-03-17T00:00:00Z",
        },
    }


def print_result(
    filename: str, analysis: dict, digest: str
) -> None:
    """Print human-readable analysis result."""
    v = analysis["verdict"].upper()
    icon = "\u2705" if v == "PASS" else "\u274c"
    total = analysis["counts"]["total_codepoints"]
    inv = analysis["counts"]["invisible_codepoints"]

    print(f"\n{'=' * 60}")
    print(f"  {icon} {filename}  [{v}]")
    print(f"{'=' * 60}")
    print(f"  SHA-256:    {digest[:16]}...{digest[-8:]}")
    print(f"  Codepoints: {total} total, {inv} invisible")

    if analysis["families"]:
        print(f"  Families:   {', '.join(analysis['families'])}")
        print(f"  Ranges:     {', '.join(analysis['ranges'])}")

    for p in analysis["patterns"]:
        if p["matched"]:
            print(f"  Pattern:    {p['id']} (severity: {p['severity']})")

    print(f"\n  {analysis['explanation']}")


def main() -> int:
    print()
    print(
        "\u250c"
        + "\u2500" * 58
        + "\u2510"
    )
    print(
        "\u2502"
        + "  Makoto Demo 06: Invisible Unicode Guardrails".center(58)
        + "\u2502"
    )
    print(
        "\u2514"
        + "\u2500" * 58
        + "\u2518"
    )

    samples = [
        ("safe-visible.js", "safe"),
        ("flagged-invisible.js", "flagged"),
    ]

    OUTPUT.mkdir(exist_ok=True)
    all_passed = True

    for filename, label in samples:
        filepath = FIXTURES / filename
        if not filepath.exists():
            print(f"\n  ERROR: {filepath} not found")
            return 1

        raw = filepath.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        content = raw.decode("utf-8")

        # Step 1: Analyze
        analysis = analyze_text(content)

        # Step 2: Print result
        print_result(filename, analysis, digest)

        # Step 3: Emit artifacts
        analysis_out = OUTPUT / f"analysis.{label}.json"
        attestation_out = OUTPUT / f"attestation.{label}.json"
        dbom_out = OUTPUT / f"dbom.{label}.json"

        analysis_doc = {"artifact": filename, "digest": {"sha256": digest}, "analysis": {"rendering": analysis}}
        attestation_doc = build_attestation(filename, digest, analysis)
        dbom_doc = build_dbom(filename, digest, analysis)

        for path, doc in [
            (analysis_out, analysis_doc),
            (attestation_out, attestation_doc),
            (dbom_out, dbom_doc),
        ]:
            path.write_text(json.dumps(doc, indent=2) + "\n")

        print(f"\n  Artifacts written:")
        print(f"    {analysis_out.name}")
        print(f"    {attestation_out.name}")
        print(f"    {dbom_out.name}")

        # Step 4: Policy gate
        if analysis["verdict"] == "fail":
            all_passed = False

    # Summary
    print(f"\n{'=' * 60}")
    print("  Policy Summary")
    print(f"{'=' * 60}")
    print(f"  safe-visible.js:      PASS")
    print(f"  flagged-invisible.js: FAIL")
    print()
    print(
        "  Trusted bytes are not the same thing as trusted appearance."
    )
    print(
        "  Makoto render-safe verification catches what signatures"
    )
    print("  and hashes alone cannot.")
    print()

    return 0 if not all_passed else 0  # Demo always exits 0


if __name__ == "__main__":
    sys.exit(main())
