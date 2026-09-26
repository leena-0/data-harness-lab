-- 실행 전 seeds/sample-data.sql을 먼저 적용해야 한다.
-- 각 예상 오류는 PL/pgSQL 예외 블록에서 잡는다.
-- 예상한 제약조건이 동작하지 않으면 TEST FAILURE 예외로 전체 실행이 실패한다.
-- 테스트 중 생성하거나 변경한 데이터는 마지막 ROLLBACK으로 모두 제거한다.

BEGIN;

SET LOCAL TIME ZONE 'UTC';

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM users WHERE email = 'alice@example.com')
       OR NOT EXISTS (SELECT 1 FROM users WHERE email = 'bob@example.com') THEN
        RAISE EXCEPTION 'TEST SETUP FAILURE: run seeds/sample-data.sql first';
    END IF;
    RAISE NOTICE 'PASS: sample data exists';
END;
$$;

DO $$
BEGIN
    BEGIN
        INSERT INTO products (name, price, stock_quantity, status)
        VALUES ('음수 가격 상품', -1.00, 1, 'ACTIVE');
        RAISE EXCEPTION 'TEST FAILURE: negative price was accepted';
    EXCEPTION
        WHEN check_violation THEN
            RAISE NOTICE 'PASS: negative product price rejected';
    END;
END;
$$;

DO $$
BEGIN
    BEGIN
        INSERT INTO products (name, price, stock_quantity, status)
        VALUES ('음수 재고 상품', 1000.00, -1, 'ACTIVE');
        RAISE EXCEPTION 'TEST FAILURE: negative stock was accepted';
    EXCEPTION
        WHEN check_violation THEN
            RAISE NOTICE 'PASS: negative stock rejected';
    END;
END;
$$;

DO $$
DECLARE
    target_order_id BIGINT;
    target_product_id BIGINT;
BEGIN
    SELECT orders.id
    INTO STRICT target_order_id
    FROM orders
    JOIN users ON users.id = orders.user_id
    WHERE users.email = 'bob@example.com';

    SELECT id
    INTO STRICT target_product_id
    FROM products
    WHERE name = '노트북';

    BEGIN
        INSERT INTO order_items (
            order_id,
            product_id,
            product_name,
            unit_price,
            quantity
        )
        VALUES (
            target_order_id,
            target_product_id,
            '노트북',
            1200000.00,
            0
        );
        RAISE EXCEPTION 'TEST FAILURE: zero quantity was accepted';
    EXCEPTION
        WHEN check_violation THEN
            RAISE NOTICE 'PASS: zero order quantity rejected';
    END;
END;
$$;

DO $$
DECLARE
    target_order_item_id BIGINT;
BEGIN
    SELECT order_items.id
    INTO STRICT target_order_item_id
    FROM order_items
    JOIN orders ON orders.id = order_items.order_id
    JOIN users ON users.id = orders.user_id
    WHERE users.email = 'bob@example.com';

    BEGIN
        INSERT INTO reviews (order_item_id, rating, content)
        VALUES (target_order_item_id, 6, '허용 범위를 벗어난 평점');
        RAISE EXCEPTION 'TEST FAILURE: out-of-range rating was accepted';
    EXCEPTION
        WHEN check_violation THEN
            RAISE NOTICE 'PASS: out-of-range review rating rejected';
    END;
END;
$$;

DO $$
BEGIN
    BEGIN
        INSERT INTO users (email, name, status)
        VALUES ('alice@example.com', '중복 앨리스', 'ACTIVE');
        RAISE EXCEPTION 'TEST FAILURE: duplicate email was accepted';
    EXCEPTION
        WHEN unique_violation THEN
            RAISE NOTICE 'PASS: duplicate user email rejected';
    END;
END;
$$;

DO $$
DECLARE
    target_order_id BIGINT;
BEGIN
    SELECT orders.id
    INTO STRICT target_order_id
    FROM orders
    JOIN users ON users.id = orders.user_id
    WHERE users.email = 'bob@example.com';

    BEGIN
        INSERT INTO payments (
            order_id,
            transaction_id,
            method,
            amount,
            status
        )
        VALUES (
            target_order_id,
            'txn-seed-success-001',
            'CARD',
            35000.00,
            'FAILED'
        );
        RAISE EXCEPTION 'TEST FAILURE: duplicate transaction ID was accepted';
    EXCEPTION
        WHEN unique_violation THEN
            RAISE NOTICE 'PASS: duplicate transaction ID rejected';
    END;
END;
$$;

DO $$
DECLARE
    target_order_id BIGINT;
BEGIN
    SELECT orders.id
    INTO STRICT target_order_id
    FROM orders
    JOIN users ON users.id = orders.user_id
    WHERE users.email = 'alice@example.com';

    BEGIN
        INSERT INTO payments (
            order_id,
            transaction_id,
            method,
            amount,
            status
        )
        VALUES (
            target_order_id,
            'txn-test-second-success',
            'CARD',
            1360000.00,
            'SUCCEEDED'
        );
        RAISE EXCEPTION 'TEST FAILURE: second successful payment was accepted';
    EXCEPTION
        WHEN unique_violation THEN
            RAISE NOTICE 'PASS: second successful payment for one order rejected';
    END;
END;
$$;

DO $$
DECLARE
    target_product_id BIGINT;
