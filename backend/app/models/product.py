"""
Product management models: Product, ProductCategory, UnitOfMeasure, ReorderRule.
"""

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, generate_uuid


class ProductCategory(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "product_categories"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_categories.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Self-referential relationship for category hierarchy
    parent = relationship("ProductCategory", remote_side="ProductCategory.id", backref="children")
    products = relationship("Product", back_populates="category")


class UnitOfMeasure(Base, SoftDeleteMixin):
    __tablename__ = "units_of_measure"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    symbol: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    created_at = mapped_column(
        __import__("sqlalchemy").DateTime(timezone=True),
        default=lambda: __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ),
        nullable=False,
    )

    products = relationship("Product", back_populates="uom")


class Product(Base, TimestampMixin, SoftDeleteMixin):
    """
    Product master data.
    IMPORTANT: No stock_quantity column. Stock is derived from stock_movements.
    """

    __tablename__ = "products"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    sku: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_categories.id", ondelete="SET NULL"),
        nullable=True,
    )
    uom_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("units_of_measure.id"),
        nullable=False,
    )
    barcode: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    weight: Mapped[float | None] = mapped_column(Numeric(10, 3), nullable=True)
    cost_price: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    sale_price: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    category = relationship("ProductCategory", back_populates="products")
    uom = relationship("UnitOfMeasure", back_populates="products")
    reorder_rules = relationship("ReorderRule", back_populates="product", cascade="all, delete-orphan")
    stock_movements = relationship("StockMovement", back_populates="product")

    __table_args__ = (
        Index("idx_product_sku", "sku"),
        Index("idx_product_barcode", "barcode", postgresql_where="barcode IS NOT NULL"),
        Index("idx_product_category", "category_id"),
        Index("idx_product_active", "is_active", "is_deleted"),
    )


class ReorderRule(Base, TimestampMixin):
    __tablename__ = "reorder_rules"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    product_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )
    warehouse_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("warehouses.id", ondelete="CASCADE"),
        nullable=False,
    )
    min_stock: Mapped[float] = mapped_column(Numeric(12, 3), default=0, nullable=False)
    max_stock: Mapped[float] = mapped_column(Numeric(12, 3), default=0, nullable=False)
    reorder_quantity: Mapped[float] = mapped_column(
        Numeric(12, 3), default=0, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    product = relationship("Product", back_populates="reorder_rules")
    warehouse = relationship("Warehouse", back_populates="reorder_rules")

    __table_args__ = (
        UniqueConstraint("product_id", "warehouse_id", name="uq_reorder_product_warehouse"),
    )
