# 01. 데이터 모델

이 문서는 `00-requirements.md`의 업무 규칙을 PostgreSQL 테이블, 관계, 키와 제약조건으로 변환한 결과다. 물리 SQL은 다음 단계에서 작성한다.

## 1. 모델링 원칙

- 기본 키는 `BIGINT` 대리 키를 사용한다.
- 금액은 부동소수점 오차를 피하기 위해 `NUMERIC(12, 2)`를 사용한다.
- 시각은 UTC 기준 `TIMESTAMPTZ`로 저장한다.
- 상태값은 마이그레이션이 비교적 쉬운 `VARCHAR`와 `CHECK` 조합을 사용한다.
- 회원정보와 법정 보존 대상 정보를 분리하고 각각의 파기 시점을 관리한다.
- 과거 주문은 회원 행 없이도 유지할 수 있게 설계한다.
- 현재 상품 정보와 주문 당시 상품 정보는 분리한다.
- 한 행만으로 검사할 수 있는 규칙은 DB 제약조건으로, 여러 행의 합계나 상태 전환처럼 행 간 검사가 필요한 규칙은 애플리케이션 트랜잭션으로 보장한다.

## 2. 엔티티별 컬럼

### `users`

| 컬럼 | 타입 | 제약조건 | 설명 |
|---|---|---|---|
| `id` | `BIGINT` | PK, identity | 사용자 식별자 |
| `email` | `VARCHAR(255)` | NOT NULL, UNIQUE | 로그인과 연락에 사용하는 이메일 |
| `name` | `VARCHAR(100)` | NOT NULL | 사용자 표시 이름 |
| `status` | `VARCHAR(20)` | NOT NULL, CHECK | `ACTIVE`, `SUSPENDED` 중 하나 |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, 기본값 현재 시각 | 가입 시각 |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, 기본값 현재 시각 | 마지막 변경 시각 |

`users`에는 서비스를 이용 중인 회원정보만 둔다. 탈퇴 시 법적으로 보존해야 하는 최소 정보를 별도 저장한 뒤 사용자 행을 삭제한다. 주문은 nullable FK를 사용하므로 사용자 행이 삭제되어도 유지된다.

### `products`

| 컬럼 | 타입 | 제약조건 | 설명 |
|---|---|---|---|
| `id` | `BIGINT` | PK, identity | 상품 식별자 |
| `name` | `VARCHAR(200)` | NOT NULL | 현재 상품명 |
| `price` | `NUMERIC(12, 2)` | NOT NULL, CHECK `>= 0` | 현재 판매 가격 |
| `stock_quantity` | `INTEGER` | NOT NULL, CHECK `>= 0` | 현재 재고 수량 |
| `status` | `VARCHAR(20)` | NOT NULL, CHECK | `DRAFT`, `ACTIVE`, `INACTIVE` 중 하나 |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, 기본값 현재 시각 | 등록 시각 |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, 기본값 현재 시각 | 마지막 변경 시각 |

이번 실습에서는 재고를 `products.stock_quantity`로 단순 관리한다. 실서비스에서 입출고 이력과 예약 재고가 필요하면 별도의 재고 원장 모델로 확장한다.

### `orders`

| 컬럼 | 타입 | 제약조건 | 설명 |
|---|---|---|---|
| `id` | `BIGINT` | PK, identity | 주문 식별자 |
| `user_id` | `BIGINT` | NULL 허용, FK | 현재 회원인 경우 주문한 사용자. 탈퇴 후 NULL |
| `status` | `VARCHAR(20)` | NOT NULL, CHECK | 주문 처리 상태 |
| `total_amount` | `NUMERIC(12, 2)` | NOT NULL, CHECK `>= 0` | 주문 항목 합계의 스냅샷 |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, 기본값 현재 시각 | 주문 시각 |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, 기본값 현재 시각 | 마지막 변경 시각 |

허용 상태는 `PENDING`, `PAID`, `PREPARING`, `SHIPPED`, `COMPLETED`, `CANCELLED`다. 허용값은 DB가 검사하고, 상태 간 전환 규칙은 애플리케이션 서비스가 트랜잭션 안에서 검사한다.

### `order_items`

