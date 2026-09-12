import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"

cases = [
    ("first", "payment-request.json"),
    ("retry", "payment-request.json"),
    ("conflict", "conflict-request.json"),
]

original = json.loads((DATA / "payment-request.json").read_text())

with sqlite3.connect(DATA / "journal.sqlite3") as db:
    db.execute("PRAGMA foreign_keys = ON")

    db.execute(
        """
        INSERT INTO operations
            (idempotency_key, reference_id, original_request_json)
        VALUES (?, ?, ?)
        ON CONFLICT(idempotency_key) DO NOTHING
        """,
        (
            original["idempotency_key"],
            original["reference_id"],
            json.dumps(original, sort_keys=True),
        ),
    )

    for name, request_file in cases:
        request = json.loads((DATA / request_file).read_text())
        response = json.loads(
            (DATA / f"{name}-response.json").read_text()
        )
        headers = (DATA / f"{name}-response.headers").read_text()

        statuses = [
            int(line.split()[1])
            for line in headers.splitlines()
            if line.startswith("HTTP/")
        ]
        if not statuses:
            raise ValueError(f"No HTTP status found for {name}")

        payment = response.get("payment", {})
        errors = response.get("errors", [])
        error_code = errors[0]["code"] if errors else None

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
                name,
                request["idempotency_key"],
                json.dumps(request, sort_keys=True),
                statuses[-1],
                payment.get("id"),
                payment.get("status"),
                error_code,
                json.dumps(response, sort_keys=True),
            ),
        )

print("Import complete; previously imported evidence was left unchanged.")
