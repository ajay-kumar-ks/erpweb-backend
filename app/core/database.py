from sqlalchemy import create_engine
from sqlalchemy import event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base
from app.core.config import settings
import contextvars
import time
import logging

logger = logging.getLogger(__name__)

# ContextVar that holds the current request's tenant UUID (or None)
current_tenant: contextvars.ContextVar = contextvars.ContextVar("current_tenant", default=None)

Base = declarative_base()

engine = create_engine(
    settings.DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=1800,
)


# Development helper: set Nile tenant GUC on new connections so dev writes
# specify a tenant implicitly. This is safe for development only.
if settings.ENVIRONMENT == 'development':
    @event.listens_for(engine, 'connect')
    def _set_nile_tenant(dbapi_connection, connection_record):
        try:
            with dbapi_connection.cursor() as cur:
                try:
                    cur.execute("ROLLBACK")
                except Exception:
                    pass
                try:
                    cur.execute("SELECT set_config('nile.tenant_id', '1', false)")
                except Exception:
                    cur.execute("SET nile.tenant_id = 1")
        except Exception:
            # ignore if DB doesn't support Nile or SET fails
            try:
                dbapi_connection.rollback()
            except Exception:
                pass

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)



# Log long-running queries for monitoring
@event.listens_for(engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    context._query_start_time = time.time()


@event.listens_for(engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    total = time.time() - getattr(context, '_query_start_time', time.time())
    # Log warnings for queries slower than 0.5s and errors for >1s
    if total >= 1.0:
        logger.warning(f"SLOW QUERY {total:.3f}s: {statement[:200]}")
    elif total >= 0.5:
        logger.info(f"Slow query {total:.3f}s: {statement[:200]}")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
def commit_or_rollback(db: Session):
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
