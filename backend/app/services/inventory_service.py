"""
Inventory service — the core engine that derives stock from movements.
All stock-changing operations MUST go through this service.
"""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import MovementType, StockMovement, StockSnapshot
from app.models.warehouse import Location


class InventoryService:
    """Stateless service — instantiate with a db session per request."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # Stock queries (derived from movements)
    # ------------------------------------------------------------------

    async def get_stock_at_location(
        self, product_id: UUID, location_id: UUID
    ) -> float:
        """Current on-hand qty for a product at a specific location."""
        result = await self.db.execute(
            text("""
                SELECT COALESCE(SUM(qty), 0) AS on_hand
                FROM (
                    SELECT  quantity AS qty FROM stock_movements
                    WHERE product_id = :pid AND to_location_id = :lid
                    UNION ALL
                    SELECT -quantity AS qty FROM stock_movements
                    WHERE product_id = :pid AND from_location_id = :lid
                ) sub
            """),
            {"pid": str(product_id), "lid": str(location_id)},
        )
        return float(result.scalar_one())

    async def get_stock_in_warehouse(
        self, product_id: UUID, warehouse_id: UUID
    ) -> float:
        """Sum on-hand across all locations in a warehouse."""
        result = await self.db.execute(
            text("""
                SELECT COALESCE(SUM(qty), 0)
                FROM (
                    SELECT sm.quantity AS qty
                    FROM stock_movements sm
                    JOIN locations l ON l.id = sm.to_location_id
                    WHERE sm.product_id = :pid AND l.warehouse_id = :wid
                    UNION ALL
                    SELECT -sm.quantity AS qty
                    FROM stock_movements sm
                    JOIN locations l ON l.id = sm.from_location_id
                    WHERE sm.product_id = :pid AND l.warehouse_id = :wid
                ) sub
            """),
            {"pid": str(product_id), "wid": str(warehouse_id)},
        )
        return float(result.scalar_one())

    async def get_global_stock(self, product_id: UUID) -> float:
        """Total on-hand across all warehouses."""
        result = await self.db.execute(
            text("""
                SELECT COALESCE(SUM(qty), 0)
                FROM (
                    SELECT  quantity AS qty FROM stock_movements
                    WHERE product_id = :pid AND to_location_id IS NOT NULL
                    UNION ALL
                    SELECT -quantity AS qty FROM stock_movements
                    WHERE product_id = :pid AND from_location_id IS NOT NULL
                ) sub
            """),
            {"pid": str(product_id)},
        )
        return float(result.scalar_one())

    # ------------------------------------------------------------------
    # Movement creation (the ONLY way to change stock)
    # ------------------------------------------------------------------

    async def create_movement(
        self,
        *,
        product_id: UUID,
        from_location_id: UUID | None,
        to_location_id: UUID | None,
        quantity: float,
        movement_type: MovementType,
        reference_type: str,
        reference_id: UUID,
        created_by: UUID,
        notes: str | None = None,
    ) -> StockMovement:
        """Create an immutable stock movement record."""
        if quantity <= 0:
            raise ValueError("Movement quantity must be positive")

        if from_location_id is None and to_location_id is None:
            raise ValueError("At least one of from_location_id or to_location_id is required")

        movement = StockMovement(
            product_id=product_id,
            from_location_id=from_location_id,
            to_location_id=to_location_id,
            quantity=quantity,
            movement_type=movement_type,
            reference_type=reference_type,
            reference_id=reference_id,
            created_by=created_by,
            notes=notes,
        )
        self.db.add(movement)
        await self.db.flush()
        return movement

    # ------------------------------------------------------------------
    # Convenience: operation-specific movement creators
    # ------------------------------------------------------------------

    async def record_receipt(
        self,
        *,
        product_id: UUID,
        to_location_id: UUID,
        quantity: float,
        receipt_id: UUID,
        created_by: UUID,
    ) -> StockMovement:
        """Goods IN from vendor — from_location is NULL (outside system)."""
        return await self.create_movement(
            product_id=product_id,
            from_location_id=None,
            to_location_id=to_location_id,
            quantity=quantity,
            movement_type=MovementType.RECEIPT,
            reference_type="receipt",
            reference_id=receipt_id,
            created_by=created_by,
        )

    async def record_delivery(
        self,
        *,
        product_id: UUID,
        from_location_id: UUID,
        quantity: float,
        delivery_order_id: UUID,
        created_by: UUID,
    ) -> StockMovement:
        """Goods OUT to customer — to_location is NULL (outside system)."""
        return await self.create_movement(
            product_id=product_id,
            from_location_id=from_location_id,
            to_location_id=None,
            quantity=quantity,
            movement_type=MovementType.DELIVERY,
            reference_type="delivery",
            reference_id=delivery_order_id,
            created_by=created_by,
        )

    async def record_transfer(
        self,
        *,
        product_id: UUID,
        from_location_id: UUID,
        to_location_id: UUID,
        quantity: float,
        transfer_id: UUID,
        created_by: UUID,
    ) -> StockMovement:
        """Internal move between locations."""
        return await self.create_movement(
            product_id=product_id,
            from_location_id=from_location_id,
            to_location_id=to_location_id,
            quantity=quantity,
            movement_type=MovementType.INTERNAL_TRANSFER,
            reference_type="transfer",
            reference_id=transfer_id,
            created_by=created_by,
        )

    async def record_adjustment(
        self,
        *,
        product_id: UUID,
        location_id: UUID,
        difference_qty: float,
        adjustment_id: UUID,
        created_by: UUID,
    ) -> StockMovement:
        """
        Stock correction.
        Positive difference = stock gained  (to_location = location, from = NULL).
        Negative difference = stock lost    (from_location = location, to = NULL).
        """
        if difference_qty == 0:
            raise ValueError("Adjustment difference is zero — no movement needed")

        if difference_qty > 0:
            return await self.create_movement(
                product_id=product_id,
                from_location_id=None,
                to_location_id=location_id,
                quantity=abs(difference_qty),
                movement_type=MovementType.ADJUSTMENT,
                reference_type="adjustment",
                reference_id=adjustment_id,
                created_by=created_by,
            )
        else:
            return await self.create_movement(
                product_id=product_id,
                from_location_id=location_id,
                to_location_id=None,
                quantity=abs(difference_qty),
                movement_type=MovementType.ADJUSTMENT,
                reference_type="adjustment",
                reference_id=adjustment_id,
                created_by=created_by,
            )

    # ------------------------------------------------------------------
    # Snapshot refresh (for performance optimisation)
    # ------------------------------------------------------------------

    async def refresh_snapshots(self) -> int:
        """
        Rebuild the stock_snapshots table from stock_movements.
        Returns the number of snapshot rows upserted.
        """
        result = await self.db.execute(
            text("""
                INSERT INTO stock_snapshots (id, product_id, location_id, quantity, snapshot_at)
                SELECT
                    uuid_generate_v4(),
                    sub.product_id,
                    sub.location_id,
                    SUM(sub.qty),
                    NOW()
                FROM (
                    SELECT product_id, to_location_id AS location_id, quantity AS qty
                    FROM stock_movements WHERE to_location_id IS NOT NULL
                    UNION ALL
                    SELECT product_id, from_location_id AS location_id, -quantity AS qty
                    FROM stock_movements WHERE from_location_id IS NOT NULL
                ) sub
                GROUP BY sub.product_id, sub.location_id
                ON CONFLICT (product_id, location_id)
                DO UPDATE SET
                    quantity = EXCLUDED.quantity,
                    snapshot_at = EXCLUDED.snapshot_at
            """)
        )
        return result.rowcount
