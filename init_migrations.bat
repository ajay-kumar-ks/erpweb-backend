@echo off
REM Initialize Alembic migrations
REM Run this script from the backend directory

if exist migrations (
    echo Migrations folder already exists
    exit /b 0
)

echo Initializing Alembic...
alembic init migrations

echo.
echo Alembic initialized. Next steps:
echo 1. Update alembic/env.py to set sqlalchemy.url from settings
echo 2. Run: alembic revision --autogenerate -m "initial migration"
echo 3. Run: alembic upgrade head
