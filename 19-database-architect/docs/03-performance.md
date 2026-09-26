# 03. 성능 분석

PostgreSQL 16에서 대표 읽기 쿼리의 인덱스 적용 전후를 `EXPLAIN (ANALYZE, BUFFERS)`로 비교했다. 결과는 로컬 Docker 환경의 웜 캐시 측정값이므로 절대 시간보다 실행 계획, 버퍼와 상대적 변화에 초점을 둔다.

## 1. 평가 대상

### 사용자 최근 주문

- 일반 사용자: `bench-user-05000@example.com`
- 주문 집중 사용자: `bench-user-09999@example.com`
- 조건: 사용자 ID 일치
- 정렬: `created_at DESC`
- 반환: 최대 20건

### 판매 중인 최신 상품

- 조건: `status = 'ACTIVE'`
- 정렬: `created_at DESC`
- 반환: 최대 20건

실행 SQL은 `queries/order-history.sql`, `queries/order-history-hot-user.sql`, `queries/product-search.sql`에 저장했다.

## 2. 데이터 규모와 분포

기본 후보 비교 데이터:

| 데이터 | 건수 |
|---|---:|
| 사용자 | 10,000 |
| 상품 | 100,000 |
| 주문 | 100,000 |
| 주문 항목 | 100,000 |

주문은 현실적인 편향을 만들기 위해 다음과 같이 분포시켰다.

| 사용자 그룹 | 사용자 수 | 1인당 주문 | 그룹 주문 수 |
|---|---:|---:|---:|
| 일반 사용자 | 9,000 | 5 | 45,000 |
| 중간 사용자 | 900 | 25 | 22,500 |
| 주문 집중 사용자 | 100 | 325 | 32,500 |
| 합계 | 10,000 | - | 100,000 |

상품 상태는 `ACTIVE` 80%, `INACTIVE` 20%로 구성했다. 최종 인덱스 선택 후에는 주문과 주문 항목을 각각 1,000,000건으로 늘려 한 번 더 검증했다.

## 3. 측정 방법

`benchmarks/measure_performance.py`가 다음 과정을 자동 수행한다.

1. 후보 인덱스가 없는 기준 상태 확인
2. `ANALYZE`로 통계 갱신
3. 각 쿼리 5회 워밍업
4. 각 쿼리 10회 본 측정
5. Planning Time, Execution Time, Buffers와 필터링 행 수의 중앙값 계산
6. 후보 인덱스를 하나씩 생성해 측정
7. 후보 인덱스를 제거한 뒤 다음 후보 측정

PostgreSQL 및 OS 캐시를 강제로 비우는 콜드 캐시 실험은 제외했다. 모든 결과에서 `shared read`가 0이므로 이번 수치는 웜 캐시 성능이다.

## 4. 주문 인덱스 비교

후보:

```sql
-- 후보 A
CREATE INDEX ON orders (user_id);

-- 후보 B
CREATE INDEX ON orders (user_id, created_at DESC);
```

10회 실행 중앙값:

| 사용자 | 후보 | 실행시간 | hit/read | 필터 제거 | 정렬 | 인덱스 크기 |
|---|---|---:|---:|---:|---|---:|
| 일반 | 인덱스 없음 | 6.055ms | 941/0 | 99,997 | quicksort | 0 |
| 일반 | `user_id` | 0.119ms | 9/0 | 0 | quicksort | 933,888B |
| 일반 | `user_id, created_at DESC` | 0.089ms | 7/0 | 0 | 없음 | 3,178,496B |
| 주문 집중 | 인덱스 없음 | 6.062ms | 941/0 | 99,677 | top-N heapsort | 0 |
| 주문 집중 | `user_id` | 0.213ms | 12/0 | 0 | top-N heapsort | 933,888B |
| 주문 집중 | `user_id, created_at DESC` | 0.107ms | 7/0 | 0 | 없음 | 3,178,496B |

복합 인덱스는 기준 대비 일반 사용자 약 68배, 주문 집중 사용자 약 57배 빨랐다. 단일 인덱스보다 크지만 정렬을 제거하고 주문이 많은 사용자에서 실행시간과 버퍼 사용을 더 안정적으로 줄였으므로 복합 인덱스를 선택했다.

최종 마이그레이션:

```sql
CREATE INDEX idx_orders_user_created_at
ON orders (user_id, created_at DESC);
```

## 5. 상품 인덱스 비교

후보:

```sql
-- 후보 A: 모든 상태 포함
CREATE INDEX ON products (status, created_at DESC);

-- 후보 B: 판매 중인 상품만 포함
CREATE INDEX ON products (created_at DESC)
WHERE status = 'ACTIVE';
```

10회 실행 중앙값:

