import requests, json, sys
url='http://127.0.0.1:8002/api/accounts/budgets'
payload={
  "name":"Test Budget - repro",
  "fiscal_year":2026,
  "total_amount":10000.0,
  "start_date":"2026-01-01T00:00:00Z",
  "end_date":"2026-12-31T23:59:59Z",
  "status":"draft"
}
print('REQUEST PAYLOAD:')
print(json.dumps(payload, indent=2))
try:
    r = requests.post(url, json=payload, timeout=15)
    print('\nHTTP STATUS:', r.status_code)
    print('\nRESPONSE BODY:')
    try:
        print(json.dumps(r.json(), indent=2))
    except Exception:
        print(r.text)
except Exception as e:
    print('REQUEST ERROR:', repr(e))
    sys.exit(2)
