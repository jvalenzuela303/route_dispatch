"""
Database session dependency for FastAPI
"""

from typing import Generator
from sqlalchemy.orm import Session

from app.config.database import SessionLocal


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency for database session

    Yields:
        SQLAlchemy database session

    Usage:
        @app.get("/endpoint")
        async def endpoint(db: Session = Depends(get_db)):
            # Use db session here
            pass
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
