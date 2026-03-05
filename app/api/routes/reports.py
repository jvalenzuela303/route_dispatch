"""
Reports API endpoints

Implements REST API for compliance and operational reporting:
- Compliance reports (cutoff, invoice, geocoding, notifications)
- Daily operations summaries
- Geocoding quality reports
"""

from fastapi import APIRouter, Depends, Query, HTTPException, status
from datetime import date, datetime, timedelta
from typing import Optional
from uuid import UUID
import math

from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_active_user, require_roles
from app.api.dependencies.database import get_db
from app.services.workflow_orchestrator import WorkflowOrchestrator
from app.schemas.report_schemas import (
    ComplianceReport,
    DailyOperationsReport,
    GeocodingQualityReport,
    GeocodingQualityMetrics
)
from app.models.models import User, Order
from app.models.enums import GeocodingConfidence


router = APIRouter(prefix="/api/reports", tags=["Reports"])


@router.get(
    "/compliance",
    response_model=ComplianceReport,
    summary="Get compliance report",
    description="""
    Generate comprehensive compliance report for date range.

    **Metrics:**
    - Order volume (created, delivered, in_progress)
    - Cutoff compliance (% following rules vs overrides)
    - Invoice compliance (% with invoice before routing)
    - Geocoding quality (% HIGH confidence)
    - Notification delivery rate (% SENT vs FAILED)

    **Use Cases:**
    - Monthly compliance audits
    - Quality assurance monitoring
    - Process optimization analysis

    **Permissions:** Administrador, Encargado de Bodega
    """
)
async def get_compliance_report(
    start_date: date = Query(..., description="Report period start date"),
    end_date: date = Query(..., description="Report period end date (inclusive)"),
    current_user: User = Depends(require_roles(['Administrador', 'Encargado de Bodega'])),
    db: Session = Depends(get_db)
):
    """
    Generate compliance report for date range
    """
    # Validate date range
    if end_date < start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_date must be >= start_date"
        )

    # Limit report range to 90 days
    if (end_date - start_date).days > 90:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Report range cannot exceed 90 days"
        )

    orchestrator = WorkflowOrchestrator(db)
    report = orchestrator.generate_compliance_report(start_date, end_date)

    return ComplianceReport(**report)


