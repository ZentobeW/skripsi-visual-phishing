"""
Sandbox Crawler for Phishing Threat Intelligence and Visual Phishing Detection.
Dataset collector for Siamese Vision Transformer (ViT) research.

Key capabilities:
- Playwright async browser automation with Chromium isolation.
- Ephemeral browser context per URL to prevent cross-site contamination and cookie tracking.
- Evasion resilience: waits for DOMContentLoaded, optional networkidle, and a fixed rendering
  delay to counter delayed JavaScript rendering/cloaking tactics.
- Bypasses untrusted/self-signed SSL certificates (standard in phishing infrastructure).
- Auto-dismisses modal popups/alerts that freeze automated analysis.
- Controlled concurrency via asyncio.Semaphore for safe CPU execution.
"""

import asyncio
from datetime import datetime
import hashlib
import logging
from pathlib import Path
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

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
logger = logging.getLogger("PhishingCrawler")


class PhishingCrawler:
    """Asynchronous sandbox crawler for capturing screenshots of suspected phishing sites."""

    def __init__(
        self,
        output_dir: str = "data/raw/screenshots",
        concurrency: int = 3,
        navigation_timeout_ms: int = 25000,
        render_delay_seconds: float = 3.5,
        viewport_width: int = 1280,
        viewport_height: int = 720,
    ) -> None:
        """
        Initialize crawler settings.

        Args:
            output_dir: Directory where raw screenshots will be stored.
            concurrency: Maximum number of concurrent browser contexts (tuned for CPU limits).
            navigation_timeout_ms: Max time (ms) to wait for initial page load before failing.
            render_delay_seconds: Additional sleep to wait out anti-analysis rendering delays
                                  and allow dynamically loaded brand assets/logos to hydrate.
            viewport_width: Viewport width in pixels.
            viewport_height: Viewport height in pixels.
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.concurrency = concurrency
        self.navigation_timeout_ms = navigation_timeout_ms
        self.render_delay_seconds = render_delay_seconds
        self.viewport = {"width": viewport_width, "height": viewport_height}

        # Common user-agent string to avoid simple headless bot detection
        self.user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )

    def _sanitize_filename(self, url: str) -> str:
        """
        Generate a safe, collision-resistant filename for a given URL.

        Structure: <sanitized_domain>_<timestamp>_<url_hash>.png
        """
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path.split("/")[0]

        # Strip ports and sanitize domain characters for safe filesystem naming
        domain_clean = re.sub(r"[^\w.-]", "_", domain)
        if not domain_clean:
            domain_clean = "unknown_target"

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # 6-character SHA-256 hash distinguishes multiple endpoints on the same domain
        url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()[:6]

        return f"{domain_clean}_{timestamp}_{url_hash}.png"

    async def _handle_dialog(self, dialog: Any) -> None:
        """Dismiss alerts, confirms, or prompts triggered by phishing scripts."""
        logger.warning("Dialog encountered and dismissed: %s", dialog.message)
        await dialog.dismiss()

    async def capture_single(
        self,
        browser: Browser,
        url: str,
        semaphore: asyncio.Semaphore,
    ) -> Dict[str, Any]:
        """
        Navigate to a single URL and capture a screenshot within an isolated browser context.

        Args:
            browser: Shared Playwright Browser instance.
            url: Target URL to inspect.
            semaphore: Semaphore controlling concurrent execution.

        Returns:
            Dictionary containing crawl result metadata and status.
        """
        target_url = url if url.startswith(("http://", "https://")) else f"http://{url}"
        filename = self._sanitize_filename(target_url)
        destination_path = self.output_dir / filename

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
                # 1. Ephemeral context creation with sandbox safeguards
                context = await browser.new_context(
                    viewport=self.viewport,
                    user_agent=self.user_agent,
                    ignore_https_errors=True,  # Crucial: Phishing kits often use broken/untrusted SSL
                    accept_downloads=False,    # Prevent drive-by file downloads
                    permissions=[],            # Deny camera, mic, geolocation permissions
                )

                page: Page = await context.new_page()

                # 2. Attach defense handlers: prevent malicious alert locks
                page.on("dialog", lambda dialog: asyncio.create_task(self._handle_dialog(dialog)))

                logger.info("Visiting: %s", target_url)

                # 3. Safe initial navigation: wait for DOMContentLoaded first
                await page.goto(
                    target_url,
                    wait_until="domcontentloaded",
                    timeout=self.navigation_timeout_ms,
                )

                # 4. Optional network idle wait (with short timeout so unclosed sockets do not hang)
                try:
                    await page.wait_for_load_state("networkidle", timeout=4000)
                except PlaywrightTimeoutError:
                    logger.debug("Network idle timed out for %s; continuing to render delay.", target_url)

                # 5. Anti-Evasion / Delayed Rendering Mitigation:
                # Malicious kits often sleep for 2-3 seconds before rendering the fake login form or brand logo
                if self.render_delay_seconds > 0:
                    logger.debug(
                        "Waiting %.1fs for deferred DOM hydration on %s...",
                        self.render_delay_seconds,
                        target_url,
                    )
                    await asyncio.sleep(self.render_delay_seconds)

                # 6. Capture full-page screenshot
                await page.screenshot(
                    path=str(destination_path),
                    full_page=True,
                )

                result["status"] = "SUCCESS"
                result["screenshot_path"] = str(destination_path)
                logger.info("Captured screenshot for %s -> %s", target_url, destination_path.name)

            except PlaywrightTimeoutError as exc:
                result["error_type"] = "TIMEOUT"
                result["error_message"] = str(exc)
                logger.warning("Timeout navigating to %s: %s", target_url, exc)

            except PlaywrightError as exc:
                # Handles DNS resolution failures, connection refused, host down, etc.
                result["error_type"] = "CONNECTION_OR_PLAYWRIGHT_ERROR"
                result["error_message"] = str(exc)
                logger.warning("Navigation failed for %s: %s", target_url, exc)

            except Exception as exc:
                result["error_type"] = "UNEXPECTED_EXCEPTION"
                result["error_message"] = str(exc)
                logger.error("Unexpected error crawling %s: %s", target_url, exc, exc_info=True)

            finally:
                if context:
                    await context.close()

        return result

    async def crawl_urls(self, urls: List[str]) -> List[Dict[str, Any]]:
        """
        Execute concurrent crawling for a list of URLs.

        Args:
            urls: Target URLs to crawl.

        Returns:
            List of crawl result dictionaries.
        """
        semaphore = asyncio.Semaphore(self.concurrency)

        async with async_playwright() as pw:
            # Launch Chromium with headless flags suited for local CPU and future Docker use
            browser = await pw.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",  # Prevents /dev/shm memory issues in Docker
                    "--no-sandbox",             # Required when eventually running as root in Docker
                ],
            )

            try:
                tasks = [
                    self.capture_single(browser, url, semaphore)
                    for url in urls
                ]
                results = await asyncio.gather(*tasks)
                return results
            finally:
                await browser.close()


# ---------------------------------------------------------------------------
# Test Harness
# ---------------------------------------------------------------------------
async def main() -> None:
    # Test batch containing legitimate baseline pages and simulated/dead URLs
    sample_urls = [
        "https://google.com",
        "https://github.com",
        "https://httpbin.org/delay/2",     # Tests delay resilience
        "https://this-domain-does-not-exist-12345.org",  # Tests dead host error handling
        "https://expired.badssl.com",      # Tests untrusted SSL bypass
    ]

    crawler = PhishingCrawler(
        output_dir="data/raw/screenshots",
        concurrency=3,                 # Tuned for local CPU
        navigation_timeout_ms=20000,
        render_delay_seconds=3.0,
    )

    logger.info("Starting crawler batch for %d targets...", len(sample_urls))
    start_time = asyncio.get_event_loop().time()
    results = await crawler.crawl_urls(sample_urls)
    duration = asyncio.get_event_loop().time() - start_time

    # Summary report
    print("\n" + "=" * 70)
    print(f"CRAWLER EXECUTION SUMMARY ({duration:.2f}s total)")
    print("=" * 70)
    for res in results:
        status_icon = "[OK]" if res["status"] == "SUCCESS" else "[FAIL]"
        details = (
            f"Path: {res['screenshot_path']}"
            if res["status"] == "SUCCESS"
            else f"Error: {res['error_type']} ({res['error_message'][:60]}...)"
        )
        print(f"{status_icon:<6} | {res['url']:<40} | {details}")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
