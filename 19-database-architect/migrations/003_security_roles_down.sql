BEGIN;

DO $$
BEGIN
    IF current_database() <> 'shop_lab' THEN
        RAISE EXCEPTION 'Expected database shop_lab, connected to %', current_database();
    END IF;
END;
$$;

REVOKE shop_owner FROM shop_migrator;

REASSIGN OWNED BY shop_owner TO lab;

DROP OWNED BY shop_app;
DROP OWNED BY shop_retention;
DROP OWNED BY shop_readonly;
DROP OWNED BY shop_migrator;
DROP OWNED BY shop_owner;

GRANT CONNECT, TEMPORARY ON DATABASE shop_lab TO PUBLIC;
GRANT USAGE ON SCHEMA public TO PUBLIC;

DROP ROLE shop_readonly;
DROP ROLE shop_retention;
DROP ROLE shop_app;
DROP ROLE shop_migrator;
DROP ROLE shop_owner;

COMMIT;
