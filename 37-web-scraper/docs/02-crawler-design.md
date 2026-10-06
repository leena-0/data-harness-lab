# 02. 크롤러 설계

## 1. 단계 목표

Books to Scrape의 전체 목록 페이지를 순회하고, 목록에서 발견한 모든 상품 상세 페이지를 안전하게 요청하는 크롤러를 설계한다.

이번 단계에서는 다음 범위까지만 다룬다.

- Scrapy 프로젝트 실행 환경 결정
- 요청 속도와 재시도 정책 결정
- 목록 및 상세 페이지 요청 흐름 설계
- URL 정규화와 도메인 제한 설계
- 페이지 구조 이상과 네트워크 실패 처리 설계
- 실행 결과를 확인할 통계 정의

상세 페이지의 필드 추출과 데이터 검증은 4단계, SQLite 저장과 CSV 내보내기는 5단계에서 진행한다.

## 2. 기술 선택

| 항목 | 결정 | 이유 |
|---|---|---|
| Python | `>=3.12,<3.15` | 현재 Python 3.13 환경을 지원하면서 호환 범위를 명확히 한다. |
| Scrapy | `>=2.19,<3.0` | 2.x 최신 안정 계열을 사용하고 호환되지 않을 수 있는 다음 메이저 버전은 제외한다. |
| spider | `BooksSpider` 하나 | 대상 도메인과 순회 흐름이 하나이므로 여러 spider로 분리하지 않는다. |
| 선택자 | CSS | 2단계에서 정의한 선택자 정책을 유지한다. |
| 렌더링 | 일반 HTTP 요청 | 대상 페이지가 JavaScript 렌더링을 요구하지 않는다. |

가상환경 안에 프로젝트를 editable 모드로 설치할 수 있도록 `pyproject.toml`을 구성한다. 의존성 잠금은 전체 구현과 테스트가 안정된 뒤 검토한다.

## 3. 처리 흐름

```text
start()
  |
  v
첫 목록 페이지 요청
  |
  v
parse_listing()
  |-- 상품 상세 URL N개 --> parse_product()
  |
  `-- 다음 목록 URL 1개 --> parse_listing()
```

### `start()`

- 시작 URL은 `https://books.toscrape.com/` 하나다.
- 첫 요청에 목록 페이지임을 나타내는 `page_kind=listing` 메타데이터를 붙인다.
- 재시도를 모두 소진한 요청을 처리할 공통 errback을 연결한다.

### `parse_listing()`

- 접근 거부 상태가 아닌지 확인한다.
- 상품 카드와 페이지 상태가 존재하는지 검증한다.
- 상품 카드에서 상세 페이지 URL을 발견한다.
- 상세 URL을 정규화하고 허용 도메인인지 확인한다.
- 각 상세 페이지를 `parse_product()`로 요청한다.
- `Page N of M`을 해석하고 다음 링크와 일치하는지 검증한다.
- 마지막 페이지가 아니면 다음 목록 페이지를 다시 `parse_listing()`으로 요청한다.

### `parse_product()`

- 3단계에서는 정상 상세 응답 수만 통계에 기록한다.
- 불완전한 item을 생성하거나 저장하지 않는다.
- 실제 필드 추출은 4단계에서 이 callback에 추가한다.

### 공통 errback

- 요청 URL, 페이지 종류와 최종 실패 원인을 기록한다.
- 목록 요청 실패는 전체 범위를 보장할 수 없으므로 spider를 중단한다.
- 상세 요청 실패는 해당 상품만 실패 처리하고 나머지 요청은 계속한다.

## 4. 요청 제한

| 설정 | 값 | 목적 |
|---|---:|---|
| `ROBOTSTXT_OBEY` | `True` | 향후 robots 정책 파일이 생기면 자동으로 준수한다. |
| `CONCURRENT_REQUESTS` | `1` | 전체 동시 요청을 하나로 제한한다. |
| `CONCURRENT_REQUESTS_PER_DOMAIN` | `1` | 도메인별 동시 요청을 하나로 제한한다. |
| `DOWNLOAD_DELAY` | `1.0` | 같은 도메인 요청 사이에 최소 1초를 둔다. |
| `DOWNLOAD_DELAY_JITTER` | `0.0` | 무작위 감소로 간격이 1초 미만이 되는 것을 막는다. |
| `DOWNLOAD_TIMEOUT` | `30` | 응답 없는 요청을 유한 시간 안에 실패 처리한다. |
| `DOWNLOAD_MAXSIZE` | `5 MiB` | 비정상적으로 큰 응답의 다운로드를 중단한다. |
| `COOKIES_ENABLED` | `False` | 필요하지 않은 세션 상태를 사용하지 않는다. |
| `TELNETCONSOLE_ENABLED` | `False` | 사용하지 않는 원격 콘솔을 비활성화한다. |

User-Agent는 프로젝트와 수집 목적을 식별할 수 있도록 다음 값으로 정한다.

```text
data-harness-lab/0.1 (+https://github.com/leena-0/data-harness-lab; educational scraper)
```

## 5. 재시도 정책

최초 요청 이후 최대 3회 재시도한다.

### 재시도 대상

```text
408, 429, 500, 502, 503, 504, 522, 524
```

DNS 조회 실패, 연결 끊김과 시간 초과 등 Scrapy가 지원하는 일시적 네트워크 오류도 재시도 대상에 포함한다.

### 재시도하지 않는 응답

- `400`: 잘못된 요청
- `404`: 존재하지 않는 리소스
- 그 밖의 영구적인 클라이언트 오류

### 접근 거부 응답

- `401`, `403`은 즉시 전체 실행을 중단한다.
- `429`는 서버의 `Retry-After`가 있으면 그 값을 우선한다.
- 최종 재시도 후에도 `429`가 계속되면 전체 실행을 중단한다.

