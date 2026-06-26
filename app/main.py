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
from app.modules.hr.upload import router as hr_upload_router
from app.modules.accounts.routers import router as accounts_router
from app.modules.crm.routers import router as crm_router, leads_router as crm_leads_router, pipelines_router as crm_pipelines_router, clients_router as crm_clients_router, ai_router as crm_ai_router
from app.modules.tasks.routers import router as tasks_router
from app.modules.tasks.upload import router as upload_router
from app.modules.tasks.scheduler import run_overdue_scheduler
from app.modules.tasks.event_handlers import register_handlers
from app.modules.recruitment.routers import router as recruitment_router
from app.modules.payments.routers import router as payments_router
from app.modules.accounts.salary_event_handlers import register_salary_event_handlers

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
app.include_router(hr_upload_router, prefix="/hr", tags=["hr"])
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
app.include_router(hr_upload_router, prefix="/api/hr", tags=["hr"])
app.include_router(accounts_router, prefix="/api/accounts", tags=["accounts"])
app.include_router(crm_router, prefix="/api/crm", tags=["crm"])
app.include_router(crm_leads_router, prefix="/api/crm", tags=["crm"])
app.include_router(crm_pipelines_router, prefix="/api/crm", tags=["crm"])
app.include_router(crm_clients_router, prefix="/api/crm", tags=["crm"])
app.include_router(recruitment_router, prefix="/api/recruitment", tags=["recruitment"])
app.include_router(upload_router, prefix="/api/tasks", tags=["tasks"])
app.include_router(crm_clients_router, prefix="/api/crm", tags=["crm"])
app.include_router(crm_ai_router, prefix="/api/crm", tags=["crm"])
app.include_router(payments_router, prefix="/payments", tags=["payments"])
app.include_router(payments_router, prefix="/api/payments", tags=["payments"])

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
        # Create tables immediately (fast)
        Base.metadata.create_all(bind=engine)
        print("[OK] Database tables created")
        
        # Run heavy migrations in background to avoid blocking startup
        asyncio.create_task(_run_database_migrations())
        
    except Exception as e:
        print(f"[WARN] Database connection warning: {str(e)[:100]}")
        print("[OK] Server started (database connection failed - check your DATABASE_URL credentials in .env)")

    register_event_handlers()
    register_salary_event_handlers()

    # Seed default chart of accounts if missing (e.g. Salary Payable 2100)
    from app.core.database import SessionLocal as _SeedSession
    from app.modules.accounts.services import seed_default_chart_of_accounts
    _seed_db = _SeedSession()
    try:
        seed_default_chart_of_accounts(_seed_db)
    finally:
        _seed_db.close()

    event_bus.connect()

    # Register tasks module event handlers
    register_handlers()

    # Start overdue task scheduler
    asyncio.create_task(run_overdue_scheduler())


