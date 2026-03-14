"""
Inventory Engine models: StockMovement (immutable ledger), StockSnapshot (cache).
"""

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, generate_uuid


class MovementType(str, enum.Enum):
    RECEIPT = "RECEIPT"
    DELIVERY = "DELIVERY"
    INTERNAL_TRANSFER = "INTERNAL_TRANSFER"
    ADJUSTMENT = "ADJUSTMENT"


class StockMovement(Base):
    """
    Immutable stock movement ledger.
    Every inventory change produces exactly one row here.
    No updated_at — movements are never modified. Corrections are reversal entries.
    """

    __tablename__ = "stock_movements"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    product_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id"), nullable=False
    )
    from_location_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id"), nullable=True
    )
    to_location_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id"), nullable=True
    )
    quantity: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False)
    movement_type: Mapped[MovementType] = mapped_column(
        Enum(MovementType, name="movement_type", create_type=False),
        nullable=False,
    )
    reference_type: Mapped[str] = mapped_column(String(20), nullable=False)
    reference_id: Mapped[str] = mapped_column(UUID(as_uuid=True), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    product = relationship("Product", back_populates="stock_movements")
    from_location = relationship("Location", foreign_keys=[from_location_id])
    to_location = relationship("Location", foreign_keys=[to_location_id])
    creator = relationship("User")

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_movement_qty_positive"),
        Index("idx_sm_product", "product_id"),
        Index("idx_sm_from_location", "from_location_id", postgresql_where="from_location_id IS NOT NULL"),
        Index("idx_sm_to_location", "to_location_id", postgresql_where="to_location_id IS NOT NULL"),
        Index("idx_sm_movement_type", "movement_type"),
        Index("idx_sm_reference", "reference_type", "reference_id"),
        Index("idx_sm_created_at", "created_at"),
        Index("idx_sm_product_location", "product_id", "to_location_id", "from_location_id"),
    )


class StockSnapshot(Base):
    """
    Performance cache table. Periodically refreshed from stock_movements.
    Used for fast stock lookups without aggregating the full movement history.
    """

    __tablename__ = "stock_snapshots"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    product_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id"), nullable=False
    )
    location_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id"), nullable=False
    )
    quantity: Mapped[float] = mapped_column(Numeric(12, 3), default=0, nullable=False)
    snapshot_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    product = relationship("Product")
    location = relationship("Location")

    __table_args__ = (
        UniqueConstraint("product_id", "location_id", name="uq_snapshot_product_location"),
        Index("idx_snapshot_product", "product_id"),
        Index("idx_snapshot_location", "location_id"),
    )
