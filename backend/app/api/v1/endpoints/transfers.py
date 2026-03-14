"""
Internal Transfer endpoints: create, list, confirm/validate.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.transfer import Transfer, TransferLine
from app.models.receipt import DocumentStatus
from app.schemas.schemas import TransferCreate, DocumentOut
from app.services.inventory_service import InventoryService

router = APIRouter()


@router.get("/", response_model=list[DocumentOut])
async def list_transfers(
    status: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    q = select(Transfer).where(Transfer.is_deleted.is_(False))
    if status:
        q = q.where(Transfer.status == status)
    q = q.offset(skip).limit(limit).order_by(Transfer.created_at.desc())
    result = await db.execute(q)
    return result.scalars().all()


@router.post("/", response_model=DocumentOut, status_code=201)
async def create_transfer(payload: TransferCreate, db: AsyncSession = Depends(get_db)):
    ref_result = await db.execute(text("SELECT fn_next_reference('TRF')"))
    reference = ref_result.scalar_one()

    transfer = Transfer(
        reference=reference,
        source_warehouse_id=payload.source_warehouse_id,
        dest_warehouse_id=payload.dest_warehouse_id,
        scheduled_date=payload.scheduled_date,
        notes=payload.notes,
        created_by="00000000-0000-0000-0000-000000000000",  # TODO: from JWT
    )
    db.add(transfer)
    await db.flush()

    for line_data in payload.lines:
        line = TransferLine(
            transfer_id=transfer.id,
            **line_data.model_dump(),
        )
        db.add(line)

    await db.flush()
    await db.refresh(transfer)
    return transfer


@router.post("/{transfer_id}/validate", response_model=DocumentOut)
async def validate_transfer(transfer_id: UUID, db: AsyncSession = Depends(get_db)):
    """
    Confirm a transfer and generate INTERNAL_TRANSFER stock movements.
    """
    result = await db.execute(
        select(Transfer)
        .where(Transfer.id == transfer_id)
        .options(selectinload(Transfer.lines))
    )
    transfer = result.scalar_one_or_none()
    if not transfer:
        raise HTTPException(status_code=404, detail="Transfer not found")
    if transfer.status != DocumentStatus.draft:
        raise HTTPException(status_code=400, detail=f"Cannot validate transfer in '{transfer.status.value}' status")

    inv = InventoryService(db)

    # Check stock at source locations
    for line in transfer.lines:
        available = await inv.get_stock_at_location(line.product_id, line.from_location_id)
        if available < float(line.quantity):
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient stock for product {line.product_id} at source location. "
                       f"Available: {available}, Requested: {line.quantity}",
            )

    for line in transfer.lines:
        await inv.record_transfer(
            product_id=line.product_id,
            from_location_id=line.from_location_id,
            to_location_id=line.to_location_id,
            quantity=float(line.quantity),
            transfer_id=transfer.id,
            created_by=transfer.created_by,
        )
        line.transferred_qty = line.quantity

    transfer.status = DocumentStatus.done
    await db.flush()
    await db.refresh(transfer)
    return transfer
