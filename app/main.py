"""
Claude Logistics API - Main FastAPI Application
Sistema de gestión de logística para botillería en Rancagua, Chile
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.health import router as health_router
from app.api.routes.auth import router as auth_router
from app.api.routes.users import router as users_router
from app.api.routes.orders import router as orders_router
from app.api.routes.invoices import router as invoices_router
from app.api.routes.delivery_routes import router as delivery_routes_router
from app.api.routes.reports import router as reports_router
from app.api.middleware.error_handler import register_exception_handlers
from app.config import get_settings


def create_application() -> FastAPI:
    """
    Create and configure the FastAPI application instance

    Returns:
        Configured FastAPI application
    """
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Sistema de gestión de logística y optimización de rutas para botillería en Rancagua, Chile",
        debug=settings.debug,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(users_router)
    app.include_router(orders_router)
    app.include_router(invoices_router)
    app.include_router(delivery_routes_router)
    app.include_router(reports_router)

    # Root endpoint
    @app.get("/", tags=["root"])
    async def root():
        """Root endpoint with API information"""
        return JSONResponse(
            content={
                "message": "Claude Logistics API - Rancagua Bottlery",
                "version": settings.app_version,
                "status": "running",
                "docs": "/docs",
                "redoc": "/redoc",
                "health": "/health",
                "description": "Sistema de gestión logística y optimización de rutas",
                "endpoints": {
                    "orders": "/api/orders",
                    "invoices": "/api/invoices",
                    "routes": "/api/routes",
                    "reports": "/api/reports",
                    "auth": "/api/auth",
                    "users": "/api/users"
                }
            }
        )

    # Register exception handlers
    register_exception_handlers(app)

    return app


# Create the application instance
app = create_application()


# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """Actions to perform on application startup"""
    settings = get_settings()
    print(f"Starting {settings.app_name} v{settings.app_version}")
    print(f"Debug mode: {settings.debug}")


@app.on_event("shutdown")
async def shutdown_event():
    """Actions to perform on application shutdown"""
    print("Shutting down Claude Logistics API")
