from sqlalchemy import create_engine, text
from app.core.config import settings

engine = create_engine(settings.DATABASE_URL)
TABLES = [
    'bills','budget_lines','budgets','chart_of_accounts','customer_payments','customers',
    'event_store','expenses','income','invoices','journal_entries','journal_lines',
    'ledger_entries','vendor_payments','vendors'
]

def run():
    # run per-table migrations; skip tables that don't exist in this DB
    for t in TABLES:
        print('Migrating table', t)
        try:
            with engine.connect() as conn:
                exists = conn.execute(text(f"SELECT to_regclass('public.{t}')")).scalar()
                if not exists:
                    print(' Table does not exist, skipping')
                    continue

                # find primary key constraint name by joining pg_constraint -> pg_class
                pk_row = conn.execute(text(
                    "SELECT con.conname FROM pg_constraint con JOIN pg_class c ON c.oid=con.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE con.contype='p' AND n.nspname='public' AND c.relname = :t"
                ), {'t': t}).fetchone()
                if pk_row and pk_row[0]:
                    pkname = pk_row[0]
                    print(' Dropping pk', pkname)
                    conn.execute(text('ALTER TABLE public."%s" DROP CONSTRAINT IF EXISTS "%s"' % (t, pkname)))

                # drop tenant_id column if exists
                conn.execute(text(f'ALTER TABLE public."{t}" DROP COLUMN IF EXISTS tenant_id'))

                # add primary key on id
                print(' Adding primary key on id')
                conn.execute(text(f'ALTER TABLE public."{t}" ADD PRIMARY KEY (id)'))
                print(' Migrated', t)
        except Exception as e:
            print(' Error migrating', t, e)


if __name__ == '__main__':
    run()
