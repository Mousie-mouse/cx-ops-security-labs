# Running the Payment Retry Lab

This guide walks you through submitting a simulated payment, retrying it
with the same idempotency key, and checking that both requests return the
same payment ID. You will also verify that changing the amount while
reusing the key is rejected, then retrieve the original payment.

Postman CLI runs the four requests and checks their responses. Python
helpers save the evidence and record the three payment-submission attempts
in SQLite; the retrieval response is saved separately.

All payments are simulated in Square Sandbox. Start with setup below,
or see the [README](README.md) for the explanation and recorded results.

## Before you run

- **Keep this lab in Sandbox.** Use Sandbox credentials and retain the
  `connect.squareupsandbox.com` endpoint. Do not adapt these commands to
  production credentials, endpoints, or real payment sources: production
  payment requests can move real money. 

- **Preserve the saved request when retrying.** Do not delete or regenerate
  `data/payment-request.json` to resolve an error. Its idempotency key
  identifies the original operation. A new key can create a separate
  payment rather than recover the previous result.

- **A missing response does not prove a payment failed.** If a request
  times out or the process is interrupted, investigate the outcome before
  deciding whether to submit a new operation.

- **Keep credentials and raw reports out of shared material.** The full
  Postman JSON report can contain authorization data. The helper processes
  it temporarily and saves selected evidence without request authorization
  headers. Review screenshots, logs, and staged files before publishing;
  `.gitignore` does not sanitize files or remove previously tracked secrets.

- **Retain evidence while investigating.** Deleting `data/` removes the
  local request, captures, and journal. It does not undo payments already
  processed by Square.

- The intention of this lab is to interact with the idempotent function.
  It is not intended for any other purpose. Please do not use this outside of a sandbox environment,
  or with real payments. 

## 1. Prepare your environment

You need:

- Python 3.10 or newer with SQLite support.
- Postman CLI available as `postman`; verified with version `1.59.0`.
- A Square developer application with its Sandbox access token and
  Sandbox location ID.
- A local checkout of this repository.

From the repository root:

```bash
cd payment-retry-lab
python3 --version
postman --version
```

Run all remaining commands from `payment-retry-lab`.

### Optional: a Python virtual environment

The Python scripts use only the standard library. You can run them with
the system's `python3`; no package installation is required.

If you prefer a virtual environment, create and activate one:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

In later terminal sessions, activate the existing environment rather than
creating it again. Postman CLI is installed separately.

### Check the importer offline

```bash
python3 -m unittest -v test_import_capture
```

Expect five passing tests. They use synthetic responses and temporary
databases, make no network requests, and do not modify the local journal.
These tests cover the importer, not the entire Postman integration.

## 2. Initialize the saved operation

In the Square Developer Console, open your lab application and select
Sandbox. Obtain its Sandbox location ID and access token.

Enter the location ID:

```bash
read -rp "Sandbox location ID: " SQUARE_LOCATION_ID
python3 setup_lab.py --location-id "$SQUARE_LOCATION_ID"
```

Setup initializes `data/journal.sqlite3` and creates
`data/payment-request.json` for a simulated $10 payment with reference
`retry-lab-001`.

It sends no API requests. If the request already exists, setup preserves
its idempotency key and parameters. A different supplied location is rejected.

**Keep the saved request:** it identifies the operation you will retry.

## 3. Load the token in each terminal session

```bash
read -rsp "Sandbox access token: " SQUARE_ACCESS_TOKEN
printf '\n'
export SQUARE_ACCESS_TOKEN
```

Paste only the Sandbox access token, without quotes or a `Bearer` prefix.
Input is hidden.

The token is loaded into this shell's environment. These commands do not
save it permanently or put the entered value in shell history. DO NOT
share it, or display it publicly. It is a credential for your Square Account. 

To check whether a value is loaded without displaying it:

```bash
if [[ -n ${SQUARE_ACCESS_TOKEN:-} ]]; then
    echo "Token is loaded."
else
    echo "Token is not loaded."
fi
```

