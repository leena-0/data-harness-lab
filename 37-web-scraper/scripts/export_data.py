"""Export stored books from SQLite to a deterministic CSV file."""

import argparse
from contextlib import closing
import csv
import os
from pathlib import Path
import sqlite3
import tempfile


COLUMNS = (
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


def export_books(database_path: Path, output_path: Path) -> int:
    """Write all books ordered by UPC and atomically replace the CSV output."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None

    try:
        with closing(sqlite3.connect(database_path)) as connection:
            rows = connection.execute(
                f"SELECT {', '.join(COLUMNS)} FROM books ORDER BY upc"
            ).fetchall()

        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=output_path.parent,
            prefix=f".{output_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            writer = csv.writer(temporary_file)
            writer.writerow(COLUMNS)
            writer.writerows(rows)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())

        os.replace(temporary_path, output_path)
        return len(rows)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def parse_args() -> argparse.Namespace:
    project_dir = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database",
        type=Path,
        default=project_dir / "data" / "processed" / "books.db",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=project_dir / "data" / "processed" / "books.csv",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    exported_count = export_books(args.database, args.output)
    print(f"Exported {exported_count} books to {args.output}")


if __name__ == "__main__":
    main()
