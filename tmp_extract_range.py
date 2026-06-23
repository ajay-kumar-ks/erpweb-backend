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
    print('decode failed'); raise SystemExit(1)
lines=text.splitlines()
start=230; end=300
for i in range(start-1,end):
    print(f'{i+1:05d}: {lines[i]}')
