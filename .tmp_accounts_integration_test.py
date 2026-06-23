import requests, json, traceback
BASE = 'http://127.0.0.1:8000/api'
results = []

def report(name, ok, details=None):
    results.append({'test': name, 'ok': ok, 'details': details})
    print('\n==', name, '==')
    print('OK' if ok else 'FAIL')
    if details:
        print(json.dumps(details, indent=2))

def do(method, path, payload=None):
    url = BASE + path
    try:
        r = requests.request(method, url, json=payload, timeout=10)
        try:
            body = r.json()
        except Exception:
            body = r.text
        return r.status_code, body
    except Exception as e:
        return None, str(e) + '\n' + traceback.format_exc()

# 1. Chart of Accounts
try:
    status, body = do('POST', '/accounts/coa', {
        'account_code': '1000',
        'account_name': 'Cash - Test',
        'account_type': 'asset',
        'parent_account_id': None,
        'is_active': True
    })
    ok = status in (200,201)
    report('Create COA', ok, {'status': status, 'body': body})
    coa_id = None
    if ok and isinstance(body, dict):
        coa_id = body.get('id')
except Exception as e:
    report('Create COA', False, {'error': str(e), 'trace': traceback.format_exc()})

# List accounts
status, body = do('GET', '/accounts/coa')
report('List COA', status == 200, {'status': status, 'body': body})

# Helper to get latest journal and ledger

def find_latest_journal():
    s,b = do('GET','/accounts/journals')
    if s==200 and isinstance(b, list) and b:
        return b[0]
    return None

def get_ledger():
    s,b = do('GET','/accounts/ledger')
    if s==200 and isinstance(b, list):
        return b
    return None

# 2. Expenses
expense_journal_id = None
try:
    status, body = do('POST', '/accounts/expenses', {
        'description': 'Test expense',
        'amount': 12.34,
        'account_id': coa_id,
        'reference': 'EXP-1'
    })
    ok = status == 200
    report('Create Expense', ok, {'status': status, 'body': body})
    if ok and isinstance(body, dict):
        expense_journal_id = body.get('journal_id')
    # verify journal exists
    journals_status, journals = do('GET','/accounts/journals')
    found = False
    if journals_status==200 and isinstance(journals, list):
        for j in journals:
            if j.get('id') == expense_journal_id:
                found = True
                break
    report('Verify Expense Journal Created', found, {'journal_id': expense_journal_id, 'journals_status': journals_status})
    # verify ledger
    ledger = get_ledger()
    ledger_ok = any(le.get('journal_id')==expense_journal_id for le in ledger) if ledger else False
    report('Verify Expense Ledger Entry', ledger_ok, {'ledger_count': len(ledger) if ledger else 0})
except Exception as e:
    report('Create Expense', False, {'error': str(e), 'trace': traceback.format_exc()})

# 3. Income
income_journal_id = None
try:
    status, body = do('POST', '/accounts/income', {
        'description': 'Test income',
        'amount': 45.67,
        'account_id': coa_id,
        'reference': 'INC-1'
    })
    ok = status == 200
    report('Create Income', ok, {'status': status, 'body': body})
    if ok and isinstance(body, dict):
        income_journal_id = body.get('journal_id')
    # verify journal
    journals_status, journals = do('GET','/accounts/journals')
    found = False
    if journals_status==200 and isinstance(journals, list):
        for j in journals:
            if j.get('id') == income_journal_id:
                found = True
                break
    report('Verify Income Journal Created', found, {'journal_id': income_journal_id})
    ledger = get_ledger()
    ledger_ok = any(le.get('journal_id')==income_journal_id for le in ledger) if ledger else False
    report('Verify Income Ledger Entry', ledger_ok, {'ledger_count': len(ledger) if ledger else 0})
except Exception as e:
    report('Create Income', False, {'error': str(e), 'trace': traceback.format_exc()})

