import argparse
import json
import sqlite3
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
REQUEST_PATH = DATA / "payment-request.json"

parser = argparse.ArgumentParser(description="Initialize the payment retry lab.")
parser.add_argument("--location-id", help="Square Sandbox location ID")
args = parser.parse_args()

if REQUEST_PATH.exists():
    payment = json.loads(REQUEST_PATH.read_text())
    if args.location_id and args.location_id != payment["location_id"]:
        parser.error("Location differs from the saved request; nothing changed.")
    created = False
else:
    if not args.location_id or not args.location_id.strip():
        parser.error("A fresh setup requires --location-id YOUR_SANDBOX_LOCATION_ID")

    payment = {
        "idempotency_key": str(uuid.uuid4()),
        "source_id": "cnon:card-nonce-ok",
        "amount_money": {"amount": 1000, "currency": "USD"},
        "location_id": args.location_id.strip(),
        "autocomplete": True,
        "reference_id": "retry-lab-001",
    }
    created = True

DATA.mkdir(exist_ok=True)

with sqlite3.connect(DATA / "journal.sqlite3") as db:
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript((ROOT / "schema.sql").read_text())

if created:
    with REQUEST_PATH.open("x") as file:
        json.dump(payment, file, indent=2)
    print("Created initial request.")
else:
    print("Preserved existing request and idempotency key.")

print("Database schema ready.")
print("Reference:", payment["reference_id"])
print("No API requests were sent.")
