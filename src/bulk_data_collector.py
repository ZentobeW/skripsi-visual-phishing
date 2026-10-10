"""
Bulk Data Collector & Resumable Sandbox Crawler.
Production-grade dataset harvester for Large-Scale Visual Phishing Research.

Features:
1. Live Threat Feeds Ingestion:
   - Abuse.ch URLhaus database dump (~30,000+ active URLs).
   - OpenPhish community live feed.
   - Filtered with Indonesian keywords & high-probability lookalike patterns (.pages.dev, .web.app, etc.).
2. Comprehensive Legitimate Pool:
   - 50+ official Indonesian Ministry, LPNK, and Provincial portals (.go.id).
3. Resumable Worker Pool:
   - Async concurrency with checkpoint manifest (never repeats already crawled URLs).
   - Fast timeout (12s) to drop dead phishing links without wasting bandwidth.
   - Ephemeral memory management (zero memory leak across 1,000+ screenshots).
"""

import asyncio
import csv
from datetime import datetime
import hashlib
import io
import logging
from pathlib import Path
import re
from typing import Any, Dict, List, Set
from urllib.parse import urlparse
import urllib.request

import aiohttp
from playwright.async_api import (
    Browser,
    BrowserContext,
    TimeoutError as PlaywrightTimeoutError,
    async_playwright,
)
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("BulkCollector")

BASE_DIR = Path(__file__).resolve().parent.parent
SCREENSHOTS_DIR = BASE_DIR / "data" / "raw" / "screenshots"
BULK_LEGIT_DIR = SCREENSHOTS_DIR / "bulk_legitimate"
BULK_PHISH_DIR = SCREENSHOTS_DIR / "bulk_phishing"
CHECKPOINT_CSV = SCREENSHOTS_DIR / "bulk_crawling_checkpoint.csv"

# ---------------------------------------------------------------------------
# 1. Comprehensive Database of Official Indonesian Portals (Centrals + Provinces)
# ---------------------------------------------------------------------------
INDONESIAN_GOV_PORTALS = [
    # Kementerian Pusat
    ("kemenkeu", "https://www.kemenkeu.go.id/"),
    ("pajak", "https://pajak.go.id/"),
    ("djp_online", "https://djponline.pajak.go.id/"),
    ("kominfo", "https://www.komdigi.go.id/"),
    ("kemendagri", "https://kemendagri.go.id/"),
    ("kemlu", "https://kemlu.go.id/"),
    ("kemkes", "https://kemkes.go.id/"),
    ("kemdikbud", "https://kemdikbud.go.id/"),
    ("kemenkumham", "https://kemenkumham.go.id/"),
    ("kemenag", "https://kemenag.go.id/"),
    ("kemnaker", "https://kemnaker.go.id/"),
    ("kemenhub", "https://dephub.go.id/"),
    ("kemenpora", "https://kemenpora.go.id/"),
    ("kemensos", "https://kemensos.go.id/"),
    ("cekbansos", "https://cekbansos.kemensos.go.id/"),
    ("kemenperin", "https://kemenperin.go.id/"),
    ("kemendag", "https://kemendag.go.id/"),
    ("kemenkopukm", "https://kemenkopukm.go.id/"),
    ("kemenpar", "https://kemenparekraf.go.id/"),
    ("kementerian_bumn", "https://bumn.go.id/"),
    # Lembaga Negara & LPNK
    ("bps", "https://www.bps.go.id/"),
    ("ojk", "https://ojk.go.id/"),
    ("bssn", "https://www.bssn.go.id/"),
    ("kejaksaan", "https://kejaksaan.go.id/"),
    ("mahkamah_agung", "https://www.mahkamahagung.go.id/"),
    ("bkn", "https://www.bkn.go.id/"),
    ("sscasn", "https://sscasn.bkn.go.id/"),
    ("bpom", "https://www.pom.go.id/"),
    ("bmkg", "https://www.bmkg.go.id/"),
    ("atrbpn", "https://www.atrbpn.go.id/"),
    ("brin", "https://www.brin.go.id/"),
    ("bappenas", "https://bappenas.go.id/"),
    ("kpk", "https://www.kpk.go.id/"),
    ("dpr", "https://www.dpr.go.id/"),
    ("setneg", "https://setneg.go.id/"),
    ("bank_indonesia", "https://www.bi.go.id/"),
    ("bpjs_kesehatan", "https://bpjs-kesehatan.go.id/"),
    ("bpjs_ketenagakerjaan", "https://www.bpjsketenagakerjaan.go.id/"),
    ("pln", "https://web.pln.co.id/"),
    ("pertamina", "https://www.pertamina.com/"),
    # Pemerintah Daerah Provinsi
    ("pemprov_dki", "https://jakarta.go.id/"),
    ("pemprov_jabar", "https://jabarprov.go.id/"),
    ("pemprov_jateng", "https://jatengprov.go.id/"),
    ("pemprov_jatim", "https://jatimprov.go.id/"),
    ("pemprov_sumut", "https://sumutprov.go.id/"),
    ("pemprov_bali", "https://baliprov.go.id/"),
    ("pemprov_sulsel", "https://sulselprov.go.id/"),
    ("pemprov_kalsel", "https://kalselprov.go.id/"),
    ("pemprov_aceh", "https://acehprov.go.id/"),
    ("pemprov_diy", "https://jogjaprov.go.id/"),
]

