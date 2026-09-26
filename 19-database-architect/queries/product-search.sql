-- 판매 중인 최신 상품 20개 조회
EXPLAIN (ANALYZE, BUFFERS)
SELECT
    products.id,
    products.name,
    products.price,
    products.stock_quantity,
    products.created_at
FROM products
WHERE products.status = 'ACTIVE'
ORDER BY products.created_at DESC
LIMIT 20;
