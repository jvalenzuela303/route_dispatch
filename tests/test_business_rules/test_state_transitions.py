"""
Comprehensive State Transition Testing (BR-006 to BR-013)

Tests all valid and invalid state transitions in the order lifecycle.
State machine must be strictly enforced - no invalid transitions allowed.

Valid transitions:
- PENDIENTE → EN_PREPARACION
- EN_PREPARACION → DOCUMENTADO
- DOCUMENTADO → EN_RUTA
- EN_RUTA → ENTREGADO
- EN_RUTA → INCIDENCIA
- INCIDENCIA → EN_RUTA (retry)
- INCIDENCIA → DOCUMENTADO (reset)
"""

import pytest

from app.models.enums import OrderStatus
from app.services.order_service import OrderService
from app.exceptions import InvalidStateTransitionError, ValidationError


class TestValidTransitions:
    """Test all valid state transitions"""

    def test_pendiente_to_en_preparacion(
        self,
        db_session,
        admin_user,
        sample_order_pendiente
    ):
        """Test PENDIENTE → EN_PREPARACION (BR-006)"""
        order_service = OrderService(db_session)

        updated_order = order_service.transition_order_state(
            order_id=sample_order_pendiente.id,
            new_status=OrderStatus.EN_PREPARACION,
            user=admin_user
        )

        assert updated_order.order_status == OrderStatus.EN_PREPARACION

    def test_en_preparacion_to_documentado(
        self,
        db_session,
        admin_user,
        sample_order_en_preparacion
    ):
        """Test EN_PREPARACION → DOCUMENTADO (BR-007)"""
        order_service = OrderService(db_session)

        # Note: Normally this happens via invoice creation (BR-005)
        # But Admin can force it
        updated_order = order_service.transition_order_state(
            order_id=sample_order_en_preparacion.id,
            new_status=OrderStatus.DOCUMENTADO,
            user=admin_user
        )

        assert updated_order.order_status == OrderStatus.DOCUMENTADO

    def test_documentado_to_en_ruta(
        self,
        db_session,
        admin_user,
        sample_order_with_invoice,
        sample_route_active
    ):
        """Test DOCUMENTADO → EN_RUTA (BR-008)"""
        order_service = OrderService(db_session)

        # Requires invoice and active route
        assert sample_order_with_invoice.invoice is not None

        updated_order = order_service.transition_order_state(
            order_id=sample_order_with_invoice.id,
            new_status=OrderStatus.EN_RUTA,
            user=admin_user,
            route_id=sample_route_active.id
        )

        assert updated_order.order_status == OrderStatus.EN_RUTA
        assert updated_order.assigned_route_id == sample_route_active.id

    def test_en_ruta_to_entregado(
        self,
        db_session,
        admin_user,
        sample_order_en_ruta
    ):
        """Test EN_RUTA → ENTREGADO (BR-009)"""
        order_service = OrderService(db_session)

        updated_order = order_service.transition_order_state(
            order_id=sample_order_en_ruta.id,
            new_status=OrderStatus.ENTREGADO,
            user=admin_user
        )

        assert updated_order.order_status == OrderStatus.ENTREGADO

    def test_en_ruta_to_incidencia(
        self,
        db_session,
        admin_user,
        sample_order_en_ruta
    ):
        """Test EN_RUTA → INCIDENCIA (BR-010)"""
        order_service = OrderService(db_session)

        updated_order = order_service.transition_order_state(
            order_id=sample_order_en_ruta.id,
            new_status=OrderStatus.INCIDENCIA,
            user=admin_user,
            reason="Cliente ausente - casa cerrada"
        )

        assert updated_order.order_status == OrderStatus.INCIDENCIA
        assert "Cliente ausente" in updated_order.notes

    def test_incidencia_to_en_ruta_retry(
        self,
        db_session,
        admin_user,
        sample_order_incidencia,
        sample_route_active
    ):
        """Test INCIDENCIA → EN_RUTA (BR-011 - retry delivery)"""
        order_service = OrderService(db_session)

        updated_order = order_service.transition_order_state(
            order_id=sample_order_incidencia.id,
            new_status=OrderStatus.EN_RUTA,
            user=admin_user,
            route_id=sample_route_active.id
        )

        assert updated_order.order_status == OrderStatus.EN_RUTA

    def test_incidencia_to_documentado_reset(
        self,
        db_session,
        admin_user,
        sample_order_incidencia
    ):
        """Test INCIDENCIA → DOCUMENTADO (BR-012 - reset to warehouse)"""
        order_service = OrderService(db_session)

        updated_order = order_service.transition_order_state(
            order_id=sample_order_incidencia.id,
            new_status=OrderStatus.DOCUMENTADO,
            user=admin_user
        )

        assert updated_order.order_status == OrderStatus.DOCUMENTADO
        # Route assignment should be cleared (BR-012)
        assert updated_order.assigned_route_id is None


