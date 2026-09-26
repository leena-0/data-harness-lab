BEGIN;

DO $$
BEGIN
    IF current_database() <> 'shop_lab' THEN
        RAISE EXCEPTION 'Expected database shop_lab, connected to %', current_database();
    END IF;
END;
$$;

CREATE INDEX idx_orders_user_created_at
    ON orders (user_id, created_at DESC);

CREATE INDEX idx_products_active_created_at
    ON products (created_at DESC)
    WHERE status = 'ACTIVE';

COMMIT;

ANALYZE orders;
ANALYZE products;
