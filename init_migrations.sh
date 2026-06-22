#!/bin/bash
# Initialize Alembic migrations
# Run this script from the backend directory

if [ -d "migrations" ]; then
    echo "Migrations folder already exists"
    exit 0
fi

echo "Initializing Alembic..."
alembic init migrations

echo ""
echo "Alembic initialized. Next steps:"
echo "1. Update alembic/env.py to set sqlalchemy.url from settings"
echo "2. Run: alembic revision --autogenerate -m \"initial migration\""
echo "3. Run: alembic upgrade head"
