import traceback
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from fastapi.testclient import TestClient
from app.main import app

# Use raise_server_exceptions=True to see actual exception
client = TestClient(app, raise_server_exceptions=True)

payload = {
    "name": "Test Budget Failure",
    "description": "Reproduce failure",
    "budget_period": "annual",
    "fiscal_year": 2026,
    "total_amount": 10000.00,
    "status": "active",
    "start_date": "2026-01-01",
    "end_date": "2026-12-31"
}

print("PAYLOAD:")
print(json.dumps(payload, indent=2))
print()

try:
    response = client.post("/api/accounts/budgets", json=payload)
    print("STATUS:", response.status_code)
    print("RESPONSE BODY:")
    try:
        print(json.dumps(response.json(), indent=2))
    except Exception:
        print(response.text)
except Exception as exc:
    print("EXCEPTION TYPE:", type(exc).__name__)
    print("EXCEPTION MESSAGE:", str(exc))
    print("TRACEBACK:")
    traceback.print_exc()
