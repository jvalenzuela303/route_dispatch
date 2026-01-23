"""
Integration tests for WorkflowOrchestrator

Tests complete multi-step workflows:
- Order creation workflow
- Invoice linking workflow
- Route generation workflow
- Compliance reporting
"""

import pytest
from datetime import date, timedelta
from app.services.workflow_orchestrator import WorkflowOrchestrator
from app.schemas.order_schemas import OrderCreate
from app.schemas.invoice_schemas import InvoiceCreate
from app.models.enums import SourceChannel, InvoiceType


class TestOrderCreationWorkflow:
    """Test complete order creation workflow"""

    def test_create_order_workflow_success(self, db_session, admin_user):
        """Test complete order creation with geocoding and cutoff"""
        orchestrator = WorkflowOrchestrator(db_session)

        order_data = OrderCreate(
            customer_name="Test Customer",
            customer_phone="+56912345678",
            address_text="Av. Brasil 1234, Rancagua, Chile",
            source_channel=SourceChannel.WEB
        )

        result = orchestrator.create_order_workflow(order_data, admin_user)

        assert "order" in result
        assert "warnings" in result
        assert "next_steps" in result
        assert result["workflow_status"] == "ORDER_CREATED"
        assert result["order"].order_status.value == "PENDIENTE"


class TestInvoiceLinkingWorkflow:
    """Test invoice linking workflow"""

    def test_invoice_linking_transitions_order(self, db_session, admin_user, sample_order):
        """Test invoice linking auto-transitions order to DOCUMENTADO"""
        # Transition to EN_PREPARACION first
        sample_order.order_status = "EN_PREPARACION"
        db_session.commit()

        orchestrator = WorkflowOrchestrator(db_session)

        invoice_data = InvoiceCreate(
            order_id=sample_order.id,
            invoice_number="FAC-WORKFLOW-001",
            invoice_type=InvoiceType.FACTURA,
            total_amount=50000
        )

        result = orchestrator.invoice_linking_workflow(invoice_data, admin_user)

        assert "invoice" in result
        assert "order" in result
        assert "transition" in result
        assert result["transition"]["to_status"] == "DOCUMENTADO"
        assert result["workflow_status"] == "ORDER_DOCUMENTED"


class TestComplianceReporting:
    """Test compliance report generation"""

    def test_generate_compliance_report(self, db_session, sample_order):
        """Test compliance report generation"""
        orchestrator = WorkflowOrchestrator(db_session)

        today = date.today()
        week_ago = today - timedelta(days=7)

        report = orchestrator.generate_compliance_report(week_ago, today)

        assert "period_start" in report
        assert "period_end" in report
        assert "orders" in report
        assert "compliance" in report
        assert "notifications" in report

    def test_generate_daily_operations_report(self, db_session, sample_order):
        """Test daily operations report"""
        orchestrator = WorkflowOrchestrator(db_session)

        report = orchestrator.generate_daily_operations_report(date.today())

        assert "report_date" in report
        assert "orders_by_status" in report
        assert "routes" in report
        assert "orders_ready_for_routing" in report
