"""Crawl quality checks and an atomic JSON run summary."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from scrapy import signals


MONITORED_STATS = (
    "books/listing_pages_seen",
    "books/detail_requests_scheduled",
    "books/detail_pages_seen",
    "books/detail_items_parsed",
    "books/detail_parse_failures",
    "books/detail_request_failures",
    "books/listing_request_failures",
    "books/retry_count",
    "books/offsite_links_skipped",
    "books/db_items_stored",
)


class CrawlMonitorExtension:
    """Evaluate crawl quality and persist a compact end-of-run summary."""

    def __init__(
        self,
        crawler: Any,
        output_path: str | Path,
        minimum_success_rate: float,
    ) -> None:
        self.crawler = crawler
        self.output_path = Path(output_path)
        self.minimum_success_rate = minimum_success_rate
        self.started_at: datetime | None = None

    @classmethod
    def from_crawler(cls, crawler: Any) -> "CrawlMonitorExtension":
        extension = cls(
            crawler,
            crawler.settings["CRAWL_STATS_PATH"],
            crawler.settings.getfloat("MIN_PARSE_SUCCESS_RATE", 0.95),
        )
        crawler.signals.connect(extension.spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(extension.spider_closed, signal=signals.spider_closed)
        return extension

    def spider_opened(self, spider: Any) -> None:
        self.started_at = datetime.now(timezone.utc)

    def spider_closed(self, spider: Any, reason: str) -> None:
        summary = self.build_summary(reason)
        quality = summary["quality_gate"]

        if quality["passed"]:
            spider.logger.info(
                "Crawl quality passed: %d parsed, %.1f%% success",
                summary["stats"]["books/detail_items_parsed"],
                quality["parse_success_rate"] * 100,
            )
        else:
            spider.logger.error(
                "Crawl quality failed: %s",
                "; ".join(quality["reasons"]),
            )

        self._write_json(summary)
        spider.logger.info("Crawl summary written to %s", self.output_path)

    def build_summary(self, reason: str) -> dict[str, Any]:
        stats = {
            key: int(self.crawler.stats.get_value(key, 0))
            for key in MONITORED_STATS
        }
        parsed = stats["books/detail_items_parsed"]
        parse_failures = stats["books/detail_parse_failures"]
        attempted = parsed + parse_failures
        success_rate = parsed / attempted if attempted else 0.0

        failure_reasons: list[str] = []
        if attempted == 0:
            failure_reasons.append("no detail pages were parsed")
        elif success_rate < self.minimum_success_rate:
            failure_reasons.append(
                f"parse success rate {success_rate:.1%} is below "
                f"{self.minimum_success_rate:.1%}"
            )

        quality_passed = not failure_reasons
        self.crawler.stats.set_value(
            "books/quality_gate_failed",
            int(not quality_passed),
        )

        finished_at = datetime.now(timezone.utc)
        started_at = self.started_at or finished_at
        return {
            "spider": "books",
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "finish_reason": reason,
            "quality_gate": {
                "passed": quality_passed,
                "minimum_parse_success_rate": self.minimum_success_rate,
                "parse_success_rate": success_rate,
                "reasons": failure_reasons,
            },
            "stats": stats,
        }

    def _write_json(self, summary: dict[str, Any]) -> None:
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.output_path.parent,
                prefix=f".{self.output_path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                json.dump(summary, temporary_file, ensure_ascii=False, indent=2)
                temporary_file.write("\n")
                temporary_file.flush()
                os.fsync(temporary_file.fileno())

            os.replace(temporary_path, self.output_path)
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()
