"""
Authorization Boundary Security Testing

CRITICAL security tests verifying RBAC (Role-Based Access Control) enforcement.
These tests verify that users cannot access resources/operations outside their role permissions.

Test categories:
1. Role-based endpoint access
2. Resource ownership validation (Vendedor can only access own orders)
3. Route assignment validation (Repartidor can only access assigned routes)
4. Admin-only operations
"""

import pytest
import uuid

from app.models.enums import OrderStatus, RouteStatus
from app.services.permission_service import PermissionService
from app.services.order_service import OrderService
from app.services.user_service import UserService
from app.exceptions import (
    InsufficientPermissionsError,
    NotYourOrderError,
    NotYourRouteError
)


class TestRoleBasedAccessControl:
    """Test RBAC matrix enforcement"""

    def test_repartidor_cannot_create_users(
        self,
        db_session,
        repartidor_user
    ):
        """
        CRITICAL: Repartidor cannot create users

        Expected: InsufficientPermissionsError with 403 status
        """
        user_service = UserService(db_session)

        with pytest.raises(InsufficientPermissionsError) as exc_info:
            user_service.create_user(
                username="hacker",
                email="hacker@evil.com",
                password="password123",
                role_id=uuid.uuid4(),
                full_name="Hacker User",
                current_user=repartidor_user
            )

        assert exc_info.value.http_status == 403
        assert "Administrador" in str(exc_info.value.message)

    def test_vendedor_cannot_create_users(
        self,
        db_session,
        vendedor_user
    ):
        """
        CRITICAL: Vendedor cannot create users

        Expected: InsufficientPermissionsError
        """
        user_service = UserService(db_session)

        with pytest.raises(InsufficientPermissionsError):
            user_service.create_user(
                username="newuser",
                email="new@example.com",
                password="password123",
                role_id=uuid.uuid4(),
                full_name="New User",
                current_user=vendedor_user
            )

    def test_encargado_cannot_create_users(
        self,
        db_session,
        encargado_user
    ):
        """
        CRITICAL: Encargado de Bodega cannot create users

        Expected: InsufficientPermissionsError
        """
        user_service = UserService(db_session)

        with pytest.raises(InsufficientPermissionsError):
            user_service.create_user(
                username="newuser",
                email="new@example.com",
                password="password123",
                role_id=uuid.uuid4(),
                full_name="New User",
                current_user=encargado_user
            )

    def test_admin_can_create_users(
        self,
        db_session,
        admin_user,
        vendedor_role
    ):
        """
        Test Admin can create users

        Expected: Success
        """
        user_service = UserService(db_session)

        new_user = user_service.create_user(
            username=f"admin_created_{uuid.uuid4().hex[:8]}",
            email=f"admin_created_{uuid.uuid4().hex[:8]}@example.com",
            password="SecurePassword123!",
            role_id=vendedor_role.id,
            full_name="Admin Created User",
            current_user=admin_user
        )

        assert new_user.id is not None
        assert new_user.active_status is True

    def test_repartidor_cannot_delete_orders(
        self,
        db_session,
        repartidor_user,
        sample_order_en_ruta
    ):
        """
        CRITICAL: Repartidor cannot delete orders

        Expected: InsufficientPermissionsError
        """
        permission_service = PermissionService(db_session)

        with pytest.raises(InsufficientPermissionsError) as exc_info:
            permission_service.require_permission(
                user=repartidor_user,
                action='delete_order',
                resource=sample_order_en_ruta
            )

        assert "Administrador" in str(exc_info.value.message)

    def test_vendedor_cannot_delete_orders(
        self,
        db_session,
        vendedor_user,
        sample_order_pendiente
    ):
        """
        CRITICAL: Vendedor cannot delete orders

        Expected: InsufficientPermissionsError
        """
        permission_service = PermissionService(db_session)

        with pytest.raises(InsufficientPermissionsError):
            permission_service.require_permission(
                user=vendedor_user,
                action='delete_order',
                resource=sample_order_pendiente
            )

    def test_admin_can_delete_orders(
        self,
        db_session,
        admin_user,
        sample_order_pendiente
    ):
        """
        Test Admin can delete orders

        Expected: Permission granted
        """
        permission_service = PermissionService(db_session)

        # Should not raise exception
        permission_service.require_permission(
            user=admin_user,
            action='delete_order',
            resource=sample_order_pendiente
        )


