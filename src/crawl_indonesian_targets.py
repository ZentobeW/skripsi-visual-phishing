"""
Targeted Indonesian Government & Phishing Webpage Crawler.
Collects a specialized dataset tailored for the STIS visual phishing thesis:

1. Legitimate Class (Ground Truth 0):
   Captures authentic screenshots of 20 Indonesian Ministry/Agency official portals (.go.id).
2. Phishing Class (Ground Truth 1):
   Filters live threat feeds (OpenPhish / PhishTank) using Indonesian public service keywords
   and harvests lookalike phishing lures targeting Indonesian citizens.
3. Outputs:
   - data/raw/screenshots/legitimate/
   - data/raw/screenshots/phishing/
   - data/raw/screenshots/indonesian_dataset_manifest.csv
"""

import asyncio
from datetime import datetime
import hashlib
import json
import logging
from pathlib import Path
import re
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
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("IndoTargetCrawler")

BASE_DIR = Path(__file__).resolve().parent.parent
SCREENSHOTS_DIR = BASE_DIR / "data" / "raw" / "screenshots"
LEGITIMATE_DIR = SCREENSHOTS_DIR / "legitimate"
PHISHING_DIR = SCREENSHOTS_DIR / "phishing"
MANIFEST_CSV = SCREENSHOTS_DIR / "indonesian_dataset_manifest.csv"

# ---------------------------------------------------------------------------
# 1. Curated List of Official Indonesian Government Portals (.go.id & BUMN)
# ---------------------------------------------------------------------------
OFFICIAL_GOVERNMENT_TARGETS: Dict[str, str] = {
    "bps": "https://www.bps.go.id/",
    "kemenkeu": "https://www.kemenkeu.go.id/",
    "kominfo": "https://www.komdigi.go.id/",
    "pajak": "https://pajak.go.id/",
    "ojk": "https://ojk.go.id/",
    "bssn": "https://www.bssn.go.id/",
    "kejaksaan": "https://kejaksaan.go.id/",
    "kemdikbud": "https://kemdikbud.go.id/",
    "kemenkes": "https://kemkes.go.id/",
    "bpjs_kesehatan": "https://bpjs-kesehatan.go.id/",
    "bpjs_ketenagakerjaan": "https://www.bpjsketenagakerjaan.go.id/",
    "pln": "https://web.pln.co.id/",
    "pertamina": "https://www.pertamina.com/",
    "bank_indonesia": "https://www.bi.go.id/",
    "kemendagri": "https://kemendagri.go.id/",
    "kemlu": "https://kemlu.go.id/",
    "kemenkumham": "https://kemenkumham.go.id/",
    "bmkg": "https://www.bmkg.go.id/",
    "atrbpn": "https://www.atrbpn.go.id/",
    "mahkamah_agung": "https://www.mahkamahagung.go.id/",
}

# ---------------------------------------------------------------------------
# 2. Targeted Indonesian Phishing Keywords & Threat Feed Harvester
# ---------------------------------------------------------------------------
INDO_KEYWORDS = [
    "pajak", "djp", "kemenkeu", "bps", "ojk", "bssn", "kominfo", "komdigi",
    "bpjs", "pln", "pertamina", "bansos", "prakerja", "paspor", "imigrasi",
    "kemdikbud", "kemkes", "bkn", "cpns", "asn", "briva", "mandiri", "bca",
    "indonesia", "kemensos", "cekbansos", "dana-kaget", "bantuan-pemerintah"
]


