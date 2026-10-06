# 01. 대상 사이트 분석

## 1. 분석 개요

| 항목 | 내용 |
|---|---|
| 대상 | [Books to Scrape](https://books.toscrape.com/) |
| 분석일 | 2026-10-06 |
| 시작 URL | `https://books.toscrape.com/` |
| 허용 도메인 | `books.toscrape.com` |
| 렌더링 방식 | 서버가 완성된 HTML을 반환하므로 JavaScript 불필요 |
| 데이터 추출 기준 | 목록은 URL 발견에만 사용하고 데이터는 상세 페이지에서 추출 |
| 선택자 방식 | CSS 선택자 |

Books to Scrape는 운영 주체가 웹 스크래핑 학습과 기술 검증을 위한 샌드박스로 소개하는 가상 서점이다. 분석일 현재 상품 1,000개, 페이지당 최대 20개, 페이지네이션 지원, JavaScript 불필요로 안내되어 있다.

## 2. 접근 정책

### 확인 결과

- 사이트 헤더는 `We love being scraped!`라고 안내한다.
- 상품 페이지에도 웹 스크래핑용 데모 사이트라는 경고가 표시된다.
- `https://books.toscrape.com/robots.txt` 요청은 분석일 현재 `404 Not Found`를 반환한다.
- HTML에는 `<meta name="robots" content="NOARCHIVE,NOCACHE">`가 있다.
- 로그인, CAPTCHA 또는 인증은 필요하지 않다.

### 적용 결정

`robots.txt`가 없다는 사실을 무제한 수집 허가로 해석하지 않는다. 다만 이 사이트는 공식적으로 스크래핑 연습용이라고 명시되어 있으므로 다음 제한을 지키며 실습을 진행한다.

- 허용 도메인은 `books.toscrape.com` 하나로 제한한다.
- 동시 요청은 1개, 요청 간격은 최소 1초로 설정한다.
- 전체 HTML 응답을 운영 데이터나 아카이브로 저장하지 않는다.
- 테스트에는 필요한 DOM만 남긴 최소 fixture를 사용한다.
- 차단, CAPTCHA 또는 명시적인 접근 거부가 새로 확인되면 실행을 중단한다.
- 이 판단은 Books to Scrape에만 적용하며 다른 사이트에 일반화하지 않는다.

구체적인 User-Agent와 재시도 대상 HTTP 상태는 3단계에서 정한다.

## 3. 페이지 구조

### 목록 페이지

시작 페이지와 이후 목록 페이지는 같은 상품 카드 구조를 사용한다.

```html
<article class="product_pod">
  <h3><a href="catalogue/example_1/index.html">Example</a></h3>
</article>
<ul class="pager">
  <li class="next"><a href="catalogue/page-2.html">next</a></li>
</ul>
```

목록 페이지의 책임은 두 가지뿐이다.

1. 각 `product_pod`에서 상품 상세 URL을 발견한다.
2. `next` 링크가 있으면 다음 목록 페이지를 요청한다.

목록에 표시된 제목, 가격, 재고와 평점은 저장 데이터로 사용하지 않는다. 모든 필드는 상세 페이지라는 하나의 출처에서 추출하여 페이지 간 불일치 가능성을 줄인다.

### 상세 페이지

상세 페이지는 다음 영역으로 구성된다.

- `.product_main`: 제목, 표시 가격, 재고 문구와 평점
- `#product_gallery`: 상품 이미지
- `.breadcrumb`: Home, Books, 카테고리, 현재 상품
- `#product_description + p`: 선택적인 상품 설명
- `table.table-striped`: UPC, 세전·세후 가격, 재고 등 상품 정보

상품 정보 표의 행 순서는 고정된 것으로 가정하지 않는다. 모든 `tr`을 CSS로 선택한 뒤 `th`를 키, `td`를 값으로 변환하여 `UPC`와 `Availability`를 이름으로 조회한다.

## 4. 선택자 설계

### 목록 페이지 선택자

| 목적 | CSS 선택자 | 예상 결과 | 필수 여부 |
|---|---|---|---|
| 상품 카드 | `article.product_pod` | 페이지의 상품 카드 목록 | 필수 |
| 상세 링크 | `article.product_pod h3 a::attr(href)` | 상대 상세 URL 목록 | 필수 |
| 다음 페이지 | `li.next a::attr(href)` | 상대 목록 URL 0개 또는 1개 | 선택 |
| 페이지 상태 | `li.current::text` | `Page 1 of 50` 형태의 문자열 | 필수 |

상품 카드가 0개이거나 페이지 상태를 찾을 수 없으면 목록 구조가 변경된 것으로 보고 전체 실행을 중단한다.

다음 링크가 없는 경우 페이지 상태의 현재 번호와 전체 번호가 같으면 정상 종료한다. 현재 번호가 전체 번호보다 작은데 다음 링크가 없다면 구조 이상으로 처리한다. 총 페이지 수 자체는 코드에 고정하지 않는다.

### 상세 페이지 선택자

| 필드 | CSS 선택자 또는 추출 규칙 | 필수 여부 |
|---|---|---|
| `title` | `article.product_page .product_main h1::text` | 필수 |
| `price_gbp` | `article.product_page .product_main p.price_color::text` | 필수 |
| 상품 정보 표 | `article.product_page table.table-striped tr`의 `th`, `td`를 키-값으로 변환 | 필수 |
| `upc` | 상품 정보 표에서 `UPC` 조회 | 필수 |
| `availability` | 상품 정보 표에서 `Availability` 조회 | 필수 |
| `stock_count` | `availability`에서 괄호 안 숫자 추출 | 필수 |
| `rating` | `.product_main p.star-rating::attr(class)`의 영문 등급을 1~5로 변환 | 필수 |
| `category` | `ul.breadcrumb li a::text` 중 현재 상품 바로 앞의 마지막 링크 | 필수 |
| `description` | `#product_description + p::text` | 선택 |
| `image_url` | `#product_gallery img::attr(src)` | 필수 |
| `product_url` | 정규화한 응답 URL | 필수 |
| `scraped_at` | 파싱 시점의 UTC 시각 생성 | 필수 |

선택자는 페이지 전체의 태그 순서보다 `product_page`, `product_main`, `product_description`처럼 의미가 드러나는 영역을 우선한다. 평점은 텍스트가 아니라 `star-rating Three`와 같은 클래스에 인코딩되어 있으므로 다음 매핑을 사용한다.

| 클래스 | 값 |
|---|---:|
| `One` | 1 |
| `Two` | 2 |
| `Three` | 3 |
| `Four` | 4 |
| `Five` | 5 |

알 수 없는 등급 클래스는 임의의 기본값으로 바꾸지 않고 필드 검증 실패로 처리한다.

## 5. URL 정규화

모든 링크는 현재 응답 URL을 기준으로 `urljoin`하여 절대 URL로 만든다.

- scheme과 host는 소문자로 정규화한다.
- `http` 링크는 대상 사이트의 `https` 주소로 정규화한다.
- fragment는 제거한다.
- 현재 수집에 의미가 없는 query string은 제거한다.
- 경로와 마지막 `/index.html`은 유지한다.
- 정규화 결과의 host가 허용 도메인과 다르면 요청하거나 저장하지 않는다.
- 중복 요청 판정과 `product_url` 저장에 같은 정규화 함수를 사용한다.

예시:

```text
입력:  ../../catalogue/a-light-in-the-attic_1000/index.html#reviews
기준:  https://books.toscrape.com/catalogue/page-2.html
결과:  https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html
```

## 6. 구조 이상과 실패 처리

| 상황 | 처리 |
|---|---|
| 목록의 상품 카드가 0개 | 전체 실행 중단 |
| 목록의 페이지 상태 누락 또는 형식 오류 | 전체 실행 중단 |
| 중간 페이지에서 다음 링크 누락 | 전체 실행 중단 |
| 상세 페이지의 필수 선택자 누락 | 해당 상품 실패 처리 후 다음 상품 계속 |
| 설명 누락 | `description = NULL`로 정상 처리 |
| 상품 정보 표의 필수 키 누락 | 해당 상품 실패 처리 |
| 허용 도메인 밖의 링크 | 요청하지 않고 경고 기록 |
| 알 수 없는 평점 클래스 | 해당 상품 실패 처리 |
| URL 정규화 실패 | 요청 또는 저장하지 않고 실패 기록 |

개별 상세 페이지 실패가 하나라도 있으면 크롤링은 가능한 범위까지 계속하되, 최종 실행 상태는 성공이 아닌 부분 실패로 표시한다.

## 7. 테스트 fixture

실제 페이지 전체를 복제하지 않고 선택자 검증에 필요한 최소 DOM만 보관한다.

| 파일 | 검증 목적 |
|---|---|
| `tests/fixtures/list_page.html` | 상품 상세 링크와 다음 페이지 추출 |
| `tests/fixtures/product_with_description.html` | 모든 필수 필드와 설명 추출 |
| `tests/fixtures/product_without_description.html` | 선택 필드인 설명 누락 처리 |

fixture의 내용은 실제 사이트 구조를 단순화한 테스트 전용 예시이며, 실제 상품 설명과 이미지 파일은 복제하지 않는다.

## 8. 변경 위험

| 위험 | 영향 | 대응 |
|---|---|---|
| `product_pod` 또는 `product_page` 클래스 변경 | 페이지 유형 인식 실패 | 카드 수와 필수 선택자 검증으로 즉시 감지 |
| 다음 페이지 클래스 변경 | 일부 페이지만 수집 | 페이지 상태와 다음 링크를 함께 검증 |
| 상품 정보 표의 행 순서 변경 | 잘못된 필드 매핑 | 행 번호 대신 `th` 텍스트로 조회 |
| 평점 클래스 표현 변경 | 평점 누락 또는 오해 | 허용된 다섯 클래스만 명시적으로 변환 |
| breadcrumb 구조 변경 | 카테고리 오추출 | 링크 개수와 마지막 링크 값을 검증 |
| 설명 영역 제거 | 영향 없음 | 유일한 선택 필드로 `NULL` 허용 |
| 상대 URL 깊이 변경 | 잘못된 주소 생성 | 문자열 연결 대신 응답 기준 `urljoin` 사용 |
| 사이트 정책 변경 | 허용되지 않은 접근 | 실행 전 정책 확인 및 명시적 거부 시 중단 |

## 9. 2단계 완료 확인

- [x] 사이트의 학습 목적과 접근 정책을 확인했다.
- [x] `robots.txt`의 404 응답과 적용 방침을 기록했다.
- [x] 목록과 상세 페이지의 책임을 분리했다.
- [x] 필드별 CSS 선택자와 변환 규칙을 정했다.
- [x] URL 정규화 규칙을 정했다.
- [x] 정상 종료와 구조 이상을 구분하는 기준을 정했다.
- [x] 대표 fixture 3개의 범위를 정했다.
- [x] 예상되는 구조 변경 위험과 대응을 기록했다.
