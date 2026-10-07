"""Downloader middleware used by the web scraper lab."""

import asyncio
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

from scrapy import Request
from scrapy.downloadermiddlewares.retry import RetryMiddleware
from scrapy.http import Response


class ExponentialBackoffRetryMiddleware(RetryMiddleware):
    """Apply a bounded delay before Scrapy reschedules retry requests."""

    @classmethod
    def from_crawler(cls, crawler: Any) -> "ExponentialBackoffRetryMiddleware":
        middleware = super().from_crawler(crawler)
        middleware.backoff_base = crawler.settings.getfloat("RETRY_BACKOFF_BASE")
        middleware.backoff_max = crawler.settings.getfloat("RETRY_BACKOFF_MAX")
        return middleware

    async def process_response(
        self,
        request: Request,
        response: Response,
    ) -> Request | Response:
        result = super().process_response(request, response)
        if isinstance(result, Request):
            retry_after = self._retry_after_seconds(response)
            await self._wait_before_retry(result, retry_after=retry_after)
        return result

    async def process_exception(
        self,
        request: Request,
        exception: Exception,
    ) -> Request | Response | None:
        result = super().process_exception(request, exception)
        if isinstance(result, Request):
            await self._wait_before_retry(result)
        return result

    async def _wait_before_retry(
        self,
        retry_request: Request,
        *,
        retry_after: float | None = None,
    ) -> None:
        retry_times = retry_request.meta.get("retry_times", 1)
        exponential_delay = min(
            self.backoff_base * (2 ** (retry_times - 1)),
            self.backoff_max,
        )
        delay = max(exponential_delay, retry_after or 0.0)

        self.crawler.stats.inc_value("books/retry_count")
        self.crawler.spider.logger.info(
            "Retrying %s in %.1f seconds (attempt %d)",
            retry_request.url,
            delay,
            retry_times,
        )
        await asyncio.sleep(delay)

    @staticmethod
    def _retry_after_seconds(response: Response) -> float | None:
        raw_value = response.headers.get("Retry-After")
        if raw_value is None:
            return None

        value = raw_value.decode("ascii", errors="ignore").strip()
        if value.isdigit():
            return float(value)

        try:
            retry_at = parsedate_to_datetime(value)
        except (TypeError, ValueError, OverflowError):
            return None

        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=timezone.utc)
        remaining = (retry_at - datetime.now(timezone.utc)).total_seconds()
        return max(0.0, remaining)
