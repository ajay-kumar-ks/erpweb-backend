import requests, json, sys
urls=['http://127.0.0.1:8000/api/accounts/invoices','http://127.0.0.1:8000/api/accounts/bills']
out={}
for u in urls:
    print('GET',u)
    try:
        r=requests.get(u, timeout=10)
        print(r.status_code)
        print(r.text)
        out[u]= {'status': r.status_code, 'text': r.text}
    except Exception as e:
        print('EXC', e)
        out[u]= {'error': str(e)}
open('diagnostics_gets.json','w',encoding='utf-8').write(json.dumps(out, indent=2))
print('Saved diagnostics_gets.json')
