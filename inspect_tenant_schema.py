from sqlalchemy import create_engine, text
from app.core.config import settings

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

    run_query('tables with tenant_id', """
SELECT table_schema, table_name, column_name
FROM information_schema.columns
WHERE column_name = 'tenant_id' AND table_schema = 'public'
ORDER BY table_name;
""")

    run_query('composite PKs containing tenant_id', """
SELECT n.nspname AS schema_name, c.relname AS table_name,
       array_agg(a.attname ORDER BY k.ordinality) AS pk_columns
FROM pg_index i
JOIN pg_class c ON c.oid = i.indrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
JOIN unnest(i.indkey) WITH ORDINALITY AS k(attnum, ordinality) ON TRUE
JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = k.attnum
WHERE i.indisprimary AND n.nspname = 'public'
GROUP BY n.nspname, c.relname
HAVING bool_or(a.attname = 'tenant_id')
ORDER BY c.relname;
""")

    run_query('foreign keys containing tenant_id', """
SELECT con.conname, n.nspname AS schema_name, c.relname AS table_name,
       array_agg(att.attname ORDER BY k.ordinality) AS columns,
       fn.nspname AS ref_schema, fc.relname AS ref_table,
       pg_get_constraintdef(con.oid) AS definition
FROM pg_constraint con
JOIN pg_class c ON c.oid = con.conrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
JOIN pg_class fc ON fc.oid = con.confrelid
JOIN pg_namespace fn ON fn.oid = fc.relnamespace
JOIN unnest(con.conkey) WITH ORDINALITY AS k(attnum, ordinality) ON TRUE
JOIN pg_attribute att ON att.attrelid = c.oid AND att.attnum = k.attnum
WHERE con.contype = 'f' AND n.nspname = 'public'
GROUP BY con.conname, n.nspname, c.relname, fn.nspname, fc.relname, con.oid
HAVING bool_or(att.attname = 'tenant_id')
ORDER BY c.relname;
""")

    run_query('tables with tenant_id in primary key', """
SELECT n.nspname AS schema_name, c.relname AS table_name,
       array_agg(a.attname ORDER BY k.ordinality) AS pk_columns
FROM pg_index i
JOIN pg_class c ON c.oid = i.indrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
JOIN unnest(i.indkey) WITH ORDINALITY AS k(attnum, ordinality) ON TRUE
JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = k.attnum
WHERE i.indisprimary AND n.nspname = 'public'
GROUP BY n.nspname, c.relname
HAVING bool_and(a.attname <> 'tenant_id') = false -- includes tenant_id
ORDER BY c.relname;
""")
