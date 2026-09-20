import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path
from postman_evidence import save_and_import


ROOT = Path(__file__).resolve().parent
COLLECTION = ROOT / "postman" / "payment-retry.postman_collection.json"
REQUEST = ROOT / "data" / "payment-request.json"
BASE = "https://connect.squareupsandbox.com/v2/payments"

parser = argparse.ArgumentParser(
    description="Prepare or run the payment retry Postman collection."
)
parser.add_argument("--run", action="store_true",
                    help="Send requests to Square Sandbox.")
args = parser.parse_args()


def test_event(source):
    return {
        "listen": "test",
        "script": {
            "type": "text/javascript",
            "exec": source.strip().splitlines(),
        },
    }


def item(name, method, url, tests, body=None):
    request = {
        "method": method,
        "header": [
            {"key": "Square-Version", "value": "2026-08-19"},
            {"key": "Content-Type", "value": "application/json"},
        ],
        "url": url,
    }
    if body is not None:
        request["body"] = {
            "mode": "raw",
            "raw": body,
            "options": {"raw": {"language": "json"}},
        }
    return {
        "name": name,
        "request": request,
        "event": [test_event(tests)],
    }


payment_checks = """
pm.test("HTTP 200", () => pm.response.to.have.status(200));
const payment = pm.response.json().payment;
const expected = JSON.parse(pm.environment.get("saved_request"));

pm.test("Payment is COMPLETED", () => {
    pm.expect(payment.status).to.eql("COMPLETED");
});
pm.test("Amount and currency match the saved request", () => {
    pm.expect(payment.amount_money).to.deep.eql(expected.amount_money);
});
pm.test("Location and reference match the saved request", () => {
    pm.expect(payment.location_id).to.eql(expected.location_id);
    pm.expect(payment.reference_id).to.eql(expected.reference_id);
});
"""

first_checks = payment_checks + """
pm.test("Payment ID is present", () => {
    pm.expect(payment.id).to.be.a("string").and.not.empty;
});
pm.collectionVariables.set("payment_id", payment.id);
"""

same_id_checks = payment_checks + """
pm.test("Same payment ID as the first response", () => {
    pm.expect(payment.id).to.eql(pm.collectionVariables.get("payment_id"));
});
"""

conflict_checks = """
pm.test("HTTP 400", () => pm.response.to.have.status(400));
pm.test("Conflicting amount is rejected", () => {
    const errors = pm.response.json().errors;
    pm.expect(errors).to.be.an("array");
    pm.expect(errors.map(error => error.code))
        .to.include("IDEMPOTENCY_KEY_REUSED");
});
"""

collection = {
    "info": {
        "name": "Payment Retry Investigation",
        "description": (
            "Square Sandbox checks using the Python lab's saved request. "
            "The first request creates or replays that operation. "
            "Captured POST responses are imported into the SQLite journal."
        ),
        "schema": (
            "https://schema.getpostman.com/json/collection/v2.1.0/"
            "collection.json"
        ),
    },
    "auth": {
        "type": "bearer",
        "bearer": [{
            "key": "token",
            "value": "{{square_token}}",
            "type": "string",
        }],
    },
    "variable": [{"key": "payment_id", "value": ""}],
    "item": [
        item("01 | Send saved operation", "POST", BASE,
             first_checks, "{{saved_request}}"),
        item("02 | Identical retry returns the same payment", "POST", BASE,
             same_id_checks, "{{saved_request}}"),
        item("03 | Changed amount is rejected", "POST", BASE,
             conflict_checks, "{{conflict_request}}"),
        item("04 | Retrieve and verify the original payment", "GET",
             BASE + "/{{payment_id}}", same_id_checks),
    ],
}

COLLECTION.parent.mkdir(exist_ok=True)
COLLECTION.write_text(json.dumps(collection, indent=2) + "\n")
print("Collection prepared:", COLLECTION, flush=True)

if not args.run:
    print("No API requests sent. Use --run to execute the collection.")
    raise SystemExit(0)

token = os.environ.get("SQUARE_ACCESS_TOKEN")
if not token:
    parser.error("Load SQUARE_ACCESS_TOKEN in this terminal first.")

try:
    saved_text = REQUEST.read_text()
    saved = json.loads(saved_text)
    if not isinstance(saved, dict):
        raise ValueError("Saved request must be a JSON object.")
    for field in ("idempotency_key", "location_id", "reference_id"):
        if not isinstance(saved.get(field), str) or not saved[field]:
            raise ValueError(f"Saved request needs a nonempty {field}.")
    if saved.get("source_id") != "cnon:card-nonce-ok":
        raise ValueError("Expected the lab's Square Sandbox test source.")
    money = saved["amount_money"]
    if type(money["amount"]) is not int or money["amount"] <= 0:
        raise ValueError("Expected a positive integer amount.")
    if money["currency"] != "USD" or saved.get("autocomplete") is not True:
        raise ValueError("Expected the lab's USD autocomplete request.")
except (OSError, ValueError, KeyError, TypeError) as error:
    parser.error(f"Cannot use saved request: {error}")

conflict = json.loads(saved_text)
conflict["amount_money"]["amount"] += 100

environment = {
    "name": "Temporary payment retry environment",
    "values": [
        {"key": "square_token", "value": token, "enabled": True},
        {"key": "saved_request", "value": saved_text, "enabled": True},
        {"key": "conflict_request",
         "value": json.dumps(conflict), "enabled": True},
    ],
}

print("Running against Square Sandbox.", flush=True)
print("POST responses will be captured and imported into SQLite.", flush=True)

evidence_ok = False

with tempfile.TemporaryDirectory(prefix="payment-postman-") as directory:
    env_path = Path(directory) / "environment.json"
    report_path = Path(directory) / "report.json"

    fd = os.open(env_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as file:
        json.dump(environment, file)

    try:
        result = subprocess.run([
            "postman", "collection", "run", str(COLLECTION),
            "--environment", str(env_path),
            "--reporters", "cli,json",
            "--reporter-json-export", str(report_path),
            "--report-events=false",
            "--timeout-request", "30000",
            "--delay-request", "1500",
            "--bail", "failure",
        ], cwd=ROOT)
    except FileNotFoundError:
        parser.error("The postman executable was not found.")
    except KeyboardInterrupt:
        print(
            "\nRun interrupted. Evidence export may be incomplete; "
            "payment outcome may be unknown.",
            flush=True,
        )
        raise SystemExit(130)

    # Preserve available HTTP evidence even when an assertion failed.
    if report_path.is_file():
        try:
            evidence_ok = save_and_import(report_path, ROOT, token)
        except Exception as error:
            # Avoid printing reporter content that could contain credentials.
            print(
                f"Evidence processing stopped ({type(error).__name__}). "
                "Check data/postman-runs before retrying.",
                flush=True,
            )
    else:
        print(
            "No JSON report was produced. No evidence was imported.",
            flush=True,
        )

raise SystemExit(result.returncode or (0 if evidence_ok else 1))
