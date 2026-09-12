import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent

parser = argparse.ArgumentParser(description="Send a saved sandbox payment request.")
parser.add_argument("request_file", type=Path)
parser.add_argument("--capture", required=True, help="New directory for evidence")
args = parser.parse_args()

token = os.environ.get("SQUARE_ACCESS_TOKEN")
if not token:
    parser.error("Load SQUARE_ACCESS_TOKEN in this terminal first.")

body = args.request_file.read_bytes()
payment = json.loads(body)
if not isinstance(payment, dict) or not payment.get("idempotency_key"):
    parser.error("The request must contain an idempotency_key.")

output = ROOT / "data" / "send-runs" / args.capture
if Path(args.capture).name != args.capture or args.capture in (".", ".."):
    parser.error("--capture must be a simple directory name.")

try:
    output.mkdir(parents=True, exist_ok=False)
except FileExistsError:
    parser.error("Capture already exists; choose a new --capture name.")

(output / "request.json").write_bytes(body)

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

metadata = {
    "started_at": datetime.now(timezone.utc).isoformat(),
    "http_status": None,
    "outcome": "unknown",
}
(output / "metadata.json").write_text(json.dumps(metadata, indent=2))

try:
    with urlopen(request, timeout=30) as response:
        status = response.status
        headers = str(response.headers)
        raw = response.read()
except HTTPError as error:
    status = error.code
    headers = str(error.headers)
    raw = error.read()
except (URLError, TimeoutError, OSError) as error:
    metadata["transport_error"] = str(error)
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2))
    raise SystemExit(
        f"No complete response captured; payment outcome unknown. See {output}"
    )

(output / "response.json").write_bytes(raw)
(output / "response.headers").write_text(headers)

metadata.update({
    "http_status": status,
    "outcome": "http_response_received",
    "finished_at": datetime.now(timezone.utc).isoformat(),
})
(output / "metadata.json").write_text(json.dumps(metadata, indent=2))

print("HTTP", status)
print("Evidence saved to:", output)

try:
    result = json.loads(raw)
except (ValueError, UnicodeDecodeError):
    raise SystemExit("Response was not valid JSON; inspect the saved evidence.")

print(json.dumps(result, indent=2))
