from sqlalchemy import create_engine, text
from app.core.config import settings

engine = create_engine(settings.DATABASE_URL)
with engine.connect() as conn:
    tables = ['bills','budget_lines','budgets','chart_of_accounts','customer_payments','customers','event_store','expenses','income','invoices','journal_entries','journal_lines','ledger_entries','vendor_payments','vendors']
    results = {}
    for t in tables:
        try:
            cnt = conn.execute(text(f"SELECT count(*) FROM public.{t}" )).scalar()
            results[t] = cnt
        except Exception as e:
            results[t] = f"ERROR: {type(e).__name__}: {e}"
    for k,v in results.items():
        print(f"{k}: {v}")
