import os,re
root=r"c:\Users\ADISH\Documents\business-suite\backend\app\modules\accounts"
removed=[]
for dirpath,dirs,files in os.walk(root):
    for fn in files:
        if fn.endswith('.py'):
            fp=os.path.join(dirpath,fn)
            with open(fp,'r',encoding='utf-8') as f:
                s=f.read()
            if 'from app.core.database import commit_or_rollback' in s and 'commit_or_rollback(db)' not in s:
                s=s.replace('from app.core.database import commit_or_rollback\n','')
                with open(fp,'w',encoding='utf-8') as f:
                    f.write(s)
                removed.append(fp)
print('removed imports from:',removed)
