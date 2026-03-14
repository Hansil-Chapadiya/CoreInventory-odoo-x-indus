-- ============================================================================
-- CoreInventory - Production-Grade Inventory Management System
-- PostgreSQL Schema v1.0
-- ============================================================================
-- Architectural Rules:
--   1. Stock is NEVER stored directly on the product table.
--   2. ALL inventory changes are recorded via the stock_movements ledger.
--   3. Current stock is always DERIVED from stock movements.
--   4. Multi-warehouse, multi-location support.
--   5. Every operation generates stock movement records.
-- ============================================================================

-- ============================================================================
-- 0. EXTENSIONS
-- ============================================================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================================
-- 1. ENUM TYPES
-- ============================================================================

CREATE TYPE user_role AS ENUM (
    'admin',
    'manager',
    'warehouse_staff',
    'viewer'
);

CREATE TYPE location_type AS ENUM (
    'warehouse',          -- physical warehouse zone
    'rack',               -- shelf / bin inside a warehouse
    'production',         -- manufacturing floor
    'vendor',             -- virtual supplier location
    'customer',           -- virtual customer location
    'adjustment'          -- virtual adjustment location
);

CREATE TYPE movement_type AS ENUM (
    'RECEIPT',
    'DELIVERY',
    'INTERNAL_TRANSFER',
    'ADJUSTMENT'
);

CREATE TYPE document_status AS ENUM (
    'draft',
    'confirmed',
    'in_progress',
    'done',
    'cancelled'
);

CREATE TYPE adjustment_reason AS ENUM (
    'damaged',
    'expired',
    'cycle_count',
    'initial_stock',
    'other'
);

-- ============================================================================
-- 2. AUTHENTICATION MODULE
-- ============================================================================

CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email           VARCHAR(255) NOT NULL UNIQUE,
    username        VARCHAR(100) NOT NULL UNIQUE,
    hashed_password TEXT NOT NULL,
    full_name       VARCHAR(255) NOT NULL,
    role            user_role NOT NULL DEFAULT 'viewer',
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    is_deleted      BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE otp_verifications (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    otp_code    VARCHAR(6) NOT NULL,
    purpose     VARCHAR(50) NOT NULL DEFAULT 'login',  -- login, password_reset
    is_used     BOOLEAN NOT NULL DEFAULT FALSE,
    expires_at  TIMESTAMPTZ NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE user_sessions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    access_token    TEXT NOT NULL UNIQUE,
    refresh_token   TEXT NOT NULL UNIQUE,
    ip_address      INET,
    user_agent      TEXT,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    expires_at      TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_otp_user   ON otp_verifications(user_id, is_used);
CREATE INDEX idx_session_user ON user_sessions(user_id, is_active);

-- ============================================================================
-- 3. PRODUCT MANAGEMENT MODULE
-- ============================================================================

CREATE TABLE product_categories (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        VARCHAR(150) NOT NULL UNIQUE,
    description TEXT,
    parent_id   UUID REFERENCES product_categories(id) ON DELETE SET NULL,
    is_deleted  BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE units_of_measure (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        VARCHAR(50) NOT NULL UNIQUE,   -- "Kilogram", "Piece", "Litre"
    symbol      VARCHAR(10) NOT NULL UNIQUE,   -- "kg", "pcs", "L"
    is_deleted  BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE products (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sku             VARCHAR(50) NOT NULL UNIQUE,
    name            VARCHAR(255) NOT NULL,
    description     TEXT,
    category_id     UUID REFERENCES product_categories(id) ON DELETE SET NULL,
    uom_id          UUID NOT NULL REFERENCES units_of_measure(id),
    barcode         VARCHAR(100) UNIQUE,
    weight          NUMERIC(10, 3),             -- in base weight unit
    cost_price      NUMERIC(12, 2) NOT NULL DEFAULT 0,
    sale_price      NUMERIC(12, 2) NOT NULL DEFAULT 0,
    image_url       TEXT,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    is_deleted      BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
    -- NOTE: No stock_quantity column. Stock is derived from stock_movements.
);

CREATE TABLE reorder_rules (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_id          UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    warehouse_id        UUID NOT NULL,   -- FK added after warehouse table
    min_stock           NUMERIC(12, 3) NOT NULL DEFAULT 0,
    max_stock           NUMERIC(12, 3) NOT NULL DEFAULT 0,
    reorder_quantity    NUMERIC(12, 3) NOT NULL DEFAULT 0,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (product_id, warehouse_id)
);

CREATE INDEX idx_product_sku      ON products(sku);
CREATE INDEX idx_product_barcode  ON products(barcode) WHERE barcode IS NOT NULL;
CREATE INDEX idx_product_category ON products(category_id);
CREATE INDEX idx_product_active   ON products(is_active, is_deleted);

-- ============================================================================
-- 4. WAREHOUSE MANAGEMENT MODULE
-- ============================================================================

CREATE TABLE warehouses (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        VARCHAR(200) NOT NULL UNIQUE,
    code        VARCHAR(20) NOT NULL UNIQUE,   -- short code: "WH-01"
    address     TEXT,
    city        VARCHAR(100),
    state       VARCHAR(100),
    country     VARCHAR(100),
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    is_deleted  BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE locations (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    warehouse_id    UUID NOT NULL REFERENCES warehouses(id) ON DELETE CASCADE,
    name            VARCHAR(200) NOT NULL,      -- "Rack A-01", "Zone B"
    code            VARCHAR(50) NOT NULL,       -- "WH01-RA01"
    location_type   location_type NOT NULL DEFAULT 'rack',
    parent_id       UUID REFERENCES locations(id) ON DELETE SET NULL,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    is_deleted      BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (warehouse_id, code)
);

-- Add the deferred FK for reorder_rules
ALTER TABLE reorder_rules
    ADD CONSTRAINT fk_reorder_warehouse
    FOREIGN KEY (warehouse_id) REFERENCES warehouses(id) ON DELETE CASCADE;

CREATE INDEX idx_location_warehouse ON locations(warehouse_id);
CREATE INDEX idx_location_type      ON locations(location_type);

-- ============================================================================
-- 5. INVENTORY OPERATIONS MODULE
-- ============================================================================

-- ---------- 5A. RECEIPTS (goods IN from vendors) ----------

CREATE TABLE receipts (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    reference           VARCHAR(50) NOT NULL UNIQUE,   -- "REC-000001"
    vendor_name         VARCHAR(255),
    warehouse_id        UUID NOT NULL REFERENCES warehouses(id),
    status              document_status NOT NULL DEFAULT 'draft',
    scheduled_date      DATE,
    completed_date      TIMESTAMPTZ,
    notes               TEXT,
    created_by          UUID NOT NULL REFERENCES users(id),
    is_deleted          BOOLEAN NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE receipt_lines (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    receipt_id      UUID NOT NULL REFERENCES receipts(id) ON DELETE CASCADE,
    product_id      UUID NOT NULL REFERENCES products(id),
    location_id     UUID NOT NULL REFERENCES locations(id),
    quantity        NUMERIC(12, 3) NOT NULL CHECK (quantity > 0),
    received_qty    NUMERIC(12, 3) NOT NULL DEFAULT 0,
    uom_id          UUID NOT NULL REFERENCES units_of_measure(id),
    cost_price      NUMERIC(12, 2),
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_receipt_status  ON receipts(status);
CREATE INDEX idx_receipt_wh      ON receipts(warehouse_id);
CREATE INDEX idx_receipt_line_receipt ON receipt_lines(receipt_id);

-- ---------- 5B. DELIVERY ORDERS (goods OUT to customers) ----------

CREATE TABLE delivery_orders (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    reference           VARCHAR(50) NOT NULL UNIQUE,   -- "DO-000001"
    customer_name       VARCHAR(255),
    warehouse_id        UUID NOT NULL REFERENCES warehouses(id),
    status              document_status NOT NULL DEFAULT 'draft',
    scheduled_date      DATE,
    completed_date      TIMESTAMPTZ,
    shipping_address    TEXT,
    notes               TEXT,
    created_by          UUID NOT NULL REFERENCES users(id),
    is_deleted          BOOLEAN NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE delivery_order_lines (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    delivery_order_id   UUID NOT NULL REFERENCES delivery_orders(id) ON DELETE CASCADE,
    product_id          UUID NOT NULL REFERENCES products(id),
    location_id         UUID NOT NULL REFERENCES locations(id),
    quantity            NUMERIC(12, 3) NOT NULL CHECK (quantity > 0),
    delivered_qty       NUMERIC(12, 3) NOT NULL DEFAULT 0,
    uom_id              UUID NOT NULL REFERENCES units_of_measure(id),
    sale_price          NUMERIC(12, 2),
    notes               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_delivery_status  ON delivery_orders(status);
CREATE INDEX idx_delivery_wh      ON delivery_orders(warehouse_id);
CREATE INDEX idx_delivery_line_do ON delivery_order_lines(delivery_order_id);

-- ---------- 5C. INTERNAL TRANSFERS ----------

CREATE TABLE transfers (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    reference               VARCHAR(50) NOT NULL UNIQUE,   -- "TRF-000001"
    source_warehouse_id     UUID NOT NULL REFERENCES warehouses(id),
    dest_warehouse_id       UUID NOT NULL REFERENCES warehouses(id),
    status                  document_status NOT NULL DEFAULT 'draft',
    scheduled_date          DATE,
    completed_date          TIMESTAMPTZ,
    notes                   TEXT,
    created_by              UUID NOT NULL REFERENCES users(id),
    is_deleted              BOOLEAN NOT NULL DEFAULT FALSE,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE transfer_lines (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    transfer_id         UUID NOT NULL REFERENCES transfers(id) ON DELETE CASCADE,
    product_id          UUID NOT NULL REFERENCES products(id),
    from_location_id    UUID NOT NULL REFERENCES locations(id),
    to_location_id      UUID NOT NULL REFERENCES locations(id),
    quantity            NUMERIC(12, 3) NOT NULL CHECK (quantity > 0),
    transferred_qty     NUMERIC(12, 3) NOT NULL DEFAULT 0,
    uom_id              UUID NOT NULL REFERENCES units_of_measure(id),
    notes               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_transfer_status ON transfers(status);
CREATE INDEX idx_transfer_line_transfer ON transfer_lines(transfer_id);

-- ---------- 5D. STOCK ADJUSTMENTS ----------

CREATE TABLE stock_adjustments (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    reference       VARCHAR(50) NOT NULL UNIQUE,   -- "ADJ-000001"
    warehouse_id    UUID NOT NULL REFERENCES warehouses(id),
    reason          adjustment_reason NOT NULL DEFAULT 'cycle_count',
    status          document_status NOT NULL DEFAULT 'draft',
    completed_date  TIMESTAMPTZ,
    notes           TEXT,
    created_by      UUID NOT NULL REFERENCES users(id),
    is_deleted      BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE adjustment_lines (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    adjustment_id       UUID NOT NULL REFERENCES stock_adjustments(id) ON DELETE CASCADE,
    product_id          UUID NOT NULL REFERENCES products(id),
    location_id         UUID NOT NULL REFERENCES locations(id),
    counted_qty         NUMERIC(12, 3) NOT NULL,    -- physically counted
    system_qty          NUMERIC(12, 3) NOT NULL,    -- what the system had
    difference_qty      NUMERIC(12, 3) GENERATED ALWAYS AS (counted_qty - system_qty) STORED,
    uom_id              UUID NOT NULL REFERENCES units_of_measure(id),
    notes               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_adjustment_status ON stock_adjustments(status);
CREATE INDEX idx_adjustment_line_adj ON adjustment_lines(adjustment_id);

-- ============================================================================
-- 6. INVENTORY ENGINE (Movement-Based Ledger)
-- ============================================================================

-- Core ledger: every stock change is an immutable row here
CREATE TABLE stock_movements (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_id          UUID NOT NULL REFERENCES products(id),
    from_location_id    UUID REFERENCES locations(id),        -- NULL for receipts (goods come from outside)
    to_location_id      UUID REFERENCES locations(id),        -- NULL for deliveries (goods go outside)
    quantity            NUMERIC(12, 3) NOT NULL CHECK (quantity > 0),
    movement_type       movement_type NOT NULL,
    reference_type      VARCHAR(20) NOT NULL,                 -- 'receipt', 'delivery', 'transfer', 'adjustment'
    reference_id        UUID NOT NULL,                        -- FK to the source document
    notes               TEXT,
    created_by          UUID NOT NULL REFERENCES users(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
    -- NOTE: No updated_at. Movements are IMMUTABLE. To correct, create a reversal movement.
);

-- Critical indexes for fast stock queries
CREATE INDEX idx_sm_product             ON stock_movements(product_id);
CREATE INDEX idx_sm_from_location       ON stock_movements(from_location_id) WHERE from_location_id IS NOT NULL;
CREATE INDEX idx_sm_to_location         ON stock_movements(to_location_id) WHERE to_location_id IS NOT NULL;
CREATE INDEX idx_sm_movement_type       ON stock_movements(movement_type);
CREATE INDEX idx_sm_reference           ON stock_movements(reference_type, reference_id);
CREATE INDEX idx_sm_created_at          ON stock_movements(created_at);
CREATE INDEX idx_sm_product_location    ON stock_movements(product_id, to_location_id, from_location_id);

-- Performance cache: periodically refreshed snapshot of current stock per product/location
CREATE TABLE stock_snapshots (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_id      UUID NOT NULL REFERENCES products(id),
    location_id     UUID NOT NULL REFERENCES locations(id),
    quantity        NUMERIC(12, 3) NOT NULL DEFAULT 0,
    snapshot_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (product_id, location_id)
);

CREATE INDEX idx_snapshot_product  ON stock_snapshots(product_id);
CREATE INDEX idx_snapshot_location ON stock_snapshots(location_id);

-- ============================================================================
-- 7. VIEWS - Derive current stock from movements
-- ============================================================================

-- Current stock per product per location (the source of truth)
CREATE OR REPLACE VIEW v_current_stock AS
SELECT
    sub.product_id,
    sub.location_id,
    l.warehouse_id,
    p.sku,
    p.name AS product_name,
    l.name AS location_name,
    w.name AS warehouse_name,
    SUM(sub.qty) AS on_hand_qty
FROM (
    -- Stock IN: movements where this location is the destination
    SELECT product_id, to_location_id AS location_id, quantity AS qty
    FROM stock_movements
    WHERE to_location_id IS NOT NULL

    UNION ALL

    -- Stock OUT: movements where this location is the source
    SELECT product_id, from_location_id AS location_id, -quantity AS qty
    FROM stock_movements
    WHERE from_location_id IS NOT NULL
) sub
JOIN products p   ON p.id = sub.product_id
JOIN locations l  ON l.id = sub.location_id
JOIN warehouses w ON w.id = l.warehouse_id
GROUP BY sub.product_id, sub.location_id, l.warehouse_id,
         p.sku, p.name, l.name, w.name;

-- Aggregated stock per product per warehouse
CREATE OR REPLACE VIEW v_warehouse_stock AS
SELECT
    product_id,
    warehouse_id,
    sku,
    product_name,
    warehouse_name,
    SUM(on_hand_qty) AS total_on_hand
FROM v_current_stock
GROUP BY product_id, warehouse_id, sku, product_name, warehouse_name;

-- Global stock per product across all warehouses
CREATE OR REPLACE VIEW v_global_stock AS
SELECT
    product_id,
    sku,
    product_name,
    SUM(on_hand_qty) AS total_on_hand
FROM v_current_stock
GROUP BY product_id, sku, product_name;

-- Low-stock alert view (joins with reorder rules)
CREATE OR REPLACE VIEW v_low_stock_alerts AS
SELECT
    ws.product_id,
    ws.warehouse_id,
    ws.sku,
    ws.product_name,
    ws.warehouse_name,
    ws.total_on_hand,
    rr.min_stock,
    rr.reorder_quantity
FROM v_warehouse_stock ws
JOIN reorder_rules rr ON rr.product_id = ws.product_id
                      AND rr.warehouse_id = ws.warehouse_id
                      AND rr.is_active = TRUE
WHERE ws.total_on_hand <= rr.min_stock;

-- ============================================================================
-- 8. FUNCTIONS
-- ============================================================================

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION fn_update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply trigger to all tables with updated_at
DO $$
DECLARE
    tbl TEXT;
BEGIN
    FOR tbl IN
        SELECT table_name FROM information_schema.columns
        WHERE column_name = 'updated_at'
          AND table_schema = 'public'
          AND table_name NOT LIKE 'v_%'
    LOOP
        EXECUTE format(
            'CREATE TRIGGER trg_%s_updated_at
             BEFORE UPDATE ON %I
             FOR EACH ROW EXECUTE FUNCTION fn_update_timestamp();',
            tbl, tbl
        );
    END LOOP;
END;
$$;

-- Generate sequential reference numbers
CREATE OR REPLACE FUNCTION fn_next_reference(prefix TEXT)
RETURNS TEXT AS $$
DECLARE
    next_val BIGINT;
BEGIN
    -- Use an advisory lock per prefix to avoid race conditions
    PERFORM pg_advisory_xact_lock(hashtext(prefix));

    SELECT COALESCE(MAX(
        CAST(SUBSTRING(reference FROM LENGTH(prefix) + 2) AS BIGINT)
    ), 0) + 1
    INTO next_val
    FROM (
        SELECT reference FROM receipts WHERE reference LIKE prefix || '-%'
        UNION ALL
        SELECT reference FROM delivery_orders WHERE reference LIKE prefix || '-%'
        UNION ALL
        SELECT reference FROM transfers WHERE reference LIKE prefix || '-%'
        UNION ALL
        SELECT reference FROM stock_adjustments WHERE reference LIKE prefix || '-%'
    ) refs;

    RETURN prefix || '-' || LPAD(next_val::TEXT, 6, '0');
END;
$$ LANGUAGE plpgsql;


-- ============================================================================
-- 9. SEED DATA
-- ============================================================================

-- Default units of measure
INSERT INTO units_of_measure (name, symbol) VALUES
    ('Piece', 'pcs'),
    ('Kilogram', 'kg'),
    ('Litre', 'L'),
    ('Metre', 'm'),
    ('Box', 'box'),
    ('Pallet', 'plt')
ON CONFLICT (name) DO NOTHING;

-- Default product categories
INSERT INTO product_categories (name, description) VALUES
    ('Raw Materials', 'Base materials for production'),
    ('Finished Goods', 'Ready-to-ship products'),
    ('Consumables', 'Office and warehouse consumables'),
    ('Spare Parts', 'Maintenance and repair parts')
ON CONFLICT (name) DO NOTHING;