class TestVendedorResourceOwnership:
    """Test Vendedor can only access own orders (scope: 'own')"""

    def test_vendedor_can_view_own_order(
        self,
        db_session,
        vendedor_user,
        order_created_by_vendedor
    ):
        """
        Test Vendedor can view order they created

        Expected: Permission granted
        """
        permission_service = PermissionService(db_session)

        # Verify ownership
        assert order_created_by_vendedor.created_by_user_id == vendedor_user.id

        # Should not raise exception
        permission_service.require_permission(
            user=vendedor_user,
            action='view_order',
            resource=order_created_by_vendedor
        )

    def test_vendedor_cannot_view_other_vendedor_order(
        self,
        db_session,
        vendedor_user,
        order_created_by_other_vendedor
    ):
        """
        CRITICAL: Vendedor cannot view order created by another Vendedor

        Expected: NotYourOrderError
        """
        permission_service = PermissionService(db_session)

        # Verify NOT owner
        assert order_created_by_other_vendedor.created_by_user_id != vendedor_user.id

        with pytest.raises(NotYourOrderError) as exc_info:
            permission_service.require_permission(
                user=vendedor_user,
                action='view_order',
                resource=order_created_by_other_vendedor
            )

        assert exc_info.value.http_status == 403
        assert "own orders" in str(exc_info.value.message).lower()

    def test_vendedor_can_edit_own_order(
        self,
        db_session,
        vendedor_user,
        order_created_by_vendedor
    ):
        """
        Test Vendedor can edit own order

        Expected: Permission granted
        """
        permission_service = PermissionService(db_session)

        # Should not raise exception
        permission_service.require_permission(
            user=vendedor_user,
            action='edit_order',
            resource=order_created_by_vendedor
        )

    def test_vendedor_cannot_edit_other_vendedor_order(
        self,
        db_session,
        vendedor_user,
        order_created_by_other_vendedor
    ):
        """
        CRITICAL: Vendedor cannot edit order created by another Vendedor

        Expected: NotYourOrderError
        """
        permission_service = PermissionService(db_session)

        with pytest.raises(NotYourOrderError):
            permission_service.require_permission(
                user=vendedor_user,
                action='edit_order',
                resource=order_created_by_other_vendedor
            )

    def test_get_orders_by_status_filters_by_vendedor(
        self,
        db_session,
        vendedor_user
    ):
        """
        Test get_orders_by_status only returns Vendedor's own orders

        Expected: Only orders created by vendedor_user returned
        """
        order_service = OrderService(db_session)

        orders = order_service.get_orders_by_status(
            status=OrderStatus.PENDIENTE,
            user=vendedor_user,
            limit=100
        )

        # All returned orders must be created by vendedor_user
        for order in orders:
            assert order.created_by_user_id == vendedor_user.id, \
                f"Order {order.order_number} not created by vendedor_user but was returned"


class TestRepartidorRouteAssignment:
    """Test Repartidor can only access assigned routes (scope: 'assigned')"""

    def test_repartidor_can_view_assigned_route(
        self,
        db_session,
        repartidor_user,
        route_assigned_to_repartidor
    ):
        """
        Test Repartidor can view route assigned to them

        Expected: Permission granted
        """
        permission_service = PermissionService(db_session)

        # Verify assignment
        assert route_assigned_to_repartidor.assigned_driver_id == repartidor_user.id

        # Should not raise exception
        permission_service.require_permission(
            user=repartidor_user,
            action='view_route',
            resource=route_assigned_to_repartidor
        )

    def test_repartidor_cannot_view_other_driver_route(
        self,
        db_session,
        repartidor_user,
        route_assigned_to_other_driver
    ):
        """
        CRITICAL: Repartidor cannot view route assigned to another driver

        Expected: NotYourRouteError
        """
        permission_service = PermissionService(db_session)

        # Verify NOT assigned
        assert route_assigned_to_other_driver.assigned_driver_id != repartidor_user.id

        with pytest.raises(NotYourRouteError) as exc_info:
            permission_service.require_permission(
                user=repartidor_user,
                action='view_route',
                resource=route_assigned_to_other_driver
            )

        assert exc_info.value.http_status == 403

    def test_repartidor_can_view_order_in_assigned_route(
        self,
        db_session,
        repartidor_user,
        order_in_repartidor_route
    ):
        """
        Test Repartidor can view order in their assigned route

        Expected: Permission granted
        """
        permission_service = PermissionService(db_session)

        # Verify order is in repartidor's route
        assert order_in_repartidor_route.assigned_route.assigned_driver_id == repartidor_user.id

        # Should not raise exception
        permission_service.require_permission(
            user=repartidor_user,
            action='view_order',
            resource=order_in_repartidor_route
        )

    def test_repartidor_cannot_view_order_in_other_route(
        self,
        db_session,
        repartidor_user,
        order_in_other_driver_route
    ):
        """
        CRITICAL: Repartidor cannot view order in another driver's route

        Expected: NotYourRouteError
        """
        permission_service = PermissionService(db_session)

        # Verify order is NOT in repartidor's route
        assert order_in_other_driver_route.assigned_route.assigned_driver_id != repartidor_user.id

        with pytest.raises(NotYourRouteError):
            permission_service.require_permission(
                user=repartidor_user,
                action='view_order',
                resource=order_in_other_driver_route
            )

    def test_repartidor_cannot_view_order_not_in_route(
        self,
        db_session,
        repartidor_user,
        sample_order_documentado
    ):
        """
        CRITICAL: Repartidor cannot view order not yet assigned to any route

        Expected: InsufficientPermissionsError
        """
        permission_service = PermissionService(db_session)

        # Order not assigned to any route yet
        assert sample_order_documentado.assigned_route_id is None

        with pytest.raises(InsufficientPermissionsError):
            permission_service.require_permission(
                user=repartidor_user,
                action='view_order',
                resource=sample_order_documentado
            )


