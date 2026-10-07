"""Crawl listing pages and schedule every discovered book detail page."""

from collections.abc import AsyncIterator, Callable, Iterable
import re
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

import scrapy
from scrapy import Request
from scrapy.exceptions import CloseSpider
from scrapy.http import Response


class BooksSpider(scrapy.Spider):
    """Traverse the complete Books to Scrape catalogue."""

    name = "books"
    allowed_domains = ["books.toscrape.com"]
    start_urls = ["https://books.toscrape.com/"]
    handle_httpstatus_list = [401, 403, 429]

    async def start(self) -> AsyncIterator[Request]:
        """Schedule the first listing page with the shared request policy."""
        for url in self.start_urls:
            yield self._request(
                url,
                callback=self.parse_listing,
                page_kind="listing",
            )

    def parse_listing(self, response: Response) -> Iterable[Request]:
        """Schedule every product detail and advance to the next listing."""
        self._raise_for_access_denial(response)
        self.crawler.stats.inc_value("books/listing_pages_seen")

        cards = response.css("article.product_pod")
        if not cards:
            raise CloseSpider("listing_products_missing")

        current_page, total_pages = self._parse_page_status(response)
        product_hrefs = response.css(
            "article.product_pod h3 a::attr(href)"
        ).getall()
        if len(product_hrefs) != len(cards):
            raise CloseSpider("listing_product_links_incomplete")

        for href in product_hrefs:
            product_url = self._normalize_url(response.url, href)
            if product_url is None:
                self.crawler.stats.inc_value("books/offsite_links_skipped")
                self.logger.warning("Skipping invalid or offsite product URL: %s", href)
                continue

            self.crawler.stats.inc_value("books/detail_requests_scheduled")
            yield self._request(
                product_url,
                callback=self.parse_product,
                page_kind="detail",
            )

        next_href = response.css("li.next a::attr(href)").get()
        if current_page < total_pages:
            if next_href is None:
                raise CloseSpider("listing_next_link_missing")

            next_url = self._normalize_url(response.url, next_href)
            if next_url is None:
                raise CloseSpider("listing_next_link_invalid")

            yield self._request(
                next_url,
                callback=self.parse_listing,
                page_kind="listing",
            )
        elif next_href is not None:
            raise CloseSpider("listing_unexpected_next_link")

    def parse_product(self, response: Response) -> None:
        """Count a fetched detail page; stage 4 will extract its fields."""
        self._raise_for_access_denial(response)
        self.crawler.stats.inc_value("books/detail_pages_seen")

    def handle_request_error(self, failure: Any) -> None:
        """Stop on listing failures and record isolated detail failures."""
        request = failure.request
        page_kind = request.meta.get("page_kind", "unknown")
        self.crawler.stats.inc_value(f"books/{page_kind}_request_failures")
        self.logger.error(
            "%s request failed after retries: %s (%s)",
            page_kind,
            request.url,
            failure.getErrorMessage(),
        )
        if page_kind == "listing":
            raise CloseSpider("listing_request_failed")

    def _request(
        self,
        url: str,
        *,
        callback: Callable[[Response], Any],
        page_kind: str,
    ) -> Request:
        return Request(
            url,
            callback=callback,
            errback=self.handle_request_error,
            meta={"page_kind": page_kind},
        )

    def _raise_for_access_denial(self, response: Response) -> None:
        if response.status in self.handle_httpstatus_list:
            raise CloseSpider(f"access_denied_{response.status}")

    @staticmethod
    def _parse_page_status(response: Response) -> tuple[int, int]:
        page_status = response.css("li.current::text").get()
        if page_status is None:
            raise CloseSpider("listing_page_status_missing")

        match = re.fullmatch(r"\s*Page\s+(\d+)\s+of\s+(\d+)\s*", page_status)
        if match is None:
            raise CloseSpider("listing_page_status_invalid")

        current_page, total_pages = map(int, match.groups())
        if current_page < 1 or total_pages < 1 or current_page > total_pages:
            raise CloseSpider("listing_page_status_invalid")

        return current_page, total_pages

    @classmethod
    def _normalize_url(cls, base_url: str, href: str) -> str | None:
        if not href or not href.strip():
            return None

        try:
            parsed = urlsplit(urljoin(base_url, href.strip()))
            port = parsed.port
        except ValueError:
            return None

        hostname = (parsed.hostname or "").lower()
        if parsed.scheme.lower() not in {"http", "https"}:
            return None
        if hostname not in cls.allowed_domains:
            return None
        if parsed.username is not None or parsed.password is not None:
            return None
        if port not in {None, 443}:
            return None

        return urlunsplit(("https", hostname, parsed.path or "/", "", ""))
