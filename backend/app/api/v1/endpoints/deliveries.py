"""
Delivery Order endpoints: create, list, confirm/validate (generates stock movements).
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.delivery import DeliveryOrder, DeliveryOrderLine
from app.models.receipt import DocumentStatus
from app.schemas.schemas import DeliveryOrderCreate, DocumentOut
from app.services.inventory_service import InventoryService

router = APIRouter()


@router.get("/", response_model=list[DocumentOut])
async def list_deliveries(
    status: str | None = None,
    warehouse_id: UUID | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    q = select(DeliveryOrder).where(DeliveryOrder.is_deleted.is_(False))
    if status:
        q = q.where(DeliveryOrder.status == status)
    if warehouse_id:
        q = q.where(DeliveryOrder.warehouse_id == warehouse_id)
    q = q.offset(skip).limit(limit).order_by(DeliveryOrder.created_at.desc())
    result = await db.execute(q)
    return result.scalars().all()


@router.post("/", response_model=DocumentOut, status_code=201)
async def create_delivery(payload: DeliveryOrderCreate, db: AsyncSession = Depends(get_db)):
    ref_result = await db.execute(text("SELECT fn_next_reference('DO')"))
    reference = ref_result.scalar_one()

    delivery = DeliveryOrder(
        reference=reference,
        customer_name=payload.customer_name,
        warehouse_id=payload.warehouse_id,
        scheduled_date=payload.scheduled_date,
        shipping_address=payload.shipping_address,
        notes=payload.notes,
        created_by="00000000-0000-0000-0000-000000000000",  # TODO: from JWT
    )
    db.add(delivery)
    await db.flush()

    for line_data in payload.lines:
        line = DeliveryOrderLine(
            delivery_order_id=delivery.id,
            **line_data.model_dump(),
        )
        db.add(line)

    await db.flush()
    await db.refresh(delivery)
    return delivery


@router.post("/{delivery_id}/validate", response_model=DocumentOut)
async def validate_delivery(delivery_id: UUID, db: AsyncSession = Depends(get_db)):
    """
    Confirm a delivery and generate DELIVERY stock movements.
    Validates sufficient stock before proceeding.
    """
    result = await db.execute(
        select(DeliveryOrder)
        .where(DeliveryOrder.id == delivery_id)
        .options(selectinload(DeliveryOrder.lines))
    )
    delivery = result.scalar_one_or_none()
    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery order not found")
    if delivery.status != DocumentStatus.draft:
        raise HTTPException(status_code=400, detail=f"Cannot validate delivery in '{delivery.status.value}' status")

    inv = InventoryService(db)

    # Check stock availability before creating movements
    for line in delivery.lines:
        available = await inv.get_stock_at_location(line.product_id, line.location_id)
        if available < float(line.quantity):
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient stock for product {line.product_id} at location {line.location_id}. "
                       f"Available: {available}, Requested: {line.quantity}",
            )

    for line in delivery.lines:
        await inv.record_delivery(
            product_id=line.product_id,
            from_location_id=line.location_id,
            quantity=float(line.quantity),
            delivery_order_id=delivery.id,
            created_by=delivery.created_by,
        )
        line.delivered_qty = line.quantity

    delivery.status = DocumentStatus.done
    await db.flush()
    await db.refresh(delivery)
    return delivery
