BEGIN;

DO $$
BEGIN
    IF current_database() <> 'shop_lab' THEN
        RAISE EXCEPTION 'Expected database shop_lab, connected to %', current_database();
    END IF;
END;
$$;

CREATE ROLE shop_owner
    NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE ROLE shop_migrator
    NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE ROLE shop_app
    NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE ROLE shop_retention
    NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE ROLE shop_readonly
    NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;

REVOKE CONNECT, TEMPORARY ON DATABASE shop_lab FROM PUBLIC;
REVOKE USAGE ON SCHEMA public FROM PUBLIC;

GRANT CONNECT ON DATABASE shop_lab
    TO shop_owner, shop_migrator, shop_app, shop_retention, shop_readonly;
GRANT USAGE ON SCHEMA public
    TO shop_owner, shop_migrator, shop_app, shop_retention, shop_readonly;
GRANT CREATE ON SCHEMA public TO shop_owner, shop_migrator;

ALTER TABLE users OWNER TO shop_owner;
ALTER TABLE products OWNER TO shop_owner;
ALTER TABLE orders OWNER TO shop_owner;
ALTER TABLE order_items OWNER TO shop_owner;
ALTER TABLE payments OWNER TO shop_owner;
ALTER TABLE reviews OWNER TO shop_owner;
ALTER TABLE legal_retention_records OWNER TO shop_owner;
ALTER FUNCTION set_updated_at() OWNER TO shop_owner;

GRANT shop_owner TO shop_migrator;

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE users TO shop_app;
GRANT SELECT, INSERT, UPDATE ON TABLE products TO shop_app;
GRANT SELECT, INSERT, UPDATE ON TABLE orders TO shop_app;
GRANT SELECT, INSERT, UPDATE ON TABLE order_items TO shop_app;
GRANT SELECT, INSERT, UPDATE ON TABLE payments TO shop_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE reviews TO shop_app;

GRANT USAGE, SELECT ON SEQUENCE
    users_id_seq,
    products_id_seq,
    orders_id_seq,
    order_items_id_seq,
    payments_id_seq,
    reviews_id_seq
TO shop_app;

GRANT SELECT ON TABLE orders TO shop_retention;
GRANT SELECT, INSERT, DELETE ON TABLE legal_retention_records TO shop_retention;
GRANT USAGE, SELECT ON SEQUENCE legal_retention_records_id_seq TO shop_retention;

GRANT SELECT ON TABLE
    users,
    products,
    orders,
    order_items,
    payments,
    reviews
TO shop_readonly;

ALTER ROLE shop_owner SET search_path = pg_catalog, public;
ALTER ROLE shop_migrator SET search_path = pg_catalog, public;
ALTER ROLE shop_app SET search_path = pg_catalog, public;
ALTER ROLE shop_retention SET search_path = pg_catalog, public;
ALTER ROLE shop_readonly SET search_path = pg_catalog, public;

COMMIT;
