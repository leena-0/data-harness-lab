"""Tests for product parsing and item validation."""

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
import unittest

from scrapy.http import HtmlResponse

from web_scraper_lab.items import BookValidationError, build_book_item
from web_scraper_lab.spiders.books import BooksSpider


FIXTURES = Path(__file__).parent / "fixtures"


class RecordingStats:
    def __init__(self) -> None:
        self.values: dict[str, int] = {}

    def inc_value(self, key: str, count: int = 1, start: int = 0) -> None:
        self.values[key] = self.values.get(key, start) + count


class ProductParserTest(unittest.TestCase):
    def setUp(self) -> None:
        self.stats = RecordingStats()
        self.spider = BooksSpider()
        self.spider.crawler = SimpleNamespace(stats=self.stats)

    def response(self, fixture_name: str) -> HtmlResponse:
        return HtmlResponse(
            url="https://books.toscrape.com/catalogue/example-book_1/index.html",
            body=(FIXTURES / fixture_name).read_bytes(),
            encoding="utf-8",
        )

    def test_extracts_and_normalizes_all_fields(self) -> None:
        items = list(
            self.spider.parse_product(
                self.response("product_with_description.html")
            )
        )

        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item["upc"], "fixture-upc-001")
        self.assertEqual(item["title"], "Example Book")
        self.assertEqual(item["price_gbp"], "12.34")
        self.assertEqual(item["availability"], "In stock (7 available)")
        self.assertEqual(item["stock_count"], 7)
        self.assertEqual(item["rating"], 4)
        self.assertEqual(item["category"], "Testing")
        self.assertEqual(
            item["description"],
            "A synthetic description used only by the parser test.",
        )
        self.assertEqual(
            item["image_url"],
            "https://books.toscrape.com/media/cache/example.jpg",
        )
        self.assertEqual(
            item["product_url"],
            "https://books.toscrape.com/catalogue/example-book_1/index.html",
        )
        self.assertIsNotNone(datetime.fromisoformat(item["scraped_at"]).tzinfo)
        self.assertEqual(self.stats.values["books/detail_items_parsed"], 1)

    def test_allows_missing_description(self) -> None:
        items = list(
            self.spider.parse_product(
                self.response("product_without_description.html")
            )
        )

        self.assertEqual(len(items), 1)
        self.assertIsNone(items[0]["description"])

    def test_rejects_missing_required_field(self) -> None:
        items = list(
            self.spider.parse_product(self.response("product_missing_upc.html"))
        )

        self.assertEqual(items, [])
        self.assertEqual(self.stats.values["books/detail_parse_failures"], 1)


class BookItemValidationTest(unittest.TestCase):
    def test_rejects_unknown_rating(self) -> None:
        with self.assertRaisesRegex(BookValidationError, "rating"):
            build_book_item(
                upc="fixture-upc-003",
                title="Invalid Rating",
                price_gbp="£1.00",
                availability="Out of stock",
                rating_classes="star-rating Six",
                category="Testing",
                description=None,
                image_url="https://books.toscrape.com/image.jpg",
                product_url="https://books.toscrape.com/book.html",
            )

    def test_rejects_price_with_too_many_decimal_places(self) -> None:
        with self.assertRaisesRegex(BookValidationError, "price_gbp"):
            build_book_item(
                upc="fixture-upc-004",
                title="Invalid Price",
                price_gbp="£1.001",
                availability="In stock (1 available)",
                rating_classes="star-rating One",
                category="Testing",
                description=None,
                image_url="https://books.toscrape.com/image.jpg",
                product_url="https://books.toscrape.com/book.html",
            )


if __name__ == "__main__":
    unittest.main()
