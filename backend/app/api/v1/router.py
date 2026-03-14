"""
API v1 router — aggregates all module routers.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    products,
    warehouses,
    receipts,
    deliveries,
    transfers,
    adjustments,
    inventory,
    dashboard,
)

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(products.router, prefix="/products", tags=["Products"])
api_router.include_router(warehouses.router, prefix="/warehouses", tags=["Warehouses"])
api_router.include_router(receipts.router, prefix="/receipts", tags=["Receipts"])
api_router.include_router(deliveries.router, prefix="/deliveries", tags=["Delivery Orders"])
api_router.include_router(transfers.router, prefix="/transfers", tags=["Internal Transfers"])
api_router.include_router(adjustments.router, prefix="/adjustments", tags=["Stock Adjustments"])
api_router.include_router(inventory.router, prefix="/inventory", tags=["Inventory Engine"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
