"""
Brand-Disjoint Triplet Dataset Generator.
Constructs publication-grade Metric Learning triplets (Anchor, Positive, Negative)
with strict Brand-Disjoint partitioning (Zero-Data-Leakage) for STIS thesis benchmark.

Partition Specification:
- Train (70%, 14 Brands): kemenkeu, kominfo, pajak, kemdikbud, kemenkes,
                          bpjs_kesehatan, bpjs_ketenagakerjaan, pln, pertamina,
                          bank_indonesia, kemendagri, kemlu, kemenkumham, mahkamah_agung.
- Val   (10%,  2 Brands): atrbpn, bmkg (used strictly for Neyman-Pearson calibration).
- Test  (20%,  4 Brands): bps, ojk, bssn, kejaksaan (Hold-out Zero-day evaluation).
"""

from collections import defaultdict
import logging
from pathlib import Path
import random
from typing import Dict, List
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("BrandDisjointBuilder")

BASE_DIR = Path(__file__).resolve().parent.parent
LOGOS_DIR = BASE_DIR / "data" / "raw" / "logos"
SYNTHETIC_DIR = BASE_DIR / "data" / "processed" / "synthetic_logos"
CROPPED_DIR = BASE_DIR / "data" / "processed" / "cropped_logos"
OUTPUT_CSV = BASE_DIR / "data" / "processed" / "triplets.csv"

# Strict Brand-Disjoint Partition Schema
BRAND_SPLITS = {
    "train": [
        "kemenkeu", "kominfo", "pajak", "kemdikbud", "kemenkes",
        "bpjs_kesehatan", "bpjs_ketenagakerjaan", "pln", "pertamina",
        "bank_indonesia", "kemendagri", "kemlu", "kemenkumham", "mahkamah_agung"
    ],
    "val": [
        "atrbpn", "bmkg"
    ],
    "test": [
        "bps", "ojk", "bssn", "kejaksaan"
    ]
}


def build_brand_disjoint_triplets(
    triplets_per_brand_train: int = 50,
    triplets_per_brand_val: int = 50,
    triplets_per_brand_test: int = 50,
    random_seed: int = 42
) -> pd.DataFrame:
    """Generates strictly disjoint triplets with zero leakage across train, val, and test."""
    rng = random.Random(random_seed)

    # 1. Index official anchor logos
    anchors_by_brand: Dict[str, Path] = {}
    for p in LOGOS_DIR.glob("*.png"):
        anchors_by_brand[p.stem] = p

    # 2. Index positive pools (synthetic variants + any cropped logos)
    positives_by_brand: Dict[str, List[Path]] = defaultdict(list)

    # Add synthetic evasion variants
    for p in SYNTHETIC_DIR.glob("*.png"):
        brand = p.stem.split("_syn_var_")[0]
        positives_by_brand[brand].append(p)

    # Add any detected crops if matching
    if CROPPED_DIR.exists():
        for p in CROPPED_DIR.glob("*.png"):
            for b in anchors_by_brand.keys():
                if p.stem.startswith(b):
                    positives_by_brand[b].append(p)
                    break

    logger.info(f"Indexed {len(anchors_by_brand)} official anchor brands.")
    for b, p_list in positives_by_brand.items():
        logger.info(f"  Brand '{b}': {len(p_list)} positive evasion variants.")

    triplet_records: List[Dict[str, str]] = []

    # 3. Sample triplets per partition
    split_targets = {
        "train": triplets_per_brand_train,
        "val": triplets_per_brand_val,
        "test": triplets_per_brand_test
    }

    for split_name, brand_list in BRAND_SPLITS.items():
        n_samples = split_targets[split_name]
        logger.info(f"Building partition '{split_name.upper()}' ({len(brand_list)} brands, {n_samples} triplets/brand)...")

        for brand in brand_list:
            if brand not in anchors_by_brand:
                logger.error(f"Missing anchor for brand: {brand}")
                continue

            anchor_path = anchors_by_brand[brand]
            pos_pool = positives_by_brand.get(brand, [anchor_path])

            # Negative pool must ONLY come from brands in the same split to avoid data leakage
            neg_brand_candidates = [b for b in brand_list if b != brand]
            if not neg_brand_candidates:
                logger.warning(f"No negative candidate in split '{split_name}' for brand '{brand}'.")
                continue

            for _ in range(n_samples):
                positive_path = rng.choice(pos_pool)
                neg_brand = rng.choice(neg_brand_candidates)
                negative_path = anchors_by_brand[neg_brand]

                rel_anchor = anchor_path.relative_to(BASE_DIR).as_posix()
                rel_positive = positive_path.relative_to(BASE_DIR).as_posix()
                rel_negative = negative_path.relative_to(BASE_DIR).as_posix()

                triplet_records.append({
                    "split": split_name,
                    "target_brand": brand,
                    "negative_brand": neg_brand,
                    "anchor_path": rel_anchor,
                    "positive_path": rel_positive,
                    "negative_path": rel_negative,
                })


    df = pd.DataFrame(triplet_records)
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_CSV, index=False)

    print("\n" + "=" * 75)
    print("BRAND-DISJOINT TRIPLET DATASET GENERATION SUMMARY")
    print("=" * 75)
    print(f"Total Triplets Generated : {len(df)}")
    print(f"Destination CSV          : {OUTPUT_CSV}")
    print("\nDistribution by Split:")
    print(df["split"].value_counts().to_string())
    print("\nBrands in Train Split (14) :", ", ".join(BRAND_SPLITS["train"]))
    print("Brands in Val Split   (2)  :", ", ".join(BRAND_SPLITS["val"]))
    print("Brands in Test Split  (4)  :", ", ".join(BRAND_SPLITS["test"]))
    print("=" * 75 + "\n")

    return df


if __name__ == "__main__":
    # Generates 50 per brand:
    # Train: 14 * 50 = 700 triplets
    # Val:    2 * 50 = 100 triplets
    # Test:   4 * 50 = 200 triplets
    # Total: 1,000 triplets!
    build_brand_disjoint_triplets(
        triplets_per_brand_train=50,
        triplets_per_brand_val=50,
        triplets_per_brand_test=50,
        random_seed=42
    )
