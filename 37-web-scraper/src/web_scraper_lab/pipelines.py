"""Persist validated book items to SQLite."""

from pathlib import Path
import sqlite3
from typing import Any

from itemadapter import ItemAdapter


BOOK_COLUMNS = (
    "upc",
    "title",
    "price_gbp",
    "availability",
    "stock_count",
    "rating",
    "category",
    "description",
    "image_url",
    "product_url",
    "scraped_at",
)

CREATE_BOOKS_TABLE = """
CREATE TABLE IF NOT EXISTS books (
    upc TEXT PRIMARY KEY CHECK (length(trim(upc)) > 0),
    title TEXT NOT NULL CHECK (length(trim(title)) > 0),
    price_gbp TEXT NOT NULL CHECK (price_gbp GLOB '[0-9]*.[0-9][0-9]'),
    availability TEXT NOT NULL CHECK (length(trim(availability)) > 0),
    stock_count INTEGER NOT NULL CHECK (stock_count >= 0),
    rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    category TEXT NOT NULL CHECK (length(trim(category)) > 0),
    description TEXT,
    image_url TEXT NOT NULL CHECK (image_url LIKE 'https://%'),
    product_url TEXT NOT NULL CHECK (product_url LIKE 'https://%'),
    scraped_at TEXT NOT NULL CHECK (length(trim(scraped_at)) > 0)
)
"""

UPSERT_BOOK = """
INSERT INTO books (
    upc, title, price_gbp, availability, stock_count, rating,
    category, description, image_url, product_url, scraped_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(upc) DO UPDATE SET
    title = excluded.title,
    price_gbp = excluded.price_gbp,
    availability = excluded.availability,
    stock_count = excluded.stock_count,
    rating = excluded.rating,
    category = excluded.category,
    description = excluded.description,
    image_url = excluded.image_url,
    product_url = excluded.product_url,
    scraped_at = excluded.scraped_at
"""


class SQLiteBookPipeline:
    """Upsert books by UPC and commit them in bounded batches."""

    def __init__(
        self,
        database_path: str | Path,
        batch_size: int = 100,
        stats: Any = None,
    ) -> None:
        self.database_path = Path(database_path)
        self.batch_size = batch_size
        self.stats = stats
        self.connection: sqlite3.Connection | None = None
        self.pending_items = 0

    @classmethod
    def from_crawler(cls, crawler: Any) -> "SQLiteBookPipeline":
        return cls(
            crawler.settings["BOOKS_DB_PATH"],
            crawler.settings.getint("SQLITE_COMMIT_BATCH_SIZE", 100),
            crawler.stats,
        )

    def open_spider(self, spider: Any = None) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.database_path)
        self.connection.execute(CREATE_BOOKS_TABLE)
        self.connection.commit()

    def process_item(self, item: Any, spider: Any = None) -> Any:
        connection = self._require_connection()
        values = ItemAdapter(item).asdict()

        try:
            connection.execute(
                UPSERT_BOOK,
                tuple(values[column] for column in BOOK_COLUMNS),
            )
            self.pending_items += 1
            if self.pending_items >= self.batch_size:
                self._commit_pending()
        except (KeyError, sqlite3.DatabaseError):
            connection.rollback()
            self.pending_items = 0
            raise

        return item

    def close_spider(self, spider: Any = None) -> None:
        if self.connection is None:
            return
        try:
            self._commit_pending()
        finally:
            self.connection.close()
            self.connection = None
            self.pending_items = 0

    def _require_connection(self) -> sqlite3.Connection:
        if self.connection is None:
            raise RuntimeError("SQLite pipeline is not open")
        return self.connection

    def _commit_pending(self) -> None:
        if self.pending_items == 0:
            return
        connection = self._require_connection()
        connection.commit()
        if self.stats is not None:
            self.stats.inc_value("books/db_items_stored", self.pending_items)
        self.pending_items = 0
