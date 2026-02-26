import logging
import os

from portal_models import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Manage database connections and operations"""

    def __init__(self):
        self.engine = None
        self.SessionLocal = None
        try:
            self._initialize_database()
        except Exception as e:
            logger.warning(f"Database initialization failed, will retry later: {str(e)}")
            # Don't fail the entire app startup

    def _initialize_database(self):
        """Initialize database connection"""
        try:
            # Get database URL from environment
            database_url = os.getenv("DATABASE_URL")

            if not database_url:
                # Fallback to SQLite for local development
                database_url = "sqlite:///./portal.db"
                logger.info("Using SQLite for local development")
            else:
                # Fix PostgreSQL URL format for SQLAlchemy
                if database_url.startswith("postgres://"):
                    database_url = database_url.replace("postgres://", "postgresql+psycopg2://", 1)
                elif database_url.startswith("postgresql://"):
                    database_url = database_url.replace("postgresql://", "postgresql+psycopg2://", 1)

            # Create engine
            if database_url.startswith("sqlite"):
                self.engine = create_engine(
                    database_url,
                    connect_args={"check_same_thread": False},
                    poolclass=StaticPool,
                )
            else:
                self.engine = create_engine(
                    database_url,
                    pool_size=10,
                    max_overflow=20,
                    pool_recycle=3600,
                    pool_pre_ping=True,
                )

            # Create session factory
            self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

            # Create tables (only if they don't exist)
            try:
                Base.metadata.create_all(bind=self.engine)
            except Exception as e:
                logger.warning(f"Tables may already exist: {str(e)}")
                # Try to continue anyway

            logger.info("Database initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize database: {str(e)}")
            raise Exception(f"Database initialization failed: {str(e)}")

    def get_session(self):
        """Get database session"""
        return self.SessionLocal()

    def close(self):
        """Close database connection"""
        if self.engine:
            self.engine.dispose()

# Global database manager instance
db_manager = DatabaseManager()

def get_db():
    """Dependency to get database session"""
    if not db_manager.SessionLocal:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Database not available")

    db = db_manager.get_session()
    try:
        yield db
    finally:
        db.close()

