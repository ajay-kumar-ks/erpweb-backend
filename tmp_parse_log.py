import io,sys
p='backend_run.log'
with open(p,'rb') as f:
    data=f.read()
# try utf-16-le decode
for enc in ('utf-8','utf-16-le','utf-16','latin-1'):
    try:
        text=data.decode(enc)
        break
    except Exception as e:
        text=None
if text is None:
    print('decode failed')
    sys.exit(1)
lines=text.splitlines()
for i,l in enumerate(lines):
    if 'Traceback' in l or 'Internal Server Error' in l or 'ERROR' in l:
        start=max(0,i-5)
        end=min(len(lines), i+20)
        print('--- FOUND at line',i+1,'---')
        for j in range(start,end):
            print(f'{j+1:05d}: {lines[j]}')
        print('\n')
