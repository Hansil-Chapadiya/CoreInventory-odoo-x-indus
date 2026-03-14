"""
Pydantic schemas for API request/response validation.
"""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# =====================================================================
# Auth
# =====================================================================

class UserCreate(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=8)
    full_name: str = Field(max_length=255)
    role: str = "viewer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: str
    username: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class TokenRefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp_code: str = Field(min_length=6, max_length=6)
    new_password: str = Field(min_length=8)


class MessageResponse(BaseModel):
    message: str


# =====================================================================
# Product
# =====================================================================

class ProductCreate(BaseModel):
    sku: str = Field(max_length=50)
    name: str = Field(max_length=255)
    description: str | None = None
    category_id: UUID | None = None
    uom_id: UUID
    barcode: str | None = None
    weight: float | None = None
    cost_price: float = 0
    sale_price: float = 0
    image_url: str | None = None


class ProductUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    category_id: UUID | None = None
    uom_id: UUID | None = None
    barcode: str | None = None
    weight: float | None = None
    cost_price: float | None = None
    sale_price: float | None = None
    image_url: str | None = None
    is_active: bool | None = None


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    sku: str
    name: str
    description: str | None
    category_id: UUID | None
    uom_id: UUID
    barcode: str | None
    weight: float | None
    cost_price: float
    sale_price: float
    is_active: bool
    created_at: datetime


class CategoryCreate(BaseModel):
    name: str = Field(max_length=150)
    description: str | None = None
    parent_id: UUID | None = None


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    description: str | None
    parent_id: UUID | None


class UomCreate(BaseModel):
    name: str = Field(max_length=50)
    symbol: str = Field(max_length=10)


class UomOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    symbol: str


class ReorderRuleCreate(BaseModel):
    product_id: UUID
    warehouse_id: UUID
    min_stock: float = 0
    max_stock: float = 0
    reorder_quantity: float = 0


class ReorderRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    product_id: UUID
    warehouse_id: UUID
    min_stock: float
    max_stock: float
    reorder_quantity: float
    is_active: bool


# =====================================================================
# Warehouse
# =====================================================================

class WarehouseCreate(BaseModel):
    name: str = Field(max_length=200)
    code: str = Field(max_length=20)
    address: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None


class WarehouseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    code: str
    address: str | None
    city: str | None
    is_active: bool
    created_at: datetime


class LocationCreate(BaseModel):
    warehouse_id: UUID
    name: str = Field(max_length=200)
    code: str = Field(max_length=50)
    location_type: str = "rack"
    parent_id: UUID | None = None


class LocationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    warehouse_id: UUID
    name: str
    code: str
    location_type: str
    parent_id: UUID | None
    is_active: bool


# =====================================================================
# Inventory Operations — Lines
# =====================================================================

class ReceiptLineIn(BaseModel):
    product_id: UUID
    location_id: UUID
    quantity: float = Field(gt=0)
    uom_id: UUID
    cost_price: float | None = None
    notes: str | None = None


class DeliveryLineIn(BaseModel):
    product_id: UUID
    location_id: UUID
    quantity: float = Field(gt=0)
    uom_id: UUID
    sale_price: float | None = None
    notes: str | None = None


class TransferLineIn(BaseModel):
    product_id: UUID
    from_location_id: UUID
    to_location_id: UUID
    quantity: float = Field(gt=0)
    uom_id: UUID
    notes: str | None = None


class AdjustmentLineIn(BaseModel):
    product_id: UUID
    location_id: UUID
    counted_qty: float
    system_qty: float
    uom_id: UUID
    notes: str | None = None


# =====================================================================
# Inventory Operations — Documents
# =====================================================================

class ReceiptCreate(BaseModel):
    vendor_name: str | None = None
    warehouse_id: UUID
    scheduled_date: date | None = None
    notes: str | None = None
    lines: list[ReceiptLineIn]


class DeliveryOrderCreate(BaseModel):
    customer_name: str | None = None
    warehouse_id: UUID
    scheduled_date: date | None = None
    shipping_address: str | None = None
    notes: str | None = None
    lines: list[DeliveryLineIn]


class TransferCreate(BaseModel):
    source_warehouse_id: UUID
    dest_warehouse_id: UUID
    scheduled_date: date | None = None
    notes: str | None = None
    lines: list[TransferLineIn]


class AdjustmentCreate(BaseModel):
    warehouse_id: UUID
    reason: str = "cycle_count"
    notes: str | None = None
    lines: list[AdjustmentLineIn]


class DocumentOut(BaseModel):
    """Generic response for any inventory document."""
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    reference: str
    status: str
    created_at: datetime
    updated_at: datetime


# =====================================================================
# Inventory Engine
# =====================================================================

class StockMovementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    product_id: UUID
    from_location_id: UUID | None
    to_location_id: UUID | None
    quantity: float
    movement_type: str
    reference_type: str
    reference_id: UUID
    created_at: datetime


class StockLevelOut(BaseModel):
    product_id: UUID
    product_name: str
    sku: str
    location_id: UUID | None = None
    location_name: str | None = None
    warehouse_id: UUID | None = None
    warehouse_name: str | None = None
    on_hand_qty: float


class LowStockAlertOut(BaseModel):
    product_id: UUID
    sku: str
    product_name: str
    warehouse_id: UUID
    warehouse_name: str
    on_hand_qty: float
    min_stock: float
    reorder_quantity: float


# =====================================================================
# Dashboard KPIs
# =====================================================================

class DashboardKPIs(BaseModel):
    total_products: int
    total_warehouses: int
    total_stock_value: float
    low_stock_count: int
    pending_receipts: int
    pending_deliveries: int
    pending_transfers: int
    movements_today: int