| 컬럼 | 타입 | 제약조건 | 설명 |
|---|---|---|---|
| `id` | `BIGINT` | PK, identity | 주문 항목 식별자 |
| `order_id` | `BIGINT` | NOT NULL, FK | 소속 주문 |
| `product_id` | `BIGINT` | NOT NULL, FK | 주문한 상품 |
| `product_name` | `VARCHAR(200)` | NOT NULL | 주문 당시 상품명 스냅샷 |
| `unit_price` | `NUMERIC(12, 2)` | NOT NULL, CHECK `>= 0` | 주문 당시 상품 단가 |
| `quantity` | `INTEGER` | NOT NULL, CHECK `>= 1` | 주문 수량 |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, 기본값 현재 시각 | 생성 시각 |

한 주문에서 같은 상품을 여러 줄로 나누지 않는다는 가정으로 `(order_id, product_id)`에 `UNIQUE`를 둔다. 옵션 상품이 추가되면 이 제약은 옵션 식별자를 포함하도록 변경해야 한다.

### `payments`

| 컬럼 | 타입 | 제약조건 | 설명 |
|---|---|---|---|
| `id` | `BIGINT` | PK, identity | 결제 시도 식별자 |
| `order_id` | `BIGINT` | NOT NULL, FK | 결제 대상 주문 |
| `transaction_id` | `VARCHAR(100)` | NOT NULL, UNIQUE | 외부 결제사의 거래 식별자 |
| `method` | `VARCHAR(20)` | NOT NULL, CHECK | `CARD`, `BANK_TRANSFER` 중 하나 |
| `amount` | `NUMERIC(12, 2)` | NOT NULL, CHECK `> 0` | 결제 시도 금액 |
| `status` | `VARCHAR(20)` | NOT NULL, CHECK | `PENDING`, `SUCCEEDED`, `FAILED`, `CANCELLED` 중 하나 |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, 기본값 현재 시각 | 결제 시도 시각 |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, 기본값 현재 시각 | 마지막 상태 변경 시각 |

카드 번호와 CVC는 저장하지 않는다. 한 주문에는 여러 결제 시도가 가능하지만 성공 결제는 하나만 허용하며, SQL 단계에서 `status = 'SUCCEEDED'`인 행을 대상으로 부분 고유 인덱스를 만든다.

### `reviews`

| 컬럼 | 타입 | 제약조건 | 설명 |
|---|---|---|---|
| `id` | `BIGINT` | PK, identity | 리뷰 식별자 |
| `order_item_id` | `BIGINT` | NOT NULL, FK, UNIQUE | 리뷰 대상 구매 항목 |
| `rating` | `SMALLINT` | NOT NULL, CHECK `BETWEEN 1 AND 5` | 평점 |
| `content` | `TEXT` | NOT NULL | 리뷰 내용 |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, 기본값 현재 시각 | 작성 시각 |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, 기본값 현재 시각 | 마지막 변경 시각 |

리뷰의 작성자와 상품은 `order_item -> order -> user`, `order_item -> product` 관계로 알 수 있으므로 중복 저장하지 않는다. 주문이 `COMPLETED` 상태인지 확인한 뒤 리뷰를 생성하는 규칙은 애플리케이션 트랜잭션에서 보장한다.

사용자 탈퇴 후에는 `orders.user_id`가 NULL이 되므로 운영 화면에서 리뷰 작성자를 탈퇴 사용자로 표시한다. 탈퇴 전에 작성된 리뷰를 계속 공개할지는 서비스 정책과 개인정보 처리방침에 따라 별도로 결정한다.

### `legal_retention_records`

| 컬럼 | 타입 | 제약조건 | 설명 |
|---|---|---|---|
| `id` | `BIGINT` | PK, identity | 법정 보존 레코드 식별자 |
| `order_id` | `BIGINT` | NOT NULL, FK | 보존 근거가 되는 주문 |
| `retention_category` | `VARCHAR(30)` | NOT NULL, CHECK | `CONTRACT`, `PAYMENT`, `DISPUTE` 중 하나 |
| `retained_data_encrypted` | `BYTEA` | NOT NULL | 해당 근거에 필요한 최소 개인정보를 애플리케이션에서 암호화한 값 |
| `retention_until` | `TIMESTAMPTZ` | NOT NULL | 파기 예정 시각 |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, 기본값 현재 시각 | 분리 보관 시작 시각 |