| 후보 | 실행시간 | hit/read | 필터 제거 | 정렬 | 인덱스 크기 |
|---|---:|---:|---:|---|---:|
| 인덱스 없음 | 15.235ms | 1,272/0 | 10,000 | top-N heapsort | 0 |
| 전체 복합 인덱스 | 0.046ms | 4/0 | 0 | 없음 | 3,366,912B |
| ACTIVE 부분 인덱스 | 0.041ms | 3/0 | 0 | 없음 | 1,810,432B |

부분 인덱스는 기준 대비 약 372배 빨랐다. 전체 복합 인덱스와 실행시간 차이는 작지만 버퍼가 하나 적고 인덱스 크기가 약 46% 작아 부분 인덱스를 선택했다.

최종 마이그레이션:

```sql
CREATE INDEX idx_products_active_created_at
ON products (created_at DESC)
WHERE status = 'ACTIVE';
```

## 6. 100만 건 확장 검증

최종 인덱스를 적용한 상태에서 사용자 10,000명, 상품 100,000개를 유지하고 주문·주문 항목을 각각 1,000,000건으로 확장했다.

| 쿼리 | 실행시간 중앙값 | hit/read | 정렬 | 실행 계획 |
|---|---:|---:|---|---|
| 일반 사용자 최근 주문 | 0.115ms | 7/0 | 없음 | Index Scan |
| 주문 집중 사용자 최근 주문 | 0.123ms | 7/0 | 없음 | Index Scan |
| 판매 중인 최신 상품 | 0.049ms | 3/0 | 없음 | Index Scan |

데이터가 10배 증가해도 `LIMIT 20`에 필요한 인덱스 엔트리만 읽었으며 전체 스캔이나 별도 정렬이 다시 나타나지 않았다.

## 7. 성공 기준 평가

- [v] 주문 조회가 전체 스캔에서 인덱스 스캔으로 변경됨
- [v] 상품 조회가 전체 스캔에서 부분 인덱스 스캔으로 변경됨
- [v] 두 쿼리 모두 별도 정렬이 제거됨
- [v] 주문 조회 버퍼가 941개에서 7개로 감소함
- [v] 상품 조회 버퍼가 1,272개에서 3개로 감소함
- [v] 실행시간 중앙값이 감소함
- [v] 인덱스 크기와 데이터 편향을 함께 검토함
- [v] 100만 건 확장 데이터에서 최종 실행 계획을 재검증함

## 8. 비용과 한계

- 인덱스는 읽기를 줄이는 대신 INSERT, UPDATE, DELETE 때 추가 쓰기 비용을 만든다.
- 주문 복합 인덱스는 단일 `user_id` 인덱스보다 약 3.4배 크다.
- 상품 부분 인덱스는 `ACTIVE` 조건과 정확히 일치하는 쿼리에만 유리하다.
- 로컬 웜 캐시 결과는 운영 서버의 디스크, 메모리, 동시 사용자와 네트워크 지연을 반영하지 않는다.
- 이번 실험은 읽기 쿼리 중심이며 동시 쓰기 처리량은 별도로 측정하지 않았다.
- 일반 `CREATE INDEX`는 운영 환경에서 쓰기를 차단할 수 있다. 운영 적용 시 `CREATE INDEX CONCURRENTLY`와 별도 배포 절차를 검토해야 한다.

## 9. 파티셔닝 판단

이번 단계에서는 파티셔닝을 적용하지 않는다.

- 100만 건에서도 선택한 인덱스로 조회가 안정적이었다.
- 현재 쿼리는 사용자 ID와 상품 상태가 핵심 조건이므로 날짜 파티션 제거 효과가 제한적이다.
- 파티셔닝은 마이그레이션, UNIQUE/FK 설계와 운영 복잡도를 높인다.

주문이 수천만 건 이상으로 증가하고 날짜 범위 조회나 기간 단위 보관·삭제가 주요 요구사항이 될 때 월별 `created_at` 파티셔닝을 다시 검토한다.

## 10. 재현 방법

```bash
# 기본 10만 건 생성
docker compose -f 19-database-architect/docker-compose.yml exec -T postgres \
  psql -v ON_ERROR_STOP=1 -v benchmark_scale=1 -U lab -d shop_lab \
  < 19-database-architect/benchmarks/generate-performance-data.sql

# 후보 인덱스 비교
python3 19-database-architect/benchmarks/measure_performance.py --mode candidates

# 최종 인덱스 적용
docker compose -f 19-database-architect/docker-compose.yml exec -T postgres \
  psql -v ON_ERROR_STOP=1 -U lab -d shop_lab \
  < 19-database-architect/migrations/002_performance_indexes_up.sql

# 최종 인덱스 측정
python3 19-database-architect/benchmarks/measure_performance.py --mode final

# 합성 데이터 정리
docker compose -f 19-database-architect/docker-compose.yml exec -T postgres \
  psql -v ON_ERROR_STOP=1 -U lab -d shop_lab \
  < 19-database-architect/benchmarks/cleanup-performance-data.sql
```

100만 건 확장 검증은 합성 데이터를 정리한 뒤 `benchmark_scale=10`으로 다시 생성한다.
