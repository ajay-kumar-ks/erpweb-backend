from sqlalchemy import create_engine, text
from app.core.config import settings
import json

engine = create_engine(settings.DATABASE_URL)
TABLES = [
    'bills','budget_lines','budgets','chart_of_accounts','customer_payments','customers',
    'event_store','expenses','income','invoices','journal_entries','journal_lines',
    'ledger_entries','vendor_payments','vendors'
]

def analyze_table(conn, t):
    out = {'table': t}
    try:
        total = conn.execute(text(f"SELECT COUNT(*) FROM public.{t}"))
        out['total_rows'] = int(total.scalar() or 0)
    except Exception as e:
        out['total_rows'] = None
        out['error_total'] = str(e)

    try:
        distinct = conn.execute(text(f"SELECT COUNT(DISTINCT id) FROM public.{t}"))
        out['distinct_ids'] = int(distinct.scalar() or 0)
    except Exception as e:
        out['distinct_ids'] = None
        out['error_distinct'] = str(e)

    try:
        dup_count_res = conn.execute(text(f"SELECT COUNT(*) FROM (SELECT id FROM public.{t} GROUP BY id HAVING COUNT(*) > 1) s"))
        out['duplicate_id_count'] = int(dup_count_res.scalar() or 0)
    except Exception as e:
        out['duplicate_id_count'] = None
        out['error_duplicate_count'] = str(e)

    # fetch up to 20 duplicate id samples if any
    try:
        if out.get('duplicate_id_count') and out['duplicate_id_count'] > 0:
            rows = list(conn.execute(text(f"SELECT id, COUNT(*) as cnt FROM public.{t} GROUP BY id HAVING COUNT(*) > 1 ORDER BY cnt DESC LIMIT 20")))
            out['duplicate_samples'] = [{'id': str(r[0]), 'count': int(r[1])} for r in rows]
        else:
            out['duplicate_samples'] = []
    except Exception as e:
        out['duplicate_samples'] = []
        out['error_duplicate_samples'] = str(e)

    # verdict: remapping required if duplicate_id_count > 0
    try:
        out['id_remap_required'] = bool(out.get('duplicate_id_count')) and out.get('duplicate_id_count', 0) > 0
    except Exception:
        out['id_remap_required'] = None

    return out

def main():
    results = []
    with engine.connect() as conn:
        for t in TABLES:
            print('Analyzing', t)
            res = analyze_table(conn, t)
            results.append(res)

    # print summary JSON
    print(json.dumps(results, indent=2, default=str))

    # also write to file
    try:
        with open('backend/id_collision_report.json', 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, default=str)
        print('Wrote backend/id_collision_report.json')
    except Exception as e:
        print('Failed to write report file:', e)

if __name__ == '__main__':
    main()
