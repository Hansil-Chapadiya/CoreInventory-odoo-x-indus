"""
Delivery Order models: DeliveryOrder (goods OUT to customers), DeliveryOrderLine.
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


class DeliveryOrder(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "delivery_orders"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    reference: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    customer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
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
    shipping_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    # Relationships
    warehouse = relationship("Warehouse", back_populates="delivery_orders")
    creator = relationship("User")
    lines = relationship(
        "DeliveryOrderLine", back_populates="delivery_order", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_delivery_status", "status"),
        Index("idx_delivery_wh", "warehouse_id"),
    )


class DeliveryOrderLine(Base):
    __tablename__ = "delivery_order_lines"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    delivery_order_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("delivery_orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    product_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id"), nullable=False
    )
    location_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id"), nullable=False
    )
    quantity: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False)
    delivered_qty: Mapped[float] = mapped_column(Numeric(12, 3), default=0, nullable=False)
    uom_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("units_of_measure.id"), nullable=False
    )
    sale_price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    delivery_order = relationship("DeliveryOrder", back_populates="lines")
    product = relationship("Product")
    location = relationship("Location")
    uom = relationship("UnitOfMeasure")

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_delivery_line_qty_positive"),
        Index("idx_delivery_line_do", "delivery_order_id"),
    )
