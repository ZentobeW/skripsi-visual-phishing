"""
Threat Feed Ingestion & Live Phishing Harvester.
Connects global threat feeds (OpenPhish / PhishTank) directly to the Playwright Sandbox Crawler.

Workflow:
1. Pulls active zero-day phishing URL feeds (OpenPhish public community feed).
2. Filters using high-priority Indonesian threat keywords (DJP/Pajak, Bansos, BPS, Bank BRI/BCA/Mandiri).
3. Dispatches filtered URLs directly into PhishingCrawler to capture live screenshots before takedown.
"""

import asyncio
import logging
from pathlib import Path
import re
import sys
from typing import List
import urllib.request

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.crawler import PhishingCrawler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("FeedCollector")

OPENPHISH_COMMUNITY_FEED_URL = "https://openphish.com/feed.txt"

# Keywords targeting Indonesian brands, government services, and domestic banking
INDONESIAN_TARGET_KEYWORDS = [
    # Government & Social Assistance
    r"\.id\b",
    r"\.go\.id",
    r"pajak",
    r"djp",
    r"kemenkeu",
    r"bansos",
    r"bantuan",
    r"bpjs",
    r"kemdikbud",
    r"kominfo",
    r"komdigi",
    r"bps",
    r"pln",
    r"pertamina",
    # Indonesian Banking & E-Wallets
    r"bca",
    r"bri",
    r"mandiri",
    r"bni",
    r"dana",
    r"ovo",
    r"gopay",
    r"shopee",
]


class LivePhishingHarvester:
    """Fetches real-time phishing feeds and dispatches the sandbox crawler."""

    def __init__(self, feed_url: str = OPENPHISH_COMMUNITY_FEED_URL) -> None:
        self.feed_url = feed_url
        self.filter_regex = re.compile(
            "|".join(INDONESIAN_TARGET_KEYWORDS),
            re.IGNORECASE,
        )

    def fetch_feed_urls(self) -> List[str]:
        """Downloads the plain-text feed of verified active phishing URLs."""
        logger.info("Fetching real-time phishing feed from: %s", self.feed_url)
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        req = urllib.request.Request(self.feed_url, headers=headers)

        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                content = response.read().decode("utf-8", errors="ignore")
                urls = [line.strip() for line in content.splitlines() if line.strip().startswith("http")]
                logger.info("Retrieved %d active global phishing URLs from feed.", len(urls))
                return urls
        except Exception as exc:
            logger.error("Failed to fetch OpenPhish feed: %s. Using simulated fallback URLs.", exc)
            # Simulated fallback feeds for testing when offline or rate-limited
            return [
                "https://pajak-klaim-bansos.xyz/login",
                "https://bca-klik-verifikasi.top/auth",
                "https://bpjs-ketenagakerjaan-dana.info",
            ]

    def filter_indonesian_targets(self, urls: List[str]) -> List[str]:
        """Filters URLs matching Indonesian target keywords or .id domains."""
        matched = [u for u in urls if self.filter_regex.search(u)]
        logger.info("Found %d high-priority Indonesian target URLs in the feed.", len(matched))
        return matched

    async def harvest_and_crawl(self, max_targets: int = 10) -> None:
        """Fetches, filters, and immediately crawls target URLs."""
        all_urls = self.fetch_feed_urls()
        targets = self.filter_indonesian_targets(all_urls)

        if not targets:
            logger.warning("No Indonesian targets found in current feed snapshot. Using top %d general URLs for testing.", min(3, len(all_urls)))
            targets = all_urls[:3]

        selected_targets = targets[:max_targets]
        logger.info("Dispatching Sandbox Crawler for %d targets...", len(selected_targets))

        # Launch the Playwright Sandbox Crawler built in Step 1
        crawler = PhishingCrawler(
            output_dir="data/raw/screenshots",
            concurrency=2,
            navigation_timeout_ms=20000,
            render_delay_seconds=3.0,
        )

        results = await crawler.crawl_urls(selected_targets)

        successful = sum(1 for r in results if r["status"] == "SUCCESS")
        logger.info("Harvest complete: %d/%d screenshots captured.", successful, len(selected_targets))


if __name__ == "__main__":
    harvester = LivePhishingHarvester()
    asyncio.run(harvester.harvest_and_crawl(max_targets=5))
