import io,os,re
root=r"c:\Users\ADISH\Documents\business-suite\backend\app\modules\accounts"
dbpath=r"c:\Users\ADISH\Documents\business-suite\backend\app\core\database.py"
# insert commit_or_rollback into database.py
with open(dbpath,'r',encoding='utf-8') as f:
    s=f.read()
if 'def commit_or_rollback' not in s:
    # find insertion point before def get_db
    idx = s.find('\ndef get_db')
    if idx == -1:
        # fallback append
        s += '\n\ndef commit_or_rollback(db: Session):\n    try:\n        db.commit()\n    except Exception:\n        db.rollback()\n        raise\n'
    else:
        insert='''\ndef commit_or_rollback(db: Session):\n    try:\n        db.commit()\n    except Exception:\n        db.rollback()\n        raise\n\n'''
        s = s[:idx] + insert + s[idx:]
    with open(dbpath,'w',encoding='utf-8') as f:
        f.write(s)
    print('updated database.py')
else:
    print('database.py already has commit_or_rollback')
# files to patch: find all .py in accounts folder
patched=[]
for dirpath,dirs,files in os.walk(root):
    for fn in files:
        if fn.endswith('.py'):
            fp=os.path.join(dirpath,fn)
            with open(fp,'r',encoding='utf-8') as f:
                text=f.read()
            orig=text
            # add import if needed
            if 'commit_or_rollback' not in text:
                # add import after other imports: find first from app.core.database or after initial imports block
                if 'from app.core.database import' in text:
                    text=text.replace('from app.core.database import get_db','from app.core.database import get_db, commit_or_rollback')
                else:
                    # insert after the last import line
                    lines=text.splitlines()
                    for i,line in enumerate(lines):
                        pass
                    # find first non-import index
                    idx=0
                    for i,line in enumerate(lines):
                        if not (line.strip().startswith('import') or line.strip().startswith('from')):
                            idx=i
                            break
                    lines.insert(idx, 'from app.core.database import commit_or_rollback')
                    text='\n'.join(lines)
            # replace db.commit() occurrences
            if 'db.commit()' in text:
                text=text.replace('db.commit()','commit_or_rollback(db)')
            if text!=orig:
                with open(fp,'w',encoding='utf-8') as f:
                    f.write(text)
                patched.append(fp)
print('patched files:',patched)
