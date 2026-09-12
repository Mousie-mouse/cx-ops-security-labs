CREATE TABLE IF NOT EXISTS operations (
    idempotency_key TEXT PRIMARY KEY,
    reference_id TEXT NOT NULL,
    original_request_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS attempts (
    attempt_id INTEGER PRIMARY KEY,
    evidence_name TEXT NOT NULL UNIQUE,
    idempotency_key TEXT NOT NULL,
    request_json TEXT NOT NULL,
    http_status INTEGER NOT NULL,
    payment_id TEXT,
    payment_status TEXT,
    error_code TEXT,
    response_json TEXT NOT NULL,
    imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (idempotency_key)
        REFERENCES operations(idempotency_key)
);
