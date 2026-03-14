"""
Stock Adjustment endpoints: create, list, confirm/validate.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.adjustment import StockAdjustment, AdjustmentLine
from app.models.receipt import DocumentStatus
from app.schemas.schemas import AdjustmentCreate, DocumentOut
from app.services.inventory_service import InventoryService

router = APIRouter()


@router.get("/", response_model=list[DocumentOut])
async def list_adjustments(
    status: str | None = None,
    warehouse_id: UUID | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    q = select(StockAdjustment).where(StockAdjustment.is_deleted.is_(False))
    if status:
        q = q.where(StockAdjustment.status == status)
    if warehouse_id:
        q = q.where(StockAdjustment.warehouse_id == warehouse_id)
    q = q.offset(skip).limit(limit).order_by(StockAdjustment.created_at.desc())
    result = await db.execute(q)
    return result.scalars().all()


@router.post("/", response_model=DocumentOut, status_code=201)
async def create_adjustment(payload: AdjustmentCreate, db: AsyncSession = Depends(get_db)):
    ref_result = await db.execute(text("SELECT fn_next_reference('ADJ')"))
    reference = ref_result.scalar_one()

    adj = StockAdjustment(
        reference=reference,
        warehouse_id=payload.warehouse_id,
        reason=payload.reason,
        notes=payload.notes,
        created_by="00000000-0000-0000-0000-000000000000",  # TODO: from JWT
    )
    db.add(adj)
    await db.flush()

    for line_data in payload.lines:
        line = AdjustmentLine(
            adjustment_id=adj.id,
            **line_data.model_dump(),
        )
        db.add(line)

    await db.flush()
    await db.refresh(adj)
    return adj


@router.post("/{adjustment_id}/validate", response_model=DocumentOut)
async def validate_adjustment(adjustment_id: UUID, db: AsyncSession = Depends(get_db)):
    """
    Confirm an adjustment and generate ADJUSTMENT stock movements.
    Creates positive or negative movements based on difference_qty per line.
    """
    result = await db.execute(
        select(StockAdjustment)
        .where(StockAdjustment.id == adjustment_id)
        .options(selectinload(StockAdjustment.lines))
    )
    adj = result.scalar_one_or_none()
    if not adj:
        raise HTTPException(status_code=404, detail="Adjustment not found")
    if adj.status != DocumentStatus.draft:
        raise HTTPException(status_code=400, detail=f"Cannot validate adjustment in '{adj.status.value}' status")

    inv = InventoryService(db)
    for line in adj.lines:
        diff = float(line.counted_qty) - float(line.system_qty)
        if diff == 0:
            continue
        await inv.record_adjustment(
            product_id=line.product_id,
            location_id=line.location_id,
            difference_qty=diff,
            adjustment_id=adj.id,
            created_by=adj.created_by,
        )

    adj.status = DocumentStatus.done
    await db.flush()
    await db.refresh(adj)
    return adj
