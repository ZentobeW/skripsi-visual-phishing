"""
Automated Threat Intelligence Ingestion & Playwright Sandbox Crawler.
Fetches fresh zero-day phishing feeds via aiohttp and captures full-page visual evidence.

Pipeline:
1. Stream live URLs from OpenPhish community feed (or optional PhishTank API).
2. Dispatch URLs through an asynchronous Playwright crawler with an ephemeral sandbox context.
3. Mitigate dynamic evasion: wait for DOM, optional network idle, and fixed render delay.
4. Tolerate rapid domain takedowns (ERR_NAME_NOT_RESOLVED, timeouts, connection refused).
5. Output collision-resistant screenshots to data/raw/screenshots/.
"""

import asyncio
from datetime import datetime
import hashlib
import logging
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import aiohttp
from playwright.async_api import (
    Browser,
    BrowserContext,
    Error as PlaywrightError,
    Page,
    TimeoutError as PlaywrightTimeoutError,
    async_playwright,
)

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("AutoCrawler")

# Configuration defaults
BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_SCREENSHOT_DIR = BASE_DIR / "data" / "raw" / "screenshots"
OPENPHISH_FEED_URL = "https://openphish.com/feed.txt"
PHISHTANK_API_URL = "https://data.phishtank.com/data/online-valid.json"


# ---------------------------------------------------------------------------
# 1. Asynchronous Threat Feed Fetchers (aiohttp)
# ---------------------------------------------------------------------------
async def fetch_openphish_urls(
    limit: int = 20,
    feed_url: str = OPENPHISH_FEED_URL,
    timeout_seconds: int = 15,
) -> List[str]:
    """
    Asynchronously fetch and parse plain-text URLs from the OpenPhish community feed.

    Args:
        limit: Maximum number of URLs to retrieve.
        feed_url: Public plain-text feed endpoint.
        timeout_seconds: HTTP request timeout.

    Returns:
        List of validated URL strings.
    """
    logger.info("Connecting to OpenPhish live feed: %s", feed_url)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ThreatResearch/1.0"
    }
    client_timeout = aiohttp.ClientTimeout(total=timeout_seconds)

    try:
        async with aiohttp.ClientSession(timeout=client_timeout) as session:
            async with session.get(feed_url, headers=headers) as response:
                if response.status != 200:
                    logger.error("OpenPhish feed returned HTTP status: %d", response.status)
                    return []

                raw_text = await response.text()
                # Parse lines, filtering comments and non-HTTP entries
                urls = [
                    line.strip()
                    for line in raw_text.splitlines()
                    if line.strip().startswith(("http://", "https://"))
                ]

                selected = urls[:limit]
                logger.info("Successfully fetched %d URLs from OpenPhish (limit=%d).", len(selected), limit)
                return selected

    except asyncio.TimeoutError:
        logger.error("Timeout while connecting to OpenPhish feed.")
        return []
    except Exception as exc:
        logger.error("Error fetching OpenPhish feed: %s", exc)
        return []


