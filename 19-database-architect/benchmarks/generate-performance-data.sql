-- 로컬 성능 비교용 합성 데이터다. 운영 환경에서는 실행하지 않는다.
-- 기본 생성 규모: 사용자 10,000명, 상품 100,000개, 주문/주문 항목 각 100,000건
-- 100만 건 확장 검증: psql -v benchmark_scale=10 -f generate-performance-data.sql

\if :{?benchmark_scale}
\else
\set benchmark_scale 1
\endif

BEGIN;

SET LOCAL TIME ZONE 'UTC';

DO $$
BEGIN
    IF current_database() <> 'shop_lab' THEN
        RAISE EXCEPTION 'Expected database shop_lab, connected to %', current_database();
    END IF;

    IF EXISTS (SELECT 1 FROM users WHERE email LIKE 'bench-user-%@example.com') THEN
        RAISE EXCEPTION 'Benchmark data already exists; run cleanup-performance-data.sql first';
    END IF;
END;
$$;

INSERT INTO users (email, name, status)
SELECT
    format('bench-user-%s@example.com', lpad(series::TEXT, 5, '0')),
    format('Benchmark User %s', series),
    'ACTIVE'
FROM generate_series(1, 10000) AS generated(series);

INSERT INTO products (
    name,
    price,
    stock_quantity,
    status,
    created_at,
    updated_at
)
SELECT
    format('Benchmark Product %s', lpad(series::TEXT, 6, '0')),
    1000.00 + (series % 50000),
    100 + (series % 900),
    CASE WHEN series % 5 = 0 THEN 'INACTIVE' ELSE 'ACTIVE' END,
    CURRENT_TIMESTAMP - (series * INTERVAL '1 second'),
    CURRENT_TIMESTAMP - (series * INTERVAL '1 second')
FROM generate_series(1, 100000) AS generated(series);

WITH benchmark_users AS (
    SELECT
        id,
        row_number() OVER (ORDER BY id) AS user_number
    FROM users
    WHERE email LIKE 'bench-user-%@example.com'
)
INSERT INTO orders (
    user_id,
    status,
    total_amount,
    created_at,
    updated_at
)
SELECT
    benchmark_users.id,
    CASE
        WHEN order_number % 5 = 0 THEN 'COMPLETED'
        WHEN order_number % 5 = 1 THEN 'PAID'
        WHEN order_number % 5 = 2 THEN 'PREPARING'
        WHEN order_number % 5 = 3 THEN 'SHIPPED'
        ELSE 'CANCELLED'
    END,
    1000.00,
    CURRENT_TIMESTAMP
        - ((benchmark_users.user_number * 10 + order_number) * INTERVAL '1 second'),
    CURRENT_TIMESTAMP
        - ((benchmark_users.user_number * 10 + order_number) * INTERVAL '1 second')
FROM benchmark_users
CROSS JOIN LATERAL generate_series(
    1,
    CASE
        WHEN benchmark_users.user_number <= 9000 THEN 5
        WHEN benchmark_users.user_number <= 9900 THEN 25
        ELSE 325
    END * :benchmark_scale
) AS generated_orders(order_number);

WITH benchmark_orders AS (
    SELECT
        orders.id,
        row_number() OVER (ORDER BY orders.id) AS row_number
    FROM orders
    JOIN users ON users.id = orders.user_id
    WHERE users.email LIKE 'bench-user-%@example.com'
),
benchmark_products AS (
    SELECT
        id,
        name,
        row_number() OVER (ORDER BY id) AS row_number
    FROM products
    WHERE name LIKE 'Benchmark Product %'
)
INSERT INTO order_items (
    order_id,
    product_id,
    product_name,
    unit_price,
    quantity
)
SELECT
    benchmark_orders.id,
    benchmark_products.id,
    benchmark_products.name,
    1000.00,
    1
FROM benchmark_orders
JOIN benchmark_products
  ON benchmark_products.row_number
     = ((benchmark_orders.row_number - 1) % 100000) + 1;

COMMIT;

ANALYZE users;
ANALYZE products;
ANALYZE orders;
ANALYZE order_items;

SELECT 'users' AS table_name, count(*) AS benchmark_rows
FROM users
WHERE email LIKE 'bench-user-%@example.com'
UNION ALL
SELECT 'products', count(*)
FROM products
WHERE name LIKE 'Benchmark Product %'
UNION ALL
SELECT 'orders', count(*)
FROM orders
WHERE user_id IN (
    SELECT id FROM users WHERE email LIKE 'bench-user-%@example.com'
)
UNION ALL
SELECT 'order_items', count(*)
FROM order_items
WHERE order_id IN (
    SELECT orders.id
    FROM orders
    JOIN users ON users.id = orders.user_id
    WHERE users.email LIKE 'bench-user-%@example.com'
)
ORDER BY table_name;
