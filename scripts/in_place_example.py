"""Generate every digest and statement on /examples/in-place/ from real SQLite runs.

The walkthrough edits one table in place. After each SQL command the table's
state is exported by ``examples/in-place/sql/export.sql`` and those export bytes
are what each statement attests. The database file is never hashed: SQLite page
layout, free lists and journal state make its bytes vary between runs that hold
identical rows.

Attested bytes, exactly: the single value ``export.sql`` returns (a JSON array
of rows ordered by ``customer_id``, keys in alphabetical order, no whitespace)
followed by one LF. That is what ``sqlite3 customers.db < export.sql`` prints,
so a reader can reproduce each digest with the sqlite3 shell and ``shasum``.

Run with no arguments to rewrite the generated files, or ``--check`` to fail
when any committed file differs from a fresh run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/in-place"
SQL = EXAMPLE / "sql"
SCHEMAS = ROOT / "schema/v0.2"
SUBJECT_NAME = "customers.db#customers"
EVENT_NAMESPACE = uuid.UUID("6f1d3c2e-8b4a-4c55-9e0f-2a7b1d4c6e90")

# The table definition runs first and changes no rows; it is not a state of the data.
CREATE = "00-create.sql"
# (state file, statement file, command file, event time, operation or None for the origin)
STEPS = (
    ("state-1.json", "state-1-origin.json", "01-load.sql", "2026-09-16T16:00:00Z", None),
    (
        "state-2.json",
        "state-2-normalize.json",
        "02-normalize.sql",
        "2026-09-16T16:05:00Z",
        ("urn:makoto:example:operation:normalize", "Normalize email, consent and region in place"),
    ),
    (
        "state-3.json",
        "state-3-withdraw-minor-consent.json",
        "03-withdraw-minor-consent.sql",
        "2026-09-16T16:10:00Z",
        ("urn:makoto:example:operation:withdraw-minor-consent", "Withdraw consent held by minors"),
    ),
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def statement_digest(statement: dict[str, Any]) -> str:
    """Canonical form: keys sorted, no insignificant whitespace (as on /examples/lifecycle/)."""
    return sha256(json.dumps(statement, sort_keys=True, separators=(",", ":")).encode())


def export_bytes(db: sqlite3.Connection) -> bytes:
    (value,) = db.execute((SQL / "export.sql").read_text(encoding="utf-8")).fetchone()
    data = value.encode("utf-8") + b"\n"
    # Cross-check the SQL export against an independent serialisation of the same rows.
    db.row_factory = sqlite3.Row
    rows = [dict(row) for row in db.execute("SELECT * FROM customers ORDER BY customer_id")]
    db.row_factory = None
    independent = json.dumps(rows, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    if data != independent.encode("utf-8") + b"\n":
        raise SystemExit("export.sql output is not the canonical serialisation of the table")
    return data


def extension(command: str, rows_changed: int | None) -> dict[str, Any]:
    body: dict[str, Any] = {
        "database": "customers.db",
        "table": "customers",
        "tableDefinition": f"sql/{CREATE}",
        "command": f"sql/{command}",
        "export": "sql/export.sql",
        "exportDigest": {"sha256": sha256((SQL / "export.sql").read_bytes())},
        "storageKeepsPreviousState": False,
    }
    if rows_changed is not None:
        body["rowsChanged"] = rows_changed
    return {"urn:makoto:example:in-place-table": body}


def build() -> dict[Path, bytes]:
    outputs: dict[Path, bytes] = {}
    previous: tuple[str, str] | None = None  # (subject digest, statement digest)
    with tempfile.TemporaryDirectory() as scratch:
        db = sqlite3.connect(Path(scratch) / "customers.db", isolation_level=None)
        try:
            db.executescript((SQL / CREATE).read_text(encoding="utf-8"))
            for state_file, statement_file, command, occurred, operation in STEPS:
                before = db.total_changes
                db.executescript((SQL / command).read_text(encoding="utf-8"))
                changed = db.total_changes - before
                state = export_bytes(db)
                digest = sha256(state)
                event = {
                    "id": f"urn:uuid:{uuid.uuid5(EVENT_NAMESPACE, statement_file)}",
                    "occurredAt": occurred,
                }
                subject = [{"name": SUBJECT_NAME, "digest": {"sha256": digest}}]
                predicate: dict[str, Any]
                if operation is None:
                    predicate_type = "https://usemakoto.dev/predicate/v0.2/origin"
                    predicate = {
                        "schemaVersion": "0.2",
                        "event": event,
                        "source": {
                            "kind": "urn:makoto:example:source:sqlite-table",
                            "name": "customers table, initial load",
                            "mediaType": "application/json",
                            "retrievedAt": occurred,
                        },
                        "profiles": [],
                        "extensions": extension(command, None),
                    }
                else:
                    assert previous is not None
                    predicate_type = "https://usemakoto.dev/predicate/v0.2/transform"
                    predicate = {
                        "schemaVersion": "0.2",
                        "event": event,
                        "operation": {
                            "type": operation[0],
                            "name": operation[1],
                            "tool": {"name": "SQLite"},
                            "parametersDigest": {"sha256": sha256((SQL / command).read_bytes())},
                        },
                        "profiles": [],
                        "extensions": extension(command, changed),
                        "inputs": [
                            {
                                "name": "previous-state",
                                "digest": {"sha256": previous[0]},
                                "provenance": {
                                    "statementDigest": {"sha256": previous[1]},
                                    "subjectName": SUBJECT_NAME,
                                },
                            }
                        ],
                    }
                statement = {
                    "_type": "https://in-toto.io/Statement/v1",
                    "subject": subject,
                    "predicateType": predicate_type,
                    "predicate": predicate,
                }
                outputs[EXAMPLE / "states" / state_file] = state
                outputs[EXAMPLE / "attestations" / statement_file] = (
                    json.dumps(statement, indent=2, ensure_ascii=False) + "\n"
                ).encode("utf-8")
                previous = (digest, statement_digest(statement))
        finally:
            db.close()
    return outputs


def validate(outputs: dict[Path, bytes]) -> None:
    resources = []
    for path in sorted(SCHEMAS.glob("*.schema.json")):
        schema = json.loads(path.read_text(encoding="utf-8"))
        resources.append((schema["$id"], Resource.from_contents(schema)))
    registry = Registry().with_resources(resources)
    statement_schema = json.loads((SCHEMAS / "statement.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(statement_schema, registry=registry)
    for path, data in outputs.items():
        if path.parent.name != "attestations":
            continue
        errors = list(validator.iter_errors(json.loads(data)))
        if errors:
            raise SystemExit(
                f"{path.relative_to(ROOT)} violates statement.schema.json: {errors[0]}"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail on drift instead of writing")
    args = parser.parse_args()
    outputs = build()
    validate(outputs)
    drift = [
        path.relative_to(ROOT).as_posix()
        for path, data in outputs.items()
        if not path.is_file() or path.read_bytes() != data
    ]
    if args.check:
        if drift:
            print(
                "in-place example is stale; run uv run scripts/in_place_example.py", file=sys.stderr
            )
            for name in drift:
                print(f"  {name}", file=sys.stderr)
            return 1
    else:
        for path, data in outputs.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    for path, data in outputs.items():
        if path.parent.name == "states":
            print(f"state      {sha256(data)}  {path.relative_to(ROOT)}")
        else:
            print(f"statement  {statement_digest(json.loads(data))}  {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
