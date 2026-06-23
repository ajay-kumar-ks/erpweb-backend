p='backend_run.log'
with open(p,'rb') as f:
    data=f.read()
for enc in ('utf-8','utf-16-le','utf-16','latin-1'):
    try:
        text=data.decode(enc)
        break
    except:
        text=None
if text is None:
    raise SystemExit('decode failed')
lines=text.splitlines()
for i,l in enumerate(lines):
    if 'GET /api/accounts/invoices' in l:
        start=i
        break
else:
    print('invoices GET not found'); raise SystemExit(0)
# print surrounding lines
for j in range(max(0,start-5), min(start+50, len(lines))):
    print(f"{j+1:05d}: {lines[j]}")