### 대기 시간

증가형 backoff는 다음 순서로 적용한다.

```text
1차 재시도: 1초
2차 재시도: 2초
3차 재시도: 4초
```

Scrapy 기본 RetryMiddleware만으로는 위 증가형 대기를 보장하지 못하므로 구현 시 전용 retry middleware가 필요하다. middleware는 Scrapy의 중복 필터를 우회하기 위한 임의 요청을 만들지 않고, 기존 재시도 횟수와 통계를 유지해야 한다.

## 6. URL 정규화

목록, 다음 페이지와 상품 상세 링크에 동일한 함수를 사용한다.

1. 현재 응답 URL과 상대 링크를 `urljoin`한다.
2. scheme은 `http`와 `https`만 허용한다.
3. hostname은 소문자로 비교한다.
4. 사용자 이름이나 비밀번호가 포함된 URL은 거부한다.
5. hostname이 `books.toscrape.com`이 아니면 거부한다.
6. 결과 URL의 scheme은 `https`로 통일한다.
7. query string과 fragment는 제거한다.
8. 빈 경로는 `/`로 정규화한다.
9. 정규화된 URL을 요청 중복 판정과 `product_url` 저장에 함께 사용한다.

예시:

```text
기준 URL: https://books.toscrape.com/catalogue/page-2.html
상대 URL: ../../catalogue/example-book_1/index.html?source=list#reviews
결과 URL: https://books.toscrape.com/catalogue/example-book_1/index.html
```

## 7. 목록 구조 검증

상품 수나 총 페이지 수는 코드에 고정하지 않는다. 각 목록 페이지가 스스로 표시하는 상태와 링크의 일관성을 확인한다.

| 조건 | 처리 |
|---|---|
| 상품 카드가 0개 | 전체 실행 중단 |
| 상품 카드 수와 상세 링크 수가 다름 | 전체 실행 중단 |
| `Page N of M`이 없음 | 전체 실행 중단 |
| 페이지 상태가 정수로 해석되지 않음 | 전체 실행 중단 |
| `N < 1`, `M < 1` 또는 `N > M` | 전체 실행 중단 |
| `N < M`인데 다음 링크가 없음 | 전체 실행 중단 |
| `N = M`인데 다음 링크가 있음 | 전체 실행 중단 |
| 다음 링크가 허용 도메인 밖임 | 전체 실행 중단 |
| 상품 링크가 허용 도메인 밖임 | 해당 링크를 건너뛰고 경고 기록 |

마지막 페이지는 다음 링크가 없고 `N = M`인 경우에만 정상 종료한다.

## 8. 실패 처리

| 상황 | 처리 | 종료 상태 |
|---|---|---|
| 목록 요청 최종 실패 | 전체 중단 | 실패 |
| 목록 구조 이상 | 전체 중단 | 실패 |
| 접근 거부 | 전체 중단 | 실패 |
| 상세 요청 최종 실패 | 해당 상품만 건너뛰고 계속 | 부분 실패 |
| 외부 상품 링크 발견 | 요청하지 않고 계속 | 경고 또는 부분 실패 |
| 상세 페이지 필수 구조 누락 | 4단계에서 해당 상품 실패 처리 | 부분 실패 |

중단 사유는 `listing_request_failed`, `listing_structure_changed`, `access_denied_403`처럼 정상 완료와 구분할 수 있는 값으로 기록한다.

## 9. 수집 통계

| 통계 키 | 의미 |
|---|---|
| `books/listing_pages_seen` | 검증을 시작한 목록 페이지 수 |
| `books/detail_requests_scheduled` | 생성한 상세 페이지 요청 수 |
| `books/detail_pages_seen` | 정상 응답을 받은 상세 페이지 수 |
| `books/offsite_links_skipped` | 거부한 외부 또는 잘못된 상품 URL 수 |
| `books/retry_count` | 전체 재시도 횟수 |
| `books/listing_request_failures` | 최종 실패한 목록 요청 수 |
| `books/detail_request_failures` | 최종 실패한 상세 요청 수 |
| `finish_reason` | 정상 완료 또는 중단 사유 |

최종 성공·부분 실패를 판정하는 구체적인 임계값은 6단계 모니터링 설계에서 정한다.

## 10. 구현 대상

다음 구현 작업에서 아래 파일을 작성한다.

| 파일 | 구현 내용 |
|---|---|
| `pyproject.toml` | Python 범위와 Scrapy 의존성 |
| `scrapy.cfg` | Scrapy 설정 모듈 연결 |
| `src/web_scraper_lab/settings.py` | 요청 제한, 재시도와 로그 설정 |
| `src/web_scraper_lab/middlewares.py` | `Retry-After`와 증가형 backoff 처리 |
| `src/web_scraper_lab/spiders/books.py` | 목록 순회, 상세 요청과 실패 처리 |

`items.py`와 상세 데이터 파싱은 4단계, `pipelines.py`와 SQLite 저장은 5단계에서 작성한다.

## 11. 설계 완료 확인

- [x] Python과 Scrapy 버전 범위를 정했다.
- [x] 단일 spider와 callback의 책임을 정했다.
- [x] 3단계 구현 범위를 페이지 순회까지로 제한했다.
- [x] 동시 요청 수와 요청 간격을 정했다.
- [x] 재시도 상태, 횟수와 backoff를 정했다.
- [x] URL 정규화와 허용 도메인 규칙을 정했다.
- [x] 목록 구조의 검증 조건을 정했다.
- [x] 목록 실패와 상세 실패의 처리 방식을 분리했다.
- [x] 수집 통계 키를 정했다.
- [ ] 설정과 크롤러 코드는 아직 구현하지 않았다.
