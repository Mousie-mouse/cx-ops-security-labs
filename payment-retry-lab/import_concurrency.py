import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

if len(sys.argv) != 2:
    raise SystemExit("Usage: python import_concurrency.py RUN_DIRECTORY")

run = Path(sys.argv[1]).resolve()
request = json.loads((run / "request.json").read_text())

with sqlite3.connect(ROOT / "data" / "journal.sqlite3") as db:
    db.execute("PRAGMA foreign_keys = ON")

    db.execute(
        """
        INSERT INTO operations
            (idempotency_key, reference_id, original_request_json)
        VALUES (?, ?, ?)
        ON CONFLICT(idempotency_key) DO NOTHING
        """,
        (
            request["idempotency_key"],
            request["reference_id"],
            json.dumps(request, sort_keys=True),
        ),
    )

    for number in (1, 2):
        response = json.loads(
            (run / f"attempt-{number}.json").read_text()
        )
        metadata = json.loads(
            (run / f"attempt-{number}-meta.json").read_text()
        )
        payment = response.get("payment", {})
        errors = response.get("errors", [])

        db.execute(
            """
            INSERT INTO attempts (
                evidence_name, idempotency_key, request_json,
                http_status, payment_id, payment_status,
                error_code, response_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(evidence_name) DO NOTHING
            """,
            (
                f"concurrent-{run.name}-{number}",
                request["idempotency_key"],
                json.dumps(request, sort_keys=True),
                metadata["http_status"],
                payment.get("id"),
                payment.get("status"),
                errors[0]["code"] if errors else None,
                json.dumps(response, sort_keys=True),
            ),
        )

print("Concurrent response evidence imported.")

with sqlite3.connect(ROOT / "data" / "journal.sqlite3") as db:
    for row in db.execute("""
        SELECT o.reference_id,
               COUNT(a.attempt_id),
               COUNT(DISTINCT a.payment_id)
        FROM operations AS o
        LEFT JOIN attempts AS a
            ON a.idempotency_key = o.idempotency_key
        GROUP BY o.idempotency_key, o.reference_id
        ORDER BY o.reference_id
    """):
        print(row)
