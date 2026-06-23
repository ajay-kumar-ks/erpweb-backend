import os
import sys
from pathlib import Path
sys.path.append(os.getcwd())
from app.core.config import settings
import psycopg2

tables = [
    'chart_of_accounts','journal_entries','journal_lines','ledger_entries',
    'budgets','budget_lines','vendors','bills','vendor_payments',
    'customers','invoices','customer_payments','expenses','income','event_store'
]
conn = psycopg2.connect(settings.DATABASE_URL)
cur = conn.cursor()
cur.execute(
    'SELECT table_name FROM information_schema.tables WHERE table_schema=%s AND table_name = ANY(%s)',
    ('public', tables)
)
rows = cur.fetchall()
print('FOUND', len(rows))
for row in rows:
    print(row[0])
cur.close()
conn.close()
