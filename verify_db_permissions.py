import psycopg2
from app.core.config import settings

conn = psycopg2.connect(settings.DATABASE_URL)
cur = conn.cursor()
try:
    cur.execute("SELECT current_user")
    print(f"USER={cur.fetchone()[0]}")

    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name='budgets'")
    print('BUDGETS_EXISTS=', bool(cur.fetchone()))

    # Check direct ALTER/DROP COLUMN permission by attempting DDL inside a single transaction.
    cur.execute('BEGIN')
    try:
        cur.execute('ALTER TABLE public.budgets ADD COLUMN perm_check_temp integer')
        cur.execute('ALTER TABLE public.budgets DROP COLUMN perm_check_temp')
        print('ALTER_DROP_COLUMN=YES')
    except Exception as e:
        print('ALTER_DROP_COLUMN=NO', type(e).__name__, str(e))
    finally:
        cur.execute('ROLLBACK')

    # Check ADD PRIMARY KEY by attempting to add and drop a temporary constraint.
    cur.execute('BEGIN')
    try:
        cur.execute('ALTER TABLE public.budgets ADD CONSTRAINT perm_check_pk_temp PRIMARY KEY (id)')
        cur.execute('ALTER TABLE public.budgets DROP CONSTRAINT perm_check_pk_temp')
        print('ADD_PRIMARY_KEY=YES')
    except Exception as e:
        print('ADD_PRIMARY_KEY=NO', type(e).__name__, str(e))
    finally:
        cur.execute('ROLLBACK')

finally:
    cur.close()
    conn.close()
