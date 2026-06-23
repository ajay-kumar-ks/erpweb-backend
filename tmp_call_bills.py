import requests
r=requests.get('http://127.0.0.1:8000/api/accounts/bills')
print('STATUS', r.status_code)
print('BODY', r.text)