@router.get(
    "/daily-operations",
    response_model=DailyOperationsReport,
    summary="Get daily operations report",
    description="""
    Daily operations summary for specific date.

    **Metrics:**
    - Orders created today
    - Orders by status (current snapshot)
    - Routes (total, active, completed, draft)
    - Deliveries completed today
    - Pending invoices
    - Orders ready for routing

    **Use Cases:**
    - Daily standup meetings
    - Operations dashboard
    - Resource planning

    **Permissions:** Administrador, Encargado de Bodega
    """
)
async def get_daily_operations_report(
    report_date: date = Query(default_factory=date.today, description="Date for report"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Generate daily operations summary
    """
    # Don't allow reports for future dates
    if report_date > date.today():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot generate report for future date"
        )

    orchestrator = WorkflowOrchestrator(db)
    report = orchestrator.generate_daily_operations_report(report_date)

    return DailyOperationsReport(**report)


@router.get(
    "/geocoding-quality",
    response_model=GeocodingQualityReport,
    summary="Get geocoding quality report",
    description="""
    Geocoding quality analysis for date range.

    **Metrics:**
    - HIGH/MEDIUM/LOW/INVALID confidence breakdown
    - Cache hit rate
    - Address validation success rate

    **Use Cases:**
    - Address data quality monitoring
    - Training vendors on address formatting
    - Identifying problematic zones

    **Permissions:** Administrador, Encargado de Bodega
    """
)
async def get_geocoding_quality_report(
    start_date: date = Query(..., description="Report period start date"),
    end_date: date = Query(..., description="Report period end date (inclusive)"),
    current_user: User = Depends(require_roles(['Administrador', 'Encargado de Bodega'])),
    db: Session = Depends(get_db)
):
    """
    Generate geocoding quality report
    """
    # Validate date range
    if end_date < start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_date must be >= start_date"
        )

    # Date range for query
    from zoneinfo import ZoneInfo
    TIMEZONE = ZoneInfo("America/Santiago")
    start_datetime = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=TIMEZONE)
    end_datetime = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=TIMEZONE)

    # Query orders in date range
    total_orders = (
        db.query(Order)
        .filter(
            Order.created_at >= start_datetime,
            Order.created_at <= end_datetime
        )
        .count()
    )

    # Count by confidence level
    high_count = (
        db.query(Order)
        .filter(
            Order.created_at >= start_datetime,
            Order.created_at <= end_datetime,
            Order.geocoding_confidence == GeocodingConfidence.HIGH
        )
        .count()
    )

    medium_count = (
        db.query(Order)
        .filter(
            Order.created_at >= start_datetime,
            Order.created_at <= end_datetime,
            Order.geocoding_confidence == GeocodingConfidence.MEDIUM
        )
        .count()
    )

    low_count = (
        db.query(Order)
        .filter(
            Order.created_at >= start_datetime,
            Order.created_at <= end_datetime,
            Order.geocoding_confidence == GeocodingConfidence.LOW
        )
        .count()
    )

    invalid_count = (
        db.query(Order)
        .filter(
            Order.created_at >= start_datetime,
            Order.created_at <= end_datetime,
            Order.geocoding_confidence == GeocodingConfidence.INVALID
        )
        .count()
    )

    # Calculate cache hit rate from audit logs
    from app.models.models import AuditLog
    geocode_actions = (
        db.query(AuditLog)
        .filter(
            AuditLog.action == 'GEOCODE_ADDRESS',
            AuditLog.timestamp >= start_datetime,
            AuditLog.timestamp <= end_datetime
        )
        .all()
    )

    cached_count = sum(1 for log in geocode_actions if log.details and log.details.get('cached') is True)
    cache_hit_rate = 0.0 if len(geocode_actions) == 0 else (cached_count / len(geocode_actions))

    metrics = GeocodingQualityMetrics(
        high_confidence=high_count,
        medium_confidence=medium_count,
        low_confidence=low_count,
        invalid=invalid_count,
        total=total_orders,
        cache_hit_rate=round(cache_hit_rate, 4)
    )

    return GeocodingQualityReport(
        period_start=start_date,
        period_end=end_date,
        metrics=metrics,
        generated_at=datetime.now(TIMEZONE).isoformat()
    )


@router.get(
    "/summary",
    summary="Get comprehensive summary",
    description="""
    Get comprehensive summary combining multiple reports.

    Returns:
    - Today's operations
    - Last 7 days compliance
    - Last 30 days geocoding quality

    **Permissions:** Administrador, Encargado de Bodega
    """
)
async def get_summary_report(
    current_user: User = Depends(require_roles(['Administrador', 'Encargado de Bodega'])),
    db: Session = Depends(get_db)
):
    """
    Get comprehensive summary for dashboard
    """
    orchestrator = WorkflowOrchestrator(db)

    today = date.today()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)

    # Daily operations for today
    daily_ops = orchestrator.generate_daily_operations_report(today)

    # Compliance for last 7 days
    compliance_7d = orchestrator.generate_compliance_report(week_ago, today)

    # Compliance for last 30 days
    compliance_30d = orchestrator.generate_compliance_report(month_ago, today)

    return {
        'generated_at': datetime.now().isoformat(),
        'daily_operations': daily_ops,
        'compliance_7_days': compliance_7d,
        'compliance_30_days': compliance_30d,
        'summary': {
            'orders_today': daily_ops['orders_created_today'],
            'active_routes': daily_ops['routes']['active_routes'],
            'pending_invoices': daily_ops['pending_invoices'],
            'compliance_score_7d': round(
                (compliance_7d['compliance']['cutoff_compliance'] +
                 compliance_7d['compliance']['invoice_compliance'] +
                 compliance_7d['compliance']['geocoding_quality']) / 3,
                4
            ),
            'notification_rate_7d': compliance_7d['notifications']['delivery_rate']
        }
    }


@router.get(
    "/audit-logs",
    summary="Get audit logs",
    description="""
    Retrieve paginated audit logs with optional filters.

    **Filters:**
    - user_id: Filter by user UUID
    - action: Filter by action type (partial match)
    - entity_type: Filter by entity type (ORDER, INVOICE, ROUTE, USER)
    - date_from: Filter logs from this date
    - date_to: Filter logs up to this date

    **Permissions:** Administrador, Encargado de Bodega
    """
)
async def get_audit_logs(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(50, ge=1, le=200, description="Items per page"),
    user_id: Optional[UUID] = Query(None, description="Filter by user UUID"),
    action: Optional[str] = Query(None, description="Filter by action type"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    date_from: Optional[date] = Query(None, description="Filter from date"),
    date_to: Optional[date] = Query(None, description="Filter to date"),
    current_user: User = Depends(require_roles(['Administrador', 'Encargado de Bodega'])),
    db: Session = Depends(get_db)
):
    """
    Get paginated audit logs with optional filtering
    """
    from app.models.models import AuditLog
    from zoneinfo import ZoneInfo
    TIMEZONE = ZoneInfo("America/Santiago")

    query = db.query(AuditLog)

    if user_id is not None:
        query = query.filter(AuditLog.user_id == user_id)

    if action:
        query = query.filter(AuditLog.action.ilike(f'%{action}%'))

    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)

    if date_from:
        start_dt = datetime.combine(date_from, datetime.min.time()).replace(tzinfo=TIMEZONE)
        query = query.filter(AuditLog.timestamp >= start_dt)

    if date_to:
        end_dt = datetime.combine(date_to, datetime.max.time()).replace(tzinfo=TIMEZONE)
        query = query.filter(AuditLog.timestamp <= end_dt)

    total = query.count()
    pages = math.ceil(total / size) if total > 0 else 1
    skip = (page - 1) * size

    logs = (
        query
        .order_by(AuditLog.timestamp.desc())
        .offset(skip)
        .limit(size)
        .all()
    )

    # Fetch users for display
    user_ids = {log.user_id for log in logs if log.user_id is not None}
    users_map: dict = {}
    if user_ids:
        db_users = db.query(User).filter(User.id.in_(user_ids)).all()
        users_map = {str(u.id): u for u in db_users}

    items = []
    for log in logs:
        user_obj = users_map.get(str(log.user_id)) if log.user_id else None
        items.append({
            "id": str(log.id),
            "user_id": str(log.user_id) if log.user_id else None,
            "user": {
                "id": str(user_obj.id),
                "full_name": user_obj.username or "",
                "email": user_obj.email or "",
            } if user_obj else None,
            "action": log.action,
            "entity_type": log.entity_type,
            "entity_id": str(log.entity_id) if log.entity_id else None,
            "details": log.details,
            "result": log.result,
            "ip_address": log.ip_address,
            "created_at": log.timestamp.isoformat() if log.timestamp else None,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "pages": pages,
    }
