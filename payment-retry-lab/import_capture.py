import argparse
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def import_capture(run, database):
    run = Path(run).resolve()
    request = json.loads((run / "request.json").read_text())
    metadata = json.loads((run / "metadata.json").read_text())

    if metadata.get("outcome") != "http_response_received":
        raise ValueError("No complete HTTP response; retain as unresolved evidence.")

    response = json.loads((run / "response.json").read_text())
    payment = response.get("payment", {})
    errors = response.get("errors", [])

    values = (
        f"send-{run.name}",
        request["idempotency_key"],
        json.dumps(request, sort_keys=True),
        metadata["http_status"],
        payment.get("id"),
        payment.get("status"),
        errors[0]["code"] if errors else None,
        json.dumps(response, sort_keys=True),
    )

    with sqlite3.connect(database) as db:
        db.execute("PRAGMA foreign_keys = ON")

        existing = db.execute(
            """
            SELECT evidence_name, idempotency_key, request_json,
                   http_status, payment_id, payment_status,
                   error_code, response_json
            FROM attempts WHERE evidence_name = ?
            """,
            (values[0],),
        ).fetchone()

        if existing is not None:
            if existing != values:
                raise ValueError("Capture contents differ from the imported record.")
            return False

        operation = db.execute(
            "SELECT reference_id FROM operations WHERE idempotency_key = ?",
            (request["idempotency_key"],),
        ).fetchone()

        if operation is None:
            if not payment.get("id") or not 200 <= metadata["http_status"] < 300:
                raise ValueError(
                    "Import the original successful request first "
                    "to establish this operation."
                )
            db.execute(
                """
                INSERT INTO operations
                    (idempotency_key, reference_id, original_request_json)
                VALUES (?, ?, ?)
                """,
                (
                    request["idempotency_key"],
                    request["reference_id"],
                    json.dumps(request, sort_keys=True),
                ),
            )

        db.execute(
            """
            INSERT INTO attempts (
                evidence_name, idempotency_key, request_json,
                http_status, payment_id, payment_status,
                error_code, response_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            values,
        )

    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import a send_payment capture.")
    parser.add_argument("run_directory", type=Path)
    args = parser.parse_args()

    try:
        added = import_capture(
            args.run_directory, ROOT / "data" / "journal.sqlite3"
        )
    except (ValueError, KeyError, OSError, sqlite3.Error) as error:
        raise SystemExit(f"Import stopped: {error}")

    print("Attempt imported." if added else "Unchanged capture already imported.")
