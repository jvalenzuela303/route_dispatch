"""
Pydantic schemas for Audit Log operations

Response models for audit trail queries
"""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional
import uuid

from app.models.enums import AuditResult


class UserBasic(BaseModel):
    """Basic user information for nested responses"""
    id: uuid.UUID
    username: str

    class Config:
        from_attributes = True


class AuditLogResponse(BaseModel):
    """Schema for audit log response"""
    id: uuid.UUID
    timestamp: datetime
    user: Optional[UserBasic]
    action: str
    entity_type: str
    entity_id: Optional[uuid.UUID]
    details: dict
    result: AuditResult
    ip_address: Optional[str]

    class Config:
        from_attributes = True


class AuditTrailResponse(BaseModel):
    """Schema for audit trail list"""
    audit_logs: list[AuditLogResponse]
    total: int


class AuditLogFilter(BaseModel):
    """Schema for filtering audit logs"""
    entity_type: Optional[str] = None
    entity_id: Optional[uuid.UUID] = None
    user_id: Optional[uuid.UUID] = None
    action: Optional[str] = None
    result: Optional[AuditResult] = None
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None
    limit: int = 50
    offset: int = 0