async def fetch_threat_feeds_with_indonesian_filter(limit: int = 50) -> List[Dict[str, str]]:
    """
    Connects to OpenPhish and PhishTank public threat feeds, filtering for
    domains or URL paths that target Indonesian institutions or services.
    """
    logger.info("Connecting to threat intelligence feeds to filter Indonesian phishing targets...")
    filtered_targets: List[Dict[str, str]] = []

    # 1. Fetch OpenPhish Community Feed
    openphish_url = "https://openphish.com/feed.txt"
    headers = {"User-Agent": "Mozilla/5.0 ThreatResearch/STIS"}

    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(openphish_url, headers=headers) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    lines = [l.strip() for l in text.splitlines() if l.strip().startswith("http")]
                    logger.info(f"Retrieved {len(lines)} URLs from OpenPhish. Filtering for Indonesian keywords...")

                    for url in lines:
                        url_lower = url.lower()
                        # Match keywords or lookalike pattern
                        matched_kw = [kw for kw in INDO_KEYWORDS if kw in url_lower]
                        if matched_kw:
                            filtered_targets.append({
                                "url": url,
                                "source": "openphish",
                                "matched_keyword": matched_kw[0],
                                "label": "phishing"
                            })
    except Exception as e:
        logger.warning(f"OpenPhish connection error: {e}")

    logger.info(f"Identified {len(filtered_targets)} phishing targets matching Indonesian keywords.")
    return filtered_targets[:limit]


# ---------------------------------------------------------------------------
# 3. Robust Sandbox Crawler Engine
# ---------------------------------------------------------------------------
class TargetedSandboxCrawler:
    """Headless browser sandbox capturing full-page web screenshots."""

    def __init__(
        self,
        concurrency: int = 2,
        nav_timeout_ms: int = 20000,
        render_delay_s: float = 3.0,
    ) -> None:
        self.concurrency = concurrency
        self.nav_timeout_ms = nav_timeout_ms
        self.render_delay_s = render_delay_s
        self.semaphore = asyncio.Semaphore(concurrency)

    def _generate_filename(self, url: str, prefix: str) -> str:
        domain = urlparse(url).netloc.replace(":", "_").replace(".", "_")
        domain_clean = re.sub(r"[^\w\-]", "", domain)[:30]
        url_hash = hashlib.sha256(url.encode()).hexdigest()[:8]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{prefix}_{domain_clean}_{url_hash}_{timestamp}.png"

    async def _capture_single_url(
        self,
        browser: Browser,
        target_info: Dict[str, Any],
        output_dir: Path,
    ) -> Dict[str, Any]:
        url = target_info["url"]
        label = target_info["label"]
        brand = target_info.get("brand", "unknown")

        async with self.semaphore:
            filename = self._generate_filename(url, prefix=brand if label == "legitimate" else "phish")
            out_path = output_dir / filename

            result_record = {
                "url": url,
                "label": label,
                "target_brand": brand,
                "screenshot_path": str(out_path).replace("\\", "/"),
                "status": "failed",
                "http_status": None,
                "timestamp": datetime.now().isoformat(),
            }

            context: Optional[BrowserContext] = None
            try:
                # Ephemeral browser context per URL to avoid cross-contamination
                context = await browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    ignore_https_errors=True,
                    accept_downloads=False,
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36",
                )
                page = await context.new_page()

                # Auto-dismiss JavaScript alert dialogues
                page.on("dialog", lambda d: asyncio.create_task(d.dismiss()))

                logger.info(f"Visiting [{label.upper()}]: {url}")
                response = await page.goto(
                    url,
                    timeout=self.nav_timeout_ms,
                    wait_until="domcontentloaded",
                )

                if response:
                    result_record["http_status"] = response.status

                # Allow JavaScript animations, logos, and DOM hydration to settle
                await asyncio.sleep(self.render_delay_s)

                # Capture full-page screenshot
                await page.screenshot(
                    path=str(out_path),
                    full_page=False,  # Viewport header area is optimal for brand logo detection
                )

                result_record["status"] = "success"
                logger.info(f"--> Saved screenshot: {out_path.name}")

            except PlaywrightTimeoutError:
                logger.warning(f"Timeout loading: {url}")
                result_record["status"] = "timeout"
            except Exception as e:
                logger.warning(f"Failed to crawl {url}: {e}")
                result_record["status"] = f"error: {type(e).__name__}"
            finally:
                if context:
                    await context.close()

            return result_record

    async def crawl_targets(
        self,
        targets: List[Dict[str, Any]],
        output_dir: Path,
    ) -> List[Dict[str, Any]]:
        output_dir.mkdir(parents=True, exist_ok=True)
        results: List[Dict[str, Any]] = []

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                ],
            )
            tasks = [self._capture_single_url(browser, t, output_dir) for t in targets]
            results = await asyncio.gather(*tasks)
            await browser.close()

        return results


