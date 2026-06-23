import requests
for i in range(10):
    r1 = requests.get('http://127.0.0.1:8000/api/accounts/invoices', timeout=10)
    print(i+1, 'INVOICES', r1.status_code)
    r2 = requests.get('http://127.0.0.1:8000/api/accounts/bills', timeout=10)
    print(i+1, 'BILLS', r2.status_code)
