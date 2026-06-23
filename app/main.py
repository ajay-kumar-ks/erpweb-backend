import os
import asyncio
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text
from sqlalchemy.types import NullType
from app.core.config import settings
from app.core.event_bus import event_bus
from app.core.event_handlers import register_event_handlers
from app.core.database import engine
from app.core.base import Base
import logging
import time
from app.modules.auth.routers import router as auth_router
from app.modules.hr.routers import router as hr_router
from app.modules.accounts.routers import router as accounts_router
from app.modules.crm.routers import router as crm_router, leads_router as crm_leads_router, pipelines_router as crm_pipelines_router, clients_router as crm_clients_router, ai_router as crm_ai_router
from app.modules.tasks.routers import router as tasks_router
from app.modules.tasks.upload import router as upload_router
from app.modules.tasks.scheduler import run_overdue_scheduler
from app.modules.tasks.event_handlers import register_handlers
from app.modules.recruitment.routers import router as recruitment_router

app = FastAPI(title="Business Suite Backend", version="0.1.0")

logger = logging.getLogger(__name__)


@app.middleware("http")
async def log_request_time(request, call_next):
    start = time.time()
    response = await call_next(request)
    total = (time.time() - start) * 1000.0
    if total >= 1000:
        logger.warning(f"Slow request {request.method} {request.url.path} took {total:.0f}ms")
    elif total >= 500:
        logger.info(f"Slow request {request.method} {request.url.path} took {total:.0f}ms")
    return response

# CORS Middleware must be added FIRST (middleware is applied in reverse order)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.ALLOWED_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Then add other middleware


app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(tasks_router, prefix="/tasks", tags=["tasks"])
app.include_router(hr_router, prefix="/hr", tags=["hr"])
app.include_router(accounts_router, prefix="/accounts", tags=["accounts"])
app.include_router(crm_router, prefix="/crm", tags=["crm"])
app.include_router(crm_leads_router, prefix="/crm", tags=["crm"])
app.include_router(crm_pipelines_router, prefix="/crm", tags=["crm"])
app.include_router(crm_clients_router, prefix="/crm", tags=["crm"])
app.include_router(upload_router, prefix="/tasks", tags=["tasks"])
app.include_router(recruitment_router, prefix="/recruitment", tags=["recruitment"])

# Also expose same API under /api/* so frontend can use /api prefixes
app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(tasks_router, prefix="/api/tasks", tags=["tasks"])
app.include_router(hr_router, prefix="/api/hr", tags=["hr"])
app.include_router(accounts_router, prefix="/api/accounts", tags=["accounts"])
app.include_router(crm_router, prefix="/api/crm", tags=["crm"])
app.include_router(crm_leads_router, prefix="/api/crm", tags=["crm"])
app.include_router(crm_pipelines_router, prefix="/api/crm", tags=["crm"])
app.include_router(crm_clients_router, prefix="/api/crm", tags=["crm"])
app.include_router(recruitment_router, prefix="/api/recruitment", tags=["recruitment"])
app.include_router(crm_clients_router, prefix="/api/crm", tags=["crm"])
app.include_router(crm_ai_router, prefix="/api/crm", tags=["crm"])

# Serve uploaded files
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "environment": settings.ENVIRONMENT}


@app.on_event("startup")
async def startup_event():
    try:
        inspector = inspect(engine)
        if 'contacts' in inspector.get_table_names():
            columns = [col['name'] for col in inspector.get_columns('contacts')]
            if 'deleted_at' not in columns:
                with engine.begin() as conn:
                    conn.execute(text('ALTER TABLE contacts ADD COLUMN deleted_at TIMESTAMP NULL'))
                    print('✓ Added missing contacts.deleted_at column')

        # Migration: candidates table — add new columns and migrate current_stage from ENUM to VARCHAR
        if 'candidates' in inspector.get_table_names():
            cols = {col['name']: col for col in inspector.get_columns('candidates')}

            # Add new columns if they don't exist (create_all cannot add cols to existing tables)
            new_columns = {
                'role_id': 'INTEGER REFERENCES roles(id)',
                'pipeline_stages': 'JSON',
                'converted_to_employee': 'BOOLEAN DEFAULT FALSE',
            }
            for col_name, col_def in new_columns.items():
                if col_name not in cols:
                    with engine.begin() as conn:
                        conn.execute(text(f'ALTER TABLE candidates ADD COLUMN {col_name} {col_def}'))
                        print(f'✓ Added candidates.{col_name}')

            # Migrate current_stage from ENUM to VARCHAR if still needed
            # (We just try the ALTER; if it fails the column is already VARCHAR)
            stage_col = cols.get('current_stage')
            if stage_col:
                type_str = str(stage_col.get('type', '')).lower()
                # The PostgreSQL ENUM type is named 'recruitmentstage' — contains no 'enum' substring.
                # Check if the column type is NullType (SQLAlchemy's marker for unrecognized types)
                is_enum = isinstance(stage_col.get('type'), NullType) or 'enum' in type_str
                if is_enum:
                    with engine.begin() as conn:
                        conn.execute(text("ALTER TABLE candidates ALTER COLUMN current_stage TYPE VARCHAR(100) USING current_stage::text"))
                        conn.execute(text("ALTER TABLE candidates ALTER COLUMN current_stage SET DEFAULT 'Applied'"))
                        conn.execute(text("UPDATE candidates SET current_stage = 'Applied' WHERE current_stage = 'APPLIED'"))
                        conn.execute(text("UPDATE candidates SET current_stage = 'Screening' WHERE current_stage = 'SCREENING'"))
                        conn.execute(text("UPDATE candidates SET current_stage = 'Interview' WHERE current_stage = 'INTERVIEW'"))
                        conn.execute(text("UPDATE candidates SET current_stage = 'Technical Round' WHERE current_stage = 'TECHNICAL_ROUND'"))
                        conn.execute(text("UPDATE candidates SET current_stage = 'HR Round' WHERE current_stage = 'HR_ROUND'"))
                        conn.execute(text("UPDATE candidates SET current_stage = 'Selected' WHERE current_stage = 'SELECTED'"))
                        conn.execute(text("UPDATE candidates SET current_stage = 'Rejected' WHERE current_stage = 'REJECTED'"))
                        conn.execute(text("UPDATE candidates SET current_stage = 'Onboarded' WHERE current_stage = 'ONBOARDED'"))
                        print('✓ Migrated candidates.current_stage from ENUM to VARCHAR')

        Base.metadata.create_all(bind=engine)
        print("[OK] Database tables created")

    except Exception as e:
        print(f"[WARN] Database connection warning: {str(e)[:100]}")
        print("[OK] Server started (database connection failed - check your DATABASE_URL credentials in .env)")

    register_event_handlers()
    event_bus.connect()

    # Register tasks module event handlers
    register_handlers()

    # Start overdue task scheduler
    asyncio.create_task(run_overdue_scheduler())


@app.on_event("shutdown")
async def shutdown_event():
    event_bus.disconnect()

