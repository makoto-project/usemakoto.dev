"""Verify Makoto DBOM records."""

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

SCHEMA_URL = "https://usemakoto.dev/schema/v0.1.json"

# Bundled schema path (fallback when offline)
_BUNDLED_SCHEMA = Path(__file__).parent / "schema" / "v0.1.json"


@dataclass
class VerifyResult:
    valid: bool
    errors: List[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.valid


def _load_schema() -> Dict[str, Any]:
    """Load schema from URL with fallback to bundled copy."""
    try:
        import requests

        resp = requests.get(SCHEMA_URL, timeout=5)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        pass

    if _BUNDLED_SCHEMA.exists():
        with open(_BUNDLED_SCHEMA) as f:
            return json.load(f)

    raise RuntimeError(
        f"Could not fetch schema from {SCHEMA_URL} and no bundled fallback found."
    )


def verify(
    dbom_path_or_dict: Union[str, Dict[str, Any]],
    file_path: Optional[str] = None,
) -> VerifyResult:
    """Verify a DBOM against the Makoto schema and optionally a source file.

    Args:
        dbom_path_or_dict: Path to a DBOM JSON file, or a DBOM dict.
        file_path: Optional path to the source data file to verify the hash.

    Returns:
        VerifyResult with valid flag and list of human-readable error strings.
    """
    errors: List[str] = []

    # Load DBOM
    if isinstance(dbom_path_or_dict, (str, os.PathLike)):
        try:
            with open(dbom_path_or_dict) as f:
                dbom = json.load(f)
        except Exception as e:
            return VerifyResult(valid=False, errors=[f"Failed to read DBOM file: {e}"])
    else:
        dbom = dbom_path_or_dict

    # Load and validate against schema
    try:
        import jsonschema

        schema = _load_schema()
        validator = jsonschema.Draft202012Validator(schema)
        schema_errors = list(validator.iter_errors(dbom))
        for err in schema_errors:
            path = " → ".join(str(p) for p in err.absolute_path) or "root"
            errors.append(f"Schema error at {path}: {err.message}")
    except ImportError:
        errors.append("jsonschema library not installed; schema validation skipped.")
    except Exception as e:
        errors.append(f"Schema validation failed: {e}")

    # File hash verification
    if file_path is not None:
        try:
            sha = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    sha.update(chunk)
            actual_hash = sha.hexdigest()
            expected_hash = dbom.get("source", {}).get("hash", {}).get("value", "")
            if actual_hash != expected_hash:
                errors.append(
                    f"File hash mismatch: expected {expected_hash}, got {actual_hash}"
                )
        except Exception as e:
            errors.append(f"Failed to hash file: {e}")

    return VerifyResult(valid=len(errors) == 0, errors=errors)