# 4. Accounts Receivable
cust_id = None
invoice_id = None
payment_id = None
try:
    s,b = do('POST','/accounts/customers', {'name':'Cust Test','email':'c@test.local','phone':'123','address':'addr','is_active':True})
    report('Create Customer', s==200, {'status':s,'body':b})
    if s==200 and isinstance(b, dict):
        cust_id = b.get('id')
    s,b = do('POST','/accounts/invoices', {'customer_id':cust_id,'invoice_number':'INV-1','invoice_date':None,'due_date':None,'amount':100,'description':'test inv'})
    report('Create Invoice', s==200, {'status':s,'body':b})
    if s==200 and isinstance(b, dict):
        invoice_id = b.get('id')
    s,b = do('POST',f'/accounts/invoices/{invoice_id}/payments', {'payment_date':None,'amount':50,'reference':'PAY-1'})
    report('Record Customer Payment', s==200, {'status':s,'body':b})
    if s==200 and isinstance(b, dict):
        payment_id = b.get('id')
    # Verify AR journal flow: check payment has journal_id
    s,b = do('GET',f'/accounts/invoices')
    report('List Invoices', s==200, {'status':s})
except Exception as e:
    report('Accounts Receivable Flow', False, {'error':str(e),'trace':traceback.format_exc()})

# 5. Accounts Payable
ven_id = None
bill_id = None
vpay_id = None
try:
    s,b = do('POST','/accounts/vendors', {'name':'Vendor Test','email':'v@test','phone':'111','address':'addr','is_active':True})
    report('Create Vendor', s==200, {'status':s,'body':b})
    if s==200 and isinstance(b, dict):
        ven_id = b.get('id')
    s,b = do('POST','/accounts/bills', {'vendor_id':ven_id,'bill_number':'BILL-1','bill_date':None,'due_date':None,'amount':200,'description':'bill test'})
    report('Create Bill', s==200, {'status':s,'body':b})
    if s==200 and isinstance(b, dict):
        bill_id = b.get('id')
    s,b = do('POST',f'/accounts/bills/{bill_id}/payments', {'payment_date':None,'amount':200,'reference':'VPay-1'})
    report('Record Vendor Payment', s==200, {'status':s,'body':b})
    if s==200 and isinstance(b, dict):
        vpay_id = b.get('id')
except Exception as e:
    report('Accounts Payable Flow', False, {'error':str(e),'trace':traceback.format_exc()})

# 6. Journals workflow
journal_id = None
try:
    payload = {
        'reference':'JNL-1','description':'Test journal','date':None,'lines':[{'account_id':coa_id,'memo':'dr','debit':100,'credit':0},{'account_id':coa_id,'memo':'cr','debit':0,'credit':100}]
    }
    s,b = do('POST','/accounts/journals', payload)
    report('Create Journal', s==200, {'status':s,'body':b})
    if s==200 and isinstance(b, dict):
        journal_id = b.get('id')
    s,b = do('POST',f'/accounts/journals/{journal_id}/submit')
    report('Submit Journal', s==200, {'status':s,'body':b})
    s,b = do('POST',f'/accounts/journals/{journal_id}/approve')
    report('Approve Journal', s==200, {'status':s,'body':b})
    s,b = do('POST',f'/accounts/journals/{journal_id}/post')
    report('Post Journal', s==200, {'status':s,'body':b})
except Exception as e:
    report('Journals Workflow', False, {'error':str(e),'trace':traceback.format_exc()})

# 7. Reports
for rpt, path in [('Trial Balance','/accounts/reports/trial-balance'),('Profit & Loss','/accounts/reports/profit-loss'),('Balance Sheet','/accounts/reports/balance-sheet')]:
    s,b = do('GET', path)
    report(rpt, s==200, {'status':s, 'body': b})

# Summary
passed = [r for r in results if r['ok']]
failed = [r for r in results if not r['ok']]
print('\n\n=== SUMMARY ===')
print('Passed:', len(passed))
print('Failed:', len(failed))
if failed:
    print(json.dumps(failed, indent=2))

