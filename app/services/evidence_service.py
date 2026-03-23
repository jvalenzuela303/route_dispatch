"""
Evidence Service — delivery photo and signature management

Handles file upload, Pillow resize/optimize, and DB record creation.
Files are stored under UPLOAD_DIR/{route_id}/{order_id}/ and served
via the /uploads/ static route registered in main.py.
"""

import os
import uuid
from datetime import datetime
from typing import Optional, List
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.models import DeliveryEvidence, Route, Order, User
from app.models.enums import EvidenceType
from app.schemas.vehicle_schemas import DeliveryEvidenceResponse
from app.exceptions import NotFoundError, ValidationError
from app.config.settings import get_settings

# Pillow is optional at import time — only needed during actual upload
try:
    from PIL import Image
    import io
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False

settings = get_settings()

# Max dimensions for resized photos (width, height)
PHOTO_MAX_SIZE = (1920, 1080)
PHOTO_QUALITY = 80  # JPEG quality %

ALLOWED_MIME = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


class EvidenceService:
    """
    Manage delivery evidence (photos and signatures) uploaded by drivers.

    Storage layout:
        {UPLOAD_DIR}/{route_id}/{order_id}/{uuid}.{ext}

    Public URL:
        /uploads/{route_id}/{order_id}/{uuid}.{ext}
    """

    def __init__(self, db: Session):
        self.db = db
        self.upload_dir = settings.upload_dir

    # ─────────────────────────────────────────────────────────────────
    # Upload
    # ─────────────────────────────────────────────────────────────────

    def save_evidence(
        self,
        route_id: UUID,
        order_id: UUID,
        uploaded_by: User,
        file_data: bytes,
        mime_type: str,
        evidence_type: EvidenceType,
        captured_at: Optional[datetime] = None,
        gps_lat: Optional[float] = None,
        gps_lon: Optional[float] = None,
    ) -> DeliveryEvidence:
        """
        Validate, optionally resize, save file, and create DB record.

        Args:
            route_id:      Route the delivery belongs to
            order_id:      Order being delivered
            uploaded_by:   Driver user uploading the evidence
            file_data:     Raw bytes of the uploaded file
            mime_type:     MIME type of the file
            evidence_type: PHOTO or SIGNATURE
            captured_at:   Device timestamp (defaults to now)
            gps_lat/lon:   Optional GPS coordinates at capture

        Raises:
            NotFoundError:  Route or order not found
            ValidationError: Unsupported mime type or order not in route
        """
        # Validate route and order exist
        route = self.db.query(Route).filter(Route.id == route_id).first()
        if not route:
            raise NotFoundError(
                code="ROUTE_NOT_FOUND",
                message=f"Route {route_id} not found",
            )

        order = self.db.query(Order).filter(Order.id == order_id).first()
        if not order:
            raise NotFoundError(
                code="ORDER_NOT_FOUND",
                message=f"Order {order_id} not found",
            )

        # Validate mime type
        if mime_type not in ALLOWED_MIME:
            raise ValidationError(
                code="UNSUPPORTED_MIME_TYPE",
                message=f"Unsupported file type '{mime_type}'. "
                        f"Allowed: {', '.join(ALLOWED_MIME)}",
            )

        # Resize photos if Pillow is available
        if evidence_type == EvidenceType.PHOTO and PILLOW_AVAILABLE:
            file_data = self._resize_photo(file_data, mime_type)

        # Build storage path
        ext = ALLOWED_MIME[mime_type]
        file_uuid = uuid.uuid4()
        relative_dir = os.path.join(str(route_id), str(order_id))
        filename = f"{file_uuid}{ext}"
        relative_path = os.path.join(relative_dir, filename)
        absolute_dir = os.path.join(self.upload_dir, relative_dir)
        absolute_path = os.path.join(absolute_dir, filename)

        # Save file
        os.makedirs(absolute_dir, exist_ok=True)
        with open(absolute_path, "wb") as f:
            f.write(file_data)

        file_size = len(file_data)
        file_url = f"/uploads/{relative_path.replace(os.sep, '/')}"

        # Create DB record
        evidence = DeliveryEvidence(
            route_id=route_id,
            order_id=order_id,
            evidence_type=evidence_type,
            file_path=relative_path,
            file_url=file_url,
            file_size_bytes=file_size,
            mime_type=mime_type,
            captured_at=captured_at or datetime.utcnow(),
            gps_lat=gps_lat,
            gps_lon=gps_lon,
            uploaded_by_user_id=uploaded_by.id,
        )

        self.db.add(evidence)
        self.db.commit()
        self.db.refresh(evidence)

        return evidence

    # ─────────────────────────────────────────────────────────────────
    # Queries
    # ─────────────────────────────────────────────────────────────────

    def get_evidence_for_order(
        self,
        route_id: UUID,
        order_id: UUID,
    ) -> List[DeliveryEvidence]:
        """Return all evidence records for a specific order within a route."""
        return (
            self.db.query(DeliveryEvidence)
            .filter(
                DeliveryEvidence.route_id == route_id,
                DeliveryEvidence.order_id == order_id,
            )
            .order_by(DeliveryEvidence.captured_at)
            .all()
        )

    def get_evidence_for_route(self, route_id: UUID) -> List[DeliveryEvidence]:
        """Return all evidence records for an entire route."""
        return (
            self.db.query(DeliveryEvidence)
            .filter(DeliveryEvidence.route_id == route_id)
            .order_by(DeliveryEvidence.captured_at)
            .all()
        )

    # ─────────────────────────────────────────────────────────────────
    # Internal helpers
    # ─────────────────────────────────────────────────────────────────

    def _resize_photo(self, file_data: bytes, mime_type: str) -> bytes:
        """
        Resize photo to max PHOTO_MAX_SIZE if larger, keeping aspect ratio.
        Returns the (possibly recompressed) bytes.
        """
        try:
            img = Image.open(io.BytesIO(file_data))
            img.thumbnail(PHOTO_MAX_SIZE, Image.LANCZOS)

            output = io.BytesIO()
            # Normalize to JPEG for photos regardless of input format
            img = img.convert("RGB")
            img.save(output, format="JPEG", quality=PHOTO_QUALITY, optimize=True)
            return output.getvalue()
        except Exception:
            # If resize fails, return original bytes unchanged
            return file_data
