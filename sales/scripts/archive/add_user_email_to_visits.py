"""
Migration script to add user_email column to visits table
Run this once to update the database schema
"""
from sqlalchemy import create_engine, text
import os

# Get database URL from environment
database_url = os.getenv("DATABASE_URL")
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

if not database_url:
    print("ERROR: DATABASE_URL environment variable not set")
    exit(1)

engine = create_engine(database_url)

try:
    with engine.connect() as conn:
        # Check if column already exists
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='visits' AND column_name='user_email'
        """))
        
        if result.fetchone():
            print("✓ Column 'user_email' already exists in visits table")
        else:
            # Add the column
            conn.execute(text("""
                ALTER TABLE visits 
                ADD COLUMN user_email VARCHAR(255)
            """))
            conn.commit()
            print("✓ Successfully added 'user_email' column to visits table")
            
            # Create index
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_visits_user_email 
                ON visits(user_email)
            """))
            conn.commit()
            print("✓ Successfully created index on user_email column")
            
except Exception as e:
    print(f"ERROR: Failed to migrate database: {e}")
    exit(1)

print("✓ Migration completed successfully")

