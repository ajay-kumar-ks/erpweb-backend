"""
Migration script to add new columns to the candidates table.
Run this if the backend startup migration didn't work.

Usage:
  cd backend
  python migrate_candidates.py
"""
import os
import sys
from sqlalchemy import inspect, text, create_engine
from sqlalchemy.types import NullType
from dotenv import load_dotenv

# Load .env
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOTENV_PATH = os.path.join(BASE_DIR, ".env")
load_dotenv(dotenv_path=DOTENV_PATH)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/business_suite_db")

if not DATABASE_URL:
    print("ERROR: DATABASE_URL not found in .env")
    sys.exit(1)

engine = create_engine(DATABASE_URL)

try:
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    if "candidates" not in tables:
        print("Table 'candidates' does not exist yet. Start the backend first to create tables.")
        sys.exit(1)

    cols = {col["name"]: col for col in inspector.get_columns("candidates")}
    print(f"Current columns in 'candidates': {list(cols.keys())}")

    # Migration 1: current_stage from ENUM to VARCHAR
    stage_col = cols.get("current_stage")
    if stage_col and (isinstance(stage_col.get("type"), NullType) or "enum" in str(stage_col.get("type", "")).lower()):
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
            print("✓ Migrated current_stage from ENUM to VARCHAR")

    # Migration 2: Add missing columns
    new_columns = {
        "role_id": "INTEGER REFERENCES roles(id)",
        "pipeline_stages": "JSON",
        "converted_to_employee": "BOOLEAN DEFAULT FALSE",
    }

    for col_name, col_def in new_columns.items():
        if col_name not in cols:
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE candidates ADD COLUMN {col_name} {col_def}"))
                print(f"✓ Added column: {col_name} {col_def}")
        else:
            print(f"  Column '{col_name}' already exists")

    # Verify final state
    final_cols = {col["name"] for col in inspector.get_columns("candidates")}
    expected = {"id", "full_name", "email", "phone", "position_applied", "role_id",
                "experience_years", "current_stage", "pipeline_stages", "status",
                "converted_to_employee", "resume_url", "notes", "created_at", "updated_at"}
    missing = expected - final_cols
    if missing:
        print(f"\n⚠ Still missing columns: {missing}")
    else:
        print("\n✓ All expected columns exist in 'candidates' table")

    print("\nMigration complete. Restart the backend and try again.")

except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)
