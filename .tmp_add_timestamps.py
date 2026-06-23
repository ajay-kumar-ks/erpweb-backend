from app.core.config import settings
import psycopg2

tables = [
    'chart_of_accounts','journal_entries','journal_lines','ledger_entries',
    'budgets','budget_lines','vendors','bills','vendor_payments',
    'customers','invoices','customer_payments','expenses','income','event_store'
]
conn = psycopg2.connect(settings.DATABASE_URL)
conn.autocommit = True
cur = conn.cursor()
for t in tables:
    try:
        cur.execute(f"ALTER TABLE {t} ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT now()")
        cur.execute(f"ALTER TABLE {t} ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT now()")
        print('altered', t)
    except Exception as e:
        print('error', t, e)
cur.close()
conn.close()
print('done')