class TestInvalidTransitions:
    """Test all invalid state transitions must be rejected"""

    def test_pendiente_to_documentado_invalid(
        self,
        db_session,
        admin_user,
        sample_order_pendiente
    ):
        """Test PENDIENTE → DOCUMENTADO is invalid (must go through EN_PREPARACION)"""
        order_service = OrderService(db_session)

        with pytest.raises(InvalidStateTransitionError) as exc_info:
            order_service.transition_order_state(
                order_id=sample_order_pendiente.id,
                new_status=OrderStatus.DOCUMENTADO,
                user=admin_user
            )

        assert "PENDIENTE" in str(exc_info.value)
        assert "DOCUMENTADO" in str(exc_info.value)

    def test_pendiente_to_en_ruta_invalid(
        self,
        db_session,
        admin_user,
        sample_order_pendiente
    ):
        """Test PENDIENTE → EN_RUTA is invalid"""
        order_service = OrderService(db_session)

        with pytest.raises(InvalidStateTransitionError):
            order_service.transition_order_state(
                order_id=sample_order_pendiente.id,
                new_status=OrderStatus.EN_RUTA,
                user=admin_user
            )

    def test_pendiente_to_entregado_invalid(
        self,
        db_session,
        admin_user,
        sample_order_pendiente
    ):
        """Test PENDIENTE → ENTREGADO is invalid (cannot skip all steps)"""
        order_service = OrderService(db_session)

        with pytest.raises(InvalidStateTransitionError):
            order_service.transition_order_state(
                order_id=sample_order_pendiente.id,
                new_status=OrderStatus.ENTREGADO,
                user=admin_user
            )

    def test_en_preparacion_to_en_ruta_invalid(
        self,
        db_session,
        admin_user,
        sample_order_en_preparacion
    ):
        """Test EN_PREPARACION → EN_RUTA is invalid (must be DOCUMENTADO first)"""
        order_service = OrderService(db_session)

        with pytest.raises(InvalidStateTransitionError):
            order_service.transition_order_state(
                order_id=sample_order_en_preparacion.id,
                new_status=OrderStatus.EN_RUTA,
                user=admin_user
            )

    def test_documentado_to_entregado_invalid(
        self,
        db_session,
        admin_user,
        sample_order_with_invoice
    ):
        """Test DOCUMENTADO → ENTREGADO is invalid (must go through EN_RUTA)"""
        order_service = OrderService(db_session)

        with pytest.raises(InvalidStateTransitionError):
            order_service.transition_order_state(
                order_id=sample_order_with_invoice.id,
                new_status=OrderStatus.ENTREGADO,
                user=admin_user
            )

    def test_entregado_to_any_status_invalid(
        self,
        db_session,
        admin_user,
        sample_order_entregado
    ):
        """Test ENTREGADO is final state - no transitions allowed (BR-013)"""
        order_service = OrderService(db_session)

        # Try transitioning back to any status - all should fail
        invalid_transitions = [
            OrderStatus.PENDIENTE,
            OrderStatus.EN_PREPARACION,
            OrderStatus.DOCUMENTADO,
            OrderStatus.EN_RUTA,
            OrderStatus.INCIDENCIA
        ]

        for target_status in invalid_transitions:
            with pytest.raises(InvalidStateTransitionError):
                order_service.transition_order_state(
                    order_id=sample_order_entregado.id,
                    new_status=target_status,
                    user=admin_user
                )


