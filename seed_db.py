import sys
sys.stdout.reconfigure(encoding='utf-8')

from app.core.database import SessionLocal, engine
from app.core.base import Base
from app.modules.auth.db_models import User as UserDB
from app.modules.auth.utils import get_password_hash


def init_db_with_seed():
    """Create all database tables and seed with initial admin user"""
    
    import sqlalchemy as sa
    inspector = sa.inspect(engine)
    existing = inspector.get_table_names()
    
    # Create all tables that don't exist yet
    Base.metadata.create_all(bind=engine)
    print("Database tables checked/created. Tables in DB:", len(inspector.get_table_names()))
    
    db = SessionLocal()
    try:
        # Check if admin user exists
        admin = db.query(UserDB).filter(UserDB.username == "admin").first()
        
        if not admin:
            admin_user = UserDB(
                username="admin",
                email="admin@example.com",
                full_name="Admin User",
                hashed_password=get_password_hash("admin"),
                disabled=False,
                is_admin=True,
            )
            db.add(admin_user)
            db.commit()
            db.refresh(admin_user)
            print("Admin user created (username: admin, password: admin)")
        else:
            print("Admin user already exists")
            
    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    init_db_with_seed()


if __name__ == "__main__":
    init_db_with_seed()
