# Running the lab

Requires Python 3.10 or newer with SQLite support.
No third-party Python packages are required.

## Offline verification

From the payment-retry-lab directory:

```bash
python3 -m unittest -v test_import_capture
```

The five tests use synthetic responses and temporary databases.
They make no network requests and do not modify the local evidence journal.

## Square Sandbox setup

Create a Square developer application and select Sandbox.
Obtain its Sandbox access token and location ID.

From the payment-retry-lab directory:

```bash
python3 -m venv .venv
source .venv/bin/activate

read -rp "Sandbox location ID: " SQUARE_LOCATION_ID
python setup_lab.py --location-id "$SQUARE_LOCATION_ID"

read -rsp "Sandbox access token: " SQUARE_ACCESS_TOKEN
printf '\n'
export SQUARE_ACCESS_TOKEN
```

The token remains in the current shell environment.
Do not put it into a request file or commit it.

## First payment and identical retry

Each capture name must be unused.

```bash
python send_payment.py data/payment-request.json --capture first
python import_capture.py data/send-runs/first

python send_payment.py data/payment-request.json --capture retry
python import_capture.py data/send-runs/retry
```

Both requests use the same saved idempotency key and parameters.
Compare their payment IDs and statuses.

The importer intentionally stops if an unknown operation has no successful
payment response. Inspect failed or incomplete captures before proceeding.

## Independent payment listing

```bash
python list_payments.py
```

The script follows all pagination cursors within its fixed query window.
For a fresh run containing only the first operation, expect one payment for
retry-lab-001 and zero for retry-lab-002 and retry-lab-003.

## Concurrent requests

```bash
python concurrent_retry.py
```

This creates or reuses a separate saved request for retry-lab-003.
It sends two copies from synchronized client threads.

Use the evidence directory printed by the script:

```bash
python import_concurrency.py data/concurrent-runs/ACTUAL_RUN_DIRECTORY
python list_payments.py
```

The concurrency importer requires two captured HTTP responses.
Transport failures require separate investigation.

## Evidence and reruns

Requests, responses, metadata, and SQLite records stay under data/.
That directory is excluded from Git.

Setup preserves an existing request's key.
The sender requires a new capture directory for every recorded attempt.
Reimporting an unchanged capture does not duplicate its database row.

Reusing a key is subject to the provider's idempotency retention policy;
these experiments do not establish indefinite duplicate prevention.

The conflict and discarded-response experiments are documented in the README.
Their original captures were prepared manually and are not included in Git.
