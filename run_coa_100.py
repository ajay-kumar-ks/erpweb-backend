import requests
import json
from datetime import datetime

BASE = "http://127.0.0.1:8001/api/accounts"
results = []

for i in range(100):
    payload = {
        'account_code': f"RCOA-{int(datetime.utcnow().timestamp())}-{i}",
        'account_name': f"RCOA Test {i}",
        'account_type': 'expense' if i % 3 == 0 else 'asset',
        'parent_account_id': None,
        'is_active': True,
    }
    try:
        r = requests.post(f"{BASE}/coa", json=payload, timeout=10)
        try:
            body = r.json()
        except Exception:
            body = r.text
        results.append({'index': i, 'payload': payload, 'status': r.status_code, 'body': body})
        print(f"{i+1}/100 -> {r.status_code}")
    except Exception as e:
        results.append({'index': i, 'payload': payload, 'status': 'exception', 'body': str(e)})
        print(f"{i+1}/100 -> exception: {e}")

with open('ui_coa_100_results.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, default=str, indent=2)

print('Saved ui_coa_100_results.json')
