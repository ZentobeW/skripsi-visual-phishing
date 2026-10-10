"""
Synthetic Evasion & Background Augmentation Module.
Generates controlled, realistic simulated phishing logo crops for Siamese ViT training.

Simulated Attack Vectors:
1. Dynamic Web Header Compositing (Alpha-blending over typical navbars: White, Navy, Gray, Dark).
2. Aspect Ratio Warping (Simulates poor CSS layout implementation by phishers).
3. Low-Quality JPEG Quantization (Simulates degraded screenshot crops and re-compression).
4. Gaussian Blur & Pixel Perturbations (Simulates low-res captures & anti-scraping noise).
"""

import logging
from pathlib import Path
import random
from typing import List, Tuple

import cv2
import numpy as np
from PIL import Image

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("SyntheticAugmentor")


class SyntheticPhishingGenerator:
    """Generates synthetic phishing variants from high-resolution canonical logos."""

    def __init__(
        self,
        target_size: Tuple[int, int] = (224, 224),
        random_seed: int = 42,
    ) -> None:
        self.target_size = target_size
        self.rng = random.Random(random_seed)
        np.random.seed(random_seed)

        # Standard government/corporate web header background colors (RGB)
        self.header_backgrounds = [
            (255, 255, 255),  # Pure White
            (245, 247, 250),  # Light Off-White / Gov Portal Gray
            (26, 42, 74),     # Deep Navy Blue (Common for Ministries)
            (18, 18, 18),     # Modern Dark Mode Header
            (230, 235, 240),  # Soft Slate
        ]

    def _apply_background_composite(self, img_rgba: np.ndarray) -> np.ndarray:
        """Alpha-blends transparent logos onto typical web header colors."""
        if img_rgba.shape[2] < 4:
            # If image doesn't have alpha channel, wrap on light gray or white
            return img_rgba[:, :, :3]

        alpha = img_rgba[:, :, 3] / 255.0
        rgb = img_rgba[:, :, :3]

        bg_color = self.rng.choice(self.header_backgrounds)
        background = np.full_like(rgb, bg_color, dtype=np.uint8)

        # Alpha composite: Result = Alpha * Foreground + (1 - Alpha) * Background
        composite = (
            rgb * alpha[:, :, np.newaxis] + background * (1.0 - alpha[:, :, np.newaxis])
        ).astype(np.uint8)

        return composite

    def _apply_aspect_ratio_warp(self, img_bgr: np.ndarray) -> np.ndarray:
        """Simulates CSS distortions (bad aspect ratio scaling by phishers)."""
        h, w = img_bgr.shape[:2]
        # Stretch or squeeze width and height by 10% - 30%
        scale_x = self.rng.uniform(0.75, 1.25)
        scale_y = self.rng.uniform(0.75, 1.25)
        new_w = max(20, int(w * scale_x))
        new_h = max(20, int(h * scale_y))

        warped = cv2.resize(img_bgr, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        return warped

    def _apply_jpeg_compression(self, img_bgr: np.ndarray, quality: int) -> np.ndarray:
        """Simulates heavy JPEG re-compression artifacts typical of low-effort phishing kits."""
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
        _, encimg = cv2.imencode(".jpg", img_bgr, encode_param)
        decoded = cv2.imdecode(encimg, cv2.IMREAD_COLOR)
        return decoded

    def _apply_noise_and_blur(self, img_bgr: np.ndarray) -> np.ndarray:
        """Adds slight Gaussian blur and pixel noise."""
        # 50% probability of slight blur
        if self.rng.random() > 0.5:
            kernel_size = self.rng.choice([3, 5])
            img_bgr = cv2.GaussianBlur(img_bgr, (kernel_size, kernel_size), 0)

        # Subtle Gaussian noise (pixel disturbance)
        noise = np.random.normal(0, 4, img_bgr.shape).astype(np.int16)
        noisy_img = np.clip(img_bgr.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        return noisy_img

    def generate_variants(
        self,
        input_logo_path: Path,
        output_dir: Path,
        num_variants: int = 10,
    ) -> List[Path]:
        """
        Creates synthetic phishing logo crops from a single canonical logo.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        img_rgba = cv2.imread(str(input_logo_path), cv2.IMREAD_UNCHANGED)

        if img_rgba is None:
            logger.error("Could not read logo at: %s", input_logo_path)
            return []

        brand_name = input_logo_path.stem.lower()
        generated_paths: List[Path] = []

        for i in range(num_variants):
            # 1. Composite onto realistic web header background
            blended_rgb = self._apply_background_composite(img_rgba)

            # 2. Apply aspect ratio layout warping
            warped = self._apply_aspect_ratio_warp(blended_rgb)

            # 3. Add noise and blur
            noisy = self._apply_noise_and_blur(warped)

            # 4. Apply realistic JPEG compression (quality 30-70)
            quality = self.rng.randint(30, 70)
            degraded = self._apply_jpeg_compression(noisy, quality)

            # 5. Standardize to consistent crop patch
            final_crop = cv2.resize(degraded, self.target_size, interpolation=cv2.INTER_AREA)

            output_filename = f"{brand_name}_synthetic_variant_{i}_q{quality}.png"
            output_filepath = output_dir / output_filename
            cv2.imwrite(str(output_filepath), final_crop)
            generated_paths.append(output_filepath)

        logger.info("Generated %d synthetic variants for '%s'", len(generated_paths), brand_name)
        return generated_paths


def run_batch_synthesis(
    logos_dir: Path,
    output_dir: Path,
    variants_per_logo: int = 8,
) -> None:
    """Batch-processes all canonical logos into the synthetic phishing dataset."""
    valid_exts = {".png", ".jpg", ".jpeg", ".webp"}
    logo_files = [p for p in logos_dir.glob("*") if p.suffix.lower() in valid_exts]

    generator = SyntheticPhishingGenerator()
    total_generated = 0

    print("\n" + "=" * 75)
    print("STARTING SYNTHETIC PHISHING LOGO GENERATION")
    print("=" * 75)

    for logo_path in logo_files:
        variants = generator.generate_variants(
            input_logo_path=logo_path,
            output_dir=output_dir,
            num_variants=variants_per_logo,
        )
        total_generated += len(variants)

    print("=" * 75)
    print(f"COMPLETE: {total_generated} synthetic positive samples generated.")
    print(f"Output directory: {output_dir}")
    print("=" * 75 + "\n")


if __name__ == "__main__":
    BASE_DIR = Path(__file__).resolve().parent.parent
    LOGOS_DIR = BASE_DIR / "data" / "raw" / "logos"
    OUTPUT_DIR = BASE_DIR / "data" / "processed" / "cropped_logos"

    run_batch_synthesis(logos_dir=LOGOS_DIR, output_dir=OUTPUT_DIR, variants_per_logo=8)
