"""
Run Accounts workflow against running server (http://127.0.0.1:8001/api).
Sends HTTP requests and logs endpoint, payload, status, body.
"""
import requests
import json
from datetime import datetime, timedelta

BASE = "http://127.0.0.1:8001/api/accounts"

results = []

def record(endpoint, payload, r):
    try:
        body = r.json()
    except Exception:
        body = r.text
    results.append({'endpoint': endpoint, 'payload': payload, 'status': r.status_code, 'body': body})
    print(endpoint, r.status_code)
    print(json.dumps({'payload': payload, 'body': body}, default=str, indent=2))

# 1) Create COA entries 1..7
coa_ids = []
for i in range(1,8):
    payload = {
        'account_code': f"{1000+i}",
        'account_name': f"Req Account {i}",
        'account_type': 'asset' if i in (1,3) else ('liability' if i in (4,) else 'revenue' if i==6 else 'expense'),
        'parent_account_id': None,
        'is_active': True,
    }
    r = requests.post(f"{BASE}/coa", json=payload)
    record(f"POST /coa", payload, r)
    if r.status_code == 200:
        coa_ids.append(r.json().get('id'))

# 2) Create Budget
start = datetime.utcnow().date()
end = start.replace(year=start.year+1)
budget_payload = {
    'name': 'Req Test Budget',
    'fiscal_year': start.year,
    'total_amount': 10000.0,
    'start_date': start.isoformat(),
    'end_date': end.isoformat(),
    'status': 'draft',
}
r = requests.post(f"{BASE}/budgets", json=budget_payload)
record("POST /budgets", budget_payload, r)
budget_id = r.json().get('id') if r.status_code==200 else None

# 3) Add Budget Line
if budget_id:
    bl_payload = {'account_id': coa_ids[0] if coa_ids else 1, 'allocated_amount': 5000.0}
    r = requests.post(f"{BASE}/budgets/{budget_id}/lines", json=bl_payload)
    record(f"POST /budgets/{budget_id}/lines", bl_payload, r)

# 4) Create Customer
cust_payload = {'name': 'Req Customer', 'email':'rc@example.com'}
r = requests.post(f"{BASE}/customers", json=cust_payload)
record("POST /customers", cust_payload, r)
customer_id = r.json().get('id') if r.status_code==200 else None

# 5) Create Invoice
invoice_id = None
if customer_id:
    invoice_payload = {'customer_id': customer_id, 'invoice_number':'INV-REQ-1', 'invoice_date': datetime.utcnow().isoformat(), 'due_date': (datetime.utcnow()+timedelta(days=30)).isoformat(), 'amount': 1500.0, 'description':'Req invoice'}
    r = requests.post(f"{BASE}/invoices", json=invoice_payload)
    record("POST /invoices", invoice_payload, r)
    if r.status_code==200:
        invoice_id = r.json().get('id')

# 6) Invoice Payment
if invoice_id:
    pay_payload = {'invoice_id': invoice_id, 'payment_date': datetime.utcnow().isoformat(), 'amount':1500.0, 'reference':'PAY-REQ-1'}
    r = requests.post(f"{BASE}/invoices/{invoice_id}/payments", json=pay_payload)
    record(f"POST /invoices/{invoice_id}/payments", pay_payload, r)

# 7) Create Vendor
vendor_payload = {'name':'Req Vendor', 'email':'rv@example.com'}
r = requests.post(f"{BASE}/vendors", json=vendor_payload)
record("POST /vendors", vendor_payload, r)
vendor_id = r.json().get('id') if r.status_code==200 else None

# 8) Create Bill
bill_id = None
if vendor_id:
    bill_payload = {'vendor_id': vendor_id, 'bill_number':'BILL-REQ-1', 'bill_date': datetime.utcnow().isoformat(), 'due_date': (datetime.utcnow()+timedelta(days=30)).isoformat(), 'amount':800.0, 'description':'Req bill'}
    r = requests.post(f"{BASE}/bills", json=bill_payload)
    record("POST /bills", bill_payload, r)
    if r.status_code==200:
        bill_id = r.json().get('id')

# 9) Bill Payment
if bill_id:
    bill_pay_payload = {'bill_id': bill_id, 'payment_date': datetime.utcnow().isoformat(), 'amount':800.0, 'reference':'BP-REQ-1'}
    r = requests.post(f"{BASE}/bills/{bill_id}/payments", json=bill_pay_payload)
    record(f"POST /bills/{bill_id}/payments", bill_pay_payload, r)

# Save results
with open('ui_workflow_http_results.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, default=str, indent=2)

print('\nSaved to ui_workflow_http_results.json')