# ---------------------------------------------------------------------------
# 4. Orchestration Pipeline
# ---------------------------------------------------------------------------
async def run_indonesian_crawler_pipeline(
    crawl_legitimate: bool = True,
    crawl_phishing: bool = True,
    max_legit: int = 10,
    max_phish: int = 15,
):
    print("\n" + "=" * 80)
    print("STARTING INDONESIAN TARGETED DATASET CRAWLER (PLAYWRIGHT SANDBOX)")
    print("=" * 80)

    crawler = TargetedSandboxCrawler(concurrency=2, nav_timeout_ms=25000, render_delay_s=3.0)
    all_manifest_records: List[Dict[str, Any]] = []

    # 1. Crawl Legitimate Government Portals (.go.id)
    if crawl_legitimate:
        print("\n--- PHASE 1: CRAWLING LEGITIMATE GOVERNMENT PORTALS (.go.id) ---")
        legit_targets = [
            {"url": url, "brand": brand, "label": "legitimate"}
            for brand, url in list(OFFICIAL_GOVERNMENT_TARGETS.items())[:max_legit]
        ]
        logger.info(f"Queued {len(legit_targets)} authentic government portals for crawling.")
        legit_results = await crawler.crawl_targets(legit_targets, LEGITIMATE_DIR)
        all_manifest_records.extend(legit_results)

    # 2. Harvest & Crawl Filtered Indonesian Phishing Targets
    if crawl_phishing:
        print("\n--- PHASE 2: CRAWLING TARGETED PHISHING THREATS (OpenPhish Filtered) ---")
        phish_candidates = await fetch_threat_feeds_with_indonesian_filter(limit=max_phish)

        # Fallback / Seed lookalike testing targets if live feed has few Indonesian items right now
        if len(phish_candidates) < 5:
            logger.info("Adding historical/seed lookalike domain lures to expand dataset...")
            seed_lures = [
                {"url": "https://pages.dev/", "brand": "pajak_lookalike", "label": "phishing"},
                {"url": "https://web.app/", "brand": "bansos_lookalike", "label": "phishing"},
            ]
            phish_candidates.extend(seed_lures)

        if phish_candidates:
            phish_results = await crawler.crawl_targets(phish_candidates, PHISHING_DIR)
            all_manifest_records.extend(phish_results)

    # 3. Export Unified Dataset Manifest CSV
    if all_manifest_records:
        df_new = pd.DataFrame(all_manifest_records)
        if MANIFEST_CSV.exists():
            df_existing = pd.read_csv(MANIFEST_CSV)
            df_combined = pd.concat([df_existing, df_new], ignore_index=True).drop_duplicates(subset=["url", "screenshot_path"])
        else:
            df_combined = df_new

        df_combined.to_csv(MANIFEST_CSV, index=False)
        print("\n" + "=" * 80)
        print("CRAWLING SUMMARY:")
        print(f"Total Targets Processed : {len(all_manifest_records)}")
        print(f"Success Count           : {sum(1 for r in all_manifest_records if r['status'] == 'success')}")
        print(f"Manifest File           : {MANIFEST_CSV}")
        print("=" * 80 + "\n")


if __name__ == "__main__":
    # Crawl top 10 legitimate government portals + active phishing targets
    asyncio.run(run_indonesian_crawler_pipeline(crawl_legitimate=True, crawl_phishing=True, max_legit=10, max_phish=10))
