import os
import sys
from pathlib import Path

sys.path.append(os.getcwd())
from app.core.config import settings
import psycopg2

migration_path = Path(__file__).resolve().parent / 'migrations' / '0001_drop_and_create_accounts_single_company.sql'
if not migration_path.exists():
    raise FileNotFoundError(f"Migration file not found: {migration_path}")

script = migration_path.read_text()
script = script.replace(' ON DELETE CASCADE', '')
script = script.replace(' CASCADE;', ';')
script = script.replace(' CASCADE\n', '\n')

print('Connecting to', settings.DATABASE_URL)
conn = psycopg2.connect(settings.DATABASE_URL)
cur = conn.cursor()
try:
    cur.execute(script)
    conn.commit()
    print('MIGRATION_OK')
except Exception as exc:
    print('MIGRATION_ERROR', type(exc).__name__, str(exc))
    conn.rollback()
    raise
finally:
    cur.close()
    conn.close()
