import os
import time
import sys
from dotenv import load_dotenv

load_dotenv('backend/.env')
sys.path.insert(0, 'backend')

from fastapi.testclient import TestClient
from app.main import app
from sqlalchemy import create_engine
import psycopg2
from psycopg2.extras import RealDictCursor

client = TestClient(app)

for path in ['/api/crm/leads', '/api/crm/contacts', '/api/crm/pipelines']:
    start = time.time()
    resp = client.get(path)
    elapsed = time.time() - start
    print(path, resp.status_code, f'{elapsed:.3f}s', 'len', len(resp.content))

start = time.time()
resp = client.post('/api/crm/ai/pipeline-insights', params={'pipeline_id': '1'})
elapsed = time.time() - start
print('/api/crm/ai/pipeline-insights', resp.status_code, f'{elapsed:.3f}s', 'len', len(resp.content))

DATABASE_URL = os.getenv('DATABASE_URL')
print('DATABASE_URL set:', bool(DATABASE_URL))
engine = create_engine(DATABASE_URL)
conn = engine.raw_connection()
cur = conn.cursor(cursor_factory=RealDictCursor)

queries = [
    ('SELECT id, title, assignee, pipeline_id, phase_id, contact_id, created_at FROM leads ORDER BY created_at DESC LIMIT 25', 'leads list', None),
    ('SELECT id, assignee FROM leads WHERE assignee ILIKE %s LIMIT 25', 'leads assignee search', ['%John%']),
    ('SELECT id, title FROM leads WHERE title ILIKE %s LIMIT 25', 'leads title search', ['%Inc%']),
    ('SELECT id, name FROM contacts WHERE name ILIKE %s LIMIT 25', 'contacts name search', ['%Smith%']),
    ('SELECT id, name, email, company, status FROM contacts LIMIT 25', 'contacts list', None),
    ('SELECT id, name, owner FROM pipelines', 'pipelines list', None),
]

cur.execute('SELECT id FROM pipelines LIMIT 1')
pipeline = cur.fetchone()
pipeline_id = pipeline['id'] if pipeline else None
print('pipeline_id:', pipeline_id)

for sql, label, params in queries:
    print('\n===', label, '===')
    try:
        if params is None:
            cur.execute('EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT) ' + sql)
        else:
            cur.execute('EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT) ' + sql, params)
        for row in cur.fetchall():
            print(row['QUERY PLAN'])
    except Exception as e:
        print('ERROR', label, type(e).__name__, e)

if pipeline_id:
    print('\n=== phases by pipeline ===')
    try:
        cur.execute('EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT) SELECT id, pipeline_id, name FROM phases WHERE pipeline_id = %s ORDER BY position', (pipeline_id,))
        for row in cur.fetchall():
            print(row['QUERY PLAN'])
    except Exception as e:
        print('ERROR phases by pipeline', type(e).__name__, e)

print('\n=== indexes ===')
cur.execute("SELECT tablename, indexname, indexdef FROM pg_indexes WHERE tablename IN ('leads','contacts','pipelines','phases','clients') ORDER BY tablename,indexname")
for row in cur.fetchall():
    print(row)

cur.close()
conn.close()