class TestTransitionPrerequisites:
    """Test prerequisite validation for specific transitions"""

    def test_en_ruta_requires_active_route(
        self,
        db_session,
        admin_user,
        sample_order_with_invoice,
        sample_route_draft
    ):
        """Test EN_RUTA transition requires ACTIVE route (not DRAFT)"""
        order_service = OrderService(db_session)

        # Route is DRAFT, not ACTIVE
        assert sample_route_draft.status.value == "DRAFT"

        with pytest.raises(ValidationError) as exc_info:
            order_service.transition_order_state(
                order_id=sample_order_with_invoice.id,
                new_status=OrderStatus.EN_RUTA,
                user=admin_user,
                route_id=sample_route_draft.id
            )

        assert "ACTIVE" in str(exc_info.value.message)

    def test_en_ruta_requires_route_id(
        self,
        db_session,
        admin_user,
        sample_order_with_invoice
    ):
        """Test EN_RUTA transition requires route_id parameter"""
        order_service = OrderService(db_session)

        with pytest.raises(ValidationError) as exc_info:
            order_service.transition_order_state(
                order_id=sample_order_with_invoice.id,
                new_status=OrderStatus.EN_RUTA,
                user=admin_user,
                route_id=None  # Missing route!
            )

        assert "route" in str(exc_info.value.message).lower()

    def test_incidencia_requires_reason(
        self,
        db_session,
        admin_user,
        sample_order_en_ruta
    ):
        """Test INCIDENCIA transition requires reason (BR-010)"""
        order_service = OrderService(db_session)

        with pytest.raises(ValidationError) as exc_info:
            order_service.transition_order_state(
                order_id=sample_order_en_ruta.id,
                new_status=OrderStatus.INCIDENCIA,
                user=admin_user,
                reason=""  # Empty reason!
            )

        assert exc_info.value.code == "INCIDENCE_REASON_REQUIRED"

    def test_incidencia_reason_appended_to_notes(
        self,
        db_session,
        admin_user,
        sample_order_en_ruta
    ):
        """Test INCIDENCIA reason is appended to order notes"""
        order_service = OrderService(db_session)

        original_notes = sample_order_en_ruta.notes or ""

        updated_order = order_service.transition_order_state(
            order_id=sample_order_en_ruta.id,
            new_status=OrderStatus.INCIDENCIA,
            user=admin_user,
            reason="Dirección incorrecta"
        )

        # Reason should be in notes
        assert "Dirección incorrecta" in updated_order.notes
        # Original notes should be preserved
        if original_notes:
            assert original_notes in updated_order.notes


class TestTransitionIdempotency:
    """Test idempotent behavior of state transitions (BR-023)"""

    def test_transition_to_same_status_is_noop(
        self,
        db_session,
        admin_user,
        sample_order_en_ruta
    ):
        """
        Test transitioning to current status is no-op (idempotent)

        Expected: No error, order remains in same state
        """
        order_service = OrderService(db_session)

        # Order is EN_RUTA
        assert sample_order_en_ruta.order_status == OrderStatus.EN_RUTA

        # Transition to EN_RUTA again (idempotent)
        updated_order = order_service.transition_order_state(
            order_id=sample_order_en_ruta.id,
            new_status=OrderStatus.EN_RUTA,
            user=admin_user,
            route_id=sample_order_en_ruta.assigned_route_id
        )

        # Should still be EN_RUTA, no error
        assert updated_order.order_status == OrderStatus.EN_RUTA


