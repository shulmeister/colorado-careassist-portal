"""
Update icon column to support longer URLs
"""
from portal_database import db_manager
from sqlalchemy import text

db = db_manager.get_session()

try:
    # Alter the column type from VARCHAR(50) to TEXT
    db.execute(text("ALTER TABLE portal_tools ALTER COLUMN icon TYPE TEXT"))
    db.commit()
    print("✅ Updated icon column to TEXT type")
except Exception as e:
    print(f"❌ Error: {str(e)}")
    db.rollback()
finally:
    db.close()




