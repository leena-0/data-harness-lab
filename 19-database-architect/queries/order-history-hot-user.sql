-- 주문이 집중된 사용자의 최근 주문 20건 조회
EXPLAIN (ANALYZE, BUFFERS)
SELECT
    orders.id,
    orders.status,
    orders.total_amount,
    orders.created_at
FROM orders
WHERE orders.user_id = (
    SELECT id
    FROM users
    WHERE email = 'bench-user-09999@example.com'
)
ORDER BY orders.created_at DESC
LIMIT 20;
