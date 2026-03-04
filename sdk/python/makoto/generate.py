"""Generate Makoto DBOM (Data Bill of Materials) records."""

import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Dict, Any


def generate(
    file_path: str,
    signer: str,
    uri: Optional[str] = None,
    lineage_steps: Optional[List[Dict[str, Any]]] = None,
    format: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate a DBOM for a file.

    Args:
        file_path: Path to the data file to hash.
        signer: Identity of the signer (e.g. "github:username").
        uri: Optional URI for the source location. Defaults to file path.
        lineage_steps: Optional list of lineage step dicts. Auto-generated if omitted.
        format: Data format string (e.g. "csv", "json"). Inferred from extension if omitted.

    Returns:
        DBOM dict conforming to https://usemakoto.dev/schema/v0.1.json
    """
    path = Path(file_path)

    # Compute file hash
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha.update(chunk)
    file_hash = sha.hexdigest()

    # Infer format from extension if not provided
    if format is None:
        ext = path.suffix.lstrip(".")
        format = ext if ext else "unknown"

    # URI defaults to file path
    source_uri = uri if uri is not None else path.as_uri()

    # Signature: sha256(file_hash + signer)
    sig_input = (file_hash + signer).encode("utf-8")
    sig_value = hashlib.sha256(sig_input).hexdigest()

    # Auto-generate lineage if not provided
    if lineage_steps is None:
        lineage_steps = [
            {
                "step": 1,
                "description": "Direct ingestion",
                "tool": "makoto-python/0.1.0",
                "input_hash": "n/a",
                "output_hash": file_hash,
            }
        ]

    dbom = {
        "schema_version": "0.1",
        "id": "dbom-" + str(uuid.uuid4()),
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": {
            "uri": source_uri,
            "hash": {
                "algorithm": "sha256",
                "value": file_hash,
            },
            "format": format,
        },
        "signature": {
            "algorithm": "sha256",
            "value": sig_value,
            "signer": signer,
        },
        "lineage": lineage_steps,
    }

    return dbom
