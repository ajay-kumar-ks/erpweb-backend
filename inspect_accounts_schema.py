from sqlalchemy import create_engine, text
from app.core.config import settings

engine = create_engine(settings.DATABASE_URL)
TABLES = [
    'bills','budget_lines','budgets','chart_of_accounts','customer_payments','customers',
    'event_store','expenses','income','invoices','journal_entries','journal_lines',
    'ledger_entries','vendor_payments','vendors'
]

for t in TABLES:
    print('\n' + '='*40)
    print('TABLE:', t)
    # Use a fresh connection per table to avoid transaction aborts impacting the full run
    try:
        with engine.connect() as conn:
            def run(q, label):
                print('\n' + label)
                try:
                    rows = list(conn.execute(text(q)))
                    if not rows:
                        print('(no rows)')
                    for r in rows:
                        print(r)
                except Exception as e:
                    print('ERROR', label, type(e).__name__, e)

            run(f"""
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_schema='public' AND table_name = '{t}'
ORDER BY ordinal_position;
""", '--- columns ---')

            run(f"""
SELECT a.attname
FROM pg_index i
JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
JOIN pg_class c ON c.oid = i.indrelid
WHERE i.indisprimary AND c.relname = '{t}'
ORDER BY a.attnum;
""", '--- primary key ---')

            run(f"""
SELECT con.conname, pg_get_constraintdef(con.oid) FROM pg_constraint con
JOIN pg_class c ON c.oid=con.conrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE con.contype = 'f' AND n.nspname = 'public' AND c.relname = '{t}';
""", '--- foreign keys ---')

            run(f"""
SELECT indexname, indexdef FROM pg_indexes WHERE schemaname='public' AND tablename = '{t}';
""", '--- indexes ---')

            run(f"""
SELECT conname, contype, pg_get_constraintdef(oid) FROM pg_constraint con
JOIN pg_class c ON c.oid = con.conrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relname = '{t}' ORDER BY conname;
""", '--- constraints ---')

            run(f"""
SELECT policyname, permissive, roles, qual, with_check FROM pg_policies
WHERE schemaname='public' AND tablename = '{t}';
""", '--- row security policies ---')

            # tenant_id usage quick check
            try:
                col = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name = :t AND column_name='tenant_id'"), {'t': t}).fetchone()
                print('\n--- tenant_id usage ---')
                if col:
                    print('tenant_id column present')
                    pk_rows = conn.execute(text("SELECT a.attname FROM pg_index i JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey) JOIN pg_class c ON c.oid = i.indrelid WHERE i.indisprimary AND c.relname = :t ORDER BY a.attnum"), {'t': t}).fetchall()
                    pk_cols = [r[0] for r in pk_rows]
                    print('tenant_id in pk:' , 'tenant_id' in pk_cols)
                else:
                    print('no tenant_id column')
            except Exception as e:
                print('ERROR tenant_id check:', type(e).__name__, e)
    except Exception as e:
        print('ERROR connecting for table', t, type(e).__name__, e)

print('\nDONE')
