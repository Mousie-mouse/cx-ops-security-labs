import json
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DATA = Path(__file__).resolve().parent / "data"
token = os.environ.get("SQUARE_ACCESS_TOKEN")
if not token:
    raise SystemExit("Load SQUARE_ACCESS_TOKEN first.")

request_path = DATA / "concurrent-request.json"

# Preserve the same operation if this script is run again.
if not request_path.exists():
    payment = json.loads((DATA / "payment-request.json").read_text())
    payment["idempotency_key"] = str(uuid.uuid4())
    payment["reference_id"] = "retry-lab-003"
    with request_path.open("x") as file:
        json.dump(payment, file, indent=2)

body = request_path.read_bytes()
run = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
output = DATA / "concurrent-runs" / run
output.mkdir(parents=True)
(output / "request.json").write_bytes(body)

barrier = threading.Barrier(2)


def send(number):
    request = Request(
        "https://connect.squareupsandbox.com/v2/payments",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Square-Version": "2026-08-19",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    barrier.wait(timeout=10)
    started = datetime.now(timezone.utc).isoformat()

    try:
        with urlopen(request, timeout=30) as response:
            status = response.status
            headers = str(response.headers)
            raw = response.read()
    except HTTPError as error:
        status = error.code
        headers = str(error.headers)
        raw = error.read()
    except (URLError, TimeoutError) as error:
        (output / f"attempt-{number}-transport-error.txt").write_text(
            f"Started: {started}\n{error}\n"
        )
        return f"Attempt {number}: transport error; outcome unknown"

    (output / f"attempt-{number}.json").write_bytes(raw)
    (output / f"attempt-{number}.headers").write_text(headers)
    (output / f"attempt-{number}-meta.json").write_text(
        json.dumps({"started_at": started, "http_status": status}, indent=2)
    )

    result = json.loads(raw)
    payment = result.get("payment", {})
    errors = [error.get("code") for error in result.get("errors", [])]
    return (
        f"Attempt {number}: HTTP {status}, "
        f"payment={payment.get('id')}, "
        f"status={payment.get('status')}, errors={errors}"
    )


with ThreadPoolExecutor(max_workers=2) as pool:
    for result in pool.map(send, (1, 2)):
        print(result)

print("Evidence saved to:", output)
