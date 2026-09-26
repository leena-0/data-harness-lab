BEGIN;

DO $$
BEGIN
    IF current_database() <> 'shop_lab' THEN
        RAISE EXCEPTION 'Expected database shop_lab, connected to %', current_database();
    END IF;
END;
$$;

DROP TABLE legal_retention_records;
DROP TABLE reviews;
DROP TABLE payments;
DROP TABLE order_items;
DROP TABLE orders;
DROP TABLE products;
DROP TABLE users;

DROP FUNCTION set_updated_at();

COMMIT;
