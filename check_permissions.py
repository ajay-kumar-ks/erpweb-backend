from sqlalchemy import create_engine, text
from app.core.config import settings

engine = create_engine(settings.DATABASE_URL)
with engine.connect() as conn:
    user = conn.execute(text("SELECT current_user")).scalar()
    print(f"USER={user}")
    for table in ['public.budgets', 'public.invoices', 'public.bills']:
        query = text(f"SELECT has_table_privilege(current_user, '{table}', 'ALTER')")
        has_alter = conn.execute(query).scalar()
        print(f"{table}: ALTER={has_alter}")