async def _run_database_migrations():
    """Run expensive database migrations in background after startup completes"""
    try:
        import time
        await asyncio.sleep(0.5)  # Brief delay to let app fully start
        
        inspector = inspect(engine)
        if 'contacts' in inspector.get_table_names():
            columns = [col['name'] for col in inspector.get_columns('contacts')]
            if 'deleted_at' not in columns:
                with engine.begin() as conn:
                    conn.execute(text('ALTER TABLE contacts ADD COLUMN deleted_at TIMESTAMP NULL'))
                    print('✓ Added missing contacts.deleted_at column')

        # Migration: employees table — add full_name & email columns, make user_id nullable
        if 'employees' in inspector.get_table_names():
            emp_cols = {col['name'] for col in inspector.get_columns('employees')}
            if 'full_name' not in emp_cols:
                with engine.begin() as conn:
                    conn.execute(text('ALTER TABLE employees ADD COLUMN full_name VARCHAR(255)'))
                    print('✓ Added employees.full_name')
            if 'email' not in emp_cols:
                with engine.begin() as conn:
                    conn.execute(text('ALTER TABLE employees ADD COLUMN email VARCHAR(255)'))
                    print('✓ Added employees.email')

        # ── Recruitment schema migration ──
        # The recruitment tables were refactored from role-based to department-based pipelines.
        # Old columns (role_id, position_applied) need to be replaced with department_id.

        # Pipeline templates: role_id → department_id
        if 'pipeline_templates' in inspector.get_table_names():
            pt_cols = {col['name'] for col in inspector.get_columns('pipeline_templates')}
            if 'department_id' not in pt_cols:
                with engine.begin() as conn:
                    conn.execute(text('ALTER TABLE pipeline_templates ADD COLUMN department_id INTEGER REFERENCES departments(id)'))
                    print('✓ Added pipeline_templates.department_id')

            # Drop the old role_id column entirely (it had NOT NULL constraint which blocks inserts)
            if 'role_id' in pt_cols:
                try:
                    with engine.begin() as conn:
                        conn.execute(text('ALTER TABLE pipeline_templates DROP COLUMN IF EXISTS role_id'))
                        print('✓ Dropped old pipeline_templates.role_id column')
                except Exception as e:
                    print(f'[INFO] Could not drop pipeline_templates.role_id: {e}')

            # Clean up old rows with NULL department_id (they were from the role-based system)
            try:
                with engine.begin() as conn:
                    conn.execute(text("DELETE FROM pipeline_templates WHERE department_id IS NULL"))
                    print('✓ Cleaned up old pipeline_templates rows with NULL department_id')
            except Exception:
                pass

        # Candidates: drop position_applied, role_id → add department_id
        if 'candidates' in inspector.get_table_names():
            cols = {col['name']: col for col in inspector.get_columns('candidates')}

            # Add department_id (replaces position_applied & role_id)
            if 'department_id' not in cols:
                with engine.begin() as conn:
                    conn.execute(text('ALTER TABLE candidates ADD COLUMN department_id INTEGER REFERENCES departments(id)'))
                    print('✓ Added candidates.department_id')

            # Remove position_applied (no longer needed)
            if 'position_applied' in cols:
                try:
                    with engine.begin() as conn:
                        conn.execute(text('ALTER TABLE candidates DROP COLUMN position_applied'))
                        print('✓ Dropped candidates.position_applied (old field)')
                except Exception as e:
                    print(f'[INFO] Could not drop candidates.position_applied: {e}')

            # Remove role_id from candidates (moved to department-based)
            if 'role_id' in cols:
                try:
                    with engine.begin() as conn:
                        conn.execute(text('ALTER TABLE candidates DROP COLUMN IF EXISTS role_id'))
                        print('✓ Dropped candidates.role_id (old field)')
                except Exception as e:
                    print(f'[INFO] Could not drop candidates.role_id: {e}')

            # Add other new columns if they don't exist
            new_columns = {
                'pipeline_stages': 'JSON',
                'converted_to_employee': 'BOOLEAN DEFAULT FALSE',
            }
            for col_name, col_def in new_columns.items():
                if col_name not in cols:
                    with engine.begin() as conn:
                        conn.execute(text(f'ALTER TABLE candidates ADD COLUMN {col_name} {col_def}'))
                        print(f'✓ Added candidates.{col_name}')

            # Migrate current_stage from ENUM to VARCHAR if still needed
            stage_col = cols.get('current_stage')
            if stage_col:
                type_str = str(stage_col.get('type', '')).lower()
                is_enum = isinstance(stage_col.get('type'), NullType) or 'enum' in type_str
                if is_enum:
                    try:
                        with engine.begin() as conn:
                            conn.execute(text("ALTER TABLE candidates ALTER COLUMN current_stage TYPE VARCHAR(100)"))
                            print('✓ Migrated candidates.current_stage from ENUM to VARCHAR (type alter)')
                    except Exception as mig_e:
                        print(f'[INFO] ALTER COLUMN TYPE not supported: {mig_e}')
                        # Fallback: add missing values to the ENUM type
                        try:
                            required_stages = [
                                'Applied', 'Screening', 'Interview', 'Technical Test',
                                'Technical Interview', 'HR Interview', 'Selected',
                                'Rejected', 'Onboarded', 'Portfolio Review',
                                'Design Assignment', 'Design Interview', 'Communication Test',
                                'HR Manager Interview',
                            ]
                            # Use AUTOCOMMIT so each ALTER TYPE runs in its own transaction
                            with engine.connect().execution_options(isolation_level='AUTOCOMMIT') as conn:
                                for stage in required_stages:
                                    try:
                                        conn.execute(text(
                                            f"ALTER TYPE recruitmentstage ADD VALUE IF NOT EXISTS '{stage}'"
                                        ))
                                    except Exception:
                                        pass  # value may already exist or not supported
                            print('✓ Added required values to recruitmentstage ENUM')
                        except Exception as enum_e:
                            print(f'[SKIP] ENUM migration also not supported: {enum_e}')
                            print('[HINT] The column type will remain as-is.')

        Base.metadata.create_all(bind=engine)
        print("[OK] Database tables created")
    except Exception as e:
        err_msg = str(e)[:200]
        if 'connection' in err_msg.lower() or 'could not connect' in err_msg.lower():
            print(f"[WARN] Database connection failed: {err_msg}")
            print("[OK] Server started (database connection failed - check your DATABASE_URL credentials in .env)")
        else:
            print(f"[WARN] Startup migration issue: {err_msg}")
            print("[OK] Server started (database tables may be incomplete)")

    register_event_handlers()
    register_salary_event_handlers()

    # Seed default chart of accounts if missing (e.g. Salary Payable 2100)
    from app.core.database import SessionLocal as _SeedSession
    from app.modules.accounts.services import seed_default_chart_of_accounts
    _seed_db = _SeedSession()
    try:
        seed_default_chart_of_accounts(_seed_db)
    finally:
        _seed_db.close()

    event_bus.connect()

    # Register tasks module event handlers
    register_handlers()

    # Start overdue task scheduler
    asyncio.create_task(run_overdue_scheduler())

    # NOTE: Removed accidental indented block that caused IndentationError.
    # Any additional background migration logic should live inside _run_database_migrations().

    
@app.on_event("shutdown")
async def shutdown_event():
    event_bus.disconnect()



