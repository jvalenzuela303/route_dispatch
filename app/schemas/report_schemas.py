"""
Pydantic schemas for Reporting and Compliance

Request/response models for compliance and operational reports
"""

from pydantic import BaseModel, Field
from datetime import date
from typing import Dict, Optional


# Compliance Report schemas

class OrderMetrics(BaseModel):
    """Order volume metrics"""
    total: int = Field(..., description="Total orders in period")
    delivered: int = Field(..., description="Orders successfully delivered")
    in_progress: int = Field(..., description="Orders currently in transit")
    pending: int = Field(..., description="Orders pending preparation")
    with_incidence: int = Field(..., description="Orders with delivery incidents")


class ComplianceMetrics(BaseModel):
    """Compliance metrics as percentages"""
    cutoff_compliance: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Percentage of orders following cutoff rules (0.0-1.0)"
    )
    invoice_compliance: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Percentage of orders with invoice before routing (0.0-1.0)"
    )
    geocoding_quality: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Percentage of HIGH confidence geocoding results (0.0-1.0)"
    )


class NotificationMetrics(BaseModel):
    """Notification delivery metrics"""
    sent: int = Field(..., description="Notifications successfully sent")
    failed: int = Field(..., description="Notifications that failed to send")
    pending: int = Field(..., description="Notifications pending delivery")
    delivery_rate: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Percentage of notifications successfully delivered (0.0-1.0)"
    )


class ComplianceReport(BaseModel):
    """Comprehensive compliance report for date range"""
    period_start: date = Field(..., description="Report period start date")
    period_end: date = Field(..., description="Report period end date")
    orders: OrderMetrics
    compliance: ComplianceMetrics
    notifications: NotificationMetrics
    generated_at: str = Field(..., description="Report generation timestamp")


# Daily Operations Report schemas

class RouteMetrics(BaseModel):
    """Route operation metrics"""
    total_routes: int = Field(..., description="Total routes in period")
    active_routes: int = Field(..., description="Routes currently active")
    completed_routes: int = Field(..., description="Routes completed")
    draft_routes: int = Field(..., description="Routes in draft status")


class DailyOrderBreakdown(BaseModel):
    """Daily order status breakdown"""
    pendiente: int = Field(0, description="Orders in PENDIENTE status")
    en_preparacion: int = Field(0, description="Orders in EN_PREPARACION status")
    documentado: int = Field(0, description="Orders in DOCUMENTADO status")
    en_ruta: int = Field(0, description="Orders in EN_RUTA status")
    entregado: int = Field(0, description="Orders in ENTREGADO status")
    incidencia: int = Field(0, description="Orders in INCIDENCIA status")


class DailyOperationsReport(BaseModel):
    """Daily operations summary report"""
    report_date: date = Field(..., description="Date of report")
    orders_created_today: int = Field(..., description="Orders created on this date")
    orders_by_status: DailyOrderBreakdown
    routes: RouteMetrics
    deliveries_completed_today: int = Field(..., description="Deliveries completed on this date")
    pending_invoices: int = Field(..., description="Orders without invoice")
    orders_ready_for_routing: int = Field(
        ...,
        description="Orders in DOCUMENTADO status ready to be routed"
    )
    generated_at: str = Field(..., description="Report generation timestamp")


# Geocoding Quality Report schemas

class GeocodingQualityMetrics(BaseModel):
    """Geocoding quality breakdown"""
    high_confidence: int = Field(..., description="HIGH confidence results")
    medium_confidence: int = Field(..., description="MEDIUM confidence results")
    low_confidence: int = Field(..., description="LOW confidence results")
    invalid: int = Field(..., description="INVALID/failed geocoding")
    total: int = Field(..., description="Total geocoding attempts")
    cache_hit_rate: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Percentage of requests served from cache (0.0-1.0)"
    )


class GeocodingQualityReport(BaseModel):
    """Geocoding quality analysis report"""
    period_start: date
    period_end: date
    metrics: GeocodingQualityMetrics
    generated_at: str
