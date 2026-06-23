from sqlalchemy import create_engine, text
from app.core.config import settings

def run():
    engine = create_engine(settings.DATABASE_URL)
    with engine.connect() as conn:
        def run_query(name, sql):
            print(f'=== {name} ===')
            try:
                rows = list(conn.execute(text(sql)))
                if not rows:
                    print('(no rows)')
                for row in rows:
                    print(row)
            except Exception as e:
                print('ERROR', type(e).__name__, e)
            print()

        run_query('budgets tables', """
SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_name = 'budgets'
ORDER BY table_schema, table_name;
""")

        run_query('budgets columns', """
SELECT table_schema, column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'budgets'
ORDER BY ordinal_position;
""")

        run_query('budgets indexes', """
SELECT schemaname, tablename, indexname, indexdef
FROM pg_indexes
WHERE tablename = 'budgets'
ORDER BY schemaname, indexname;
""")

        run_query('budgets constraints', """
SELECT n.nspname AS schema_name, c.relname AS table_name, con.conname, con.contype, pg_get_constraintdef(con.oid)
FROM pg_constraint con
JOIN pg_class c ON c.oid = con.conrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relname = 'budgets'
ORDER BY n.nspname, con.conname;
""")

        run_query('budgets triggers', """
SELECT n.nspname AS schema_name, c.relname AS table_name, t.tgname, t.tgenabled, pg_get_triggerdef(t.oid)
FROM pg_trigger t
JOIN pg_class c ON c.oid = t.tgrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relname = 'budgets' AND NOT t.tgisinternal
ORDER BY n.nspname, t.tgname;
""")

        run_query('budgets row security policies', """
SELECT schemaname, tablename, policyname, permissive, roles, qual, with_check
FROM pg_policies
WHERE tablename = 'budgets'
ORDER BY schemaname, policyname;
""")

        run_query('nile settings', """
SELECT name, setting, unit, short_desc
FROM pg_settings
WHERE name LIKE 'nile.%'
ORDER BY name;
""")

        run_query('pg_extension nile', """
SELECT extname, extversion
FROM pg_extension
WHERE extname LIKE '%nile%'
ORDER BY extname;
""")

        run_query('current nile.tenant_id', """
SELECT current_setting('nile.tenant_id', true) AS value;
""")

if __name__ == '__main__':
    run()