This checks presence, not validity.

## 4. ▶ Run the Postman workflow

To generate the collection without sending requests:

```bash
python3 postman_lab.py
```

To generate it and run the API checks:

```bash
python3 postman_lab.py --run
```

The helper reuses the saved request and key. It changes an in-memory copy
of the amount for the conflict check; it does not change the saved file.

| Request | Expected result for the saved $10 operation |
|---|---|
| Send saved operation | HTTP 200, completed $10 payment |
| Identical retry | HTTP 200, same payment ID |
| Change amount to $11, preserving the key | HTTP 400, `IDEMPOTENCY_KEY_REUSED` |
| Retrieve original payment | HTTP 200, original payment details |

The first request may replay an existing payment rather than create one.

### What a complete successful run looks like

Expect **17 assertions with zero failures**, followed by:

```text
Payment attempts added: 3
Retrieval responses saved separately: 1
Items needing review: 0
```

The HTTP 400 is an expected rejection and counts as a passing check.

Check both summaries. Passing API assertions does not mean evidence was
successfully imported. Conversely, an assertion failure does not
automatically prevent available HTTP evidence from being imported.

The verified local runs worked without signing into Postman. Notices
requesting `postman login` concerned publishing run details to Postman's
cloud; they did not prevent local execution.

## 5. 🔎 Inspect the evidence

The helper prints a unique directory under:

```text
data/postman-runs/
```

Each executed request has a capture subdirectory. Successfully exported
POST captures include:

- `request.json`: submitted payment parameters.
- `response.json`: response body.
- `metadata.json`: method, HTTP status, outcome, and export time.

The GET response is saved separately as supporting evidence and is not
imported as a payment-submission attempt. The run's `summary.json` records
the export and import counts.

### Inspect the latest journaled Postman attempts

This query opens SQLite read-only and prints the most recent three
Postman attempt rows:

```bash
python3 - <<'PY'
import sqlite3

with sqlite3.connect("file:data/journal.sqlite3?mode=ro", uri=True) as db:
    rows = db.execute("""
        SELECT evidence_name,
               json_extract(request_json, '$.amount_money.amount'),
               http_status, payment_id, error_code
        FROM attempts
        WHERE evidence_name LIKE 'send-postman-%'
        ORDER BY attempt_id DESC
        LIMIT 3
    """).fetchall()

for row in reversed(rows):
    print(row)
PY
```

After a complete successful run, expect:

| Amount in cents | HTTP status | Payment ID | Error code |
|---:|---:|---|---|
| 1000 | 200 | Original ID | None |
| 1000 | 200 | Same ID | None |
| 1100 | 400 | None | `IDEMPOTENCY_KEY_REUSED` |

Check the evidence names against the run directory just printed. If the
latest run did not import three attempts, this query can include older rows.

## 6. Understand reruns and reimports

| Action | Sends API requests? | Effect on the journal |
|---|---|---|
| `python3 postman_lab.py` | No | None; generates the collection |
| `python3 postman_lab.py --run` | Yes | Imports new eligible POST attempts |
| Reimport an unchanged saved POST capture | No | Adds no duplicate row |
| Reimport changed contents under an existing evidence name | No | Import is rejected |

To reimport one POST capture, replace the placeholders with actual directory
names printed by the helper:

```bash
python3 import_capture.py data/postman-runs/ACTUAL_RUN/ACTUAL_CAPTURE
```

Import one POST capture at a time: choose the subdirectory containing
that request's `request.json`, `response.json`, and `metadata.json`.
Do not pass the directory containing the whole run. The GET capture only
retrieves an existing payment, so it is not imported as a payment attempt.

Running the collection again sends new requests and adds new attempt
records, even if Square returns the same payment ID. Importing the same
saved capture again sends no requests and adds no duplicate records.

Square's idempotency guarantees are subject to its key-retention policy.
These results demonstrate the retries observed during this lab; they do
not prove that reusing a key will prevent duplicate payments forever.