class TestRepartidorTransitionRestrictions:
    """Test Repartidor-specific transition restrictions (BR-009, BR-010)"""

    def test_repartidor_can_mark_entregado_own_route(
        self,
        db_session,
        repartidor_user,
        sample_order_en_ruta_assigned_to_repartidor
    ):
        """Test Repartidor can mark order ENTREGADO if in assigned route"""
        order_service = OrderService(db_session)

        # Verify order is in repartidor's route
        assert sample_order_en_ruta_assigned_to_repartidor.assigned_route.assigned_driver_id == repartidor_user.id

        updated_order = order_service.transition_order_state(
            order_id=sample_order_en_ruta_assigned_to_repartidor.id,
            new_status=OrderStatus.ENTREGADO,
            user=repartidor_user
        )

        assert updated_order.order_status == OrderStatus.ENTREGADO

    def test_repartidor_cannot_mark_entregado_other_route(
        self,
        db_session,
        repartidor_user,
        sample_order_en_ruta_assigned_to_other_driver
    ):
        """
        SECURITY TEST: Repartidor cannot mark ENTREGADO order in another driver's route

        Expected: InsufficientPermissionsError or NotYourRouteError
        """
        order_service = OrderService(db_session)

        # Verify order is NOT in repartidor's route
        assert sample_order_en_ruta_assigned_to_other_driver.assigned_route.assigned_driver_id != repartidor_user.id

        with pytest.raises(Exception) as exc_info:
            order_service.transition_order_state(
                order_id=sample_order_en_ruta_assigned_to_other_driver.id,
                new_status=OrderStatus.ENTREGADO,
                user=repartidor_user
            )

        # Should be permission error
        error_message = str(exc_info.value.message).lower()
        assert any(word in error_message for word in ["route", "permission", "access", "assigned"])

    def test_repartidor_can_mark_incidencia_own_route(
        self,
        db_session,
        repartidor_user,
        sample_order_en_ruta_assigned_to_repartidor
    ):
        """Test Repartidor can mark INCIDENCIA for order in assigned route"""
        order_service = OrderService(db_session)

        updated_order = order_service.transition_order_state(
            order_id=sample_order_en_ruta_assigned_to_repartidor.id,
            new_status=OrderStatus.INCIDENCIA,
            user=repartidor_user,
            reason="Nadie en casa"
        )

        assert updated_order.order_status == OrderStatus.INCIDENCIA

    def test_repartidor_cannot_transition_to_documentado(
        self,
        db_session,
        repartidor_user,
        sample_order_incidencia
    ):
        """
        SECURITY TEST: Repartidor cannot reset order to DOCUMENTADO

        Expected: InsufficientPermissionsError
        """
        order_service = OrderService(db_session)

        with pytest.raises(Exception) as exc_info:
            order_service.transition_order_state(
                order_id=sample_order_incidencia.id,
                new_status=OrderStatus.DOCUMENTADO,
                user=repartidor_user
            )

        # Should be permission error
        error_message = str(exc_info.value.message).lower()
        assert "permission" in error_message or "autorizado" in error_message


class TestConcurrentTransitions:
    """Test concurrent state transitions (BR-022)"""

    def test_concurrent_transitions_with_pessimistic_lock(
        self,
        db_session,
        admin_user,
        sample_order_en_ruta
    ):
        """
        Test pessimistic locking prevents concurrent modification

        Note: This is a basic test. Real concurrency testing requires
        multi-threading or multi-process setup.
        """
        order_service = OrderService(db_session)

        # First transition acquires lock
        updated_order = order_service.transition_order_state(
            order_id=sample_order_en_ruta.id,
            new_status=OrderStatus.ENTREGADO,
            user=admin_user
        )

        assert updated_order.order_status == OrderStatus.ENTREGADO

        # Verify transition was persisted
        db_session.refresh(sample_order_en_ruta)
        assert sample_order_en_ruta.order_status == OrderStatus.ENTREGADO
