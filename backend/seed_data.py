"""
CoreInventory — Seed Data Script
=================================
Populates the Neon DB with realistic test data:
  - 2 users (admin + manager)
  - 2 warehouses with 3 locations each
  - 5 products
  - 2 validated receipts → stock movements so /inventory/stock returns data

Run from the backend directory:
    python seed_data.py
"""

import asyncio
import sys
import os
from uuid import UUID

# ── Make sure app imports resolve ──────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session as AsyncSessionLocal
from app.core.security import hash_password
from app.models.auth import User
from app.models.product import Product, ProductCategory, UnitOfMeasure
from app.models.warehouse import Location, LocationType, Warehouse
from app.models.receipt import DocumentStatus, Receipt, ReceiptLine
from app.services.inventory_service import InventoryService


# ── Helpers ────────────────────────────────────────────────────────────────

async def _get_or_create_user(
    db: AsyncSession, email: str, username: str, full_name: str,
    password: str, role: str,
) -> User:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user:
        print(f"  [skip] user '{username}' already exists")
        return user
    user = User(
        email=email,
        username=username,
        full_name=full_name,
        hashed_password=hash_password(password),
        role=role,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    print(f"  [OK]   created user '{username}' ({role})")
    return user


async def _get_or_create_warehouse(
    db: AsyncSession, name: str, code: str, address: str,
) -> Warehouse:
    result = await db.execute(
        select(Warehouse).where(Warehouse.code == code, Warehouse.is_deleted.is_(False))
    )
    wh = result.scalar_one_or_none()
    if wh:
        print(f"  [skip] warehouse '{code}' already exists")
        return wh
    wh = Warehouse(name=name, code=code, address=address)
    db.add(wh)
    await db.flush()
    await db.refresh(wh)
    print(f"  [OK]   created warehouse '{code}' — {name}")
    return wh


async def _get_or_create_location(
    db: AsyncSession, warehouse_id: UUID, name: str, code: str,
    location_type: LocationType,
) -> Location:
    result = await db.execute(
        select(Location).where(
            Location.warehouse_id == warehouse_id,
            Location.code == code,
            Location.is_deleted.is_(False),
        )
    )
    loc = result.scalar_one_or_none()
    if loc:
        print(f"  [skip] location '{code}' already exists")
        return loc
    loc = Location(
        warehouse_id=warehouse_id, name=name, code=code,
        location_type=location_type,
    )
    db.add(loc)
    await db.flush()
    await db.refresh(loc)
    print(f"  [OK]   created location '{code}'")
    return loc


async def _get_uom(db: AsyncSession, symbol: str) -> UnitOfMeasure:
    result = await db.execute(
        select(UnitOfMeasure).where(UnitOfMeasure.symbol == symbol)
    )
    uom = result.scalar_one_or_none()
    if not uom:
        raise RuntimeError(
            f"UOM '{symbol}' not found — run 001_schema.sql first to apply seed UOMs"
        )
    return uom


async def _get_category(db: AsyncSession, name: str) -> ProductCategory:
    result = await db.execute(
        select(ProductCategory).where(ProductCategory.name == name)
    )
    cat = result.scalar_one_or_none()
    if not cat:
        raise RuntimeError(
            f"Category '{name}' not found — run 001_schema.sql first to apply seed categories"
        )
    return cat


async def _get_or_create_product(
    db: AsyncSession, name: str, sku: str, uom_id: UUID,
    category_id: UUID, cost_price: float, sale_price: float,
) -> Product:
    result = await db.execute(
        select(Product).where(Product.sku == sku, Product.is_deleted.is_(False))
    )
    product = result.scalar_one_or_none()
    if product:
        print(f"  [skip] product '{sku}' already exists")
        return product
    product = Product(
        name=name, sku=sku, uom_id=uom_id,
        category_id=category_id, cost_price=cost_price, sale_price=sale_price,
    )
    db.add(product)
    await db.flush()
    await db.refresh(product)
    print(f"  [OK]   created product '{sku}' — {name}")
    return product


async def _create_and_validate_receipt(
    db: AsyncSession,
    reference: str,
    vendor_name: str,
    warehouse_id: UUID,
    created_by: UUID,
    lines: list[dict],
) -> Receipt | None:
    """
    lines: [{"product_id", "location_id", "uom_id", "quantity", "cost_price"}]
    """
    result = await db.execute(
        select(Receipt).where(Receipt.reference == reference)
    )
    if result.scalar_one_or_none():
        print(f"  [skip] receipt '{reference}' already exists")
        return None

    receipt = Receipt(
        reference=reference,
        vendor_name=vendor_name,
        warehouse_id=warehouse_id,
        status=DocumentStatus.draft,
        created_by=created_by,
    )
    db.add(receipt)
    await db.flush()

    inv = InventoryService(db)
    for ld in lines:
        line = ReceiptLine(
            receipt_id=receipt.id,
            product_id=ld["product_id"],
            location_id=ld["location_id"],
            uom_id=ld["uom_id"],
            quantity=ld["quantity"],
            received_qty=ld["quantity"],
            cost_price=ld["cost_price"],
        )
        db.add(line)
        await db.flush()

        await inv.record_receipt(
            product_id=ld["product_id"],
            to_location_id=ld["location_id"],
            quantity=float(ld["quantity"]),
            receipt_id=receipt.id,
            created_by=created_by,
        )

    receipt.status = DocumentStatus.done
    await db.flush()
    await db.refresh(receipt)
    print(f"  [OK]   receipt '{reference}' validated — {len(lines)} movement(s) created")
    return receipt


# ── Main seed logic ────────────────────────────────────────────────────────

async def seed():
    async with AsyncSessionLocal() as db:
        async with db.begin():

            print("\n=== USERS ===")
            admin = await _get_or_create_user(
                db,
                email="admin@coreinventory.com",
                username="admin",
                full_name="System Administrator",
                password="Admin@1234",
                role="admin",
            )
            manager = await _get_or_create_user(
                db,
                email="manager@coreinventory.com",
                username="manager",
                full_name="Warehouse Manager",
                password="Manager@1234",
                role="manager",
            )

            print("\n=== WAREHOUSES & LOCATIONS ===")
            wh1 = await _get_or_create_warehouse(
                db, name="Main Warehouse", code="WH-MAIN",
                address="123 Industrial Zone, City A",
            )
            wh2 = await _get_or_create_warehouse(
                db, name="Cold Storage Facility", code="WH-COLD",
                address="456 Logistics Park, City B",
            )

            # Locations for Main Warehouse
            loc_main_a1 = await _get_or_create_location(
                db, wh1.id, name="Zone A - Rack 1", code="WH-MAIN-A1",
                location_type=LocationType.rack,
            )
            loc_main_a2 = await _get_or_create_location(
                db, wh1.id, name="Zone A - Rack 2", code="WH-MAIN-A2",
                location_type=LocationType.rack,
            )
            await _get_or_create_location(
                db, wh1.id, name="Zone B - Rack 1", code="WH-MAIN-B1",
                location_type=LocationType.rack,
            )

            # Locations for Cold Storage
            loc_cold_r1 = await _get_or_create_location(
                db, wh2.id, name="Cold Room 1", code="WH-COLD-R1",
                location_type=LocationType.rack,
            )
            loc_cold_r2 = await _get_or_create_location(
                db, wh2.id, name="Cold Room 2", code="WH-COLD-R2",
                location_type=LocationType.rack,
            )
            await _get_or_create_location(
                db, wh2.id, name="Dispatch Bay", code="WH-COLD-D1",
                location_type=LocationType.warehouse,
            )

            print("\n=== PRODUCTS ===")
            uom_pcs = await _get_uom(db, "pcs")
            uom_kg  = await _get_uom(db, "kg")
            uom_box = await _get_uom(db, "box")

            cat_raw      = await _get_category(db, "Raw Materials")
            cat_finished = await _get_category(db, "Finished Goods")
            cat_parts    = await _get_category(db, "Spare Parts")

            p_laptop = await _get_or_create_product(
                db, name="Laptop Pro 15", sku="ELEC-LP15",
                uom_id=uom_pcs.id, category_id=cat_finished.id,
                cost_price=850.00, sale_price=1199.99,
            )
            p_phone = await _get_or_create_product(
                db, name="Smartphone X12", sku="ELEC-SP12",
                uom_id=uom_pcs.id, category_id=cat_finished.id,
                cost_price=320.00, sale_price=599.99,
            )
            p_cable = await _get_or_create_product(
                db, name="USB-C Cable 2m", sku="ACC-USBC2M",
                uom_id=uom_box.id, category_id=cat_finished.id,
                cost_price=8.50, sale_price=19.99,
            )
            p_steel = await _get_or_create_product(
                db, name="Steel Sheet 304", sku="RAW-SS304",
                uom_id=uom_kg.id, category_id=cat_raw.id,
                cost_price=2.80, sale_price=5.50,
            )
            p_motor = await _get_or_create_product(
                db, name="DC Motor 12V", sku="PART-DCM12",
                uom_id=uom_pcs.id, category_id=cat_parts.id,
                cost_price=45.00, sale_price=89.99,
            )

            print("\n=== RECEIPTS (Generating Stock Movements) ===")
            await _create_and_validate_receipt(
                db,
                reference="RCP-0001",
                vendor_name="TechSupplier Ltd.",
                warehouse_id=wh1.id,
                created_by=admin.id,
                lines=[
                    {"product_id": p_laptop.id, "location_id": loc_main_a1.id,
                     "uom_id": uom_pcs.id, "quantity": 50, "cost_price": 850.00},
                    {"product_id": p_phone.id,  "location_id": loc_main_a1.id,
                     "uom_id": uom_pcs.id, "quantity": 100, "cost_price": 320.00},
                    {"product_id": p_cable.id,  "location_id": loc_main_a2.id,
                     "uom_id": uom_box.id, "quantity": 500, "cost_price": 8.50},
                ],
            )
            await _create_and_validate_receipt(
                db,
                reference="RCP-0002",
                vendor_name="Industrial Metals Co.",
                warehouse_id=wh2.id,
                created_by=manager.id,
                lines=[
                    {"product_id": p_steel.id, "location_id": loc_cold_r1.id,
                     "uom_id": uom_kg.id, "quantity": 2000, "cost_price": 2.80},
                    {"product_id": p_motor.id, "location_id": loc_cold_r2.id,
                     "uom_id": uom_pcs.id, "quantity": 75, "cost_price": 45.00},
                    {"product_id": p_laptop.id, "location_id": loc_cold_r1.id,
                     "uom_id": uom_pcs.id, "quantity": 20, "cost_price": 850.00},
                ],
            )

        print("\n=== DONE ===")
        print("Seed data committed successfully.\n")
        print("Login credentials:")
        print("  Admin   — email: admin@coreinventory.com   | password: Admin@1234")
        print("  Manager — email: manager@coreinventory.com | password: Manager@1234\n")
        print("Data created:")
        print("  2 users, 2 warehouses, 6 locations, 5 products, 2 receipts, 6 movements\n")
        print("Routes to verify (after login with Bearer token):")
        print("  GET /api/v1/warehouses/           -> 2 warehouses")
        print("  GET /api/v1/products/             -> 5 products")
        print("  GET /api/v1/products/uom/         -> 6 UOMs")
        print("  GET /api/v1/products/categories/  -> 4 categories")
        print("  GET /api/v1/inventory/stock       -> 6 stock levels")
        print("  GET /api/v1/inventory/movements   -> 6 movements")
        print("  GET /api/v1/receipts/             -> 2 receipts")


if __name__ == "__main__":
    asyncio.run(seed())
