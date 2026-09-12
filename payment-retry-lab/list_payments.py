import json
import os
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"

token = os.environ.get("SQUARE_ACCESS_TOKEN")
if not token:
    raise SystemExit("Load SQUARE_ACCESS_TOKEN in this terminal first.")

original = json.loads((DATA / "payment-request.json").read_text())
first = json.loads((DATA / "first-response.json").read_text())["payment"]

# Keep the location and time window fixed across every page.
start = datetime.fromisoformat(first["created_at"].replace("Z", "+00:00"))
now = datetime.now(timezone.utc)
params = {
    "location_id": original["location_id"],
    "begin_time": (start - timedelta(minutes=1)).isoformat(),
    "end_time": now.isoformat(),
    "sort_order": "ASC",
    "limit": 1,
}

output = DATA / "list-runs" / now.strftime("%Y%m%dT%H%M%S%fZ")
output.mkdir(parents=True)
(output / "query.json").write_text(json.dumps(params, indent=2))

payments = {}
seen_cursors = set()

for page_number in range(1, 1001):
    request = Request(
        "https://connect.squareupsandbox.com/v2/payments?"
        + urlencode(params),
        headers={
            "Authorization": f"Bearer {token}",
            "Square-Version": "2026-08-19",
            "Accept": "application/json",
        },
    )

    try:
        with urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as error:
        (output / f"error-{page_number}.json").write_bytes(error.read())
        raise SystemExit(f"HTTP {error.code}: stopped; see {output}")
    except (URLError, TimeoutError) as error:
        raise SystemExit(f"Connection failed; listing incomplete: {error}")

    (output / f"page-{page_number}.json").write_text(raw)
    page = json.loads(raw)
    if page.get("errors"):
        raise SystemExit(f"API error; listing incomplete. See {output}")

    batch = page.get("payments", [])
    for payment in batch:
        payments[payment["id"]] = payment

    print(f"Page {page_number}: {len(batch)} payment(s)")
    cursor = page.get("cursor")
    if not cursor:
        break
    if cursor in seen_cursors:
        raise SystemExit("Repeated cursor; stopped with an incomplete listing.")
    seen_cursors.add(cursor)
    params["cursor"] = cursor
else:
    raise SystemExit("Page limit reached; listing incomplete.")

counts = Counter(p.get("reference_id") for p in payments.values())
print("\nPagination complete for the saved location and time window.")
for reference in ("retry-lab-001", "retry-lab-002","retry-lab-003"):
    print(f"{reference}: {counts[reference]} distinct payment(s)")
print("Evidence saved to:", output)
