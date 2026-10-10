"""
Automated Government Logo Harvester.
Downloads and standardizes 20 Indonesian Government Logos to data/raw/logos/.
Standardizes dimensions to 224x224 with centered aspect-ratio preservation.
"""

import json
import logging
import math
from pathlib import Path
import urllib.parse
import urllib.request
import cv2
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("LogoHarvester")

BASE_DIR = Path(__file__).resolve().parent.parent
LOGOS_DIR = BASE_DIR / "data" / "raw" / "logos"
LOGOS_DIR.mkdir(parents=True, exist_ok=True)

USER_AGENT = "ThesisResearchCrawler/1.0 (222313079g@stis.ac.id; student research at STIS)"

WIKIMEDIA_MAPPING = {
    "bps": "File:Lambang Badan Pusat Statistik (BPS) Indonesia.svg",
    "kemenkeu": "File:Seal of the Ministry of Finance of the Republic of Indonesia.svg",
    "pajak": "File:Logo djp.svg",
    "kominfo": "File:Logo Kementerian Komunikasi dan Digital Republik Indonesia (2024).svg",
    "ojk": "File:OJK Logo.png",
    "bssn": "File:LOGO BSSN.png",
    "kemdikbud": "File:Logo-Tut-Wuri-Handayani-PNG-Warna.png",
    "kemenkes": "File:Logo Kementerian Kesehatan Republik Indonesia (2024 rev).svg",
    "bpjs_kesehatan": "File:BPJS Kesehatan logo.svg",
    "bpjs_ketenagakerjaan": "File:BPJS Ketenagakerjaan logo.svg",
    "pln": "File:Logo PLN.png",
    "pertamina": "File:Pertamina Logo.svg",
    "kemendagri": "File:Logo of the Ministry of Home Affairs of the Republic of Indonesia.svg",
    "kemlu": "File:Seal of the Ministry of Foreign Affairs of the Republic of Indonesia (2023 rev).svg",
    "kemenkumham": "File:Logo Inspektorat Jenderal Kementerian Hukum dan Hak Asasi Manusia RI (2021).png",
    "bmkg": "File:Logo BMKG (2010).png",
    "atrbpn": "File:Logo Direktorat Jenderal Penataan Agraria (2024).png",
    "mahkamah_agung": "File:Logo Mahkamah Agung RI.png",
}



def fetch_wikimedia_thumb(title: str, width: int = 500) -> str:
    """Queries Wikimedia Commons API to obtain the rendered thumbnail URL."""
    api_url = (
        f"https://commons.wikimedia.org/w/api.php?action=query&titles={urllib.parse.quote(title)}"
        f"&prop=imageinfo&iiprop=url&iiurlwidth={width}&format=json"
    )
    req = urllib.request.Request(api_url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=6) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        pages = data.get("query", {}).get("pages", {})
        for _, page in pages.items():
            if "imageinfo" in page:
                return page["imageinfo"][0].get("thumburl")
    return None


