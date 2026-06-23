"""
Run Accounts workflow tests in-process using FastAPI TestClient.
This script forces an SQLite test DB via environment variable before importing the app.

It performs:
- create COA entries (1..7)
- create budget
- add budget line
- create customer
- create invoice
- record invoice payment
- create vendor
- create bill
- record bill payment

Prints endpoint, payload, status, response body for each step.
"""
import os
import json
from datetime import datetime, timedelta

# Use a local sqlite file for tests so we don't touch external DB
os.environ['DATABASE_URL'] = 'sqlite:///./test_workflow.db'
os.environ['ENVIRONMENT'] = 'development'

import httpx
from httpx import ASGITransport

# Import app after env var set
from app.main import app

# Use httpx ASGI client to call the app in-process
transport = ASGITransport(app=app)
client = httpx.Client(transport=transport, base_url="http://testserver")

results = []

API_PREFIX = "/api/accounts"

def record(endpoint, payload, response):
    try:
        body = response.json()
    except Exception:
        body = response.text
    results.append({
        'endpoint': endpoint,
        'payload': payload,
        'status': response.status_code,
        'body': body,
    })
    print(f"{endpoint} -> {response.status_code}")
    print(json.dumps({'payload': payload, 'body': body}, default=str, indent=2))

# Ensure DB and tables initialized by hitting health
client.get('/api/health')

# 1) Create COA entries (1..7)
coa_ids = []
for i in range(1, 8):
    payload = {
        'account_code': f"{1000+i}",
        'account_name': f"Test Account {i}",
        'account_type': 'asset' if i in (1,3) else ('liability' if i in (4,) else 'revenue' if i==6 else 'expense') ,
        'parent_account_id': None,
        'is_active': True,
    }
    r = client.post(f"{API_PREFIX}/coa", json=payload)
    record(f"POST {API_PREFIX}/coa", payload, r)
    if r.status_code == 200:
        coa_ids.append(r.json().get('id'))

# 2) Create Budget
start = datetime.utcnow().date()
end = start.replace(year=start.year+1)
budget_payload = {
    'name': 'Test Budget',
    'fiscal_year': start.year,
    'total_amount': 10000.0,
    'start_date': start.isoformat(),
    'end_date': end.isoformat(),
    'status': 'draft',
}
r = client.post(f"{API_PREFIX}/budgets", json=budget_payload)
record(f"POST {API_PREFIX}/budgets", budget_payload, r)
budget_id = None
if r.status_code == 200:
    budget_id = r.json().get('id')

# 3) Add Budget Line
if budget_id:
    bl_payload = {
        'account_id': coa_ids[0] if coa_ids else 1,
        'allocated_amount': 5000.0,
    }
    r = client.post(f"{API_PREFIX}/budgets/{budget_id}/lines", json=bl_payload)
    record(f"POST {API_PREFIX}/budgets/{budget_id}/lines", bl_payload, r)

# 4) Create Customer
cust_payload = {
    'name': 'Test Customer',
    'email': 'cust@example.com',
    'phone': '1234567890',
    'address': '123 Street',
}
r = client.post(f"{API_PREFIX}/customers", json=cust_payload)
record(f"POST {API_PREFIX}/customers", cust_payload, r)
customer_id = None
if r.status_code == 200:
    customer_id = r.json().get('id')

# 5) Create Invoice
invoice_id = None
if customer_id:
    invoice_payload = {
        'customer_id': customer_id,
        'invoice_number': 'INV-1001',
        'invoice_date': datetime.utcnow().isoformat(),
        'due_date': (datetime.utcnow() + timedelta(days=30)).isoformat(),
        'amount': 1500.0,
        'description': 'Test invoice',
    }
    r = client.post(f"{API_PREFIX}/invoices", json=invoice_payload)
    record(f"POST {API_PREFIX}/invoices", invoice_payload, r)
    if r.status_code == 200:
        invoice_id = r.json().get('id')

# 6) Record Invoice Payment
if invoice_id:
    pay_payload = {
        'invoice_id': invoice_id,
        'payment_date': datetime.utcnow().isoformat(),
        'amount': 1500.0,
        'reference': 'PAY-INV-1001',
    }
    r = client.post(f"{API_PREFIX}/invoices/{invoice_id}/payments", json=pay_payload)
    record(f"POST {API_PREFIX}/invoices/{invoice_id}/payments", pay_payload, r)

# 7) Create Vendor
vendor_payload = {
    'name': 'Test Vendor',
    'email': 'vendor@example.com',
    'phone': '0987654321',
    'address': '456 Avenue',
}
r = client.post(f"{API_PREFIX}/vendors", json=vendor_payload)
record(f"POST {API_PREFIX}/vendors", vendor_payload, r)
vendor_id = None
if r.status_code == 200:
    vendor_id = r.json().get('id')

# 8) Create Bill
bill_id = None
if vendor_id:
    bill_payload = {
        'vendor_id': vendor_id,
        'bill_number': 'BILL-1001',
        'bill_date': datetime.utcnow().isoformat(),
        'due_date': (datetime.utcnow() + timedelta(days=30)).isoformat(),
        'amount': 800.0,
        'description': 'Test bill',
    }
    r = client.post(f"{API_PREFIX}/bills", json=bill_payload)
    record(f"POST {API_PREFIX}/bills", bill_payload, r)
    if r.status_code == 200:
        bill_id = r.json().get('id')

# 9) Record Bill Payment
if bill_id:
    bill_pay_payload = {
        'bill_id': bill_id,
        'payment_date': datetime.utcnow().isoformat(),
        'amount': 800.0,
        'reference': 'PAY-BILL-1001',
    }
    r = client.post(f"{API_PREFIX}/bills/{bill_id}/payments", json=bill_pay_payload)
    record(f"POST {API_PREFIX}/bills/{bill_id}/payments", bill_pay_payload, r)

# Summary table
print('\n\n=== Workflow Summary ===')
for idx, r in enumerate(results, 1):
    print(f"{idx}. {r['endpoint']} -> {r['status']}")

# Save results
with open('ui_workflow_results.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, default=str, indent=2)

print('\nSaved results to ui_workflow_results.json')
