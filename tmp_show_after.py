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
    if 'GET /api/accounts/bills' in l:
        start=i
        break
else:
    print('not found'); raise SystemExit(0)
for j in range(start, min(start+200, len(lines))):
    print(f"{j+1:05d}: {lines[j]}")
