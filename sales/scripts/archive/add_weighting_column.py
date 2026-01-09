import os
from sqlalchemy import create_engine, text

# Get database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")

# Handle Heroku postgres:// vs postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Create engine
engine = create_engine(DATABASE_URL)

try:
    with engine.connect() as conn:
        # Add weighting column
        conn.execute(text("""
            ALTER TABLE pipeline_stages 
            ADD COLUMN IF NOT EXISTS weighting FLOAT NOT NULL DEFAULT 1.0
        """))
        conn.commit()
        print("✅ Successfully added weighting column to pipeline_stages table!")
        
except Exception as e:
    print(f"❌ Error adding column: {e}")

