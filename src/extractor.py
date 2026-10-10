"""
Logo Extractor & Siamese Triplet Pipeline.
Dataset engineering for Visual Phishing Detection via Siamese Vision Transformer (ViT).

Pipeline stages:
1. Full-page screenshot ingestion via OpenCV (cv2).
2. Logo object detection using Ultralytics YOLOv8 (pluggable model architecture).
3. Bounding-box coordinate normalization, clipping, and cropping to disk.
4. Triplet generation (Anchor, Positive, Negative) with reproducible pseudo-random sampling
   for Metric Learning / Contrastive Loss / Triplet Margin Loss optimization.
"""

from collections import defaultdict
import logging
from pathlib import Path
import random
import re
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
import pandas as pd
from ultralytics import YOLO

# Structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("LogoExtractor")


class LogoExtractor:
    """Handles object detection and cropping of brand/government logos from screenshots."""

    def __init__(
        self,
        model_path: str = "yolov8n.pt",
        conf_thresh: float = 0.25,
        iou_thresh: float = 0.45,
        save_top_k: int = 1,
    ) -> None:
        """
        Initialize the YOLOv8 detector.

        Args:
            model_path: Path to YOLO weights. Defaults to 'yolov8n.pt' as a placeholder.
                        Replace with your fine-tuned model path (e.g., 'runs/detect/best.pt')
                        once trained on your Indonesian gov logo dataset.
            conf_thresh: Confidence score threshold for candidate bounding boxes.
            iou_thresh: NMS (Non-Maximum Suppression) IoU threshold.
            save_top_k: Maximum number of highest-confidence logo crops to save per screenshot.
        """
        self.model_path = model_path
        self.conf_thresh = conf_thresh
        self.iou_thresh = iou_thresh
        self.save_top_k = save_top_k

        logger.info("Initializing YOLOv8 detector using model: %s", self.model_path)
        # Ultralytics will automatically download generic yolov8n.pt if not found locally
        self.model = YOLO(self.model_path)

    def extract_from_image(
        self,
        image_path: Path,
        output_dir: Path,
        brand_label: Optional[str] = None,
    ) -> List[Path]:
        """
        Detect, crop, and save logo(s) from a single screenshot.

        Args:
            image_path: Path to the raw screenshot.
            output_dir: Directory where cropped logo images will be saved.
            brand_label: Optional ground-truth brand or domain tag to prefix in the crop filename.

        Returns:
            List of Path objects pointing to saved cropped logo files.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        img_bgr = cv2.imread(str(image_path))

        if img_bgr is None:
            logger.error("Failed to load image at %s (file missing or corrupt).", image_path)
            return []

        h_img, w_img = img_bgr.shape[:2]

        # 1. Run YOLO inference
        results = self.model.predict(
            source=img_bgr,
            conf=self.conf_thresh,
            iou=self.iou_thresh,
            verbose=False,
        )

        saved_crops: List[Path] = []
        if not results or len(results[0].boxes) == 0:
            logger.warning("No logos detected in: %s", image_path.name)
            return []

        boxes = results[0].boxes

        # Sort detections by confidence score in descending order
        sorted_indices = sorted(
            range(len(boxes)),
            key=lambda idx: float(boxes.conf[idx]),
            reverse=True,
        )
        selected_indices = sorted_indices[: self.save_top_k]

        prefix = f"{brand_label}_" if brand_label else ""

        for rank, idx in enumerate(selected_indices):
            box = boxes[idx]
            conf = float(box.conf[0])
            xyxy = box.xyxy[0].cpu().numpy()

            # 2. Coordinate clipping to prevent out-of-boundary indexing
            x1 = max(0, int(round(xyxy[0])))
            y1 = max(0, int(round(xyxy[1])))
            x2 = min(w_img, int(round(xyxy[2])))
            y2 = min(h_img, int(round(xyxy[3])))

            # Sanity check: Ensure positive crop dimensions
            if (x2 - x1) <= 5 or (y2 - y1) <= 5:
                logger.debug("Skipping degenerate bbox [%d, %d, %d, %d] in %s", x1, y1, x2, y2, image_path.name)
                continue

            crop = img_bgr[y1:y2, x1:x2]

            crop_filename = f"{prefix}{image_path.stem}_crop{rank}_conf{int(conf * 100)}.png"
            crop_path = output_dir / crop_filename

            # Save the cropped logo patch
            success = cv2.imwrite(str(crop_path), crop)
            if success:
                saved_crops.append(crop_path)
                logger.info(
                    "Cropped [%dx%d] conf=%.2f from %s -> %s",
                    x2 - x1,
                    y2 - y1,
                    conf,
                    image_path.name,
                    crop_filename,
                )
            else:
                logger.error("Failed writing cropped patch to %s", crop_path)

        return saved_crops

    def batch_extract(
        self,
        screenshots_dir: Path,
        output_dir: Path,
    ) -> Dict[str, List[Path]]:
        """
        Process all valid screenshot images in a directory.

        Returns:
            Dictionary mapping original screenshot filenames to lists of extracted crop paths.
        """
        valid_extensions = {".png", ".jpg", ".jpeg", ".webp"}
        image_files = [p for p in screenshots_dir.rglob("*") if p.is_file() and p.suffix.lower() in valid_extensions]

        logger.info("Found %d screenshot(s) across directories to process in %s", len(image_files), screenshots_dir)
        results: Dict[str, List[Path]] = {}

        for img_path in image_files:
            # Extract inferable brand name from filename if possible (e.g., 'pajak_go_id_...png')
            inferred_brand = img_path.stem.split("_")[0]
            crops = self.extract_from_image(img_path, output_dir, brand_label=inferred_brand)
            results[img_path.name] = crops

        return results


# ---------------------------------------------------------------------------
# Triplet Dataset Generator for Metric Learning (PyTorch Ready)
# ---------------------------------------------------------------------------
def _extract_brand_identifier(filepath: Path) -> str:
    """
    Heuristic to extract brand label from a file or folder name.
    Examples:
      'data/raw/logos/kemenkeu.png' -> 'kemenkeu'
      'data/processed/cropped_logos/kemenkeu_screenshot1_crop0.png' -> 'kemenkeu'
      'data/raw/logos/bps/logo_canonical.png' -> 'bps'
    """
    if filepath.parent.name not in {"logos", "cropped_logos", "raw", "processed"}:
        return filepath.parent.name.lower()
    # Otherwise extract leading token before first underscore or dot
    token = re.split(r"[._-]", filepath.stem)[0]
    return token.lower()


def generate_triplet_csv(
    logos_dir: Path,
    cropped_dir: Path,
    output_csv: Path,
    num_triplets_per_brand: int = 5,
    random_seed: int = 42,
) -> pd.DataFrame:
    """
    Generate an Anchor-Positive-Negative triplet dataset table for Siamese training.

    Triplet Formulation:
      - Anchor (A): Canonical legitimate government logo from `data/raw/logos/`.
      - Positive (P): Harvested/cropped logo from `data/processed/cropped_logos/` of the SAME brand.
      - Negative (N): Canonical or cropped logo from a DIFFERENT brand.

    Args:
        logos_dir: Directory containing legitimate reference logos.
        cropped_dir: Directory containing cropped logo extractions from web screenshots.
        output_csv: Path where the resulting triplets.csv will be saved.
        num_triplets_per_brand: Number of triplets to sample per target brand.
        random_seed: RNG seed for reproducible metric learning dataset splits.

    Returns:
        Pandas DataFrame containing [anchor_path, positive_path, negative_path, brand_label].
    """
    rng = random.Random(random_seed)
    valid_exts = {".png", ".jpg", ".jpeg", ".webp"}

    # 1. Index canonical reference logos by brand (Anchors)
    canonical_logos = [p for p in logos_dir.rglob("*") if p.suffix.lower() in valid_exts]
    anchors_by_brand: Dict[str, List[Path]] = defaultdict(list)
    for p in canonical_logos:
        brand = _extract_brand_identifier(p)
        anchors_by_brand[brand].append(p)

    # 2. Index detected/cropped logos by brand (Positives)
    cropped_logos = [p for p in cropped_dir.rglob("*") if p.suffix.lower() in valid_exts]
    positives_by_brand: Dict[str, List[Path]] = defaultdict(list)
    for p in cropped_logos:
        brand = _extract_brand_identifier(p)
        positives_by_brand[brand].append(p)

    logger.info(
        "Indexed %d anchor brand classes and %d cropped positive brand classes.",
        len(anchors_by_brand),
        len(positives_by_brand),
    )

    triplet_records: List[Dict[str, str]] = []

    # Identify common brands available in both sets
    shared_brands = set(anchors_by_brand.keys()).intersection(set(positives_by_brand.keys()))

    if not shared_brands:
        logger.warning(
            "No overlapping brands between '%s' and '%s'. "
            "Generating simulated fallback entries so the pipeline is fully testable.",
            logos_dir,
            cropped_dir,
        )
        # Simulation mode: Allows the pipeline to produce a valid dataframe schema even
        # before the student populates the legitimate logos folder with all ministry assets.
        dummy_brands = ["kemenkeu", "bps", "pajak", "kominfo"]
        for brand in dummy_brands:
            for i in range(num_triplets_per_brand):
                neg_brand = rng.choice([b for b in dummy_brands if b != brand])
                triplet_records.append(
                    {
                        "anchor_path": str(logos_dir / f"{brand}.png"),
                        "positive_path": str(cropped_dir / f"{brand}_screenshot_{i}_crop0.png"),
                        "negative_path": str(logos_dir / f"{neg_brand}.png"),
                        "target_brand": brand,
                        "negative_brand": neg_brand,
                    }
                )
    else:
        all_negative_pool = list(anchors_by_brand.keys())

        for brand in shared_brands:
            candidate_anchors = anchors_by_brand[brand]
            candidate_positives = positives_by_brand[brand]
            other_brands = [b for b in all_negative_pool if b != brand]

            if not other_brands:
                logger.warning("Need at least 2 distinct brands to sample negative pairs. Skipping %s.", brand)
                continue

            for _ in range(num_triplets_per_brand):
                anchor = rng.choice(candidate_anchors)
                positive = rng.choice(candidate_positives)
                neg_brand = rng.choice(other_brands)
                negative = rng.choice(anchors_by_brand[neg_brand])

                triplet_records.append(
                    {
                        "anchor_path": str(anchor).replace("\\", "/"),
                        "positive_path": str(positive).replace("\\", "/"),
                        "negative_path": str(negative).replace("\\", "/"),
                        "target_brand": brand,
                        "negative_brand": neg_brand,
                    }
                )

    df_triplets = pd.DataFrame(triplet_records)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    df_triplets.to_csv(output_csv, index=False)
    logger.info("Successfully exported %d triplets to %s", len(df_triplets), output_csv)

    return df_triplets


# ---------------------------------------------------------------------------
# Execution Pipeline / Test Harness
# ---------------------------------------------------------------------------
def main() -> None:
    # Path configuration following thesis structure
    base_dir = Path(__file__).resolve().parent.parent
    screenshots_dir = base_dir / "data" / "raw" / "screenshots"
    logos_dir = base_dir / "data" / "raw" / "logos"
    cropped_dir = base_dir / "data" / "processed" / "cropped_logos"
    triplets_csv_path = base_dir / "data" / "processed" / "triplets.csv"

    # Ensure required directory structure exists
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    logos_dir.mkdir(parents=True, exist_ok=True)
    cropped_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 70)
    print("STAGE 1: LOGO EXTRACTION (YOLOv8)")
    print("=" * 70)

    # 1. Initialize detector (swap 'yolov8n.pt' with your custom checkpoint later)
    extractor = LogoExtractor(
        model_path="yolov8n.pt",
        conf_thresh=0.20,
        iou_thresh=0.45,
        save_top_k=2,
    )

    # 2. Run extraction over collected screenshots
    extraction_results = extractor.batch_extract(
        screenshots_dir=screenshots_dir,
        output_dir=cropped_dir,
    )

    total_crops = sum(len(crops) for crops in extraction_results.values())
    print(f"\nExtraction complete: {len(extraction_results)} screenshots processed, {total_crops} logo crops saved.")

    print("\n" + "=" * 70)
    print("STAGE 2: TRIPLET DATASET GENERATION")
    print("=" * 70)

    # 3. Generate Triplet DataFrame & CSV for Siamese Vision Transformer training
    df_triplets = generate_triplet_csv(
        logos_dir=logos_dir,
        cropped_dir=cropped_dir,
        output_csv=triplets_csv_path,
        num_triplets_per_brand=5,
        random_seed=42,  # Fixed seed for statistical reproducibility
    )

    print("\nSample Triplet Data (First 3 rows):")
    print(df_triplets.head(3).to_string())
    print("\n" + "=" * 70 + "\n")


if __name__ == "__main__":
    main()
