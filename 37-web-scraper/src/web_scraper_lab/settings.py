"""Scrapy settings for the web scraper lab."""

from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[2]

BOT_NAME = "web_scraper_lab"

SPIDER_MODULES = ["web_scraper_lab.spiders"]
NEWSPIDER_MODULE = "web_scraper_lab.spiders"
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"

# The target returned 404 for robots.txt during analysis. Keep the middleware
# enabled so a future policy file is respected automatically.
ROBOTSTXT_OBEY = True

# Conservative request limits defined in docs/02-crawler-design.md.
CONCURRENT_REQUESTS = 1
CONCURRENT_REQUESTS_PER_DOMAIN = 1
DOWNLOAD_DELAY = 1.0
DOWNLOAD_DELAY_JITTER = 0.0
DOWNLOAD_TIMEOUT = 30
DOWNLOAD_MAXSIZE = 5 * 1024 * 1024

RETRY_ENABLED = True
RETRY_TIMES = 3
RETRY_HTTP_CODES = [408, 429, 500, 502, 503, 504, 522, 524]
RETRY_BACKOFF_BASE = 1.0
RETRY_BACKOFF_MAX = 60.0

DOWNLOADER_MIDDLEWARES = {
    "scrapy.downloadermiddlewares.retry.RetryMiddleware": None,
    "web_scraper_lab.middlewares.ExponentialBackoffRetryMiddleware": 550,
}

ITEM_PIPELINES = {
    "web_scraper_lab.pipelines.SQLiteBookPipeline": 300,
}
BOOKS_DB_PATH = str(PROJECT_DIR / "data" / "processed" / "books.db")
SQLITE_COMMIT_BATCH_SIZE = 100

EXTENSIONS = {
    "web_scraper_lab.extensions.CrawlMonitorExtension": 500,
}
CRAWL_STATS_PATH = str(PROJECT_DIR / "data" / "processed" / "crawl-stats.json")
MIN_PARSE_SUCCESS_RATE = 0.95

USER_AGENT = (
    "data-harness-lab/0.1 "
    "(+https://github.com/leena-0/data-harness-lab; educational scraper)"
)

COOKIES_ENABLED = False
TELNETCONSOLE_ENABLED = False

LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"

FEED_EXPORT_ENCODING = "utf-8"
