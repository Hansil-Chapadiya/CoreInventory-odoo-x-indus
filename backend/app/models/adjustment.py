"""
Stock Adjustment models: StockAdjustment, AdjustmentLine.
"""

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Computed,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    Boolean,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, generate_uuid
from app.models.receipt import DocumentStatus


class AdjustmentReason(str, enum.Enum):
    damaged = "damaged"
    expired = "expired"
    cycle_count = "cycle_count"
    initial_stock = "initial_stock"
    other = "other"


class StockAdjustment(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "stock_adjustments"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    reference: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    warehouse_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.id"), nullable=False
    )
    reason: Mapped[AdjustmentReason] = mapped_column(
        Enum(AdjustmentReason, name="adjustment_reason", create_type=False),
        default=AdjustmentReason.cycle_count,
        nullable=False,
    )
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="document_status", create_type=False),
        default=DocumentStatus.draft,
        nullable=False,
    )
    completed_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    # Relationships
    warehouse = relationship("Warehouse")
    creator = relationship("User")
    lines = relationship(
        "AdjustmentLine", back_populates="adjustment", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_adjustment_status", "status"),
    )


class AdjustmentLine(Base):
    __tablename__ = "adjustment_lines"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    adjustment_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stock_adjustments.id", ondelete="CASCADE"),
        nullable=False,
    )
    product_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id"), nullable=False
    )
    location_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id"), nullable=False
    )
    counted_qty: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False)
    system_qty: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False)
    difference_qty: Mapped[float] = mapped_column(
        Numeric(12, 3),
        Computed("counted_qty - system_qty", persisted=True),
    )
    uom_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("units_of_measure.id"), nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    adjustment = relationship("StockAdjustment", back_populates="lines")
    product = relationship("Product")
    location = relationship("Location")
    uom = relationship("UnitOfMeasure")

    __table_args__ = (
        Index("idx_adjustment_line_adj", "adjustment_id"),
    )