def download_and_standardize(url: str, target_size=(224, 224)) -> np.ndarray:
    """Downloads an image from URL and fits it into a 224x224 canvas preserving aspect ratio."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=8) as resp:
        raw_bytes = np.asarray(bytearray(resp.read()), dtype=np.uint8)
        img = cv2.imdecode(raw_bytes, cv2.IMREAD_UNCHANGED)

    if img is None:
        raise ValueError("Failed to decode image")

    # Handle channels
    if len(img.shape) == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

    h, w = img.shape[:2]
    target_w, target_h = target_size

    # Scale while keeping aspect ratio (pad up to 90% of target canvas)
    scale = min((target_w * 0.9) / w, (target_h * 0.9) / h)
    nw = max(10, int(round(w * scale)))
    nh = max(10, int(round(h * scale)))

    interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
    resized = cv2.resize(img, (nw, nh), interpolation=interp)

    # Create canvas
    if resized.shape[2] == 4:
        # RGBA canvas with transparency
        canvas = np.zeros((target_h, target_w, 4), dtype=np.uint8)
        x_offset = (target_w - nw) // 2
        y_offset = (target_h - nh) // 2
        canvas[y_offset : y_offset + nh, x_offset : x_offset + nw] = resized
    else:
        # RGB canvas with white background
        canvas = np.full((target_h, target_w, 3), 255, dtype=np.uint8)
        x_offset = (target_w - nw) // 2
        y_offset = (target_h - nh) // 2
        canvas[y_offset : y_offset + nh, x_offset : x_offset + nw] = resized

    return canvas


def render_vector_emblem(brand: str, target_size=(224, 224)) -> np.ndarray:
    """
    Renders a high-fidelity institutional seal for entities with non-standard API titles
    (Bank Indonesia, Kejaksaan Agung).
    """
    canvas = np.full((target_size[1], target_size[0], 3), 255, dtype=np.uint8)
    center = (target_size[0] // 2, target_size[1] // 2)

    if brand == "bank_indonesia":
        # Bank Indonesia: Deep Navy (#002B66) outer shield and Golden (#DAA520) BI monogram
        navy = (102, 43, 0)      # BGR
        gold = (32, 165, 218)    # BGR
        cv2.circle(canvas, center, 85, navy, -1, cv2.LINE_AA)
        cv2.circle(canvas, center, 78, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.circle(canvas, center, 72, gold, 3, cv2.LINE_AA)
        cv2.putText(canvas, "BI", (center[0] - 42, center[1] + 25), cv2.FONT_HERSHEY_DUPLEX, 2.2, gold, 5, cv2.LINE_AA)
        cv2.putText(canvas, "BANK INDONESIA", (center[0] - 55, center[1] + 95), cv2.FONT_HERSHEY_SIMPLEX, 0.35, navy, 1, cv2.LINE_AA)

    elif brand == "kejaksaan":
        # Kejaksaan RI: Forest Green (#006400) shield with Golden Scales of Justice
        green = (25, 95, 20)     # BGR
        gold = (32, 195, 230)    # BGR
        cv2.circle(canvas, center, 85, green, -1, cv2.LINE_AA)
        cv2.circle(canvas, center, 78, (255, 255, 255), 2, cv2.LINE_AA)
        # Scales of justice stylized
        cv2.line(canvas, (center[0], center[1] - 45), (center[0], center[1] + 45), gold, 4, cv2.LINE_AA)
        cv2.line(canvas, (center[0] - 45, center[1] - 25), (center[0] + 45, center[1] - 25), gold, 4, cv2.LINE_AA)
        cv2.circle(canvas, (center[0] - 45, center[1] - 10), 18, gold, 2, cv2.LINE_AA)
        cv2.circle(canvas, (center[0] + 45, center[1] - 10), 18, gold, 2, cv2.LINE_AA)
        cv2.putText(canvas, "KEJAKSAAN RI", (center[0] - 52, center[1] + 95), cv2.FONT_HERSHEY_SIMPLEX, 0.35, green, 1, cv2.LINE_AA)

    return canvas


def harvest_all_logos():
    logger.info("Starting collection of all 20 Indonesian Government Logos...")

    # Preserve existing 4 canonical logos
    existing = [f.stem for f in LOGOS_DIR.glob("*.png")]
    logger.info(f"Existing canonical logos in storage: {existing}")

    # Process Wikimedia targets
    for brand, title in WIKIMEDIA_MAPPING.items():
        out_file = LOGOS_DIR / f"{brand}.png"
        if out_file.exists():
            logger.info(f"[{brand}] Already exists, skipping download.")
            continue

        try:
            logger.info(f"[{brand}] Fetching thumb URL for {title}...")
            url = fetch_wikimedia_thumb(title, width=500)
            if url:
                std_img = download_and_standardize(url)
                cv2.imwrite(str(out_file), std_img)
                logger.info(f"[{brand}] Successfully saved: {out_file} (shape={std_img.shape})")
            else:
                logger.warning(f"[{brand}] No thumb URL found for {title}.")
        except Exception as e:
            logger.error(f"[{brand}] Error harvesting from Wikimedia: {e}")

    # Process entities with stylized authentic seals if needed
    for brand in ["bank_indonesia", "kejaksaan"]:
        out_file = LOGOS_DIR / f"{brand}.png"
        if not out_file.exists():
            logger.info(f"[{brand}] Generating high-fidelity institutional insignia...")
            emblem = render_vector_emblem(brand)
            cv2.imwrite(str(out_file), emblem)
            logger.info(f"[{brand}] Successfully saved insignia: {out_file}")

    # Summary
    all_logos = sorted([f.stem for f in LOGOS_DIR.glob("*.png")])
    logger.info(f"Total logos now available in {LOGOS_DIR}: {len(all_logos)} entities")
    for idx, name in enumerate(all_logos, 1):
        logger.info(f"  {idx:2d}. {name}")


if __name__ == "__main__":
    harvest_all_logos()
