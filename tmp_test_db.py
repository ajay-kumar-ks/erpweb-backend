from app.core.config import settings
from sqlalchemy import create_engine, text
engine = create_engine(settings.DATABASE_URL, echo=False)
with engine.connect() as conn:
    print('SCHEMA', conn.execute(text('select current_schema()')).scalar())
    print('VERSION', conn.execute(text('select version()')).scalar())
    print('SELECT1', conn.execute(text('select 1')).scalar())
    print('BUDGETS_EXISTS', conn.execute(text("select exists(select 1 from information_schema.tables where table_schema=current_schema() and table_name='budgets')")).scalar())
    print('BILLS_EXISTS', conn.execute(text("select exists(select 1 from information_schema.tables where table_schema=current_schema() and table_name='bills')")).scalar())
    print('INVOICES_EXISTS', conn.execute(text("select exists(select 1 from information_schema.tables where table_schema=current_schema() and table_name='invoices')")).scalar())
