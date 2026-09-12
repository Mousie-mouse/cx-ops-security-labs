# Payment Retry Investigation Lab

A REST API troubleshooting lab using Square Sandbox, Python, and SQLite.
All payments are simulated. I used ChatGPT for the Python and SQLite, this was a project I took on simply because I wanted to understand idempotent REST APIs better structurally. 
For setup, offline tests, and sandbox commands, see the [runbook](RUNBOOK.md).

## Observed results

| Scenario | Result |
|---|---|
| Initial $10 payment | HTTP 200, COMPLETED |
| Identical sequential retry | HTTP 200, same payment ID |
| Same key, amount changed to $11 | HTTP 400, IDEMPOTENCY_KEY_REUSED |
| Response body deliberately discarded, then request retried | Completed payment details recovered |
| Two concurrent client requests with the same key and parameters | Both HTTP 200, same completed payment ID |

An independent paginated listing returned one distinct payment for each
reference: retry-lab-001, retry-lab-002, and retry-lab-003.

## SQLite evidence

| Operation reference | Recorded attempts | Distinct payment IDs observed |
|---|---:|---:|
| retry-lab-001 | 4 | 1 |
| retry-lab-002 | 1 | 1 |
| retry-lab-003 | 2 | 1 |

The fourth attempt for retry-lab-001 is the later replay through the reusable Python sender.
The deliberately discarded response is not included in the journal.
Reimporting the same named evidence does not create duplicate rows.

## Files

- setup_lab.py: initializes the database and preserves or creates the initial request.
- send_payment.py: sends a saved sandbox request and captures the response.
- import_capture.py: imports sender captures and rejects changed reimports.
- test_import_capture.py: five offline tests using temporary databases.
- RUNBOOK.md: fresh-clone setup and execution instructions.
- schema.sql: operation and request-attempt tables.
- import_evidence.py: imports the sequential, conflict, and recovery captures.
- list_payments.py: follows pagination cursors and counts distinct payment IDs
  for the lab references within a fixed location and time window.
- concurrent_retry.py: sends a persisted request from two synchronized threads.
- import_concurrency.py: imports both HTTP responses from a selected run.
- data/: local requests, responses, listing runs, and database; excluded from Git.

Python scripts use the standard library. API scripts read
SQUARE_ACCESS_TOKEN from the environment.

## Support investigation findings

A request attempt is not a payment. Multiple attempts can identify one
payment operation.

Persist the idempotency key and request parameters before sending a payment.
Retry that operation with the same key and parameters if its outcome is unknown.

A parameter conflict requires investigation. Automatically substituting a new
key can create another payment rather than recover the original one.

Follow every pagination cursor before drawing conclusions from a payment list.
This lab deduplicates listed results by payment ID.

## Scope and limitations

Square implements payment-side idempotency; this lab investigates its behavior.

Discarding a successful response body simulates missing local evidence,
not an actual network timeout.

Synchronized client threads do not prove overlapping execution inside Square.
The concurrency result describes the observed run.

Payment-list findings apply to the saved query's location and time window.
Listings can lag recent changes.

The legacy import_evidence.py and import_concurrency.py importers skip previously
imported evidence names without comparing contents. import_capture.py compares the
parsed fields it stores and rejects changes to an already imported capture.
The concurrency importer requires two captured HTTP responses; it does not
import transport-error-only attempts.

Fresh-clone setup and all five offline importer tests passed. The runbook covers
initial payments, retries, listing, and concurrency. The conflict and discarded-response
experiments used manually prepared captures, which are excluded from Git.

## References

- https://developer.squareup.com/docs/build-basics/common-api-patterns/idempotency
- https://developer.squareup.com/reference/square/payments-api/list-payments
- https://developer.squareup.com/docs/devtools/sandbox/payments
- https://www.freecodecamp.org/news/idempotence-explained
- https://restfulapi.net/idempotent-rest-apis/