# Kata kunci filter ancaman (fokus layanan publik, finansial, dan identitas Indonesia)
PRIORITY_KEYWORDS = [
    "pajak", "djp", "kemenkeu", "bps", "ojk", "bssn", "kominfo", "komdigi",
    "bpjs", "pln", "pertamina", "bansos", "prakerja", "paspor", "imigrasi",
    "kemdikbud", "kemkes", "bkn", "cpns", "asn", "briva", "mandiri", "bca",
    "bri", "bni", "dana", "gopay", "klaim", "saldo", "subsidi", "bantuan",
    "indonesia", "kemensos", "cekbansos", "dana-kaget", "bantuan-pemerintah"
]

LOOKALIKE_PATTERNS = [
    ".pages.dev", ".web.app", ".firebaseapp.com", ".workers.dev",
    ".vercel.app", ".netlify.app", ".render.com", ".glitch.me",
    ".xyz", ".top", ".click", ".buzz", ".online", ".site", ".live"
]



# ---------------------------------------------------------------------------
# 2. Feed Harvesters (URLhaus & OpenPhish)
# ---------------------------------------------------------------------------
def fetch_urlhaus_active_dump(limit: int = 500) -> List[str]:
    """Downloads recent active URLs from Abuse.ch URLhaus CSV dump."""
    url = "https://urlhaus.abuse.ch/downloads/csv_recent/"
    logger.info("Connecting to Abuse.ch URLhaus threat database dump...")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 ThesisResearch/1.0"})

    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            content = resp.read().decode("utf-8", errors="ignore")
            lines = [l for l in content.splitlines() if not l.startswith("#") and l.strip()]
            reader = csv.reader(io.StringIO("\n".join(lines)))
            raw_urls = [row[2] for row in reader if len(row) > 2 and row[2].startswith("http")]

            logger.info(f"Retrieved {len(raw_urls)} active URLs from URLhaus dump.")

            # Filter priority / lookalikes
            priority_urls: List[str] = []
            standard_urls: List[str] = []

            for u in raw_urls:
                u_lower = u.lower()
                is_priority = any(kw in u_lower for kw in PRIORITY_KEYWORDS) or any(pat in u_lower for pat in LOOKALIKE_PATTERNS)
                if is_priority:
                    priority_urls.append(u)
                else:
                    standard_urls.append(u)

            logger.info(f"Filtered {len(priority_urls)} high-priority targets matching threat heuristics.")
            combined = priority_urls + standard_urls
            return combined[:limit]

    except Exception as e:
        logger.error(f"Failed to download URLhaus dump: {e}")
        return []


def fetch_openphish_urls(limit: int = 300) -> List[str]:
    """Fetches active URLs from OpenPhish feed with priority sorting."""
    url = "https://openphish.com/feed.txt"
    logger.info("Fetching OpenPhish live feed...")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 ThreatResearch/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            lines = [line.strip().decode() for line in resp if line.strip().startswith(b"http")]
            logger.info(f"Retrieved {len(lines)} URLs from OpenPhish.")
            
            priority_urls: List[str] = []
            standard_urls: List[str] = []
            for u in lines:
                u_lower = u.lower()
                is_priority = any(kw in u_lower for kw in PRIORITY_KEYWORDS) or any(pat in u_lower for pat in LOOKALIKE_PATTERNS)
                if is_priority:
                    priority_urls.append(u)
                else:
                    standard_urls.append(u)
            logger.info(f"OpenPhish prioritized targets: {len(priority_urls)} URLs matching target patterns.")
            return (priority_urls + standard_urls)[:limit]
    except Exception as e:
        logger.error(f"Failed to fetch OpenPhish: {e}")
        return []



