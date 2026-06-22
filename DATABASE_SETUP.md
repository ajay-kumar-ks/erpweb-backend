# Database Setup & Migration Guide

## PostgreSQL Database Configuration

Your database credentials:
- **Host**: us-west-2.db.thenile.dev
- **Port**: 5432
- **Database**: business_suite_db
- **API Host**: https://us-west-2.api.thenile.dev/v2/databases/019ed429-f542-7277-a13f-29f08d50a550

## Setup Instructions

### 1. Update Environment Variables

Edit `backend/.env` and update the DATABASE_URL with your credentials:

```env
DATABASE_URL=postgresql://username:password@us-west-2.db.thenile.dev:5432/business_suite_db
```

Replace `username` and `password` with your actual Nile database credentials.

### 2. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 3. Initialize Database & Seed Data

```bash
# From the backend directory
python seed_db.py
```

This will:
- Create all database tables automatically
- Seed an admin user with credentials:
  - Username: `admin`
  - Password: `secret`

### 4. Run the Server

```bash
uvicorn app.main:app --reload
```

The server will be available at `http://localhost:8000`

## API Endpoints

### Health Check
- **GET** `/api/health` - Check server status

### Authentication
- **POST** `/api/auth/login` - Login with username/password
  ```json
  {
    "username": "admin",
    "password": "secret"
  }
  ```
  Returns: `access_token` and `token_type`

- **GET** `/api/auth/dashboard` - View dashboard (requires token)
  - Header: `Authorization: Bearer <access_token>`

## Database Schema

### Users Table
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(255),
    hashed_password VARCHAR(255) NOT NULL,
    disabled BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Using Alembic for Migrations (Optional)

For version-controlled database migrations:

```bash
# Initialize Alembic (one time)
alembic init migrations

# Create a migration
alembic revision --autogenerate -m "description of change"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1
```

## File Structure

```
backend/
├── .env
├── requirements.txt
├── seed_db.py          # Database initialization & seeding
├── init_db.py          # Database creation utility
├── app/
│   ├── main.py         # FastAPI app entry point
│   ├── core/
│   │   ├── config.py   # Settings from .env
│   │   ├── database.py # SQLAlchemy setup
│   │   ├── base.py     # Base model for all tables
│   │   └── event_bus.py
│   └── modules/
│       └── auth/
│           ├── routers.py     # Login, dashboard endpoints
│           ├── db_models.py   # SQLAlchemy User model
│           ├── models.py      # Pydantic schemas
│           ├── schemas.py     # Request/response models
│           └── utils.py       # Password & JWT utilities
```

## Troubleshooting

### Connection Error
- Verify DATABASE_URL in `.env`
- Check network connectivity to `us-west-2.db.thenile.dev`
- Ensure credentials are correct

### Import Errors
- Run `pip install -r requirements.txt` again
- Check Python version (3.9+ required)

### Database Already Exists
- The `seed_db.py` script checks if admin user exists before creating
- To reset: drop tables and re-run `python seed_db.py`
