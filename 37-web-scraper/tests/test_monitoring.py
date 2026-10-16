"""Tests for crawl quality evaluation and summary persistence."""

from datetime import datetime, timezone
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from web_scraper_lab.extensions import CrawlMonitorExtension
from web_scraper_lab.spiders.books import BooksSpider


class RecordingStats:
    def __init__(self, values: dict[str, int] | None = None) -> None:
        self.values = values or {}

    def get_value(self, key: str, default: int = 0) -> int:
        return self.values.get(key, default)

    def set_value(self, key: str, value: int) -> None:
        self.values[key] = value


class CrawlMonitorTests(unittest.TestCase):
    def make_monitor(
        self,
        output_path: Path,
        *,
        parsed: int,
        failures: int,
    ) -> tuple[CrawlMonitorExtension, RecordingStats]:
        stats = RecordingStats(
            {
                "books/detail_items_parsed": parsed,
                "books/detail_parse_failures": failures,
            }
        )
        crawler = SimpleNamespace(stats=stats)
        monitor = CrawlMonitorExtension(crawler, output_path, 0.95)
        monitor.started_at = datetime(2026, 10, 16, tzinfo=timezone.utc)
        return monitor, stats

    def test_writes_passing_summary_as_json(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_path = Path(temporary_directory) / "crawl-stats.json"
            monitor, stats = self.make_monitor(
                output_path,
                parsed=95,
                failures=5,
            )
            spider = BooksSpider()

            monitor.spider_closed(spider, "finished")

            summary = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertTrue(summary["quality_gate"]["passed"])
            self.assertEqual(summary["quality_gate"]["parse_success_rate"], 0.95)
            self.assertEqual(summary["finish_reason"], "finished")
            self.assertEqual(stats.values["books/quality_gate_failed"], 0)

    def test_marks_below_threshold_as_failed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_path = Path(temporary_directory) / "crawl-stats.json"
            monitor, stats = self.make_monitor(
                output_path,
                parsed=94,
                failures=6,
            )

            summary = monitor.build_summary("finished")

            self.assertFalse(summary["quality_gate"]["passed"])
            self.assertIn("below 95.0%", summary["quality_gate"]["reasons"][0])
            self.assertEqual(stats.values["books/quality_gate_failed"], 1)

    def test_marks_zero_parsed_pages_as_failed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_path = Path(temporary_directory) / "crawl-stats.json"
            monitor, _ = self.make_monitor(
                output_path,
                parsed=0,
                failures=0,
            )

            summary = monitor.build_summary("finished")

            self.assertFalse(summary["quality_gate"]["passed"])
            self.assertEqual(
                summary["quality_gate"]["reasons"],
                ["no detail pages were parsed"],
            )


if __name__ == "__main__":
    unittest.main()
