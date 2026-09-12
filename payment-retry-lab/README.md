# Payment Retry Investigation Lab

A hands-on REST API investigation using Square Sandbox, Python, and SQLite.
All payments are simulated.

## Verified results

| Attempt | HTTP status | Result |
|---|---|---|
| Initial $10 payment | 200 | COMPLETED |
| Same key and identical parameters | 200 | Same payment ID |
| Same key with amount changed to $11 | 400 | IDEMPOTENCY_KEY_REUSED |

The SQLite journal contains one intended operation and three request attempts.
The saved responses contain one distinct payment ID.

Reimporting the same named evidence files leaves the attempt count unchanged.

## Investigation findings

An HTTP attempt is not the same thing as a payment.
Multiple attempts can refer to one payment operation.

A retry preserves the original idempotency key and request parameters.
Changing the parameters while reusing the key produces a conflict.
Automatically replacing the key after an error could create another payment.

## Current files

- schema.sql: operation and attempt tables.
- import_evidence.py: imports the first, retry, and conflict evidence files.
- data/: local request files, response files, and SQLite database; excluded from Git.

The importer uses Python's standard library and parameterized SQL.
It expects an initialized database and the locally captured evidence files.
It is currently an evidence importer, not an automated API client.

## Scope and limitations

Square provides payment-side idempotency. This project investigates that
behavior and records evidence locally.

The observed payment ID count comes from saved responses, not an independent
query of Square's complete payment list.

Evidence names identify fixed captures. Reimporting an existing name skips it;
the importer does not currently detect changed contents under that name.

## Next steps

- Add reproducible request generation and an automated Python client.
- Simulate a lost response and recover using the persisted request.
- Test concurrent requests.
- Retrieve paginated payment records and compare with the local journal.
