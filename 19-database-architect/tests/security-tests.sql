-- 003_security_roles_up.sql 적용 후 권한 구조를 검증한다.

DO $$
DECLARE
    login_enabled BOOLEAN;
    owned_tables INTEGER;
BEGIN
    SELECT bool_or(rolcanlogin)
    INTO login_enabled
    FROM pg_roles
    WHERE rolname IN (
        'shop_owner',
        'shop_migrator',
        'shop_app',
        'shop_retention',
        'shop_readonly'
    );

    IF login_enabled IS DISTINCT FROM FALSE THEN
        RAISE EXCEPTION 'SECURITY TEST FAILURE: group roles must be NOLOGIN';
    END IF;
    RAISE NOTICE 'PASS: all security roles are NOLOGIN';

    SELECT count(*)
    INTO owned_tables
    FROM pg_class
    JOIN pg_roles ON pg_roles.oid = pg_class.relowner
    WHERE pg_class.relnamespace = 'public'::regnamespace
      AND pg_class.relkind IN ('r', 'p')
      AND pg_roles.rolname = 'shop_owner'
      AND pg_class.relname IN (
          'users', 'products', 'orders', 'order_items',
          'payments', 'reviews', 'legal_retention_records'
      );

    IF owned_tables <> 7 THEN
        RAISE EXCEPTION 'SECURITY TEST FAILURE: expected 7 shop_owner tables, found %', owned_tables;
    END IF;
    RAISE NOTICE 'PASS: shop_owner owns all 7 application tables';

    IF NOT has_schema_privilege('shop_migrator', 'public', 'CREATE') THEN
        RAISE EXCEPTION 'SECURITY TEST FAILURE: migrator lacks schema CREATE';
    END IF;
    IF has_schema_privilege('shop_app', 'public', 'CREATE') THEN
        RAISE EXCEPTION 'SECURITY TEST FAILURE: application role has schema CREATE';
    END IF;
    RAISE NOTICE 'PASS: DDL permission is limited to migration roles';

    IF NOT has_table_privilege('shop_app', 'orders', 'SELECT,INSERT,UPDATE') THEN
        RAISE EXCEPTION 'SECURITY TEST FAILURE: application role lacks expected order DML';
    END IF;
    IF has_table_privilege('shop_app', 'orders', 'DELETE') THEN
        RAISE EXCEPTION 'SECURITY TEST FAILURE: application role can delete orders';
    END IF;
    IF has_table_privilege('shop_app', 'legal_retention_records', 'SELECT') THEN
        RAISE EXCEPTION 'SECURITY TEST FAILURE: application role can read legal retention data';
    END IF;
    RAISE NOTICE 'PASS: application role has limited business DML and no retention access';

    IF NOT has_table_privilege(
        'shop_retention',
        'legal_retention_records',
        'SELECT,INSERT,DELETE'
    ) THEN
        RAISE EXCEPTION 'SECURITY TEST FAILURE: retention role lacks required privileges';
    END IF;
    IF has_table_privilege('shop_retention', 'users', 'SELECT') THEN
        RAISE EXCEPTION 'SECURITY TEST FAILURE: retention role can read active users';
    END IF;
    RAISE NOTICE 'PASS: legal retention data is isolated';

    IF NOT has_table_privilege('shop_readonly', 'orders', 'SELECT') THEN
        RAISE EXCEPTION 'SECURITY TEST FAILURE: readonly role cannot read orders';
    END IF;
    IF has_table_privilege('shop_readonly', 'orders', 'INSERT') THEN
        RAISE EXCEPTION 'SECURITY TEST FAILURE: readonly role can insert orders';
    END IF;
    IF has_table_privilege('shop_readonly', 'legal_retention_records', 'SELECT') THEN
        RAISE EXCEPTION 'SECURITY TEST FAILURE: readonly role can read retention data';
    END IF;
    RAISE NOTICE 'PASS: readonly role cannot write or read retention data';
END;
$$;

SELECT 'ALL SECURITY PRIVILEGE TESTS PASSED' AS result;
