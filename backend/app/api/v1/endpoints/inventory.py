"""
Inventory Engine endpoints: stock queries and movement history.
Role protection:
  - GET stock / GET movements → any authenticated user
  - POST snapshots/refresh → admin or manager only
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_admin_manager
from app.models.auth import User
from app.models.inventory import StockMovement
from app.schemas.schemas import StockLevelOut, StockMovementOut
from app.services.inventory_service import InventoryService

router = APIRouter()


@router.get("/stock", response_model=list[StockLevelOut])
async def get_current_stock(
    product_id: UUID | None = None,
    warehouse_id: UUID | None = None,
    location_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Current stock levels derived from movements. Filterable by product/warehouse/location."""

    # Build SQL dynamically — avoids passing NULL bind params and the ::uuid cast conflict
    sql = """
        SELECT
            sub.product_id,
            p.name  AS product_name,
            p.sku,
            sub.location_id,
            l.name  AS location_name,
            l.warehouse_id,
            w.name  AS warehouse_name,
            SUM(sub.qty) AS on_hand_qty
        FROM (
            SELECT product_id, to_location_id   AS location_id,  quantity AS qty
            FROM stock_movements WHERE to_location_id IS NOT NULL
            UNION ALL
            SELECT product_id, from_location_id AS location_id, -quantity AS qty
            FROM stock_movements WHERE from_location_id IS NOT NULL
        ) sub
        JOIN products   p ON p.id = sub.product_id
        JOIN locations  l ON l.id = sub.location_id
        JOIN warehouses w ON w.id = l.warehouse_id
    """

    conditions, params = [], {}

    if product_id:
        conditions.append("sub.product_id = CAST(:product_id AS uuid)")
        params["product_id"] = str(product_id)

    if warehouse_id:
        conditions.append("l.warehouse_id = CAST(:warehouse_id AS uuid)")
        params["warehouse_id"] = str(warehouse_id)

    if location_id:
        conditions.append("sub.location_id = CAST(:location_id AS uuid)")
        params["location_id"] = str(location_id)

    if conditions:
        sql += " WHERE " + " AND ".join(conditions)

    sql += """
        GROUP BY sub.product_id, sub.location_id, p.name, p.sku,
                 l.name, l.warehouse_id, w.name
        HAVING SUM(sub.qty) != 0
        ORDER BY p.name, w.name, l.name
    """

    result = await db.execute(text(sql), params)
    return [StockLevelOut(**dict(row)) for row in result.mappings().all()]


@router.get("/movements", response_model=list[StockMovementOut])
async def list_movements(
    product_id: UUID | None = None,
    location_id: UUID | None = None,
    movement_type: str | None = None,
    reference_type: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
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
async def refresh_snapshots(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin_manager),
):
    """Rebuild stock_snapshots cache from movements. Admin/Manager only."""
    inv = InventoryService(db)
    count = await inv.refresh_snapshots()
    return {"message": f"Refreshed {count} snapshot rows"}
