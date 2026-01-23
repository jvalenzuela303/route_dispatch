"""
Global error handling middleware for FastAPI

Provides consistent error responses for all custom business exceptions
and integrates with FastAPI's exception handling system.
"""

from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError as SQLAlchemyIntegrityError
from typing import Union

from app.exceptions import (
    BusinessRuleViolationError,
    ValidationError,
    PermissionError,
    NotFoundError,
    ConcurrencyError,
    IntegrityError,
    InvalidStateTransitionError,
    InvoiceRequiredError,
    CutoffViolationError,
    InsufficientPermissionsError,
    AdminOverrideRequiredError,
    NotYourRouteError,
    NotYourOrderError,
    InvalidAddressError,
    GeocodingServiceError,
    RouteOptimizationError,
    AuthenticationError,
    InvalidCredentialsError,
    TokenExpiredError,
    InvalidTokenError,
    UserInactiveError,
    UserAlreadyExistsError,
    WeakPasswordError
)


async def business_rule_violation_handler(
    request: Request,
    exc: BusinessRuleViolationError
) -> JSONResponse:
    """
    Handle all business rule violation exceptions

    Returns consistent error response with:
    - error: Error code
    - message: Human-readable message
    - details: Additional context
    - path: Request path where error occurred
    """
    return JSONResponse(
        status_code=exc.http_status,
        content={
            "error": exc.code,
            "message": exc.message,
            "details": exc.details,
            "path": str(request.url.path)
        }
    )


async def validation_error_handler(
    request: Request,
    exc: Union[RequestValidationError, ValidationError]
) -> JSONResponse:
    """
    Handle Pydantic validation errors and custom validation errors

    Formats Pydantic errors into consistent response structure
    """
    if isinstance(exc, RequestValidationError):
        # Pydantic validation error
        errors = []
        for error in exc.errors():
            errors.append({
                "field": ".".join(str(loc) for loc in error["loc"]),
                "message": error["msg"],
                "type": error["type"]
            })

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": {"errors": errors},
                "path": str(request.url.path)
            }
        )
    else:
        # Custom ValidationError
        return await business_rule_violation_handler(request, exc)


async def sqlalchemy_integrity_error_handler(
    request: Request,
    exc: SQLAlchemyIntegrityError
) -> JSONResponse:
    """
    Handle SQLAlchemy integrity constraint violations

    Converts database integrity errors to user-friendly messages
    """
    error_message = str(exc.orig) if hasattr(exc, 'orig') else str(exc)

    # Try to identify common constraint violations
    if 'unique constraint' in error_message.lower():
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "error": "DUPLICATE_ENTRY",
                "message": "A record with this value already exists",
                "details": {"database_error": error_message},
                "path": str(request.url.path)
            }
        )
    elif 'foreign key constraint' in error_message.lower():
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "error": "FOREIGN_KEY_VIOLATION",
                "message": "Cannot perform operation due to related records",
                "details": {"database_error": error_message},
                "path": str(request.url.path)
            }
        )
    else:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "error": "DATABASE_INTEGRITY_ERROR",
                "message": "Database integrity constraint violated",
                "details": {"database_error": error_message},
                "path": str(request.url.path)
            }
        )


async def generic_exception_handler(
    request: Request,
    exc: Exception
) -> JSONResponse:
    """
    Handle unexpected exceptions

    This is the last resort handler for exceptions not caught by
    more specific handlers. In production, should log to monitoring
    service (Sentry, CloudWatch, etc.)
    """
    import traceback
    import logging

    logger = logging.getLogger(__name__)

    # Log full traceback for debugging
    logger.error(
        f"Unhandled exception in {request.method} {request.url.path}",
        exc_info=exc
    )

    # In debug mode, include traceback in response
    from app.config import get_settings
    settings = get_settings()

    error_details = {
        "type": type(exc).__name__,
    }

    if settings.debug:
        error_details["traceback"] = traceback.format_exc()

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected error occurred",
            "details": error_details,
            "path": str(request.url.path)
        }
    )


def register_exception_handlers(app):
    """
    Register all exception handlers with FastAPI application

    Args:
        app: FastAPI application instance

    Usage:
        from app.api.middleware.error_handler import register_exception_handlers

        app = FastAPI()
        register_exception_handlers(app)
    """
    # Business rule violations
    app.add_exception_handler(InvalidStateTransitionError, business_rule_violation_handler)
    app.add_exception_handler(InvoiceRequiredError, business_rule_violation_handler)
    app.add_exception_handler(CutoffViolationError, business_rule_violation_handler)
    app.add_exception_handler(InvalidAddressError, business_rule_violation_handler)
    app.add_exception_handler(GeocodingServiceError, business_rule_violation_handler)
    app.add_exception_handler(RouteOptimizationError, business_rule_violation_handler)

    # Permission errors
    app.add_exception_handler(InsufficientPermissionsError, business_rule_violation_handler)
    app.add_exception_handler(AdminOverrideRequiredError, business_rule_violation_handler)
    app.add_exception_handler(NotYourRouteError, business_rule_violation_handler)
    app.add_exception_handler(NotYourOrderError, business_rule_violation_handler)
    app.add_exception_handler(PermissionError, business_rule_violation_handler)

    # Authentication errors
    app.add_exception_handler(InvalidCredentialsError, business_rule_violation_handler)
    app.add_exception_handler(TokenExpiredError, business_rule_violation_handler)
    app.add_exception_handler(InvalidTokenError, business_rule_violation_handler)
    app.add_exception_handler(UserInactiveError, business_rule_violation_handler)
    app.add_exception_handler(AuthenticationError, business_rule_violation_handler)

    # User management errors
    app.add_exception_handler(UserAlreadyExistsError, business_rule_violation_handler)
    app.add_exception_handler(WeakPasswordError, business_rule_violation_handler)

    # Resource errors
    app.add_exception_handler(NotFoundError, business_rule_violation_handler)
    app.add_exception_handler(ConcurrencyError, business_rule_violation_handler)
    app.add_exception_handler(IntegrityError, business_rule_violation_handler)

    # Validation errors
    app.add_exception_handler(ValidationError, business_rule_violation_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)

    # Database errors
    app.add_exception_handler(SQLAlchemyIntegrityError, sqlalchemy_integrity_error_handler)

    # Generic fallback
    app.add_exception_handler(Exception, generic_exception_handler)

    # Base business rule violation (catches any we missed)
    app.add_exception_handler(BusinessRuleViolationError, business_rule_violation_handler)
