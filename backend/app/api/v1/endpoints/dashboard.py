"""
Dashboard KPI endpoint.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.product import Product
from app.models.warehouse import Warehouse
from app.models.receipt import Receipt, DocumentStatus
from app.models.delivery import DeliveryOrder
from app.models.transfer import Transfer
from app.models.inventory import StockMovement
from app.schemas.schemas import DashboardKPIs, LowStockAlertOut

router = APIRouter()


@router.get("/kpis", response_model=DashboardKPIs)
async def get_dashboard_kpis(db: AsyncSession = Depends(get_db)):
    """Aggregate KPIs for the dashboard."""

    # Total active products
    total_products = (await db.execute(
        select(func.count()).where(Product.is_deleted.is_(False), Product.is_active.is_(True))
    )).scalar_one()

    # Total active warehouses
    total_warehouses = (await db.execute(
        select(func.count()).where(Warehouse.is_deleted.is_(False), Warehouse.is_active.is_(True))
    )).scalar_one()

    # Total stock value (sum of on_hand * cost_price)
    stock_value_result = await db.execute(text("""
        SELECT COALESCE(SUM(sub.on_hand * p.cost_price), 0)
        FROM (
            SELECT product_id, SUM(qty) AS on_hand
            FROM (
                SELECT product_id, quantity AS qty FROM stock_movements WHERE to_location_id IS NOT NULL
                UNION ALL
                SELECT product_id, -quantity AS qty FROM stock_movements WHERE from_location_id IS NOT NULL
            ) inner_sub
            GROUP BY product_id
            HAVING SUM(qty) > 0
        ) sub
        JOIN products p ON p.id = sub.product_id
    """))
    total_stock_value = float(stock_value_result.scalar_one())

    # Low stock alerts count
    low_stock_result = await db.execute(text("""
        SELECT COUNT(*) FROM (
            SELECT ws.product_id
            FROM (
                SELECT sub.product_id, l.warehouse_id, SUM(sub.qty) AS total_on_hand
                FROM (
                    SELECT product_id, to_location_id AS lid, quantity AS qty
                    FROM stock_movements WHERE to_location_id IS NOT NULL
                    UNION ALL
                    SELECT product_id, from_location_id AS lid, -quantity AS qty
                    FROM stock_movements WHERE from_location_id IS NOT NULL
                ) sub
                JOIN locations l ON l.id = sub.lid
                GROUP BY sub.product_id, l.warehouse_id
            ) ws
            JOIN reorder_rules rr ON rr.product_id = ws.product_id
                                  AND rr.warehouse_id = ws.warehouse_id
                                  AND rr.is_active = TRUE
            WHERE ws.total_on_hand <= rr.min_stock
        ) alerts
    """))
    low_stock_count = low_stock_result.scalar_one()

    # Pending documents
    pending_receipts = (await db.execute(
        select(func.count()).where(Receipt.status == DocumentStatus.draft, Receipt.is_deleted.is_(False))
    )).scalar_one()

    pending_deliveries = (await db.execute(
        select(func.count()).where(DeliveryOrder.status == DocumentStatus.draft, DeliveryOrder.is_deleted.is_(False))
    )).scalar_one()

    pending_transfers = (await db.execute(
        select(func.count()).where(Transfer.status == DocumentStatus.draft, Transfer.is_deleted.is_(False))
    )).scalar_one()

    # Movements today
    movements_today = (await db.execute(
        select(func.count()).where(
            func.date(StockMovement.created_at) == func.current_date()
        )
    )).scalar_one()

    return DashboardKPIs(
        total_products=total_products,
        total_warehouses=total_warehouses,
        total_stock_value=total_stock_value,
        low_stock_count=low_stock_count,
        pending_receipts=pending_receipts,
        pending_deliveries=pending_deliveries,
        pending_transfers=pending_transfers,
        movements_today=movements_today,
    )


@router.get("/low-stock-alerts", response_model=list[LowStockAlertOut])
async def get_low_stock_alerts(db: AsyncSession = Depends(get_db)):
    """Products where current stock <= reorder rule min_stock."""
    result = await db.execute(text("""
        SELECT
            ws.product_id,
            p.sku,
            p.name AS product_name,
            ws.warehouse_id,
            w.name AS warehouse_name,
            ws.total_on_hand AS on_hand_qty,
            rr.min_stock,
            rr.reorder_quantity
        FROM (
            SELECT sub.product_id, l.warehouse_id, SUM(sub.qty) AS total_on_hand
            FROM (
                SELECT product_id, to_location_id AS lid, quantity AS qty
                FROM stock_movements WHERE to_location_id IS NOT NULL
                UNION ALL
                SELECT product_id, from_location_id AS lid, -quantity AS qty
                FROM stock_movements WHERE from_location_id IS NOT NULL
            ) sub
            JOIN locations l ON l.id = sub.lid
            GROUP BY sub.product_id, l.warehouse_id
        ) ws
        JOIN reorder_rules rr ON rr.product_id = ws.product_id
                              AND rr.warehouse_id = ws.warehouse_id
                              AND rr.is_active = TRUE
        JOIN products p    ON p.id = ws.product_id
        JOIN warehouses w  ON w.id = ws.warehouse_id
        WHERE ws.total_on_hand <= rr.min_stock
        ORDER BY (rr.min_stock - ws.total_on_hand) DESC
    """))
    rows = result.mappings().all()
    return [LowStockAlertOut(**dict(row)) for row in rows]
