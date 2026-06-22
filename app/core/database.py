from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base
from app.core.config import settings
import contextvars

# ContextVar that holds the current request's tenant UUID (or None)
current_tenant: contextvars.ContextVar = contextvars.ContextVar("current_tenant", default=None)

Base = declarative_base()

engine = create_engine(
    settings.DATABASE_URL,
    pool_size=10,
    max_overflow=20,
)


def _checkout_set_nile_tenant(dbapi_conn, connection_record, connection_proxy):
    """
    When a connection is checked out from the pool, set the Nile GUC for tenant
    if a tenant is present in the current context var. This ensures the
    Postgres-side Nile routing/validation sees the tenant for the session.
    """
    try:
        tenant = current_tenant.get()
        cur = dbapi_conn.cursor()
        if tenant:
            cur.execute("SET nile.tenant_id = %s", (str(tenant),))
        else:
            # Clear any previous value so the connection is neutral
            cur.execute("RESET nile.tenant_id")
        cur.close()
    except Exception:
        # Fail-safe: don't raise here — errors will surface during queries
        try:
            cur.close()
        except Exception:
            pass


event.listen(engine, "checkout", _checkout_set_nile_tenant)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
