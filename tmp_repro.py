import requests

base = 'http://127.0.0.1:8000/api'

print('GET /api/accounts/coa')
try:
    r = requests.get(f'{base}/accounts/coa', timeout=10)
    print(r.status_code)
    print(r.text)
except Exception as e:
    print('ERROR GET /coa', e)

print('\nPOST /api/accounts/expenses')
payload = {
    'description': 'Test expense',
    'amount': 10.0,
    'account_id': 1,
    'reference': 'EXP-TEST'
}
try:
    r = requests.post(f'{base}/accounts/expenses', json=payload, timeout=20)
    print(r.status_code)
    print(r.text)
except Exception as e:
    print('ERROR POST /expenses', e)

print('\nPOST /api/accounts/income')
payload = {
    'description': 'Test income',
    'amount': 20.0,
    'account_id': 1,
    'reference': 'INC-TEST'
}
try:
    r = requests.post(f'{base}/accounts/income', json=payload, timeout=20)
    print(r.status_code)
    print(r.text)
except Exception as e:
    print('ERROR POST /income', e)