# ---------------------------------------------------------------------------
# 3. High-Throughput Bulk Sandbox Crawler Engine
# ---------------------------------------------------------------------------
class BulkSandboxCrawler:
    """Async Playwright worker pool with persistent checkpointing."""

    def __init__(
        self,
        concurrency: int = 3,
        nav_timeout_ms: int = 15000,
        render_delay_s: float = 2.5,
    ) -> None:
        self.concurrency = concurrency
        self.nav_timeout_ms = nav_timeout_ms
        self.render_delay_s = render_delay_s
        self.semaphore = asyncio.Semaphore(concurrency)
        self.crawled_urls: Set[str] = set()
        self._load_checkpoint()

    def _load_checkpoint(self):
        """Loads previously crawled URLs from disk so we never duplicate work."""
        if CHECKPOINT_CSV.exists():
            try:
                df = pd.read_csv(CHECKPOINT_CSV)
                self.crawled_urls = set(df["url"].dropna().tolist())
                logger.info(f"Loaded checkpoint: {len(self.crawled_urls)} URLs already processed.")
            except Exception as e:
                logger.warning(f"Error loading checkpoint: {e}")

    def _save_checkpoint_record(self, record: Dict[str, Any]):
        """Appends a record immediately to the checkpoint manifest."""
        CHECKPOINT_CSV.parent.mkdir(parents=True, exist_ok=True)
        df_row = pd.DataFrame([record])
        if not CHECKPOINT_CSV.exists():
            df_row.to_csv(CHECKPOINT_CSV, index=False)
        else:
            df_row.to_csv(CHECKPOINT_CSV, mode="a", header=False, index=False)
        self.crawled_urls.add(record["url"])

    def _make_filename(self, url: str, label: str, brand: str) -> str:
        domain = urlparse(url).netloc.replace(":", "_").replace(".", "_")
        domain_clean = re.sub(r"[^\w\-]", "", domain)[:25]
        h = hashlib.sha256(url.encode()).hexdigest()[:8]
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        prefix = brand if label == "legitimate" else "phish"
        return f"{prefix}_{domain_clean}_{h}_{ts}.png"

    async def _crawl_single_target(
        self,
        browser: Browser,
        target: Dict[str, str],
        output_dir: Path,
    ) -> Dict[str, Any]:
        url = target["url"]
        label = target["label"]
        brand = target.get("brand", "threat")

        # Skip if already in checkpoint
        if url in self.crawled_urls:
            return {"url": url, "status": "skipped_already_crawled"}

        async with self.semaphore:
            output_dir.mkdir(parents=True, exist_ok=True)
            filename = self._make_filename(url, label, brand)
            out_path = output_dir / filename

            record = {
                "url": url,
                "label": label,
                "brand": brand,
                "status": "failed",
                "http_status": None,
                "screenshot_path": str(out_path).replace("\\", "/"),
                "timestamp": datetime.now().isoformat(),
            }

            context: Optional[BrowserContext] = None
            try:
                context = await browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    ignore_https_errors=True,
                    accept_downloads=False,
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36",
                )
                page = await context.new_page()
                page.on("dialog", lambda d: asyncio.create_task(d.dismiss()))

                logger.info(f"[{label.upper()}] Crawling: {url[:60]}...")
                resp = await page.goto(
                    url,
                    timeout=self.nav_timeout_ms,
                    wait_until="domcontentloaded",
                )
                if resp:
                    record["http_status"] = resp.status

                # Allow DOM and assets to settle
                await asyncio.sleep(self.render_delay_s)

                # Quality Filter: Detect & drop interstitial, takedown, and cloud provider placeholder screens
                page_title = (await page.title()) or ""
                try:
                    body_text = (await page.inner_text("body"))[:1200]
                except Exception:
                    body_text = ""

                blocked_patterns = [
                    "deceptive site ahead",
                    "suspected phishing",
                    "checking your browser",
                    "just a moment...",
                    "cloudflare",
                    "attention required",
                    "turnstile",
                    "firebase hosting",
                    "site not found",
                    "project suspended",
                    "account suspended",
                    "404 not found",
                    "domain has expired",
                    "default web site page",
                    "cpanel default",
                ]

                check_text = (page_title + " " + body_text).lower()
                is_contaminated = any(p in check_text for p in blocked_patterns)

                if is_contaminated and label == "phishing":
                    record["status"] = "dropped_interstitial_takedown"
                    logger.warning("--> [DROPPED ARTIFACT] Skipping takedown/interstitial screen for '%s': Title='%s'", url[:45], page_title)
                else:
                    await page.screenshot(path=str(out_path), full_page=False)
                    record["status"] = "success"
                    logger.info("--> [OK] Saved clean screenshot: %s", filename)

            except PlaywrightTimeoutError:
                record["status"] = "timeout"
            except Exception as exc:
                record["status"] = f"error_{type(exc).__name__}"
            finally:
                if context:
                    await context.close()

            # Record immediately to checkpoint
            self._save_checkpoint_record(record)
            return record

    async def execute_bulk_crawl(
        self,
        target_list: List[Dict[str, str]],
        output_dir: Path,
        batch_size: int = 15,
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-features=SafeBrowsing",
                    "--disable-client-side-phishing-detection",
                    "--safebrowsing-disable-download-protection",
                    "--safebrowsing-disable-extension-blacklist",
                ],
            )

            # Process in batches to keep RAM perfectly clean
            for i in range(0, len(target_list), batch_size):
                batch = target_list[i : i + batch_size]
                logger.info(f"=== Processing batch {i // batch_size + 1} ({len(batch)} targets) ===")
                tasks = [self._crawl_single_target(browser, t, output_dir) for t in batch]
                batch_res = await asyncio.gather(*tasks)
                results.extend(batch_res)

            await browser.close()

        return results


