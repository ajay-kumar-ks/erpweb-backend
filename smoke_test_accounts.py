import urllib.request, json, datetime
base='http://127.0.0.1:8002/api/accounts'

def call(method,path,data=None):
    url=base+path
    headers={}
    if data is not None:
        data_bytes=json.dumps(data).encode()
        headers={'Content-Type':'application/json'}
    req=urllib.request.Request(url, data=(data_bytes if data is not None else None), headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body=resp.read().decode()
            print('\n---', method, path, 'STATUS', resp.status,'---')
            try:
                print(json.dumps(json.loads(body), indent=2))
            except Exception:
                print(body)
            return resp.status, body
    except urllib.error.HTTPError as e:
        body=e.read().decode()
        print('\n---', method, path, 'HTTPError', e.code,'---')
        print(body)
        return e.code, body
    except Exception as e:
        print('\n---', method, path, 'ERROR ---')
        print(str(e))
        return None, str(e)

# Health
call('GET','/')
# COA
status, body = call('GET','/coa')
account_id=None
try:
    arr=json.loads(body)
    if isinstance(arr, list) and arr:
        account_id=arr[0]['id']
except Exception:
    account_id=None
print('\nFirst account id:', account_id)

# Create budget
now=datetime.datetime.utcnow()
start=now.replace(month=1, day=1).isoformat()+"Z"
end=now.replace(month=12, day=31).isoformat()+"Z"
budget_payload={
    'name':'Test Budget',
    'fiscal_year': now.year,
    'total_amount': 1000.0,
    'start_date': start,
    'end_date': end,
}
call('POST','/budgets', budget_payload)

# Create expense (needs account_id)
if account_id is not None:
    expense_payload={
        'description':'Test expense',
        'amount':10.5,
        'account_id': account_id,
    }
    call('POST','/expenses', expense_payload)
else:
    print('Skipping expense POST (no account id)')

# Create income
if account_id is not None:
    income_payload={
        'description':'Test income',
        'amount':20.0,
        'account_id': account_id,
    }
    call('POST','/income', income_payload)
else:
    print('Skipping income POST (no account id)')
