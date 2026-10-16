"""Tests for listing traversal and crawl stop policies."""

from pathlib import Path
from types import SimpleNamespace
import unittest

from scrapy import Request
from scrapy.exceptions import CloseSpider
from scrapy.http import HtmlResponse

from web_scraper_lab.spiders.books import BooksSpider


FIXTURES = Path(__file__).parent / "fixtures"


class RecordingStats:
    def __init__(self) -> None:
        self.values: dict[str, int] = {}

    def inc_value(self, key: str, count: int = 1, start: int = 0) -> None:
        self.values[key] = self.values.get(key, start) + count


class ListingCrawlerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.stats = RecordingStats()
        self.spider = BooksSpider()
        self.spider.crawler = SimpleNamespace(stats=self.stats)

    def response(
        self,
        body: bytes,
        *,
        status: int = 200,
        url: str = "https://books.toscrape.com/",
    ) -> HtmlResponse:
        return HtmlResponse(
            url=url,
            status=status,
            body=body,
            encoding="utf-8",
        )

    def test_schedules_details_and_next_listing_page(self) -> None:
        response = self.response((FIXTURES / "list_page.html").read_bytes())

        requests = list(self.spider.parse_listing(response))

        self.assertEqual(
            [request.url for request in requests],
            [
                "https://books.toscrape.com/catalogue/example-book_1/index.html",
                "https://books.toscrape.com/catalogue/another-book_2/index.html",
                "https://books.toscrape.com/catalogue/page-2.html",
            ],
        )
        self.assertEqual(
            [request.meta["page_kind"] for request in requests],
            ["detail", "detail", "listing"],
        )
        self.assertEqual(self.stats.values["books/detail_requests_scheduled"], 2)

    def test_skips_offsite_product_link(self) -> None:
        response = self.response(
            b"""
            <article class="product_pod">
              <h3><a href="https://example.com/book.html">Book</a></h3>
            </article>
            <li class="current">Page 1 of 1</li>
            """
        )

        self.assertEqual(list(self.spider.parse_listing(response)), [])
        self.assertEqual(self.stats.values["books/offsite_links_skipped"], 1)

    def test_stops_when_listing_products_are_missing(self) -> None:
        response = self.response(b'<li class="current">Page 1 of 1</li>')

        with self.assertRaises(CloseSpider) as raised:
            list(self.spider.parse_listing(response))
        self.assertEqual(raised.exception.reason, "listing_products_missing")

    def test_stops_when_page_status_is_missing(self) -> None:
        response = self.response(
            b"""
            <article class="product_pod">
              <h3><a href="catalogue/book.html">Book</a></h3>
            </article>
            """
        )

        with self.assertRaises(CloseSpider) as raised:
            list(self.spider.parse_listing(response))
        self.assertEqual(raised.exception.reason, "listing_page_status_missing")

    def test_stops_when_next_link_is_missing(self) -> None:
        response = self.response(
            b"""
            <article class="product_pod">
              <h3><a href="catalogue/book.html">Book</a></h3>
            </article>
            <li class="current">Page 1 of 2</li>
            """
        )

        with self.assertRaises(CloseSpider) as raised:
            list(self.spider.parse_listing(response))
        self.assertEqual(raised.exception.reason, "listing_next_link_missing")

    def test_stops_on_access_denial(self) -> None:
        for status in (401, 403, 429):
            with self.subTest(status=status):
                response = self.response(b"denied", status=status)

                with self.assertRaises(CloseSpider) as raised:
                    list(self.spider.parse_listing(response))
                self.assertEqual(
                    raised.exception.reason,
                    f"access_denied_{status}",
                )

    def test_detail_request_failure_is_isolated(self) -> None:
        failure = SimpleNamespace(
            request=Request(
                "https://books.toscrape.com/catalogue/book.html",
                meta={"page_kind": "detail"},
            ),
            getErrorMessage=lambda: "timeout",
        )

        self.assertIsNone(self.spider.handle_request_error(failure))
        self.assertEqual(self.stats.values["books/detail_request_failures"], 1)

    def test_listing_request_failure_stops_crawl(self) -> None:
        failure = SimpleNamespace(
            request=Request(
                "https://books.toscrape.com/catalogue/page-2.html",
                meta={"page_kind": "listing"},
            ),
            getErrorMessage=lambda: "timeout",
        )

        with self.assertRaises(CloseSpider) as raised:
            self.spider.handle_request_error(failure)
        self.assertEqual(raised.exception.reason, "listing_request_failed")


if __name__ == "__main__":
    unittest.main()
