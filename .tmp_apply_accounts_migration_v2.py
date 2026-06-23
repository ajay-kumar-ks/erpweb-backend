import os
import sys
from pathlib import Path
sys.path.append(os.getcwd())
from app.core.config import settings
import psycopg2

migration_path = Path(__file__).resolve().parent / 'migrations' / '0001_drop_and_create_accounts_single_company.sql'
if not migration_path.exists():
    raise FileNotFoundError(f"Migration file not found: {migration_path}")

with open(migration_path, 'r', encoding='utf-8') as f:
    script = f.read()

lines = []
for line in script.splitlines():
    stripped = line.strip()
    if stripped.upper().startswith('DROP TABLE IF EXISTS'):
        if stripped.endswith('CASCADE;'):
            line = line.replace(' CASCADE;', ';')
        elif stripped.endswith('CASCADE'):
            line = line.replace(' CASCADE', '')
    lines.append(line)
script = '\n'.join(lines)

statements = [stmt.strip() for stmt in script.split(';') if stmt.strip()]
print(f'Parsed {len(statements)} SQL statements')
print('Connecting to', settings.DATABASE_URL)
conn = psycopg2.connect(settings.DATABASE_URL)
cur = conn.cursor()
try:
    for idx, stmt in enumerate(statements, start=1):
        print(f'Executing statement {idx}/{len(statements)}: {stmt.splitlines()[0][:80]}')
        cur.execute(stmt)
    conn.commit()
    print('MIGRATION_OK')
except Exception as exc:
    print('MIGRATION_ERROR', type(exc).__name__, str(exc))
    conn.rollback()
    raise
finally:
    cur.close()
    conn.close()
