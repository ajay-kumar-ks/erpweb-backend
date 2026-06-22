"""
Migration script to add 'creates_client' column to Phase table
Run this script to update the database schema:
  python migrate_add_creates_client.py
"""

from sqlalchemy import text
from app.core.database import engine


def migrate():
    """Add creates_client column to phases table if it doesn't exist"""
    with engine.connect() as connection:
        try:
            # Check if column already exists
            result = connection.execute(
                text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'phases' 
                    AND column_name = 'creates_client'
                """)
            )
            
            if result.fetchone():
                print("✓ 'creates_client' column already exists in phases table")
                return
            
            # Add the column if it doesn't exist
            connection.execute(
                text("""
                    ALTER TABLE phases 
                    ADD COLUMN creates_client BOOLEAN DEFAULT FALSE
                """)
            )
            connection.commit()
            print("✓ Successfully added 'creates_client' column to phases table")
            
        except Exception as e:
            print(f"✗ Error during migration: {e}")
            connection.rollback()
            raise


if __name__ == "__main__":
    print("Starting migration...")
    migrate()
    print("Migration complete!")