async def fetch_phishtank_urls(
    api_key: Optional[str] = None,
    limit: int = 20,
    feed_url: str = PHISHTANK_API_URL,
) -> List[str]:
    """
    Scaffold function: Fetches and parses PhishTank verified online JSON feed.

    Note:
    PhishTank requires registering for a free App Key if making automated requests,
    otherwise requests may be rate-limited or return HTTP 429.

    Format expected from PhishTank JSON:
    [
      {
        "phish_id": "1234567",
        "url": "http://example-phishing.com/login",
        "verified": "yes",
        "online": "yes",
        "target": "Bank of America"
      },
      ...
    ]
    """
    logger.info("Fetching PhishTank verified JSON feed...")
    headers = {
        "User-Agent": f"phishtank/{api_key if api_key else 'academic_research_stis'}"
    }

    try:
        async with aiohttp.ClientSession() as session:
            # When using PhishTank API key:
            # payload = {"app_key": api_key, "format": "json"} if api_key else {"format": "json"}
            async with session.get(feed_url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json(content_type=None)
                    # Extract active target URLs
                    urls = [
                        item["url"]
                        for item in data
                        if item.get("online") == "yes" and "url" in item
                    ]
                    return urls[:limit]
                else:
                    logger.warning("PhishTank returned status %d. Check API key/rate limit.", response.status)
                    return []
    except Exception as exc:
        logger.error("PhishTank request failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# 2. File Naming Sanitization
# ---------------------------------------------------------------------------
def sanitize_filename(url: str) -> str:
    """
    Generate a safe, collision-resistant filename.
    Format: <sanitized_domain>_<timestamp>_<sha256_hash>.png
    """
    parsed = urlparse(url)
    domain = parsed.netloc or parsed.path.split("/")[0]

    domain_clean = re.sub(r"[^\w.-]", "_", domain)
    if not domain_clean:
        domain_clean = "unknown_target"

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()[:6]

    return f"{domain_clean}_{timestamp}_{url_hash}.png"


# ---------------------------------------------------------------------------
# 3. Playwright Screenshot Pipeline with Threat Sandboxing
# ---------------------------------------------------------------------------
async def capture_single_url(
    browser: Browser,
    url: str,
    output_dir: Path,
    semaphore: asyncio.Semaphore,
    navigation_timeout_ms: int = 20000,
    render_delay_seconds: float = 3.0,
) -> Dict[str, Any]:
    """
    Safely visit a single phishing URL and capture evidence within an isolated context.
    """
    target_url = url if url.startswith(("http://", "https://")) else f"http://{url}"
    filename = sanitize_filename(target_url)
    output_path = output_dir / filename

    result: Dict[str, Any] = {
        "url": target_url,
        "status": "FAILED",
        "screenshot_path": None,
        "error_type": None,
        "error_message": None,
    }

    async with semaphore:
        context: Optional[BrowserContext] = None
        try:
            # Sandbox isolation per URL: prevents cookie/cache leakage across targets
            context = await browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                ignore_https_errors=True,  # Crucial: Phishing kits often use broken/expired SSL
                accept_downloads=False,    # Sandbox defense against drive-by malware
                permissions=[],            # Deny camera, mic, and location requests
            )

            page: Page = await context.new_page()

            # Prevent malicious alert() loops from freezing the headless runner
            page.on("dialog", lambda dialog: asyncio.create_task(dialog.dismiss()))

            logger.info("Visiting: %s", target_url)

            # 1. Initial navigation: wait for DOMContentLoaded first
            await page.goto(
                target_url,
                wait_until="domcontentloaded",
                timeout=navigation_timeout_ms,
            )

            # 2. Wait for network idle (capped to avoid hanging on persistent sockets)
            try:
                await page.wait_for_load_state("networkidle", timeout=3500)
            except PlaywrightTimeoutError:
                logger.debug("Network idle timed out for %s; continuing to render delay.", target_url)

            # 3. Mitigate delayed rendering: allow dynamic JS forms & brand logos to settle
            if render_delay_seconds > 0:
                await asyncio.sleep(render_delay_seconds)

            # 4. Capture full-page screenshot
            await page.screenshot(path=str(output_path), full_page=True)

            result["status"] = "SUCCESS"
            result["screenshot_path"] = str(output_path)
            logger.info("[SUCCESS] Captured: %s -> %s", target_url, filename)

        except PlaywrightTimeoutError as exc:
            result["error_type"] = "TIMEOUT"
            result["error_message"] = str(exc)
            logger.warning("[TIMEOUT] %s (site unresponsive or hung)", target_url)

        except PlaywrightError as exc:
            # Handles DNS failure (ERR_NAME_NOT_RESOLVED), connection refused, host down
            err_str = str(exc)
            result["error_type"] = "CONNECTION_ERROR"
            result["error_message"] = err_str

            if "ERR_NAME_NOT_RESOLVED" in err_str:
                logger.warning("[DEAD DOMAIN] %s (DNS record takedown)", target_url)
            elif "ERR_CONNECTION_REFUSED" in err_str:
                logger.warning("[REFUSED] %s (Port closed / web server stopped)", target_url)
            else:
                logger.warning("[PLAYWRIGHT ERROR] %s: %s", target_url, err_str[:80])

        except Exception as exc:
            result["error_type"] = "UNEXPECTED_ERROR"
            result["error_message"] = str(exc)
            logger.error("[ERROR] Unexpected exception crawling %s: %s", target_url, exc)

        finally:
            if context:
                await context.close()

    return result


async def crawl_urls(
    urls: List[str],
    output_dir: Path,
    concurrency: int = 3,
    navigation_timeout_ms: int = 20000,
    render_delay_seconds: float = 3.0,
) -> List[Dict[str, Any]]:
    """
    Orchestrates concurrent headless crawling for a batch of URLs.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    semaphore = asyncio.Semaphore(concurrency)

    async with async_playwright() as pw:
        # Chromium flags tailored for stability on CPU and Docker readiness
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ],
        )

        try:
            tasks = [
                capture_single_url(
                    browser=browser,
                    url=url,
                    output_dir=output_dir,
                    semaphore=semaphore,
                    navigation_timeout_ms=navigation_timeout_ms,
                    render_delay_seconds=render_delay_seconds,
                )
                for url in urls
            ]
            results = await asyncio.gather(*tasks)
            return results
        finally:
            await browser.close()


# ---------------------------------------------------------------------------
# 4. Main Integrated Entrypoint
# ---------------------------------------------------------------------------
async def run_pipeline(limit: int = 10, concurrency: int = 3) -> None:
    """
    End-to-end execution:
    1. Fetch fresh threat intelligence URLs via aiohttp.
    2. Crawl and capture evidence via Playwright.
    3. Generate triage summary.
    """
    start_time = asyncio.get_event_loop().time()

    print("\n" + "=" * 75)
    print("STAGE 1: THREAT FEED INGESTION (aiohttp)")
    print("=" * 75)

    urls = await fetch_openphish_urls(limit=limit)

    if not urls:
        logger.warning("No URLs retrieved from OpenPhish feed. Using simulated fallback targets.")
        urls = [
            "https://google.com",
            "https://httpbin.org/delay/2",
            "https://this-domain-does-not-exist-12345.org",
        ]

    print("\n" + "=" * 75)
    print(f"STAGE 2: SANDBOX CRAWLER CAPTURE ({len(urls)} targets, concurrency={concurrency})")
    print("=" * 75)

    results = await crawl_urls(
        urls=urls,
        output_dir=DEFAULT_SCREENSHOT_DIR,
        concurrency=concurrency,
        navigation_timeout_ms=18000,
        render_delay_seconds=3.0,
    )

    elapsed = asyncio.get_event_loop().time() - start_time

    # Triage Summary Statistics
    successful = [r for r in results if r["status"] == "SUCCESS"]
    failed = [r for r in results if r["status"] == "FAILED"]

    print("\n" + "=" * 75)
    print(f"HARVEST EXECUTION REPORT (Total: {elapsed:.2f}s)")
    print("=" * 75)
    print(f"Total Targets Evaluated : {len(results)}")
    print(f"Evidence Captured (OK)  : {len(successful)} (Survival Rate: {len(successful)/len(results)*100:.1f}%)")
    print(f"Dead / Timed Out Links  : {len(failed)}")
    print("-" * 75)

    for r in results:
        status_flag = "[OK]" if r["status"] == "SUCCESS" else "[FAIL]"
        detail = (
            f"Saved: {Path(r['screenshot_path']).name}"
            if r["status"] == "SUCCESS"
            else f"Error: {r['error_type']} ({str(r['error_message'])[:45]}...)"
        )
        print(f"{status_flag:<6} | {r['url']:<45} | {detail}")

    print("=" * 75 + "\n")


if __name__ == "__main__":
    # Tune limits: 10 URLs with 3 concurrent workers is optimal for local CPU testing
    asyncio.run(run_pipeline(limit=10, concurrency=3))
