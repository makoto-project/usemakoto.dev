#!/usr/bin/env python3
"""Example: generate a DBOM for a temporary CSV file."""

import json
import sys
import tempfile
from pathlib import Path

# Allow running from examples/ without install
sys.path.insert(0, str(Path(__file__).parent.parent))

from makoto import generate

# Create a sample CSV file
csv_content = "id,name,value\n1,Alice,100\n2,Bob,200\n3,Carol,300\n"

with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False) as f:
    f.write(csv_content)
    tmp_path = f.name

print(f"Created sample file: {tmp_path}\n")

# Generate DBOM
dbom = generate(
    file_path=tmp_path,
    signer="github:example-user",
    uri=f"s3://my-data-bucket/example.csv",
    format="csv",
)

print("Generated DBOM:")
print(json.dumps(dbom, indent=2))

# Optionally save it
dbom_path = tmp_path + ".dbom.json"
with open(dbom_path, "w") as f:
    json.dump(dbom, f, indent=2)

print(f"\nSaved DBOM to: {dbom_path}")
print("\nRun examples/verify_dbom.py to verify it.")
