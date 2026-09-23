# 19. Database Architect Lab

[Harness 100의 Database Architect](https://github.com/revfactory/harness-100/tree/main/ko/19-database-architect/.claude)가 정의한 흐름을 참고하여, 작은 쇼핑몰의 PostgreSQL 데이터베이스를 직접 설계하고 검증하는 실습입니다.

원본 하네스를 복사하는 대신 다음 과정을 직접 수행하고, 판단 근거와 실행 결과를 문서로 남깁니다.

```text
요구사항 -> 데이터 모델 -> 마이그레이션 -> 성능/보안 검토 -> 통합 리뷰
```

## 학습 목표

- 업무 요구사항을 엔티티, 관계, 제약조건으로 변환한다.
- 정규화된 스키마와 ERD를 설계한다.
- 적용과 롤백이 가능한 PostgreSQL 마이그레이션을 작성한다.
- 실제 조회 패턴을 기준으로 인덱스를 설계한다.
- 권한, 개인정보, 감사 관점에서 스키마를 검토한다.
- 설계 결정과 검증 결과를 재현 가능한 기록으로 남긴다.

## 실습 시나리오

사용자, 상품, 주문, 주문 항목, 결제, 리뷰를 관리하는 작은 쇼핑몰을 설계합니다. 자세한 요구사항은 [`docs/00-requirements.md`](docs/00-requirements.md)에 정리합니다.

기본 환경은 PostgreSQL 16이며, 학습용 예상 규모는 다음과 같습니다.

- 사용자 100만 명
- 상품 10만 개
- 하루 주문 10만 건
- 주문 내역 조회와 상품 조회가 주요 읽기 패턴

## 진행 순서

- [v] 1단계: 요구사항과 주요 액세스 패턴 정리
- [v] 2단계: 엔티티, 관계, 정규화 및 ERD 설계
- [ ] 3단계: 적용·롤백 마이그레이션 작성
- [ ] 4단계: 샘플 데이터와 스키마 제약조건 테스트
- [ ] 5단계: `EXPLAIN ANALYZE` 기반 성능 비교
- [ ] 6단계: 보안 검토
- [ ] 7단계: 통합 리뷰와 회고

## 디렉터리

```text
19-database-architect/
├── README.md
├── docker-compose.yml
├── docs/
│   ├── 00-requirements.md
│   ├── 01-data-model.md
│   ├── 02-migration-plan.md
│   ├── 03-performance.md
│   ├── 04-security.md
│   └── 05-review-report.md
├── diagrams/erd.mmd
├── migrations/
│   ├── 001_initial_up.sql
│   └── 001_initial_down.sql
├── queries/
├── seeds/sample-data.sql
└── tests/schema-tests.sql
```

## 로컬 실행

Docker가 설치되어 있다면 다음 명령으로 학습용 PostgreSQL을 실행합니다.

```bash
docker compose up -d
docker compose exec postgres psql -U lab -d shop_lab
```

실습을 마친 뒤에는 다음 명령으로 컨테이너를 종료합니다.

```bash
docker compose down
```

데이터까지 초기화해야 할 때만 `docker compose down -v`를 사용합니다.

> `docker-compose.yml`의 비밀번호는 로컬 학습 전용입니다. 실제 서비스에서는 비밀 관리 도구를 사용해야 합니다.

## 완료 기준

- 빈 DB에서 마이그레이션 적용, 테스트, 롤백, 재적용이 모두 성공한다.
- 모든 관계와 삭제 정책에 선택 이유가 기록되어 있다.
- 주요 쿼리의 인덱스 적용 전후 실행 계획을 비교했다.
- 보안 검토의 필수 수정 사항이 통합 리뷰 전에 해결되었다.
