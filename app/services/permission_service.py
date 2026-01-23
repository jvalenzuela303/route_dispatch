"""
Permission service for RBAC (Role-Based Access Control)

Implements business rules BR-014, BR-015, BR-016, BR-017 for managing
permissions based on user roles.

Permission matrix:
- Administrador: Full access + override capabilities
- Encargado de Bodega: Route management + order management
- Vendedor: Create orders/invoices (own orders only for viewing)
- Repartidor: View assigned routes + update delivery status
"""

from typing import Optional, Any
import uuid

from sqlalchemy.orm import Session

from app.models.models import User, Order, Route
from app.models.enums import AuditResult
from app.exceptions import (
    InsufficientPermissionsError,
    NotYourOrderError,
    NotYourRouteError
)


class PermissionService:
    """
    Centralized RBAC permission service

    All permission checks should go through this service to ensure consistency
    """

    # Permission matrix: action -> allowed_roles
    PERMISSIONS = {
        # Order operations (BR-014)
        'create_order': {
            'allowed_roles': ['Administrador', 'Encargado de Bodega', 'Vendedor'],
            'scope': 'all'
        },
        'view_order': {
            'allowed_roles': ['Administrador', 'Encargado de Bodega', 'Vendedor', 'Repartidor'],
            'scope': {
                'Administrador': 'all',
                'Encargado de Bodega': 'all',
                'Vendedor': 'own',
                'Repartidor': 'assigned_routes'
            }
        },
        'edit_order': {
            'allowed_roles': ['Administrador', 'Encargado de Bodega', 'Vendedor'],
            'scope': {
                'Administrador': 'all',
                'Encargado de Bodega': 'all',
                'Vendedor': 'own'
            }
        },
        'delete_order': {
            'allowed_roles': ['Administrador'],
            'scope': 'all'
        },

        # State transitions (BR-006 to BR-013)
        'transition_to_EN_PREPARACION': {
            'allowed_roles': ['Administrador', 'Encargado de Bodega', 'Vendedor'],
            'scope': 'all'
        },
        'transition_to_DOCUMENTADO': {
            'allowed_roles': ['Administrador'],  # Normally auto via BR-005
            'scope': 'all'
        },
        'transition_to_EN_RUTA': {
            'allowed_roles': ['Administrador', 'Encargado de Bodega'],
            'scope': 'all'
        },
        'transition_to_ENTREGADO': {
            'allowed_roles': ['Administrador', 'Repartidor'],
            'scope': {
                'Administrador': 'all',
                'Repartidor': 'assigned_routes'
            }
        },
        'transition_to_INCIDENCIA': {
            'allowed_roles': ['Administrador', 'Repartidor'],
            'scope': {
                'Administrador': 'all',
                'Repartidor': 'assigned_routes'
            }
        },
        'retry_delivery': {
            'allowed_roles': ['Administrador', 'Encargado de Bodega'],
            'scope': 'all'
        },
        'reset_to_documentado': {
            'allowed_roles': ['Administrador', 'Encargado de Bodega'],
            'scope': 'all'
        },

        # Invoice operations (BR-015)
        'create_invoice': {
            'allowed_roles': ['Administrador', 'Encargado de Bodega', 'Vendedor'],
            'scope': 'all'
        },
        'view_invoice': {
            'allowed_roles': ['Administrador', 'Encargado de Bodega', 'Vendedor'],
            'scope': {
                'Administrador': 'all',
                'Encargado de Bodega': 'all',
                'Vendedor': 'own'
            }
        },
        'delete_invoice': {
            'allowed_roles': ['Administrador'],
            'scope': 'all'
        },

        # Route operations (BR-016)
        'generate_route': {
            'allowed_roles': ['Administrador', 'Encargado de Bodega'],
            'scope': 'all'
        },
        'view_route': {
            'allowed_roles': ['Administrador', 'Encargado de Bodega', 'Repartidor'],
            'scope': {
                'Administrador': 'all',
                'Encargado de Bodega': 'all',
                'Repartidor': 'assigned'
            }
        },
        'assign_driver': {
            'allowed_roles': ['Administrador', 'Encargado de Bodega'],
            'scope': 'all'
        },
        'activate_route': {
            'allowed_roles': ['Administrador', 'Encargado de Bodega'],
            'scope': 'all'
        },
        'complete_route': {
            'allowed_roles': ['Administrador', 'Encargado de Bodega'],
            'scope': 'all'
        },

        # Admin overrides (BR-017)
        'override_cutoff': {
            'allowed_roles': ['Administrador'],
            'scope': 'all'
        },
        'force_delivery_date': {
            'allowed_roles': ['Administrador'],
            'scope': 'all'
        },

        # User management
        'create_user': {
            'allowed_roles': ['Administrador'],
            'scope': 'all'
        },
        'edit_user': {
            'allowed_roles': ['Administrador'],
            'scope': 'all'
        },
        'deactivate_user': {
            'allowed_roles': ['Administrador'],
            'scope': 'all'
        },
    }

    def __init__(self, db: Session):
        """
        Initialize permission service

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    def can_execute_action(
        self,
        user: User,
        action: str,
        resource: Optional[Any] = None
    ) -> bool:
        """
        Check if user can execute action on resource

        Args:
            user: User attempting action
            action: Action name (e.g., 'create_order', 'view_route')
            resource: Optional resource (Order, Route, Invoice)

        Returns:
            bool: True if user has permission

        Raises:
            InsufficientPermissionsError: If user lacks permission
            NotYourOrderError: If Vendedor accessing other's order
            NotYourRouteError: If Repartidor accessing other's route
        """
        # Get permission config
        perm_config = self.PERMISSIONS.get(action)

        if not perm_config:
            raise InsufficientPermissionsError(
                action=action,
                user_role=user.role.role_name,
                required_role='Unknown action'
            )

        # Check if role is allowed
        user_role = user.role.role_name

        if user_role not in perm_config['allowed_roles']:
            raise InsufficientPermissionsError(
                action=action,
                user_role=user_role,
                required_role=', '.join(perm_config['allowed_roles'])
            )

        # Check resource-level scope
        scope = perm_config.get('scope')

        if isinstance(scope, dict):
            # Different scopes per role
            user_scope = scope.get(user_role, 'none')
        else:
            # Same scope for all roles
            user_scope = scope

        # Validate resource-level access
        if resource and user_scope != 'all':
            self._check_resource_scope(
                user=user,
                user_scope=user_scope,
                action=action,
                resource=resource
            )

        return True

    def require_permission(
        self,
        user: User,
        action: str,
        resource: Optional[Any] = None
    ) -> None:
        """
        Helper that raises exception if user lacks permission

        Args:
            user: User attempting action
            action: Action name
            resource: Optional resource

        Raises:
            InsufficientPermissionsError: If permission denied
            NotYourOrderError: If accessing other's order
            NotYourRouteError: If accessing other's route
        """
        self.can_execute_action(user, action, resource)

    def _check_resource_scope(
        self,
        user: User,
        user_scope: str,
        action: str,
        resource: Any
    ):
        """
        Check resource-level permissions

        Args:
            user: User attempting action
            user_scope: Scope for user role ('own', 'assigned_routes', 'assigned')
            action: Action name
            resource: Resource being accessed

        Raises:
            NotYourOrderError: If Vendedor accessing other's order
            NotYourRouteError: If Repartidor accessing other's route
        """
        if user_scope == 'own':
            # User can only access resources they created
            if isinstance(resource, Order):
                if resource.created_by_user_id != user.id:
                    # Log denial
                    from app.services.audit_service import AuditService
                    audit_service = AuditService(self.db)
                    audit_service.log_permission_denial(
                        action=action,
                        user=user,
                        entity_type='ORDER',
                        entity_id=resource.id,
                        denial_reason='User can only access own orders',
                        required_role=None
                    )
                    raise NotYourOrderError()

        elif user_scope == 'assigned_routes':
            # Repartidor can only access orders in assigned routes
            if isinstance(resource, Order):
                if not resource.assigned_route_id:
                    raise InsufficientPermissionsError(
                        action=action,
                        user_role=user.role.role_name,
                        required_role='Order must be in a route'
                    )

                route = resource.assigned_route
                if route.assigned_driver_id != user.id:
                    # Log denial
                    from app.services.audit_service import AuditService
                    audit_service = AuditService(self.db)
                    audit_service.log_permission_denial(
                        action=action,
                        user=user,
                        entity_type='ORDER',
                        entity_id=resource.id,
                        denial_reason='Order not in user assigned route',
                        required_role=None
                    )
                    raise NotYourRouteError()

        elif user_scope == 'assigned':
            # Repartidor can only access routes assigned to them
            if isinstance(resource, Route):
                if resource.assigned_driver_id != user.id:
                    # Log denial
                    from app.services.audit_service import AuditService
                    audit_service = AuditService(self.db)
                    audit_service.log_permission_denial(
                        action=action,
                        user=user,
                        entity_type='ROUTE',
                        entity_id=resource.id,
                        denial_reason='Route not assigned to user',
                        required_role=None
                    )
                    raise NotYourRouteError()

    def is_admin(self, user: User) -> bool:
        """
        Check if user is Administrador

        Args:
            user: User to check

        Returns:
            bool: True if Administrador
        """
        return user.role.role_name == 'Administrador'

    def is_encargado(self, user: User) -> bool:
        """
        Check if user is Encargado de Bodega

        Args:
            user: User to check

        Returns:
            bool: True if Encargado de Bodega
        """
        return user.role.role_name == 'Encargado de Bodega'

    def is_vendedor(self, user: User) -> bool:
        """
        Check if user is Vendedor

        Args:
            user: User to check

        Returns:
            bool: True if Vendedor
        """
        return user.role.role_name == 'Vendedor'

    def is_repartidor(self, user: User) -> bool:
        """
        Check if user is Repartidor

        Args:
            user: User to check

        Returns:
            bool: True if Repartidor
        """
        return user.role.role_name == 'Repartidor'

    def can_create_user(self, user: User) -> bool:
        """
        Check if user can create/manage users (Admin only)

        Only Administrators are allowed to create, update, or delete users.
        This implements security requirement BR-023.

        Args:
            user: User to check

        Returns:
            bool: True if user is Admin, False otherwise
        """
        return self.is_admin(user)
