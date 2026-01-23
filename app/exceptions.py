"""
Custom exceptions for business logic validation

This module defines all custom exceptions used throughout the application
to handle business rule violations, validation errors, and permission issues.

All exceptions follow the pattern:
- code: Unique error code for client handling
- message: Human-readable error message
- http_status: Suggested HTTP status code for API responses
"""

from typing import Optional


class BusinessRuleViolationError(Exception):
    """Base exception for all business rule violations"""

    def __init__(
        self,
        code: str,
        message: str,
        http_status: int = 400,
        details: Optional[dict] = None
    ):
        """
        Initialize business rule violation

        Args:
            code: Unique error code (e.g., 'INVOICE_REQUIRED_FOR_ROUTING')
            message: Human-readable error message
            http_status: Suggested HTTP status code
            details: Additional context information
        """
        self.code = code
        self.message = message
        self.http_status = http_status
        self.details = details or {}
        super().__init__(message)

    def to_dict(self) -> dict:
        """Convert exception to dictionary for API responses"""
        return {
            'code': self.code,
            'message': self.message,
            'details': self.details
        }


class ValidationError(BusinessRuleViolationError):
    """Raised when data validation fails"""

    def __init__(self, code: str, message: str, details: Optional[dict] = None):
        super().__init__(
            code=code,
            message=message,
            http_status=400,
            details=details
        )


class PermissionError(BusinessRuleViolationError):
    """Raised when user lacks required permissions"""

    def __init__(self, code: str, message: str, details: Optional[dict] = None):
        super().__init__(
            code=code,
            message=message,
            http_status=403,
            details=details
        )


class NotFoundError(BusinessRuleViolationError):
    """Raised when requested resource does not exist"""

    def __init__(self, code: str, message: str, details: Optional[dict] = None):
        super().__init__(
            code=code,
            message=message,
            http_status=404,
            details=details
        )


class ConcurrencyError(BusinessRuleViolationError):
    """Raised when concurrent modification is detected"""

    def __init__(self, code: str, message: str, details: Optional[dict] = None):
        super().__init__(
            code=code,
            message=message,
            http_status=409,
            details=details
        )


class IntegrityError(BusinessRuleViolationError):
    """Raised when database integrity constraint is violated"""

    def __init__(self, code: str, message: str, details: Optional[dict] = None):
        super().__init__(
            code=code,
            message=message,
            http_status=409,
            details=details
        )


# Specific business rule exceptions for common cases

class InvalidStateTransitionError(ValidationError):
    """Raised when order state transition is invalid"""

    def __init__(self, from_status: str, to_status: str):
        super().__init__(
            code='INVALID_STATE_TRANSITION',
            message=f'Cannot transition from {from_status} to {to_status}',
            details={
                'from_status': from_status,
                'to_status': to_status
            }
        )


class InvoiceRequiredError(ValidationError):
    """Raised when order requires invoice but doesn't have one"""

    def __init__(self, order_id: Optional[str] = None):
        super().__init__(
            code='INVOICE_REQUIRED_FOR_ROUTING',
            message='Order must have an invoice before routing',
            details={'order_id': order_id} if order_id else {}
        )


class CutoffViolationError(ValidationError):
    """Raised when cutoff time rules are violated"""

    def __init__(self, requested_date: str, calculated_date: str):
        super().__init__(
            code='CUTOFF_VIOLATION',
            message=f'Requested delivery {requested_date} violates cutoff rules. Calculated: {calculated_date}',
            details={
                'requested_date': requested_date,
                'calculated_date': calculated_date
            }
        )


class InsufficientPermissionsError(PermissionError):
    """Raised when user lacks required role permissions"""

    def __init__(self, action: str, user_role: str, required_role: Optional[str] = None):
        message = f"Role '{user_role}' cannot execute '{action}'"
        if required_role:
            message += f" (requires '{required_role}')"

        super().__init__(
            code='INSUFFICIENT_PERMISSIONS',
            message=message,
            details={
                'action': action,
                'user_role': user_role,
                'required_role': required_role
            }
        )


class AdminOverrideRequiredError(PermissionError):
    """Raised when admin override is required"""

    def __init__(self, action: str):
        super().__init__(
            code='ADMIN_OVERRIDE_REQUIRED',
            message=f'Action {action} requires Administrator authorization',
            details={'action': action}
        )


class NotYourRouteError(PermissionError):
    """Raised when repartidor tries to access order not in their route"""

    def __init__(self):
        super().__init__(
            code='NOT_YOUR_ROUTE',
            message='You can only access orders in your assigned routes'
        )


class NotYourOrderError(PermissionError):
    """Raised when vendedor tries to access order they didn't create"""

    def __init__(self):
        super().__init__(
            code='NOT_YOUR_ORDER',
            message='You can only access orders you created'
        )


class InvalidAddressError(BusinessRuleViolationError):
    """Raised when address is not valid for geocoding"""

    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(
            code='INVALID_ADDRESS',
            message=message,
            http_status=400,
            details=details or {}
        )


class GeocodingServiceError(BusinessRuleViolationError):
    """Raised when geocoding service communication fails"""

    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(
            code='GEOCODING_SERVICE_ERROR',
            message=message,
            http_status=503,
            details=details or {}
        )


class RouteOptimizationError(BusinessRuleViolationError):
    """Raised when route optimization fails"""

    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(
            code='ROUTE_OPTIMIZATION_ERROR',
            message=message,
            http_status=400,
            details=details or {}
        )


# Authentication and Authorization Exceptions

class AuthenticationError(BusinessRuleViolationError):
    """Base exception for authentication errors"""

    def __init__(self, code: str, message: str, details: Optional[dict] = None):
        super().__init__(
            code=code,
            message=message,
            http_status=401,
            details=details
        )


class InvalidCredentialsError(AuthenticationError):
    """Raised when login credentials are invalid"""

    def __init__(self, message: str = "Invalid username or password"):
        super().__init__(
            code='INVALID_CREDENTIALS',
            message=message
        )


class TokenExpiredError(AuthenticationError):
    """Raised when JWT token has expired"""

    def __init__(self, message: str = "Token has expired"):
        super().__init__(
            code='TOKEN_EXPIRED',
            message=message
        )


class InvalidTokenError(AuthenticationError):
    """Raised when JWT token is invalid or malformed"""

    def __init__(self, message: str = "Invalid token"):
        super().__init__(
            code='INVALID_TOKEN',
            message=message
        )


class UserInactiveError(AuthenticationError):
    """Raised when user account is deactivated"""

    def __init__(self, message: str = "User account is deactivated"):
        super().__init__(
            code='USER_INACTIVE',
            message=message
        )


class UserAlreadyExistsError(BusinessRuleViolationError):
    """Raised when attempting to create user with duplicate username/email"""

    def __init__(self, field: str, value: str):
        super().__init__(
            code='USER_ALREADY_EXISTS',
            message=f"User with {field} '{value}' already exists",
            http_status=409,
            details={'field': field, 'value': value}
        )


class WeakPasswordError(ValidationError):
    """Raised when password doesn't meet security requirements"""

    def __init__(self, message: str = "Password does not meet security requirements"):
        super().__init__(
            code='WEAK_PASSWORD',
            message=message
        )
