"""
Receipt models: Receipt (goods IN from vendors), ReceiptLine.
"""

import enum
from datetime import date, datetime, timezone

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    Boolean,
    CheckConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, generate_uuid


class DocumentStatus(str, enum.Enum):
    draft = "draft"
    confirmed = "confirmed"
    in_progress = "in_progress"
    done = "done"
    cancelled = "cancelled"


class Receipt(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "receipts"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    reference: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    vendor_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    warehouse_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.id"), nullable=False
    )
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="document_status", create_type=False),
        default=DocumentStatus.draft,
        nullable=False,
    )
    scheduled_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    completed_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    # Relationships
    warehouse = relationship("Warehouse", back_populates="receipts")
    creator = relationship("User")
    lines = relationship("ReceiptLine", back_populates="receipt", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_receipt_status", "status"),
        Index("idx_receipt_wh", "warehouse_id"),
    )


class ReceiptLine(Base):
    __tablename__ = "receipt_lines"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    receipt_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("receipts.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id"), nullable=False
    )
    location_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id"), nullable=False
    )
    quantity: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False)
    received_qty: Mapped[float] = mapped_column(Numeric(12, 3), default=0, nullable=False)
    uom_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("units_of_measure.id"), nullable=False
    )
    cost_price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    receipt = relationship("Receipt", back_populates="lines")
    product = relationship("Product")
    location = relationship("Location")
    uom = relationship("UnitOfMeasure")

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_receipt_line_qty_positive"),
        Index("idx_receipt_line_receipt", "receipt_id"),
    )
