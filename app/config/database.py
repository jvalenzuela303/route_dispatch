"""
Database configuration and session management

This module provides:
- SQLAlchemy engine configuration
- Session factory for database connections
- FastAPI dependency for dependency injection
- Connection pooling settings
"""

from typing import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool

from app.config.settings import get_settings


settings = get_settings()

# Create SQLAlchemy engine with connection pooling
# Connection pool settings:
# - pool_size: Number of permanent connections to maintain
# - max_overflow: Number of connections that can be created beyond pool_size
# - pool_pre_ping: Verify connections are alive before using them
# - pool_recycle: Recycle connections after this many seconds (prevents stale connections)
engine = create_engine(
    settings.database_url,
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=settings.debug,  # Log SQL queries in debug mode
)


# Enable PostGIS extension on connection
# This ensures PostGIS functions are available for geographic queries
@event.listens_for(engine, "connect")
def enable_postgis(dbapi_conn, connection_record):
    """
    Enable PostGIS extension on new connections

    This listener runs whenever a new database connection is established,
    ensuring PostGIS spatial functions are available.
    """
    cursor = dbapi_conn.cursor()
    try:
        # Enable PostGIS extension (idempotent - safe to run multiple times)
        cursor.execute("CREATE EXTENSION IF NOT EXISTS postgis")
        dbapi_conn.commit()
    except Exception as e:
        # Log the error but don't fail - extension might already exist
        # or user might not have permissions (will fail later if PostGIS is needed)
        print(f"Warning: Could not enable PostGIS: {e}")
    finally:
        cursor.close()


# Session factory
# autocommit=False: Explicit commit required (recommended for safety)
# autoflush=False: Control when changes are flushed to database
# bind=engine: Bind sessions to our configured engine
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency for database sessions

    Provides a database session for each request and ensures it's properly
    closed after the request completes, even if an error occurs.

    Usage in FastAPI endpoints:
        @app.get("/users")
        def get_users(db: Session = Depends(get_db)):
            return db.query(User).all()

    Yields:
        Database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """
    Context manager for database sessions

    Use this in scripts or non-FastAPI contexts where you need
    a database session with automatic cleanup.

    Usage:
        with get_db_context() as db:
            users = db.query(User).all()
            # Session automatically closed when context exits

    Yields:
        Database session
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()  # Auto-commit on success
    except Exception:
        db.rollback()  # Rollback on error
        raise
    finally:
        db.close()


def init_db():
    """
    Initialize database tables

    Creates all tables defined in SQLAlchemy models.
    Note: In production, use Alembic migrations instead.
    This is mainly for testing or initial development setup.
    """
    from app.models.base import Base
    Base.metadata.create_all(bind=engine)


def drop_db():
    """
    Drop all database tables

    WARNING: This permanently deletes all data!
    Only use in development/testing environments.
    """
    from app.models.base import Base
    Base.metadata.drop_all(bind=engine)
