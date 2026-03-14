"""
Receipt endpoints: create, list, confirm/validate (generates stock movements).
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.receipt import Receipt, ReceiptLine, DocumentStatus
from app.schemas.schemas import ReceiptCreate, DocumentOut
from app.services.inventory_service import InventoryService

router = APIRouter()


@router.get("/", response_model=list[DocumentOut])
async def list_receipts(
    status: str | None = None,
    warehouse_id: UUID | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    q = select(Receipt).where(Receipt.is_deleted.is_(False))
    if status:
        q = q.where(Receipt.status == status)
    if warehouse_id:
        q = q.where(Receipt.warehouse_id == warehouse_id)
    q = q.offset(skip).limit(limit).order_by(Receipt.created_at.desc())
    result = await db.execute(q)
    return result.scalars().all()


@router.post("/", response_model=DocumentOut, status_code=201)
async def create_receipt(payload: ReceiptCreate, db: AsyncSession = Depends(get_db)):
    # Generate reference number
    ref_result = await db.execute(text("SELECT fn_next_reference('REC')"))
    reference = ref_result.scalar_one()

    receipt = Receipt(
        reference=reference,
        vendor_name=payload.vendor_name,
        warehouse_id=payload.warehouse_id,
        scheduled_date=payload.scheduled_date,
        notes=payload.notes,
        created_by="00000000-0000-0000-0000-000000000000",  # TODO: from JWT
    )
    db.add(receipt)
    await db.flush()

    for line_data in payload.lines:
        line = ReceiptLine(
            receipt_id=receipt.id,
            **line_data.model_dump(),
        )
        db.add(line)

    await db.flush()
    await db.refresh(receipt)
    return receipt


@router.post("/{receipt_id}/validate", response_model=DocumentOut)
async def validate_receipt(receipt_id: UUID, db: AsyncSession = Depends(get_db)):
    """
    Confirm a receipt and generate RECEIPT stock movements.
    Transitions: draft -> done.
    """
    result = await db.execute(
        select(Receipt)
        .where(Receipt.id == receipt_id)
        .options(selectinload(Receipt.lines))
    )
    receipt = result.scalar_one_or_none()
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    if receipt.status != DocumentStatus.draft:
        raise HTTPException(status_code=400, detail=f"Cannot validate receipt in '{receipt.status.value}' status")

    inv = InventoryService(db)
    for line in receipt.lines:
        await inv.record_receipt(
            product_id=line.product_id,
            to_location_id=line.location_id,
            quantity=float(line.quantity),
            receipt_id=receipt.id,
            created_by=receipt.created_by,
        )
        line.received_qty = line.quantity

    receipt.status = DocumentStatus.done
    await db.flush()
    await db.refresh(receipt)
    return receipt
