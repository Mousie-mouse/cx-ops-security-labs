import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from import_capture import import_capture


def response_bytes(response):
    """Decode supported Postman JSON reporter response formats."""
    stream = response.get("stream")
    if isinstance(stream, dict) and stream.get("type") == "Buffer":
        return bytes(stream["data"])
    if isinstance(stream, str):
        return stream.encode("utf-8")
    if isinstance(response.get("body"), str):
        return response["body"].encode("utf-8")
    raise ValueError("Response body missing or unsupported report format.")


def save_and_import(report_path, root, token):
    root = Path(root)
    database = root / "data" / "journal.sqlite3"
    report = json.loads(Path(report_path).read_text())
    executions = report["run"]["executions"]

    if not executions:
        raise ValueError("Report contains no executed requests.")

    run_id = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        + "-" + uuid.uuid4().hex
    )
    output = root / "data" / "postman-runs" / run_id
    output.mkdir(parents=True, exist_ok=False)

    def write(path, content):
        raw = content if isinstance(content, bytes) else content.encode("utf-8")
        # Refuse to persist the active credential, even if reflected in a body.
        if token and token.encode("utf-8") in raw:
            raise ValueError("Credential found in evidence; file not saved.")
        path.write_bytes(raw)

    def write_json(path, value):
        write(path, json.dumps(value, indent=2) + "\n")

    captures = []
    pending = 0
    retrievals = 0

    # Save all available evidence before attempting database imports.
    for number, execution in enumerate(executions, 1):
        capture = output / f"postman-{run_id}-{number:02d}"
        capture.mkdir()

        request = execution.get("requestExecuted")
        if request is None:
            request = execution.get("request")
        if not isinstance(request, dict):
            raise ValueError("Report request is missing or not an object.")
        response = execution.get("response") or {}
        method = request.get("method")
        status = response.get("code")
        metadata = {
            "source": "postman",
            "method": method,
            "http_status": status,
            "outcome": "unknown",
            "exported_at": datetime.now(timezone.utc).isoformat(),
        }
        write_json(capture / "metadata.json", metadata)

        try:
            # Only body data is retained: never headers or auth configuration.
            if method == "POST":
                raw_request = (request.get("body") or {}).get("raw")
                if not isinstance(raw_request, str):
                    raise ValueError("POST request body missing from report.")
                write(capture / "request.txt", raw_request)
                payment_request = json.loads(raw_request)
                if not isinstance(payment_request, dict):
                    raise ValueError("POST body is not a JSON object.")
                if not payment_request.get("idempotency_key"):
                    raise ValueError("POST body lacks an idempotency key.")
                write_json(capture / "request.json", payment_request)
            elif method == "GET":
                # Retrieval evidence is not passed to the payment importer.
                write_json(capture / "request.json", {"method": "GET"})
            else:
                raise ValueError("Unexpected request method.")

            if execution.get("requestError"):
                raise ValueError("Transport error; outcome remains unknown.")
            if type(status) is not int or not 100 <= status <= 599:
                raise ValueError("No valid HTTP status in report.")

            raw_response = response_bytes(response)
            write(capture / "response.json", raw_response)
            metadata["outcome"] = "http_response_received"
            write_json(capture / "metadata.json", metadata)

            # Preserve non-JSON responses, but do not send them to the importer.
            decoded = json.loads(raw_response)
            if not isinstance(decoded, dict):
                raise ValueError("Response is not a JSON object.")

            if method == "POST":
                captures.append(capture)
            else:
                retrievals += 1

        except (ValueError, KeyError, TypeError, OverflowError) as error:
            pending += 1
            print(
                f"Evidence needs review: {capture.name} "
                f"({type(error).__name__})",
                flush=True,
            )

    added = 0
    for capture in captures:
        try:
            if not database.is_file():
                raise ValueError("Initialize the lab database first.")
            if import_capture(capture, database):
                added += 1
        except (ValueError, KeyError, TypeError, OSError, sqlite3.Error):
            pending += 1
            print(f"Import needs review: {capture.name}", flush=True)

    summary = {
        "executions_reported": len(executions),
        "attempts_added": added,
        "retrievals_saved": retrievals,
        "items_needing_review": pending,
    }
    write_json(output / "summary.json", summary)

    print("Evidence saved to:", output, flush=True)
    print("Payment attempts added:", added, flush=True)
    print("Retrieval responses saved separately:", retrievals, flush=True)
    print("Items needing review:", pending, flush=True)
    return pending == 0
