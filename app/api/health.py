"""
Health check endpoint
"""

from fastapi import APIRouter, status
from pydantic import BaseModel
import redis
from sqlalchemy import create_engine, text

from app.config import get_settings


router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Health check response model"""

    status: str
    service: str
    database: str
    redis: str


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Health Check",
    description="Check the health status of the service and its dependencies",
)
async def health_check() -> HealthResponse:
    """
    Health check endpoint that verifies:
    - API service is running
    - Database connection is working
    - Redis connection is working

    Returns:
        HealthResponse with status of all services
    """
    settings = get_settings()

    # Check database connection
    db_status = "disconnected"
    try:
        engine = create_engine(settings.database_url)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            db_status = "connected"
        engine.dispose()
    except Exception as e:
        print(f"Database connection error: {e}")
        db_status = "disconnected"

    # Check Redis connection
    redis_status = "disconnected"
    try:
        redis_client = redis.from_url(settings.redis_url)
        redis_client.ping()
        redis_status = "connected"
        redis_client.close()
    except Exception as e:
        print(f"Redis connection error: {e}")
        redis_status = "disconnected"

    return HealthResponse(
        status="healthy",
        service="claude-logistics",
        database=db_status,
        redis=redis_status,
    )
