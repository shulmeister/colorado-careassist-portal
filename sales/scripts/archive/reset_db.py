import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

def reset_database():
    """Drop and recreate all tables"""
    try:
        # Get database URL
        database_url = os.getenv("DATABASE_URL")
        
        if not database_url:
            print("No DATABASE_URL found")
            return
        
        # Fix PostgreSQL URL format
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql+psycopg2://", 1)
        elif database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+psycopg2://", 1)
        
        # Create engine
        engine = create_engine(database_url)
        
        # Drop all tables
        with engine.connect() as conn:
            conn.execute(text("DROP TABLE IF EXISTS visits CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS time_entries CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS contacts CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS analytics_cache CASCADE"))
            conn.commit()
        
        print("✅ All tables dropped successfully")
        
        # Recreate tables
        from models import Base
        Base.metadata.create_all(bind=engine)
        
        print("✅ All tables recreated successfully")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    reset_database()

