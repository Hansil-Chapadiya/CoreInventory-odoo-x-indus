"""
Warehouse management models: Warehouse, Location.
"""

import enum

from sqlalchemy import (
    Boolean,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, generate_uuid


class LocationType(str, enum.Enum):
    warehouse = "warehouse"
    rack = "rack"
    production = "production"
    vendor = "vendor"
    customer = "customer"
    adjustment = "adjustment"


class Warehouse(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "warehouses"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    locations = relationship("Location", back_populates="warehouse", cascade="all, delete-orphan")
    reorder_rules = relationship("ReorderRule", back_populates="warehouse")
    receipts = relationship("Receipt", back_populates="warehouse")
    delivery_orders = relationship("DeliveryOrder", back_populates="warehouse")


class Location(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "locations"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    warehouse_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("warehouses.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    location_type: Mapped[LocationType] = mapped_column(
        Enum(LocationType, name="location_type", create_type=False),
        default=LocationType.rack,
        nullable=False,
    )
    parent_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    warehouse = relationship("Warehouse", back_populates="locations")
    parent = relationship("Location", remote_side="Location.id", backref="children")

    __table_args__ = (
        UniqueConstraint("warehouse_id", "code", name="uq_location_warehouse_code"),
        Index("idx_location_warehouse", "warehouse_id"),
        Index("idx_location_type", "location_type"),
    )
