"""
Internal Transfer models: Transfer (warehouse-to-warehouse or rack-to-rack), TransferLine.
"""

from datetime import date, datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Date,
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


class Transfer(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "transfers"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    reference: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    source_warehouse_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.id"), nullable=False
    )
    dest_warehouse_id: Mapped[str] = mapped_column(
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
    source_warehouse = relationship("Warehouse", foreign_keys=[source_warehouse_id])
    dest_warehouse = relationship("Warehouse", foreign_keys=[dest_warehouse_id])
    creator = relationship("User")
    lines = relationship(
        "TransferLine", back_populates="transfer", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_transfer_status", "status"),
    )


class TransferLine(Base):
    __tablename__ = "transfer_lines"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    transfer_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transfers.id", ondelete="CASCADE"),
        nullable=False,
    )
    product_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id"), nullable=False
    )
    from_location_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id"), nullable=False
    )
    to_location_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id"), nullable=False
    )
    quantity: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False)
    transferred_qty: Mapped[float] = mapped_column(Numeric(12, 3), default=0, nullable=False)
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
    transfer = relationship("Transfer", back_populates="lines")
    product = relationship("Product")
    from_location = relationship("Location", foreign_keys=[from_location_id])
    to_location = relationship("Location", foreign_keys=[to_location_id])
    uom = relationship("UnitOfMeasure")

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_transfer_line_qty_positive"),
        Index("idx_transfer_line_transfer", "transfer_id"),
    )