BEGIN
    SELECT id
    INTO STRICT target_product_id
    FROM products
    WHERE name = '노트북';

    BEGIN
        INSERT INTO order_items (
            order_id,
            product_id,
            product_name,
            unit_price,
            quantity
        )
        VALUES (
            -1,
            target_product_id,
            '노트북',
            1200000.00,
            1
        );
        RAISE EXCEPTION 'TEST FAILURE: missing order reference was accepted';
    EXCEPTION
        WHEN foreign_key_violation THEN
            RAISE NOTICE 'PASS: missing order reference rejected';
    END;
END;
$$;

DO $$
DECLARE
    target_order_id BIGINT;
BEGIN
    SELECT orders.id
    INTO STRICT target_order_id
    FROM orders
    JOIN users ON users.id = orders.user_id
    WHERE users.email = 'bob@example.com';

    BEGIN
        INSERT INTO order_items (
            order_id,
            product_id,
            product_name,
            unit_price,
            quantity
        )
        VALUES (
            target_order_id,
            -1,
            '존재하지 않는 상품',
            1000.00,
            1
        );
        RAISE EXCEPTION 'TEST FAILURE: missing product reference was accepted';
    EXCEPTION
        WHEN foreign_key_violation THEN
            RAISE NOTICE 'PASS: missing product reference rejected';
    END;
END;
$$;

DO $$
DECLARE
    target_product_id BIGINT;
BEGIN
    SELECT id
    INTO STRICT target_product_id
    FROM products
    WHERE name = '노트북';

    BEGIN
        DELETE FROM products WHERE id = target_product_id;
        RAISE EXCEPTION 'TEST FAILURE: referenced product was deleted';
    EXCEPTION
        WHEN foreign_key_violation THEN
            RAISE NOTICE 'PASS: referenced product deletion restricted';
    END;
END;
$$;

DO $$
DECLARE
    target_order_id BIGINT;
BEGIN
    SELECT orders.id
    INTO STRICT target_order_id
    FROM orders
    JOIN users ON users.id = orders.user_id
    WHERE users.email = 'alice@example.com';

    BEGIN
        DELETE FROM orders WHERE id = target_order_id;
        RAISE EXCEPTION 'TEST FAILURE: referenced order was deleted';
    EXCEPTION
        WHEN foreign_key_violation THEN
            RAISE NOTICE 'PASS: referenced order deletion restricted';
    END;
END;
$$;

DO $$
DECLARE
    test_user_id BIGINT;
    test_order_id BIGINT;
    remaining_user_id BIGINT;
BEGIN
    INSERT INTO users (email, name, status)
    VALUES ('delete-test@example.com', '삭제 테스트', 'ACTIVE')
    RETURNING id INTO test_user_id;

    INSERT INTO orders (user_id, status, total_amount)
    VALUES (test_user_id, 'PENDING', 0.00)
    RETURNING id INTO test_order_id;

    DELETE FROM users WHERE id = test_user_id;

    SELECT user_id
    INTO remaining_user_id
    FROM orders
    WHERE id = test_order_id;

    IF remaining_user_id IS NOT NULL THEN
        RAISE EXCEPTION 'TEST FAILURE: orders.user_id was not set to NULL';
    END IF;

    RAISE NOTICE 'PASS: deleting user sets orders.user_id to NULL';
END;
$$;

DO $$
DECLARE
    target_product_id BIGINT;
    snapshot_name VARCHAR(200);
    snapshot_price NUMERIC(12, 2);
BEGIN
    SELECT products.id, order_items.product_name, order_items.unit_price
    INTO STRICT target_product_id, snapshot_name, snapshot_price
    FROM order_items
    JOIN orders ON orders.id = order_items.order_id
    JOIN users ON users.id = orders.user_id
    JOIN products ON products.id = order_items.product_id
    WHERE users.email = 'alice@example.com'
      AND products.name = '노트북';

    UPDATE products
    SET name = '이름이 변경된 노트북',
        price = 1300000.00
    WHERE id = target_product_id;

    IF NOT EXISTS (
        SELECT 1
        FROM order_items
        WHERE product_id = target_product_id
          AND product_name = snapshot_name
          AND unit_price = snapshot_price
    ) THEN
        RAISE EXCEPTION 'TEST FAILURE: order item snapshot changed with product';
    END IF;

    RAISE NOTICE 'PASS: order item snapshot survives product changes';
END;
$$;

DO $$
DECLARE
    test_product_id BIGINT;
    before_update TIMESTAMPTZ;
    after_update TIMESTAMPTZ;
BEGIN
    INSERT INTO products (
        name,
        price,
        stock_quantity,
        status,
        created_at,
        updated_at
    )
    VALUES (
        '트리거 테스트 상품',
        1000.00,
        1,
        'ACTIVE',
        TIMESTAMPTZ '2000-01-01 00:00:00+00',
        TIMESTAMPTZ '2000-01-01 00:00:00+00'
    )
    RETURNING id, updated_at INTO test_product_id, before_update;

    UPDATE products
    SET stock_quantity = 2
    WHERE id = test_product_id;

    SELECT updated_at
    INTO STRICT after_update
    FROM products
    WHERE id = test_product_id;

    IF after_update <= before_update THEN
        RAISE EXCEPTION 'TEST FAILURE: updated_at trigger did not advance timestamp';
    END IF;

    RAISE NOTICE 'PASS: updated_at trigger advances timestamp';
END;
$$;

ROLLBACK;

SELECT 'ALL SCHEMA TESTS PASSED' AS result;
