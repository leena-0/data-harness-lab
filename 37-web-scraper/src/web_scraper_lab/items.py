"""Item schema and validation helpers for scraped books."""

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import re
from urllib.parse import urlsplit

import scrapy


class BookValidationError(ValueError):
    """Raised when a scraped field does not satisfy the item contract."""

    def __init__(self, field: str, reason: str) -> None:
        self.field = field
        self.reason = reason
        super().__init__(f"{field}: {reason}")


class BookItem(scrapy.Item):
    """Validated representation of one Books to Scrape product."""

    upc = scrapy.Field()
    title = scrapy.Field()
    price_gbp = scrapy.Field()
    availability = scrapy.Field()
    stock_count = scrapy.Field()
    rating = scrapy.Field()
    category = scrapy.Field()
    description = scrapy.Field()
    image_url = scrapy.Field()
    product_url = scrapy.Field()
    scraped_at = scrapy.Field()


RATING_VALUES = {
    "One": 1,
    "Two": 2,
    "Three": 3,
    "Four": 4,
    "Five": 5,
}


def build_book_item(
    *,
    upc: str | None,
    title: str | None,
    price_gbp: str | None,
    availability: str | None,
    rating_classes: str | None,
    category: str | None,
    description: str | None,
    image_url: str | None,
    product_url: str | None,
    scraped_at: datetime | None = None,
) -> BookItem:
    """Normalize raw values and return a fully validated ``BookItem``."""
    normalized_availability = _required_text(availability, "availability")
    collected_at = scraped_at or datetime.now(timezone.utc)
    if collected_at.tzinfo is None or collected_at.utcoffset() is None:
        raise BookValidationError("scraped_at", "must include timezone information")

    return BookItem(
        upc=_required_text(upc, "upc", forbid_whitespace=True),
        title=_required_text(title, "title"),
        price_gbp=_price_string(price_gbp),
        availability=normalized_availability,
        stock_count=_stock_count(normalized_availability),
        rating=_rating_value(rating_classes),
        category=_required_text(category, "category"),
        description=_optional_text(description),
        image_url=_https_url(image_url, "image_url"),
        product_url=_https_url(product_url, "product_url"),
        scraped_at=collected_at.astimezone(timezone.utc).isoformat(),
    )


def _required_text(
    value: str | None,
    field: str,
    *,
    forbid_whitespace: bool = False,
) -> str:
    normalized = _optional_text(value)
    if normalized is None:
        raise BookValidationError(field, "is required")
    if forbid_whitespace and any(character.isspace() for character in normalized):
        raise BookValidationError(field, "must not contain whitespace")
    return normalized


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.split())
    return normalized or None


def _price_string(value: str | None) -> str:
    text = _required_text(value, "price_gbp")
    if not text.startswith("£"):
        raise BookValidationError("price_gbp", "must start with the GBP symbol")

    try:
        price = Decimal(text.removeprefix("£"))
    except InvalidOperation as error:
        raise BookValidationError("price_gbp", "must be a decimal number") from error

    if not price.is_finite() or price < 0:
        raise BookValidationError("price_gbp", "must be a finite non-negative value")
    if price.as_tuple().exponent < -2:
        raise BookValidationError("price_gbp", "must have at most two decimal places")
    return f"{price:.2f}"


def _stock_count(availability: str) -> int:
    if availability.casefold() == "out of stock":
        return 0

    match = re.fullmatch(r"In stock \((\d+) available\)", availability)
    if match is None:
        raise BookValidationError(
            "stock_count",
            "could not be derived from availability",
        )
    return int(match.group(1))


def _rating_value(classes: str | None) -> int:
    class_names = set(_required_text(classes, "rating").split())
    matches = class_names.intersection(RATING_VALUES)
    if len(matches) != 1:
        raise BookValidationError("rating", "must contain one known rating class")
    return RATING_VALUES[matches.pop()]


def _https_url(value: str | None, field: str) -> str:
    url = _required_text(value, field)
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise BookValidationError(field, "must be an absolute HTTPS URL")
    return url