같은 주문과 보존 범주가 중복되지 않도록 `(order_id, retention_category)`에 `UNIQUE`를 둔다. 암호화 키는 DB에 함께 저장하지 않으며, 일반 애플리케이션 계정은 이 테이블을 읽을 수 없다. 만료된 행은 별도의 파기 작업이 삭제한다.

## 3. 관계와 카디널리티

| 부모 | 자식 | 관계 | 의미 |
|---|---|---|---|
| `users` | `orders` | 1:N | 한 사용자는 0개 이상의 주문을 만든다. 탈퇴 후 주문의 사용자 관계는 없어질 수 있다. |
| `orders` | `order_items` | 1:N | 한 주문에는 1개 이상의 주문 항목이 있어야 한다. |
| `products` | `order_items` | 1:N | 한 상품은 여러 주문 항목에서 참조될 수 있다. |
| `orders` | `payments` | 1:N | 한 주문에는 여러 결제 시도가 존재할 수 있다. |
| `order_items` | `reviews` | 1:0..1 | 한 주문 항목에는 리뷰가 없거나 하나만 존재한다. |
| `orders` | `legal_retention_records` | 1:N | 한 주문에 보존 근거별 레코드가 0개 이상 존재할 수 있다. |

`orders`에 주문 항목이 최소 하나 존재하는지는 일반적인 FK나 `CHECK`만으로 보장할 수 없다. 주문과 주문 항목을 하나의 트랜잭션에서 생성하고, 주문 생성 API가 빈 항목 목록을 거부하도록 한다.

## 4. 키와 제약조건

### DB에서 직접 보장

- 사용자 이메일의 유일성
- 상품 가격과 재고가 음수가 아님
- 주문 총액과 주문 당시 단가가 음수가 아님
- 주문 수량이 1 이상임
- 평점이 1~5 사이임
- 상태와 결제 수단이 허용된 값임
- 외부 결제 거래 식별자의 유일성
- 한 주문 항목당 최대 한 개의 리뷰
- 한 주문당 최대 한 개의 성공 결제
- 주문과 보존 범주 조합의 유일성
- 법정 보존 레코드의 파기 예정 시각 존재

### 애플리케이션 트랜잭션에서 보장

- 주문에는 최소 한 개의 주문 항목이 존재함
- `orders.total_amount`가 `SUM(order_items.unit_price * quantity)`와 일치함
- 성공한 결제 금액이 주문 총액과 일치함
- 재고 확인과 차감이 동시 주문에서도 안전함
- 주문 상태가 허용된 순서로 전환됨
- 완료된 주문의 구매자만 리뷰를 작성함
- 탈퇴 시 필요한 법정 보존 정보 분리와 회원정보 삭제가 함께 완료됨
- 보존기간이 지난 법정 보존 정보가 복구 불가능하게 파기됨

이 규칙들은 이후 테스트에서 정상 사례와 위반 사례를 모두 검증한다.

## 5. 정규화 검토

### 1NF

모든 컬럼은 원자값을 가진다. 주문의 상품 목록을 배열이나 JSON으로 저장하지 않고 `order_items` 행으로 분리한다.

### 2NF

각 테이블은 단일 대리 키를 기본 키로 사용하며, 일반 속성은 해당 엔티티 전체에 종속된다. 주문 항목의 수량과 주문 당시 단가는 `order_items.id`에 종속된다.

### 3NF

현재 사용자 정보는 `users`, 현재 상품 정보는 `products`, 결제 정보는 `payments`에 분리한다. `reviews`에는 관계를 통해 유도할 수 있는 `user_id`와 `product_id`를 중복 저장하지 않는다. 법적 의무로 보존하는 개인정보는 `legal_retention_records`로 분리해 일반 회원정보와 수명주기 및 접근 권한을 다르게 관리한다.

### 의도적인 중복 저장

`order_items.product_name`과 `order_items.unit_price`는 현재 `products` 값과 중복될 수 있다. 하지만 이는 과거 주문 계약 내용을 보존하기 위한 시점 스냅샷이므로 제거하지 않는다. `orders.total_amount`도 빠른 주문·결제 조회와 결제 금액 검증을 위해 저장하되, 주문 생성 트랜잭션에서 항목 합계와 함께 계산한다.

## 6. 삭제 정책

