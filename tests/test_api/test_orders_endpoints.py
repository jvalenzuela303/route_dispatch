"""
Integration tests for Orders API endpoints

Tests:
- POST /api/orders - Create order
- GET /api/orders - List orders
- GET /api/orders/{id} - Get order
- PUT /api/orders/{id}/status - Transition status
- RBAC enforcement
"""

import pytest
from datetime import date


class TestCreateOrder:
    """Test POST /api/orders"""

    def test_create_order_success(self, client, admin_token):
        """Test successful order creation"""
        response = client.post(
            "/api/orders",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "customer_name": "Pedro González",
                "customer_phone": "+56987654321",
                "customer_email": "pedro@example.cl",
                "address_text": "Calle O'Higgins 567, Rancagua",
                "source_channel": "WEB"
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert "order" in data
        assert data["order"]["customer_name"] == "Pedro González"
        assert data["order"]["order_status"] == "PENDIENTE"
        assert "delivery_date_info" in data
        assert "next_steps" in data

    def test_create_order_invalid_phone(self, client, admin_token):
        """Test order creation with invalid phone"""
        response = client.post(
            "/api/orders",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "customer_name": "Pedro González",
                "customer_phone": "123456789",  # Invalid format
                "address_text": "Calle O'Higgins 567, Rancagua",
                "source_channel": "WEB"
            }
        )

        assert response.status_code == 422

    def test_create_order_vendedor_permission(self, client, vendedor_token):
        """Test vendedor can create orders"""
        response = client.post(
            "/api/orders",
            headers={"Authorization": f"Bearer {vendedor_token}"},
            json={
                "customer_name": "María López",
                "customer_phone": "+56912345678",
                "address_text": "Av. Millán 890, Rancagua",
                "source_channel": "RRSS"
            }
        )

        assert response.status_code == 201

    def test_create_order_unauthorized(self, client):
        """Test order creation without authentication"""
        response = client.post(
            "/api/orders",
            json={
                "customer_name": "Test User",
                "customer_phone": "+56912345678",
                "address_text": "Test Address 123, Rancagua",
                "source_channel": "WEB"
            }
        )

        assert response.status_code == 403


class TestListOrders:
    """Test GET /api/orders"""

    def test_list_orders_admin(self, client, admin_token, sample_order):
        """Test admin can see all orders"""
        response = client.get(
            "/api/orders",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_list_orders_with_filters(self, client, admin_token, sample_order):
        """Test listing orders with status filter"""
        response = client.get(
            f"/api/orders?status={sample_order.order_status.value}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_list_orders_search(self, client, admin_token, sample_order):
        """Test search functionality"""
        response = client.get(
            f"/api/orders?search={sample_order.customer_name[:5]}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestGetOrder:
    """Test GET /api/orders/{id}"""

    def test_get_order_success(self, client, admin_token, sample_order):
        """Test getting order by ID"""
        response = client.get(
            f"/api/orders/{sample_order.id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(sample_order.id)
        assert data["customer_name"] == sample_order.customer_name

    def test_get_order_not_found(self, client, admin_token):
        """Test getting non-existent order"""
        import uuid
        fake_id = uuid.uuid4()
        response = client.get(
            f"/api/orders/{fake_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 404


class TestTransitionOrderStatus:
    """Test PUT /api/orders/{id}/status"""

    def test_transition_pendiente_to_en_preparacion(self, client, admin_token, sample_order):
        """Test valid state transition"""
        response = client.put(
            f"/api/orders/{sample_order.id}/status",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "new_status": "EN_PREPARACION"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["order_status"] == "EN_PREPARACION"

    def test_transition_invalid(self, client, admin_token, sample_order):
        """Test invalid state transition"""
        response = client.put(
            f"/api/orders/{sample_order.id}/status",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "new_status": "ENTREGADO"  # Invalid from PENDIENTE
            }
        )

        assert response.status_code == 400

    def test_transition_idempotent(self, client, admin_token, sample_order):
        """Test idempotent transition (same status)"""
        response = client.put(
            f"/api/orders/{sample_order.id}/status",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "new_status": sample_order.order_status.value
            }
        )

        assert response.status_code == 200


class TestOrdersReadyForRouting:
    """Test GET /api/orders/ready-for-routing/delivery-date/{date}"""

    def test_get_orders_ready_for_routing(self, client, admin_token, sample_order, sample_invoice):
        """Test getting orders ready for routing"""
        response = client.get(
            f"/api/orders/ready-for-routing/delivery-date/{sample_order.delivery_date}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestDeleteOrder:
    """Test DELETE /api/orders/{id}"""

    def test_delete_order_admin_only(self, client, admin_token, sample_order):
        """Test only admin can delete orders"""
        response = client.delete(
            f"/api/orders/{sample_order.id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 204

    def test_delete_order_vendedor_denied(self, client, vendedor_token, sample_order):
        """Test vendedor cannot delete orders"""
        response = client.delete(
            f"/api/orders/{sample_order.id}",
            headers={"Authorization": f"Bearer {vendedor_token}"}
        )

        assert response.status_code == 403