The journal contains only evidence that was saved and successfully
imported. If an earlier response was not captured, that gap remains:
a screenshot or a later response cannot replace the missing capture.

## 7. Additional experiments

The Postman collection checks sequential retries, a conflicting amount,
and retrieval of the original payment. The Python scripts below let you
explore other parts of the investigation:

- **Send and retry manually:** run each payment request separately and
  inspect its captured response before importing it into SQLite.
- **List payments independently:** query Square's payment list, follow
  every pagination cursor, and count distinct payment IDs for the lab's
  references within the configured location and time window.
- **Send concurrent requests:** use two synchronized client threads to
  submit the same saved operation and compare the returned payment IDs.

These scripts use the same Sandbox token loaded earlier. They are optional
and are not run automatically by the Postman collection.

The final subsection describes the original discarded-response experiment.
It records what was investigated; it is not an automated procedure.

### Send and retry manually

Each capture name must be unused. The example names below work once;
choose new names for later runs.

```bash
python3 send_payment.py data/payment-request.json --capture first
python3 import_capture.py data/send-runs/first

python3 send_payment.py data/payment-request.json --capture retry
python3 import_capture.py data/send-runs/retry
```

Both submissions use the same saved key and parameters. Compare their
payment IDs and statuses.

The importer cannot establish an unknown operation from an unsuccessful
response alone. Import the original successful capture first.

### List payments independently

```bash
python3 list_payments.py
```

The script follows pagination cursors within its configured location and
fixed time window. Inspect those settings before using it for a later run;
a new payment outside that window will not appear.

For a fresh experiment containing only the first operation, expect one
payment for `retry-lab-001` and zero for the other two references only if
the query covers that operation and the listing has caught up.

### Send concurrent requests

```bash
python3 concurrent_retry.py
```

This creates or reuses a separate persisted request for `retry-lab-003`
and sends two copies from synchronized threads.

Use the actual evidence directory printed by the script:

```bash
python3 import_concurrency.py data/concurrent-runs/ACTUAL_RUN_DIRECTORY
python3 list_payments.py
```

The concurrency importer requires two captured HTTP responses.
Transport failures require separate investigation. Client synchronization
does not establish simultaneous execution inside Square.

### Original discarded-response experiment

The original investigation deliberately discarded a successful response
body and recovered payment details by retrying. Its manually prepared
captures are not included in Git, and the Postman collection does not
automate that experiment.

## 8. Troubleshooting

| Symptom | Meaning and next step |
|---|---|
| `postman: command not found` | Postman CLI is missing from PATH; resolve this before running the helper |
| Missing `SQUARE_ACCESS_TOKEN` | Load the token in the same terminal used to run the helper |
| Square returns HTTP 401 | Verify the Sandbox token, application, and token entry; this is separate from Postman login |
| HTTP 400 on the changed-amount request, with passing assertions | Expected conflict rejection |
| API assertions pass but no attempts are added | Evidence export/import failed; inspect the import summary and capture files |
| `Items needing review` is nonzero | Some evidence was not processed successfully; imports may be partial |
| A Python sender capture name already exists | Choose an unused name for a new submission; retain earlier evidence |
| Changed capture is rejected on reimport | The stored fields differ from the previously imported evidence |
| Run interrupted or response unavailable | The payment outcome may be unknown; retain available evidence and investigate before retrying |

The current assertion scripts can produce additional missing-payment
errors after a response such as HTTP 401. Start with the original HTTP
error rather than treating those follow-on errors as separate payment defects.

## Evidence storage and limitations

Requests, responses, metadata, and SQLite records stay under `data/`,
which is excluded from Git.

Postman captures omit request authorization headers. The full reporter
output and token environment file are temporary and removed on normal
exit. An interruption before export can leave missing evidence.

`import_capture.py` rejects changes to the parsed fields it previously
stored. The legacy `import_evidence.py` and `import_concurrency.py`
importers skip existing evidence names without comparing contents.

The journal records captured and imported attempts. It is not a complete
record of every request ever sent, and it should not be treated as one.