| FK | 정책 | 근거 |
|---|---|---|
| `orders.user_id -> users.id` | `ON DELETE SET NULL` | 회원정보를 파기하면서 개인정보가 없는 주문 기록은 유지한다. |
| `order_items.order_id -> orders.id` | `ON DELETE RESTRICT` | 주문과 주문 항목은 거래 기록으로 보존한다. |
| `order_items.product_id -> products.id` | `ON DELETE RESTRICT` | 과거 주문이 참조한 상품의 물리 삭제를 막는다. |
| `payments.order_id -> orders.id` | `ON DELETE RESTRICT` | 결제 감사 기록을 보존한다. |
| `reviews.order_item_id -> order_items.id` | `ON DELETE RESTRICT` | 실제 구매와 리뷰의 연결을 유지한다. |
| `legal_retention_records.order_id -> orders.id` | `ON DELETE RESTRICT` | 법정 보존기간 중 근거 거래가 삭제되는 것을 막는다. |

- 사용자는 탈퇴 처리 시 법정 보존 대상만 분리한 뒤 `users` 행을 삭제한다.
- 상품은 행을 삭제하는 대신 `INACTIVE` 상태로 변경한다.
- 주문, 주문 항목과 결제는 적용되는 보존기간 동안 일반 운영 기능에서 물리 삭제하지 않는다.
- 보존기간 종료 후에는 법정 보존 레코드를 삭제하고, 거래 레코드의 외부 식별자처럼 재식별에 사용될 수 있는 값도 삭제 또는 비식별 처리한다.

탈퇴 처리 순서:

1. 로그인을 차단하고 활성 세션과 토큰을 폐기한다.
2. 적용 법령에 따라 필요한 최소 정보만 암호화하여 `legal_retention_records`에 저장한다.
3. `users` 행을 삭제하면 `orders.user_id`는 자동으로 NULL이 된다.
4. 정기 파기 작업이 `retention_until`이 지난 보존 레코드를 삭제하고 결과를 감사 로그에 남긴다.

## 7. 설계 결정 기록

| 결정 | 선택지 | 선택 | 근거 |
|---|---|---|---|
| 사용자 탈퇴 | 영구 소프트 삭제 / 익명화 / 회원 삭제·법정 정보 분리 | 회원 삭제 + 법정 정보 분리 보관 | 목적이 끝난 회원정보는 파기하고 법적 의무가 있는 최소 정보만 제한적으로 보존한다. |
| 재고 관리 | 상품에 현재 수량 / 별도 재고 원장 | 상품에 `stock_quantity` 저장 | 첫 실습의 범위를 제한한다. 입출고 이력이 필요해지면 원장으로 확장한다. |
| 주문 총액 | 매번 계산 / 주문에 저장 | `orders.total_amount`에 저장 | 주문 조회와 결제 검증이 빈번하다. 생성 트랜잭션에서 항목 합계와 일치시킨다. |
| 주문 당시 상품 정보 | 현재 상품 참조 / 스냅샷 저장 | 이름과 단가 저장 | 상품 정보가 바뀌어도 과거 주문 계약 내용을 유지한다. |
| 주문 상태 이력 | 별도 이력 테이블 / 현재 상태만 저장 | 현재 상태만 저장 | 첫 실습 범위를 제한한다. 감사 요구가 생기면 이력 테이블을 추가한다. |
| 성공 결제 수 | 애플리케이션 검사 / DB 제약 | 부분 고유 인덱스 | 동시 요청에서도 DB가 주문당 성공 결제 하나를 보장하게 한다. |
| 파티셔닝 | 처음부터 적용 / 측정 후 적용 | 초기에는 적용하지 않음 | 파티셔닝은 운영 복잡도를 높인다. 실제 크기와 쿼리 병목을 확인한 뒤 결정한다. |
| 리뷰의 사용자·상품 | 리뷰에 중복 저장 / 관계로 유도 | `order_item` 관계로 유도 | 갱신 불일치 가능성을 없애고 3NF를 유지한다. |

## 8. 2단계 완료 기준

- [v] 모든 핵심 엔티티의 컬럼과 타입을 정의했다.
- [v] 관계와 카디널리티를 정의했다.
- [v] DB 제약조건과 애플리케이션 규칙을 구분했다.
- [v] 정규화와 의도적 중복 저장의 이유를 기록했다.
- [v] 모든 FK의 삭제 정책을 결정했다.
- [v] 요구사항 문서의 미결정 사항을 검토했다.
- [v] 문서와 일치하는 ERD를 작성했다.
