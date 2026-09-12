import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from import_capture import import_capture

ROOT = Path(__file__).resolve().parent


class ImportCaptureTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.database = self.root / "journal.sqlite3"

        with sqlite3.connect(self.database) as db:
            db.executescript((ROOT / "schema.sql").read_text())

    def capture(self, name, amount=1000, conflict=False, unknown=False):
        run = self.root / name
        run.mkdir(exist_ok=True)

        request = {
            "idempotency_key": "synthetic-operation-001",
            "reference_id": "offline-test-001",
            "amount_money": {"amount": amount, "currency": "USD"},
        }

        metadata = {
            "http_status": None if unknown else (400 if conflict else 200),
            "outcome": "unknown" if unknown else "http_response_received",
        }

        if conflict:
            response = {
                "errors": [{
                    "code": "IDEMPOTENCY_KEY_REUSED",
                    "category": "INVALID_REQUEST_ERROR",
                }]
            }
        else:
            response = {
                "payment": {
                    "id": "synthetic-payment-001",
                    "status": "COMPLETED",
                }
            }

        for filename, contents in (
            ("request.json", request),
            ("metadata.json", metadata),
            ("response.json", response),
        ):
            (run / filename).write_text(json.dumps(contents))

        return run

    def counts(self):
        with sqlite3.connect(self.database) as db:
            operations = db.execute(
                "SELECT COUNT(*) FROM operations"
            ).fetchone()[0]
            attempts = db.execute(
                "SELECT COUNT(*) FROM attempts"
            ).fetchone()[0]
        return operations, attempts

    def test_reimport_does_not_duplicate_evidence(self):
        run = self.capture("first")

        self.assertTrue(import_capture(run, self.database))
        self.assertFalse(import_capture(run, self.database))
        self.assertEqual(self.counts(), (1, 1))

    def test_changed_capture_is_rejected(self):
        run = self.capture("first")
        import_capture(run, self.database)

        self.capture("first", amount=1100)
        with self.assertRaisesRegex(ValueError, "contents differ"):
            import_capture(run, self.database)

        with sqlite3.connect(self.database) as db:
            saved = db.execute(
                "SELECT request_json FROM attempts"
            ).fetchone()[0]
        self.assertEqual(json.loads(saved)["amount_money"]["amount"], 1000)
        self.assertEqual(self.counts(), (1, 1))

    def test_conflict_is_an_attempt_not_another_operation(self):
        import_capture(self.capture("first"), self.database)
        conflict = self.capture("conflict", amount=1100, conflict=True)
        import_capture(conflict, self.database)

        self.assertEqual(self.counts(), (1, 2))
        with sqlite3.connect(self.database) as db:
            error = db.execute(
                "SELECT http_status, error_code, payment_id "
                "FROM attempts WHERE evidence_name = ?",
                ("send-conflict",),
            ).fetchone()
        self.assertEqual(error, (400, "IDEMPOTENCY_KEY_REUSED", None))

    def test_unknown_outcome_is_not_imported_as_success(self):
        run = self.capture("interrupted", unknown=True)

        with self.assertRaisesRegex(ValueError, "No complete HTTP response"):
            import_capture(run, self.database)

        self.assertEqual(self.counts(), (0, 0))

    def test_conflict_alone_cannot_establish_original_operation(self):
        run = self.capture("conflict", amount=1100, conflict=True)

        with self.assertRaisesRegex(ValueError, "original successful request"):
            import_capture(run, self.database)

        self.assertEqual(self.counts(), (0, 0))


if __name__ == "__main__":
    unittest.main()
