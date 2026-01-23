"""
Integration tests for Invoices API endpoints

Tests:
- POST /api/invoices - Create invoice and auto-transition order
- GET /api/invoices - List invoices
- GET /api/invoices/{id} - Get invoice
- Workflow validation
"""

import pytest
from datetime import datetime


class TestCreateInvoice:
    """Test POST /api/invoices"""

    def test_create_invoice_success(self, client, admin_token, sample_order, db_session):
        """Test invoice creation and auto-transition"""
        # First transition order to EN_PREPARACION
        sample_order.order_status = "EN_PREPARACION"
        db_session.commit()

        response = client.post(
            "/api/invoices",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "order_id": str(sample_order.id),
                "invoice_number": "FAC-TEST-001",
                "invoice_type": "FACTURA",
                "total_amount": 45000
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert "invoice" in data
        assert "transition" in data
        assert data["transition"]["to_status"] == "DOCUMENTADO"

    def test_create_invoice_duplicate_fails(self, client, admin_token, sample_invoice):
        """Test duplicate invoice number fails"""
        response = client.post(
            "/api/invoices",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "order_id": str(sample_invoice.order_id),
                "invoice_number": sample_invoice.invoice_number,
                "invoice_type": "FACTURA",
                "total_amount": 45000
            }
        )

        assert response.status_code == 409


class TestListInvoices:
    """Test GET /api/invoices"""

    def test_list_invoices(self, client, admin_token, sample_invoice):
        """Test listing invoices"""
        response = client.get(
            "/api/invoices",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
