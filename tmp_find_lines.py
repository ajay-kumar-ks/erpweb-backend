import inspect
import app.modules.accounts.routers as r
src = inspect.getsource(r)
for i, line in enumerate(src.splitlines(), start=1):
    if 'def list_bills' in line or 'db.query(Bill).all()' in line:
        print(i, line.strip())
