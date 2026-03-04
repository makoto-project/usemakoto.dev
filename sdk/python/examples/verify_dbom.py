#!/usr/bin/env python3
"""Example: verify a DBOM against the schema and source file."""

import json
import sys
import tempfile
from pathlib import Path

# Allow running from examples/ without install
sys.path.insert(0, str(Path(__file__).parent.parent))

from makoto import generate, verify

# Create a sample CSV + DBOM
csv_content = "id,name,value\n1,Alice,100\n2,Bob,200\n3,Carol,300\n"

with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False) as f:
    f.write(csv_content)
    tmp_path = f.name

dbom = generate(file_path=tmp_path, signer="github:example-user", format="csv")
dbom_path = tmp_path + ".dbom.json"
with open(dbom_path, "w") as f:
    json.dump(dbom, f, indent=2)

print(f"Generated DBOM: {dbom_path}")
print(f"Source file:    {tmp_path}\n")

# --- Verify: valid case ---
result = verify(dbom_path, file_path=tmp_path)
if result.valid:
    print("✓ DBOM is valid — schema and file hash both pass")
else:
    print("✗ Validation failed:")
    for err in result.errors:
        print(f"  - {err}")

# --- Verify: tampered file ---
print("\nSimulating tampered file...")
with open(tmp_path, "a") as f:
    f.write("4,Dave,999\n")

result2 = verify(dbom_path, file_path=tmp_path)
if result2.valid:
    print("✓ Valid (unexpected)")
else:
    print("✗ Detected tampering:")
    for err in result2.errors:
        print(f"  - {err}")
