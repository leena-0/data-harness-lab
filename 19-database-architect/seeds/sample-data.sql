-- 학습용 정상 데이터다. 비어 있는 스키마에서 한 번만 실행한다.
-- 다시 실행하면 UNIQUE 제약조건에 의해 실패하며 전체 트랜잭션이 롤백된다.

BEGIN;

SET LOCAL TIME ZONE 'UTC';

INSERT INTO users (email, name, status)
VALUES
    ('alice@example.com', '앨리스', 'ACTIVE'),
    ('bob@example.com', '밥', 'ACTIVE');

INSERT INTO products (name, price, stock_quantity, status)
VALUES
    ('노트북', 1200000.00, 10, 'ACTIVE'),
    ('기계식 키보드', 80000.00, 30, 'ACTIVE'),
    ('무선 마우스', 35000.00, 50, 'ACTIVE');

WITH new_order AS (
    INSERT INTO orders (user_id, status, total_amount)
    SELECT id, 'COMPLETED', 1360000.00
    FROM users
    WHERE email = 'alice@example.com'
    RETURNING id
), requested_items (product_name, quantity) AS (
    VALUES
        ('노트북'::VARCHAR, 1),
        ('기계식 키보드'::VARCHAR, 2)
)
INSERT INTO order_items (
    order_id,
    product_id,
    product_name,
    unit_price,
    quantity
)
SELECT
    new_order.id,
    products.id,
    products.name,
    products.price,
    requested_items.quantity
FROM new_order
JOIN requested_items ON TRUE
JOIN products ON products.name = requested_items.product_name;

WITH new_order AS (
    INSERT INTO orders (user_id, status, total_amount)
    SELECT id, 'PENDING', 35000.00
    FROM users
    WHERE email = 'bob@example.com'
    RETURNING id
)
INSERT INTO order_items (
    order_id,
    product_id,
    product_name,
    unit_price,
    quantity
)
SELECT
    new_order.id,
    products.id,
    products.name,
    products.price,
    1
FROM new_order
JOIN products ON products.name = '무선 마우스';

INSERT INTO payments (
    order_id,
    transaction_id,
    method,
    amount,
    status
)
SELECT
    orders.id,
    'txn-seed-failed-001',
    'CARD',
    orders.total_amount,
    'FAILED'
FROM orders
JOIN users ON users.id = orders.user_id
WHERE users.email = 'alice@example.com';

INSERT INTO payments (
    order_id,
    transaction_id,
    method,
    amount,
    status
)
SELECT
    orders.id,
    'txn-seed-success-001',
    'CARD',
    orders.total_amount,
    'SUCCEEDED'
FROM orders
JOIN users ON users.id = orders.user_id
WHERE users.email = 'alice@example.com';

INSERT INTO reviews (order_item_id, rating, content)
SELECT
    order_items.id,
    5,
    '키감이 좋고 배송도 빨랐어요.'
FROM order_items
JOIN orders ON orders.id = order_items.order_id
JOIN users ON users.id = orders.user_id
JOIN products ON products.id = order_items.product_id
WHERE users.email = 'alice@example.com'
  AND products.name = '기계식 키보드';

-- 실제 서비스에서는 애플리케이션이 최소 개인정보를 암호화해 BYTEA로 전달한다.
-- 아래 값은 암호화 흐름을 흉내 내기 위한 합성 바이트이며 실제 개인정보가 아니다.
INSERT INTO legal_retention_records (
    order_id,
    retention_category,
    retained_data_encrypted,
    retention_until
)
SELECT
    orders.id,
    'PAYMENT',
    decode('8f14e45fceea167a5a36dedd4bea2543', 'hex'),
    CURRENT_TIMESTAMP + INTERVAL '5 years'
FROM orders
JOIN users ON users.id = orders.user_id
WHERE users.email = 'alice@example.com';

COMMIT;

SELECT 'users' AS table_name, count(*) AS row_count FROM users
UNION ALL
SELECT 'products', count(*) FROM products
UNION ALL
SELECT 'orders', count(*) FROM orders
UNION ALL
SELECT 'order_items', count(*) FROM order_items
UNION ALL
SELECT 'payments', count(*) FROM payments
UNION ALL
SELECT 'reviews', count(*) FROM reviews
UNION ALL
SELECT 'legal_retention_records', count(*) FROM legal_retention_records
ORDER BY table_name;
