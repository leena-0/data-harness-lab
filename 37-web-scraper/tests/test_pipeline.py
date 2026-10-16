"""Tests for SQLite persistence and CSV export."""

import csv
import importlib.util
from pathlib import Path
import sqlite3
import tempfile
import unittest

from web_scraper_lab.items import BookItem
from web_scraper_lab.pipelines import BOOK_COLUMNS, SQLiteBookPipeline


PROJECT_DIR = Path(__file__).resolve().parents[1]
EXPORT_MODULE_SPEC = importlib.util.spec_from_file_location(
    "export_data",
    PROJECT_DIR / "scripts" / "export_data.py",
)
if EXPORT_MODULE_SPEC is None or EXPORT_MODULE_SPEC.loader is None:
    raise RuntimeError("Could not load export_data.py")
EXPORT_MODULE = importlib.util.module_from_spec(EXPORT_MODULE_SPEC)
EXPORT_MODULE_SPEC.loader.exec_module(EXPORT_MODULE)
export_books = EXPORT_MODULE.export_books


class RecordingStats:
    def __init__(self) -> None:
        self.values: dict[str, int] = {}

    def inc_value(self, key: str, count: int = 1, start: int = 0) -> None:
        self.values[key] = self.values.get(key, start) + count


def make_book(upc: str, *, title: str = "A Light in the Attic") -> BookItem:
    return BookItem(
        upc=upc,
        title=title,
        price_gbp="51.77",
        availability="In stock (22 available)",
        stock_count=22,
        rating=3,
        category="Poetry",
        description=None,
        image_url="https://books.toscrape.com/media/example.jpg",
        product_url=f"https://books.toscrape.com/catalogue/{upc}.html",
        scraped_at="2026-10-14T00:00:00+00:00",
    )


class SQLiteBookPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "books.db"
        self.stats = RecordingStats()
        self.pipeline = SQLiteBookPipeline(
            self.database_path,
            batch_size=2,
            stats=self.stats,
        )
        self.pipeline.open_spider()

    def tearDown(self) -> None:
        self.pipeline.close_spider()
        self.temporary_directory.cleanup()

    def rows(self) -> list[tuple]:
        connection = self.pipeline._require_connection()
        return connection.execute(
            "SELECT upc, title FROM books ORDER BY upc"
        ).fetchall()

    def test_creates_schema_and_inserts_book(self) -> None:
        self.pipeline.process_item(make_book("upc-1"))
        self.assertEqual(self.rows(), [("upc-1", "A Light in the Attic")])

    def test_counts_only_items_in_successful_commits(self) -> None:
        self.pipeline.process_item(make_book("upc-1"))
        self.assertNotIn("books/db_items_stored", self.stats.values)

        self.pipeline.process_item(make_book("upc-2"))
        self.assertEqual(self.stats.values["books/db_items_stored"], 2)

    def test_upserts_same_upc_and_keeps_other_books(self) -> None:
        self.pipeline.process_item(make_book("upc-1"))
        self.pipeline.process_item(make_book("upc-1", title="Updated title"))
        self.pipeline.process_item(make_book("upc-2", title="Second book"))

        self.assertEqual(
            self.rows(),
            [("upc-1", "Updated title"), ("upc-2", "Second book")],
        )

    def test_database_constraints_reject_invalid_rating(self) -> None:
        invalid_book = make_book("invalid-rating")
        invalid_book["rating"] = 6

        with self.assertRaises(sqlite3.IntegrityError):
            self.pipeline.process_item(invalid_book)

        self.assertEqual(self.rows(), [])

    def test_failed_batch_rolls_back_but_keeps_previous_commit(self) -> None:
        self.pipeline.process_item(make_book("committed-1"))
        self.pipeline.process_item(make_book("committed-2"))
        self.pipeline.process_item(make_book("rolled-back"))
        invalid_book = make_book("invalid-stock")
        invalid_book["stock_count"] = -1

        with self.assertRaises(sqlite3.IntegrityError):
            self.pipeline.process_item(invalid_book)

        self.assertEqual(
            self.rows(),
            [
                ("committed-1", "A Light in the Attic"),
                ("committed-2", "A Light in the Attic"),
            ],
        )


class ExportBooksTests(unittest.TestCase):
    def test_exports_header_and_rows_sorted_by_upc(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            database_path = directory / "books.db"
            output_path = directory / "books.csv"
            pipeline = SQLiteBookPipeline(database_path)
            pipeline.open_spider()
            pipeline.process_item(make_book("upc-b", title="Second"))
            pipeline.process_item(make_book("upc-a", title="First"))
            pipeline.close_spider()

            exported_count = export_books(database_path, output_path)

            with output_path.open(encoding="utf-8", newline="") as csv_file:
                rows = list(csv.reader(csv_file))

            self.assertEqual(exported_count, 2)
            self.assertEqual(rows[0], list(BOOK_COLUMNS))
            self.assertEqual([row[0] for row in rows[1:]], ["upc-a", "upc-b"])
            self.assertEqual([row[1] for row in rows[1:]], ["First", "Second"])


if __name__ == "__main__":
    unittest.main()
