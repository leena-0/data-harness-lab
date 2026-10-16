"""Tests for bounded retry backoff without real waiting or network access."""

from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from scrapy import Request
from scrapy.http import Response
from scrapy.settings import Settings
from twisted.internet.error import TimeoutError

from web_scraper_lab.middlewares import ExponentialBackoffRetryMiddleware
from web_scraper_lab.spiders.books import BooksSpider


class RecordingStats:
    def __init__(self) -> None:
        self.values: dict[str, int] = {}

    def inc_value(self, key: str, count: int = 1, start: int = 0) -> None:
        self.values[key] = self.values.get(key, start) + count


class RetryMiddlewareTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        settings = Settings()
        settings.setmodule("web_scraper_lab.settings")
        self.stats = RecordingStats()
        self.crawler = SimpleNamespace(settings=settings, stats=self.stats)
        self.spider = BooksSpider()
        self.spider.crawler = self.crawler
        self.crawler.spider = self.spider
        self.middleware = ExponentialBackoffRetryMiddleware.from_crawler(
            self.crawler
        )

    async def test_retries_server_error_with_exponential_delay(self) -> None:
        request = Request("https://books.toscrape.com/")
        response = Response(request.url, status=500, request=request)

        with patch(
            "web_scraper_lab.middlewares.asyncio.sleep",
            new_callable=AsyncMock,
        ) as sleep:
            result = await self.middleware.process_response(request, response)

        self.assertIsInstance(result, Request)
        self.assertEqual(result.meta["retry_times"], 1)
        sleep.assert_awaited_once_with(1.0)
        self.assertEqual(self.stats.values["books/retry_count"], 1)

    async def test_retry_after_header_takes_priority(self) -> None:
        request = Request("https://books.toscrape.com/")
        response = Response(
            request.url,
            status=429,
            headers={"Retry-After": "7"},
            request=request,
        )

        with patch(
            "web_scraper_lab.middlewares.asyncio.sleep",
            new_callable=AsyncMock,
        ) as sleep:
            await self.middleware.process_response(request, response)

        sleep.assert_awaited_once_with(7.0)

    async def test_network_timeout_is_retried(self) -> None:
        request = Request("https://books.toscrape.com/")

        with patch(
            "web_scraper_lab.middlewares.asyncio.sleep",
            new_callable=AsyncMock,
        ) as sleep:
            result = await self.middleware.process_exception(
                request,
                TimeoutError(),
            )

        self.assertIsInstance(result, Request)
        sleep.assert_awaited_once_with(1.0)

    async def test_backoff_is_capped_at_configured_maximum(self) -> None:
        retry_request = Request(
            "https://books.toscrape.com/",
            meta={"retry_times": 8},
        )

        with patch(
            "web_scraper_lab.middlewares.asyncio.sleep",
            new_callable=AsyncMock,
        ) as sleep:
            await self.middleware._wait_before_retry(retry_request)

        sleep.assert_awaited_once_with(60.0)

    async def test_success_response_is_not_retried(self) -> None:
        request = Request("https://books.toscrape.com/")
        response = Response(request.url, status=200, request=request)

        with patch(
            "web_scraper_lab.middlewares.asyncio.sleep",
            new_callable=AsyncMock,
        ) as sleep:
            result = await self.middleware.process_response(request, response)

        self.assertIs(result, response)
        sleep.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
