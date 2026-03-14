"""
Inventory Engine endpoints: stock queries and movement history.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.inventory import StockMovement
from app.schemas.schemas import StockMovementOut, StockLevelOut
from app.services.inventory_service import InventoryService

router = APIRouter()


@router.get("/stock", response_model=list[StockLevelOut])
async def get_current_stock(
    product_id: UUID | None = None,
    warehouse_id: UUID | None = None,
    location_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Get current stock levels derived from stock movements.
    Filters by product, warehouse, or location.
    """
    q = text("""
        SELECT
            sub.product_id,
            p.name AS product_name,
            p.sku,
            sub.location_id,
            l.name AS location_name,
            l.warehouse_id,
            w.name AS warehouse_name,
            SUM(sub.qty) AS on_hand_qty
        FROM (
            SELECT product_id, to_location_id AS location_id, quantity AS qty
            FROM stock_movements WHERE to_location_id IS NOT NULL
            UNION ALL
            SELECT product_id, from_location_id AS location_id, -quantity AS qty
            FROM stock_movements WHERE from_location_id IS NOT NULL
        ) sub
        JOIN products p   ON p.id = sub.product_id
        JOIN locations l  ON l.id = sub.location_id
        JOIN warehouses w ON w.id = l.warehouse_id
        WHERE 1=1
            AND (:product_id IS NULL OR sub.product_id = :product_id)
            AND (:warehouse_id IS NULL OR l.warehouse_id = :warehouse_id)
            AND (:location_id IS NULL OR sub.location_id = :location_id)
        GROUP BY sub.product_id, sub.location_id, p.name, p.sku,
                 l.name, l.warehouse_id, w.name
        HAVING SUM(sub.qty) != 0
        ORDER BY p.name, w.name, l.name
    """)
    result = await db.execute(q, {
        "product_id": str(product_id) if product_id else None,
        "warehouse_id": str(warehouse_id) if warehouse_id else None,
        "location_id": str(location_id) if location_id else None,
    })
    rows = result.mappings().all()
    return [StockLevelOut(**dict(row)) for row in rows]


@router.get("/movements", response_model=list[StockMovementOut])
async def list_movements(
    product_id: UUID | None = None,
    location_id: UUID | None = None,
    movement_type: str | None = None,
    reference_type: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List stock movements with filtering and pagination."""
    q = select(StockMovement)
    if product_id:
        q = q.where(StockMovement.product_id == product_id)
    if location_id:
        q = q.where(
            (StockMovement.from_location_id == location_id)
            | (StockMovement.to_location_id == location_id)
        )
    if movement_type:
        q = q.where(StockMovement.movement_type == movement_type)
    if reference_type:
        q = q.where(StockMovement.reference_type == reference_type)
    q = q.offset(skip).limit(limit).order_by(StockMovement.created_at.desc())
    result = await db.execute(q)
    return result.scalars().all()


@router.post("/snapshots/refresh")
async def refresh_snapshots(db: AsyncSession = Depends(get_db)):
    """Rebuild stock_snapshots from stock_movements for fast lookups."""
    inv = InventoryService(db)
    count = await inv.refresh_snapshots()
    return {"message": f"Refreshed {count} snapshot rows"}
