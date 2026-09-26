BEGIN;

DO $$
BEGIN
    IF current_database() <> 'shop_lab' THEN
        RAISE EXCEPTION 'Expected database shop_lab, connected to %', current_database();
    END IF;
END;
$$;

DROP INDEX idx_products_active_created_at;
DROP INDEX idx_orders_user_created_at;

COMMIT;
