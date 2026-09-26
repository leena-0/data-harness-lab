# 02. 마이그레이션 계획

이 문서는 `01-data-model.md`의 논리 모델을 PostgreSQL 16의 초기 스키마로 적용하고 되돌리는 절차를 정의한다.

## 1. 적용 범위와 원칙

- 대상은 비어 있는 학습용 데이터베이스 `shop_lab`이다.
- 마이그레이션은 별도 도구 없이 순수 SQL로 작성한다.
- 모든 DDL은 하나의 트랜잭션 안에서 실행한다.
- 하나라도 실패하면 전체를 롤백하여 부분 스키마가 남지 않게 한다.
- `IF NOT EXISTS`를 사용하지 않는다. 예상하지 못한 기존 객체가 있으면 즉시 실패시켜 스키마 불일치를 드러낸다.
- 기본 `public` 스키마를 사용한다.
- 모든 PK, FK, UNIQUE, CHECK 제약조건에는 명시적인 이름을 붙인다.
- 샘플 데이터는 마이그레이션에 포함하지 않고 `seeds/sample-data.sql`에서 관리한다.
- 이 계획은 최초 설치용이다. 데이터가 존재하는 운영 DB의 무중단 변경에는 별도의 증분 마이그레이션이 필요하다.

## 2. 파일 구성

| 파일 | 역할 |
|---|---|
| `migrations/001_initial_up.sql` | 함수, 테이블, 제약조건, 무결성 인덱스와 트리거 생성 |
| `migrations/001_initial_down.sql` | 생성한 객체를 의존 관계의 역순으로 제거 |
| `seeds/sample-data.sql` | 스키마 검증에 사용할 학습용 데이터 입력 |
| `tests/schema-tests.sql` | 정상 입력과 제약조건 위반 사례 검증 |

## 3. 적용 순서

`001_initial_up.sql`은 다음 순서로 실행한다.

### 3.1 트랜잭션 시작

1. `BEGIN`으로 전체 마이그레이션을 시작한다.
2. `SET LOCAL TIME ZONE 'UTC'`로 현재 트랜잭션의 시간대를 UTC로 설정한다.

`TIMESTAMPTZ`는 절대 시각을 저장하지만, 테스트 결과와 기본값 표현을 일관되게 하기 위해 마이그레이션 세션도 UTC를 사용한다.

### 3.2 공통 함수 생성

`updated_at` 컬럼을 자동 갱신하는 `set_updated_at()` 트리거 함수를 생성한다.

- 실행 시점: 각 행의 `UPDATE` 이전
- 동작: `NEW.updated_at = CURRENT_TIMESTAMP`
- 적용 대상: `users`, `products`, `orders`, `payments`, `reviews`

### 3.3 테이블 생성

FK 의존 관계를 고려하여 다음 순서로 생성한다.

1. `users`
2. `products`
3. `orders`
4. `order_items`
5. `payments`
6. `reviews`
7. `legal_retention_records`

주요 FK 정책:

| FK | 삭제 정책 |
|---|---|
| `orders.user_id -> users.id` | `ON DELETE SET NULL` |
| `order_items.order_id -> orders.id` | `ON DELETE RESTRICT` |
| `order_items.product_id -> products.id` | `ON DELETE RESTRICT` |
| `payments.order_id -> orders.id` | `ON DELETE RESTRICT` |
| `reviews.order_item_id -> order_items.id` | `ON DELETE RESTRICT` |
| `legal_retention_records.order_id -> orders.id` | `ON DELETE RESTRICT` |

PK는 모두 `BIGINT GENERATED ALWAYS AS IDENTITY`로 생성한다. 상태값은 PostgreSQL ENUM 대신 `VARCHAR + CHECK`를 사용한다.

### 3.4 무결성 인덱스 생성

초기 마이그레이션에는 무결성 보장에 필요한 인덱스만 포함한다.

- PK에 의해 생성되는 고유 인덱스
- `users.email` UNIQUE
- `payments.transaction_id` UNIQUE
- `reviews.order_item_id` UNIQUE
- `order_items(order_id, product_id)` UNIQUE
- `legal_retention_records(order_id, retention_category)` UNIQUE
- `payments(order_id)`에 대해 `status = 'SUCCEEDED'`인 행만 대상으로 하는 부분 UNIQUE 인덱스

사용자의 최근 주문이나 상품 목록 같은 조회 성능용 인덱스는 이 단계에서 만들지 않는다. 5단계에서 `EXPLAIN (ANALYZE, BUFFERS)`로 적용 전후를 비교한 뒤 추가한다.

### 3.5 트리거 생성

`updated_at`이 있는 각 테이블에 `BEFORE UPDATE` 트리거를 생성하고 `set_updated_at()` 함수를 연결한다.

### 3.6 커밋

모든 객체 생성에 성공하면 `COMMIT`한다. 중간에 오류가 발생하면 PostgreSQL이 트랜잭션을 실패 상태로 전환하며, 실행자는 `ROLLBACK` 후 원인을 수정한다.

## 4. 명명 규칙

객체 이름만 보고 용도를 알 수 있도록 다음 규칙을 사용한다.