class TestAdminBypassRestrictions:
    """Test Admin can bypass all resource ownership restrictions"""

    def test_admin_can_view_any_order(
        self,
        db_session,
        admin_user,
        order_created_by_vendedor
    ):
        """
        Test Admin can view any order regardless of creator

        Expected: Permission granted
        """
        permission_service = PermissionService(db_session)

        # Should not raise exception
        permission_service.require_permission(
            user=admin_user,
            action='view_order',
            resource=order_created_by_vendedor
        )

    def test_admin_can_edit_any_order(
        self,
        db_session,
        admin_user,
        order_created_by_vendedor
    ):
        """
        Test Admin can edit any order

        Expected: Permission granted
        """
        permission_service = PermissionService(db_session)

        # Should not raise exception
        permission_service.require_permission(
            user=admin_user,
            action='edit_order',
            resource=order_created_by_vendedor
        )

    def test_admin_can_view_any_route(
        self,
        db_session,
        admin_user,
        route_assigned_to_repartidor
    ):
        """
        Test Admin can view any route

        Expected: Permission granted
        """
        permission_service = PermissionService(db_session)

        # Should not raise exception
        permission_service.require_permission(
            user=admin_user,
            action='view_route',
            resource=route_assigned_to_repartidor
        )


class TestEncargadoPermissions:
    """Test Encargado de Bodega permissions"""

    def test_encargado_can_generate_routes(
        self,
        db_session,
        encargado_user
    ):
        """
        Test Encargado can generate routes

        Expected: Permission granted
        """
        permission_service = PermissionService(db_session)

        # Should not raise exception
        permission_service.require_permission(
            user=encargado_user,
            action='generate_route'
        )

    def test_encargado_can_assign_driver(
        self,
        db_session,
        encargado_user
    ):
        """
        Test Encargado can assign drivers to routes

        Expected: Permission granted
        """
        permission_service = PermissionService(db_session)

        # Should not raise exception
        permission_service.require_permission(
            user=encargado_user,
            action='assign_driver'
        )

    def test_encargado_can_view_all_orders(
        self,
        db_session,
        encargado_user,
        order_created_by_vendedor
    ):
        """
        Test Encargado can view all orders (scope: 'all')

        Expected: Permission granted
        """
        permission_service = PermissionService(db_session)

        # Should not raise exception
        permission_service.require_permission(
            user=encargado_user,
            action='view_order',
            resource=order_created_by_vendedor
        )

    def test_vendedor_cannot_generate_routes(
        self,
        db_session,
        vendedor_user
    ):
        """
        CRITICAL: Vendedor cannot generate routes

        Expected: InsufficientPermissionsError
        """
        permission_service = PermissionService(db_session)

        with pytest.raises(InsufficientPermissionsError):
            permission_service.require_permission(
                user=vendedor_user,
                action='generate_route'
            )

    def test_repartidor_cannot_generate_routes(
        self,
        db_session,
        repartidor_user
    ):
        """
        CRITICAL: Repartidor cannot generate routes

        Expected: InsufficientPermissionsError
        """
        permission_service = PermissionService(db_session)

        with pytest.raises(InsufficientPermissionsError):
            permission_service.require_permission(
                user=repartidor_user,
                action='generate_route'
            )


class TestPermissionAuditLogging:
    """Test permission denials are logged for audit trail"""

    def test_permission_denial_creates_audit_log(
        self,
        db_session,
        vendedor_user,
        order_created_by_other_vendedor
    ):
        """
        Test permission denials are logged in audit trail

        Expected: Audit log created with DENIED result
        """
        from app.services.audit_service import AuditService
        from app.models.enums import AuditResult

        permission_service = PermissionService(db_session)

        # Attempt access (will fail)
        try:
            permission_service.require_permission(
                user=vendedor_user,
                action='view_order',
                resource=order_created_by_other_vendedor
            )
        except NotYourOrderError:
            pass

        # Query audit log
        audit_service = AuditService(db_session)
        from app.models.models import AuditLog

        recent_denials = db_session.query(AuditLog).filter(
            AuditLog.user_id == vendedor_user.id,
            AuditLog.result == AuditResult.DENIED,
            AuditLog.entity_type == 'ORDER',
            AuditLog.entity_id == order_created_by_other_vendedor.id
        ).order_by(AuditLog.timestamp.desc()).first()

        assert recent_denials is not None, "Permission denial should be logged in audit trail"
        assert "own orders" in recent_denials.details.get('denial_reason', '').lower()
