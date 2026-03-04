# Makoto Python SDK

Generate and verify [Makoto DBOM](https://usemakoto.dev) (Data Bill of Materials) files in Python.

## Install

```bash
uv add makoto
# or
pip install makoto
```

## Quick Start

### Generate a DBOM

```python
from makoto import generate
import json

dbom = generate(
    file_path="data/sales.csv",
    signer="github:your-username",
    uri="s3://my-bucket/sales.csv",    # optional
    format="csv",                       # optional, inferred from extension
)

print(json.dumps(dbom, indent=2))
```

### Verify a DBOM

```python
from makoto import verify

result = verify("sales.csv.dbom.json", file_path="data/sales.csv")

if result.valid:
    print("✓ DBOM is valid")
else:
    for err in result.errors:
        print(f"✗ {err}")
```

## Schema

DBOMs are validated against `https://usemakoto.dev/schema/v0.1.json`.
A bundled copy is included for offline use.

## API

### `generate(file_path, signer, uri=None, lineage_steps=None, format=None) → dict`

| Param | Type | Description |
|-------|------|-------------|
| `file_path` | str | Path to the source data file |
| `signer` | str | Signer identity (e.g. `github:username`) |
| `uri` | str | Source URI (defaults to `file://` path) |
| `lineage_steps` | list | Custom lineage. Auto-generated if omitted |
| `format` | str | Data format. Inferred from extension if omitted |

### `verify(dbom_path_or_dict, file_path=None) → VerifyResult`

| Param | Type | Description |
|-------|------|-------------|
| `dbom_path_or_dict` | str or dict | Path to DBOM JSON file, or a DBOM dict |
| `file_path` | str | Optional data file to verify hash against |

`VerifyResult.valid` — bool  
`VerifyResult.errors` — list of error strings

## Examples

See [`examples/`](examples/) for runnable scripts.