| 객체 | 형식 | 예시 |
|---|---|---|
| 기본 키 | `pk_{table}` | `pk_users` |
| 외래 키 | `fk_{table}_{column}` | `fk_orders_user_id` |
| UNIQUE 제약조건 | `uq_{table}_{columns}` | `uq_order_items_order_product` |
| CHECK 제약조건 | `ck_{table}_{rule}` | `ck_products_price_non_negative` |
| 인덱스 | `idx_{table}_{purpose}` | `idx_payments_one_success_per_order` |
| 트리거 | `trg_{table}_set_updated_at` | `trg_users_set_updated_at` |
| 트리거 함수 | 동작을 나타내는 이름 | `set_updated_at` |

## 5. 롤백 순서

`001_initial_down.sql` 역시 하나의 트랜잭션으로 실행한다. `IF EXISTS`를 사용하지 않으며, 예상한 객체가 없으면 스키마 불일치로 간주하고 실패시킨다.

테이블은 FK 의존 관계의 역순으로 제거한다.

1. `legal_retention_records`
2. `reviews`
3. `payments`
4. `order_items`
5. `orders`
6. `products`
7. `users`
8. `set_updated_at()` 함수

테이블을 삭제하면 해당 테이블의 트리거, 제약조건과 인덱스도 함께 제거된다. 모든 객체가 정상적으로 제거된 경우에만 `COMMIT`한다.

## 6. 데이터 손실 위험

`001_initial_down.sql`은 모든 실습 테이블을 삭제하므로 저장된 데이터도 복구할 수 없게 된다.

- 로컬 학습 환경에서만 실행한다.
- 실행 전에 연결 대상이 `shop_lab`인지 확인한다.
- 운영 또는 공유 DB에서는 실행하지 않는다.
- 보존할 데이터가 있다면 먼저 백업하고 복원 가능성을 확인한다.
- 법정 보존 대상 데이터가 존재하는 실제 서비스에서는 이 롤백 방식을 사용하지 않는다.

이번 초기 마이그레이션에는 데이터 변환이 없으므로 적용 시 기존 데이터 손실 위험은 없다. 다만 같은 이름의 객체가 존재하면 덮어쓰지 않고 실패하도록 설계한다.

## 7. 실패 처리

| 실패 상황 | 처리 방법 |
|---|---|
| SQL 문법 또는 타입 오류 | 전체 롤백 후 SQL 수정 |
| 기존 객체와 이름 충돌 | 기존 스키마를 조사하고 원인을 해결한 뒤 재실행 |
| FK 생성 실패 | 부모 테이블과 참조 컬럼의 생성 순서 및 타입 확인 |
| CHECK/UNIQUE 위반 | 테스트 데이터가 업무 규칙에 맞는지 확인 |
| 트리거 생성 실패 | 함수가 먼저 생성됐는지, 대상 테이블에 `updated_at`이 있는지 확인 |
| 롤백 실패 | 남은 객체를 조사하되 임의로 `CASCADE`를 사용하지 않음 |

## 8. 검증 절차

### 구조 검증

- [v] 빈 `shop_lab` DB에 `001_initial_up.sql` 적용
- [v] 7개 테이블과 `set_updated_at()` 함수 생성 확인
- [v] PK, FK, UNIQUE, CHECK 제약조건 이름과 정책 확인
- [v] `updated_at` 트리거가 5개 테이블에 연결됐는지 확인
- [v] 주문당 성공 결제 하나를 보장하는 부분 UNIQUE 인덱스 확인

### 데이터 검증

- [ ] `seeds/sample-data.sql`로 정상 데이터 입력
- [ ] 음수 가격, 0개 수량, 범위를 벗어난 평점 거부 확인
- [ ] 중복 이메일과 외부 거래 식별자 거부 확인
- [ ] 동일 주문의 성공 결제 두 건 거부 확인
- [ ] 사용자 삭제 후 `orders.user_id`가 NULL로 변경되는지 확인
- [ ] 거래 기록이 존재하는 주문과 상품의 삭제가 거부되는지 확인
- [ ] UPDATE 후 `updated_at`이 자동 변경되는지 확인

### 롤백 및 재적용 검증

- [v] `001_initial_down.sql` 실행
- [v] 7개 테이블과 공통 함수가 모두 제거됐는지 확인
- [v] `001_initial_up.sql` 재실행
- [v] 재적용 후 스키마 구조가 최초 적용 결과와 같은지 확인

구조 검증과 롤백 및 재적용 검증을 마치면 README의 3단계를 완료로 표시한다. 데이터 검증 항목은 4단계에서 샘플 데이터와 테스트 SQL을 작성한 뒤 완료한다.

## 9. 실행 결과

2026-09-27에 Docker의 PostgreSQL 16 환경에서 검증했다.

| 검증 항목 | 결과 |
|---|---:|
| 생성된 테이블 | 7개 |
| `updated_at` 트리거 | 5개 |
| 성공 결제 부분 UNIQUE 인덱스 | 1개 |
| 이름이 지정된 제약조건 | 31개 |
| FK 삭제 정책 | `SET NULL` 1개, `RESTRICT` 5개 |
| 롤백 후 남은 대상 테이블 | 0개 |
| 롤백 후 남은 공통 함수 | 0개 |
| 재적용 | 성공 |
