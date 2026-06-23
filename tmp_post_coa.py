import requests
import json
payload = {'account_code':'1002','account_name':'Req Account 2','account_type':'expense','parent_account_id':None,'is_active':True}
print('Posting:', payload)
r = requests.post('http://127.0.0.1:8001/api/accounts/coa', json=payload)
print('Status:', r.status_code)
try:
    print(json.dumps(r.json(), indent=2))
except Exception:
    print(r.text)
