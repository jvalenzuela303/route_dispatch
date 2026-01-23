"""
Base models and mixins for SQLAlchemy models

Provides common functionality across all database models including:
- UUID primary keys
- Timestamp tracking (created_at, updated_at)
- Declarative base configuration
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import MetaData, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, declared_attr


# Naming convention for constraints - helps with Alembic migrations
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}

metadata = MetaData(naming_convention=NAMING_CONVENTION)


class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy models

    Provides metadata configuration for consistent constraint naming
    across all tables and migrations.
    """
    metadata = metadata

    # Type annotation for metadata
    type_annotation_map = {
        datetime: DateTime(timezone=True)
    }


class UUIDMixin:
    """
    Mixin to add UUID primary key to models

    Uses PostgreSQL UUID type with Python uuid4 as default generator.
    UUIDs are preferred over auto-incrementing integers for:
    - Better security (non-sequential)
    - Easier data merging across systems
    - No collision risk when generating IDs client-side
    """

    @declared_attr
    def id(cls) -> Mapped[uuid.UUID]:
        return mapped_column(
            UUID(as_uuid=True),
            primary_key=True,
            default=uuid.uuid4,
            unique=True,
            nullable=False,
            comment="Unique identifier for this record"
        )


class TimestampMixin:
    """
    Mixin to add timestamp tracking to models

    Automatically tracks:
    - created_at: Set once when record is created
    - updated_at: Updated automatically on every modification

    All timestamps use timezone-aware datetime (UTC recommended).
    """

    @declared_attr
    def created_at(cls) -> Mapped[datetime]:
        return mapped_column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
            comment="Timestamp when record was created"
        )

    @declared_attr
    def updated_at(cls) -> Mapped[datetime]:
        return mapped_column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
            onupdate=func.now(),
            comment="Timestamp when record was last updated"
        )


class BaseModel(Base, UUIDMixin, TimestampMixin):
    """
    Abstract base model combining all common mixins

    Provides:
    - UUID primary key (id)
    - Timestamp tracking (created_at, updated_at)
    - Declarative base functionality

    Use this as the base class for most models in the application.
    """
    __abstract__ = True

    def __repr__(self) -> str:
        """
        Generic representation for debugging

        Shows class name and id. Override in specific models to show
        more relevant information.
        """
        return f"<{self.__class__.__name__}(id={self.id})>"

    def to_dict(self) -> dict[str, Any]:
        """
        Convert model instance to dictionary

        Useful for serialization and debugging. Excludes SQLAlchemy
        internal attributes (those starting with _).

        Returns:
            Dictionary with column names as keys and values as values
        """
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }
