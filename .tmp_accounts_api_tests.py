import requests
import json

BASE = 'http://127.0.0.1:8000/api/accounts'

headers = {'Content-Type': 'application/json'}

payloads = {
    'budgets': {'name': 'Test Budget', 'fiscal_year': 2026, 'total_amount': 10000.0, 'start_date': '2026-01-01T00:00:00', 'end_date': '2026-12-31T23:59:59', 'status': 'draft'},
    'expenses': {'description': 'Test Expense', 'amount': 100.0, 'expense_date': '2026-06-22T00:00:00', 'account_id': 1, 'reference': 'EXP-001'},
    'income': {'description': 'Test Income', 'amount': 200.0, 'income_date': '2026-06-22T00:00:00', 'account_id': 4, 'reference': 'INC-001'},
    'invoices': {'customer_id': 1, 'invoice_number': 'INV-001', 'invoice_date': '2026-06-22T00:00:00', 'due_date': '2026-07-22T00:00:00', 'amount': 500.0, 'description': 'Test invoice'},
    'bills': {'vendor_id': 1, 'bill_number': 'BILL-001', 'bill_date': '2026-06-22T00:00:00', 'due_date': '2026-07-22T00:00:00', 'amount': 300.0, 'description': 'Test bill'},
    'journals': {'reference': 'JRN-001', 'description': 'Test journal', 'date': '2026-06-22T00:00:00', 'lines': [{'account_id': 1, 'memo': 'Cash debit', 'debit': 100.0, 'credit': 0.0}, {'account_id': 4, 'memo': 'Sales credit', 'debit': 0.0, 'credit': 100.0}]}
}

results = {}
for key, payload in payloads.items():
    url = f'{BASE}/{key}'
    try:
        r = requests.post(url, data=json.dumps(payload), headers=headers, timeout=10)
        results[key] = {'status_code': r.status_code, 'body': r.text}
    except Exception as ex:
        results[key] = {'error': str(ex)}

checks = ['budgets', 'expenses', 'income']
for key in checks:
    try:
        r = requests.get(f'{BASE}/{key}', timeout=10)
        results[f'get_{key}'] = {'status_code': r.status_code, 'body': r.text}
    except Exception as ex:
        results[f'get_{key}'] = {'error': str(ex)}

for name in ['trial-balance', 'profit-loss', 'balance-sheet']:
    try:
        r = requests.get(f'{BASE}/reports/{name}', timeout=10)
        results[name] = {'status_code': r.status_code, 'body': r.text}
    except Exception as ex:
        results[name] = {'error': str(ex)}

print(json.dumps(results, indent=2))
