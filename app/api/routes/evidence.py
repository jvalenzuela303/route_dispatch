"""
Delivery Evidence API endpoints

Used by the driver APK to upload photos and signatures at delivery time.
Also used by the logistics dashboard to review evidence per order.
"""

from datetime import datetime
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_active_user, require_roles
from app.api.dependencies.database import get_db
from app.services.evidence_service import EvidenceService
from app.schemas.vehicle_schemas import DeliveryEvidenceResponse
from app.models.models import User
from app.models.enums import EvidenceType
from app.exceptions import BusinessRuleViolationError


router = APIRouter(prefix="/api/evidence", tags=["Delivery Evidence"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


def _http(exc: BusinessRuleViolationError) -> HTTPException:
    return HTTPException(status_code=exc.http_status, detail=exc.to_dict())


@router.post(
    "/routes/{route_id}/orders/{order_id}",
    response_model=DeliveryEvidenceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload delivery evidence",
    description="""
    Upload a photo or signature as delivery confirmation.

    **Used by:** Driver APK (React Native)

    **Accepted files:** image/jpeg, image/png, image/webp — max 10 MB

    **Behavior:**
    - Photos are resized to max 1920×1080 and re-compressed as JPEG (quality 80)
    - Signatures are stored as-is
    - GPS coordinates and capture timestamp are optional metadata
    """,
)
async def upload_evidence(
    route_id: UUID,
    order_id: UUID,
    file: UploadFile = File(..., description="Photo or signature image"),
    evidence_type: EvidenceType = Form(..., description="PHOTO or SIGNATURE"),
    captured_at: Optional[datetime] = Form(
        None, description="ISO datetime when evidence was captured on device"
    ),
    gps_lat: Optional[float] = Form(None, ge=-90, le=90),
    gps_lon: Optional[float] = Form(None, ge=-180, le=180),
    current_user: User = Depends(require_roles(["Repartidor", "Administrador", "Encargado de Bodega"])),
    db: Session = Depends(get_db),
):
    # Check content type early
    content_type = file.content_type or ""
    if content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported media type '{content_type}'. Use image/jpeg, image/png, or image/webp.",
        )

    # Read and size-check
    file_data = await file.read()
    if len(file_data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size is {MAX_UPLOAD_BYTES // (1024*1024)} MB.",
        )

    try:
        service = EvidenceService(db)
        evidence = service.save_evidence(
            route_id=route_id,
            order_id=order_id,
            uploaded_by=current_user,
            file_data=file_data,
            mime_type=content_type,
            evidence_type=evidence_type,
            captured_at=captured_at,
            gps_lat=gps_lat,
            gps_lon=gps_lon,
        )
        return DeliveryEvidenceResponse.model_validate(evidence)
    except BusinessRuleViolationError as e:
        raise _http(e)


@router.get(
    "/routes/{route_id}/orders/{order_id}",
    response_model=List[DeliveryEvidenceResponse],
    summary="List evidence for order",
    description="Return all photos and signatures for a specific order within a route.",
)
async def list_order_evidence(
    route_id: UUID,
    order_id: UUID,
    current_user: User = Depends(require_roles(["Repartidor", "Administrador", "Encargado de Bodega"])),
    db: Session = Depends(get_db),
):
    service = EvidenceService(db)
    items = service.get_evidence_for_order(route_id=route_id, order_id=order_id)
    return [DeliveryEvidenceResponse.model_validate(e) for e in items]


@router.get(
    "/routes/{route_id}",
    response_model=List[DeliveryEvidenceResponse],
    summary="List all evidence for route",
    description="Return all delivery evidence records across all orders in the route.",
)
async def list_route_evidence(
    route_id: UUID,
    current_user: User = Depends(require_roles(["Administrador", "Encargado de Bodega"])),
    db: Session = Depends(get_db),
):
    service = EvidenceService(db)
    items = service.get_evidence_for_route(route_id=route_id)
    return [DeliveryEvidenceResponse.model_validate(e) for e in items]
