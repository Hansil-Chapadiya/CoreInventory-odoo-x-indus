# CoreInventory — Production-Grade Inventory Management System

A **movement-based inventory system** with multi-warehouse support, built with **FastAPI** + **SQLAlchemy** (async) backend and **PostgreSQL (Neon)** database.

```
🏗️  Stock is NEVER stored on products.
📊 Current stock = SUM(to_movements) - SUM(from_movements) per product per location.
✅ Every operation (Receipt, Delivery, Transfer, Adjustment) generates immutable stock movement records.
```

---

## 🚀 Quick Start

### Backend (Already Configured)

**Windows:**
```bash
# Just double-click this:
start_backend.bat
```

**Mac/Linux:**
```bash
./start_backend.sh
```

**Or manually:**
```bash
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

✅ **API Docs:** http://localhost:8000/docs
✅ **Health Check:** http://localhost:8000/health
✅ **Database:** Neon PostgreSQL (already connected, schema applied)

---

## 🔌 API Endpoints (30 Total)

All endpoints available at: http://localhost:8000/docs

**Key endpoints:**
```
GET    /api/v1/products/
GET    /api/v1/warehouses/
GET    /api/v1/receipts/           (POST + validate to create movements)
GET    /api/v1/deliveries/         (POST + validate to create movements)
GET    /api/v1/transfers/          (POST + validate to create movements)
GET    /api/v1/adjustments/        (POST + validate to create movements)
GET    /api/v1/inventory/stock     (derived current stock levels)
GET    /api/v1/inventory/movements (stock movement history)
GET    /api/v1/dashboard/kpis      (KPIs and analytics)
GET    /api/v1/dashboard/low-stock-alerts
```

---

## 📚 Documentation

- **`docs/ARCHITECTURE.md`** — Complete system design, ERD, all endpoints, React integration
- **`docs/ER_DIAGRAM.md`** — Database diagram (Mermaid) with relationships
- **`docs/SETUP_TROUBLESHOOTING.md`** — Setup guide & troubleshooting

---

## 🗄️ Database

- **Type:** PostgreSQL (Neon)
- **Tables:** 19 (users, products, warehouses, locations, receipts, deliveries, transfers, adjustments, stock movements, etc.)
- **Views:** 4 (v_current_stock, v_warehouse_stock, v_global_stock, v_low_stock_alerts)
- **Status:** ✅ Connected & Schema Applied

---

## 🧪 Test It

```bash
# Check backend is running
curl http://localhost:8000/health

# Get all products
curl http://localhost:8000/api/v1/products/

# Open API docs
# http://localhost:8000/docs
```

---

## 🛠️ Tech Stack

- **Backend:** FastAPI (Python)
- **ORM:** SQLAlchemy (async)
- **Database:** PostgreSQL (Neon)
- **Authentication:** JWT (python-jose)
- **Validation:** Pydantic v2
- **Server:** Uvicorn

---

## 📊 Stock Movement Logic

```
Receipt (creating goods IN):
  POST /receipts/{id}/validate
    ↓ Creates StockMovement:
    {
      product_id: UUID,
      from_location_id: NULL,      (entering system)
      to_location_id: warehouse,
      quantity: 100,
      movement_type: RECEIPT
    }
    ↓
  Current stock = SUM(to_qty) - SUM(from_qty)
    ↓
  View calculates automatically
```

Same pattern for Deliveries, Transfers, and Adjustments.

---

## ✅ Project Status

| Component | Status |
|---|---|
| Database Schema | ✅ Applied to Neon |
| ORM Models | ✅ 10 models created |
| API Endpoints | ✅ 30 endpoints ready |
| Documentation | ✅ Complete |
| Backend Testing | ✅ All endpoints working |

---

## 🚨 If You See "Failed to Fetch" Error

1. Verify backend is running: `curl http://localhost:8000/health`
2. Check `.env` DATABASE_URL is correct
3. Ensure frontend CORS_ORIGINS matches backend
4. See `docs/SETUP_TROUBLESHOOTING.md` for detailed debugging

---

**Last Updated:** March 14, 2026 | **Status:** Production Ready | **Database:** ✅ Connected