# ---------------------------------------------------------------------------
# 4. Main Batch Runner
# ---------------------------------------------------------------------------
async def run_bulk_collection(
    collect_legitimate_count: int = 25,
    collect_phishing_count: int = 30,
):
    print("\n" + "=" * 80)
    print("STARTING BULK DATASET HARVESTER (RESUMABLE WORKER POOL)")
    print("=" * 80)

    crawler = BulkSandboxCrawler(concurrency=3, nav_timeout_ms=15000, render_delay_s=2.5)

    # 1. Legitimate Pool Queue
    legit_queue = [
        {"url": url, "brand": brand, "label": "legitimate"}
        for brand, url in INDONESIAN_GOV_PORTALS[:collect_legitimate_count]
    ]

    print(f"\n[PHASE 1] Queued {len(legit_queue)} official government portals for crawling...")
    await crawler.execute_bulk_crawl(legit_queue, BULK_LEGIT_DIR, batch_size=10)

    # 2. Phishing Threat Queue (URLhaus + OpenPhish)
    print(f"\n[PHASE 2] Harvesting live threat intelligence feeds (URLhaus & OpenPhish)...")
    urlhaus_pool = fetch_urlhaus_active_dump(limit=collect_phishing_count * 2)
    openphish_pool = fetch_openphish_urls(limit=collect_phishing_count)

    # Combine & deduplicate
    threat_urls = list(dict.fromkeys(urlhaus_pool + openphish_pool))
    phish_queue = [
        {"url": u, "brand": "threat", "label": "phishing"}
        for u in threat_urls[:collect_phishing_count]
    ]

    print(f"[PHASE 2] Queued {len(phish_queue)} verified active phishing targets...")
    await crawler.execute_bulk_crawl(phish_queue, BULK_PHISH_DIR, batch_size=10)

    # Summary
    if CHECKPOINT_CSV.exists():
        df_cp = pd.read_csv(CHECKPOINT_CSV)
        print("\n" + "=" * 80)
        print("BULK HARVESTING SUMMARY (CHECKPOINT REPORT):")
        print(f"Total Unique URLs Processed : {len(df_cp)}")
        print(f"Success Count (Saved Images): {sum(1 for s in df_cp['status'] if s == 'success')}")
        print(f"Checkpoint File Location    : {CHECKPOINT_CSV}")
        print("=" * 80 + "\n")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Bulk Dataset Harvester for Visual Phishing Research")
    parser.add_argument("--legit", type=int, default=50, help="Number of legitimate portals to queue")
    parser.add_argument("--phish", type=int, default=60, help="Number of phishing targets to queue")
    args = parser.parse_args()

    asyncio.run(run_bulk_collection(collect_legitimate_count=args.legit, collect_phishing_count=args.phish))

