-- generate-performance-data.sql로 만든 데이터만 의존 관계의 역순으로 제거한다.

BEGIN;

DO $$
BEGIN
    IF current_database() <> 'shop_lab' THEN
        RAISE EXCEPTION 'Expected database shop_lab, connected to %', current_database();
    END IF;
END;
$$;

-- 대량 상품 삭제 시 FK 검사가 order_items 전체를 반복 스캔하지 않게 한다.
CREATE INDEX bench_cleanup_order_items_product_id
    ON order_items (product_id);

DELETE FROM order_items
WHERE order_id IN (
    SELECT orders.id
    FROM orders
    JOIN users ON users.id = orders.user_id
    WHERE users.email LIKE 'bench-user-%@example.com'
);

DELETE FROM orders
WHERE user_id IN (
    SELECT id
    FROM users
    WHERE email LIKE 'bench-user-%@example.com'
);

DELETE FROM users
WHERE email LIKE 'bench-user-%@example.com';

DELETE FROM products
WHERE name LIKE 'Benchmark Product %';

DROP INDEX bench_cleanup_order_items_product_id;

COMMIT;

ANALYZE users;
ANALYZE products;
ANALYZE orders;
ANALYZE order_items;
