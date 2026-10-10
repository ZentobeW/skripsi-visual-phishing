"""
Synthetic Evasion Dataset Generator for Visual Phishing Detection.
Constructs realistic, degraded, and composited logo crops using pure OpenCV (cv2) and NumPy.

Mathematical & Computer Vision Principles:
1. Alpha-compositing (Porter-Duff 'over' operator) for RGBA onto BGR canvases.
2. Aspect-ratio preserving affine scaling with bilinear/area resampling.
3. Quantization degradation via lossy JPEG discrete cosine transform (DCT) encoding/decoding.
4. Linear spatial filtering via 2D Gaussian kernel convolution.
"""

import logging
from pathlib import Path
import random
from typing import List, Optional, Tuple

import cv2
import numpy as np

# Structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("SyntheticEvasion")

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
LOGOS_DIR = BASE_DIR / "data" / "raw" / "logos"
OUTPUT_DIR = BASE_DIR / "data" / "processed" / "synthetic_logos"


class SyntheticEvasionGenerator:
    """Generates synthetic phishing variants from canonical government logos."""

    def __init__(
        self,
        canvas_size: Tuple[int, int] = (224, 224),
        random_seed: int = 42,
    ) -> None:
        """
        Args:
            canvas_size: Fixed (width, height) dimensions matching ViT input standards.
            random_seed: Seed for reproducible dataset generation.
        """
        self.canvas_w, self.canvas_h = canvas_size
        self.rng = random.Random(random_seed)
        np.random.seed(random_seed)

        # Predefined header background colors (OpenCV uses BGR format)
        # Format: (B, G, R)
        self.header_palette = {
            "white": np.array([255, 255, 255], dtype=np.uint8),
            "light_gray": np.array([245, 242, 240], dtype=np.uint8),   # Typical government portal background
            "navy_blue": np.array([67, 32, 15], dtype=np.uint8),       # Institutional navy (RGB: 15, 32, 67)
            "black": np.array([0, 0, 0], dtype=np.uint8),
            "dark_gray": np.array([41, 37, 33], dtype=np.uint8),       # Modern dark-mode navbar
        }

    def _create_background_canvas(self) -> np.ndarray:
        """Generates a blank 3-channel BGR canvas filled with a sampled palette color."""
        color_name = self.rng.choice(list(self.header_palette.keys()))
        bgr_color = self.header_palette[color_name]

        # Allocate (H, W, 3) matrix
        canvas = np.full((self.canvas_h, self.canvas_w, 3), bgr_color, dtype=np.uint8)
        return canvas

    def _scale_logo(self, logo_rgba: np.ndarray) -> np.ndarray:
        """
        Rescales logo while strictly maintaining its original aspect ratio.
        Scale factor is chosen randomly between 50% and 90% of the canvas.
        """
        orig_h, orig_w = logo_rgba.shape[:2]

        # Scale factor relative to maximum canvas dimension
        scale_ratio = self.rng.uniform(0.50, 0.90)
        max_allowed_w = int(self.canvas_w * scale_ratio)
        max_allowed_h = int(self.canvas_h * scale_ratio)

        # Compute scaling factor preserving aspect ratio (w / h)
        scale = min(max_allowed_w / orig_w, max_allowed_h / orig_h)
        new_w = max(10, int(round(orig_w * scale)))
        new_h = max(10, int(round(orig_h * scale)))

        # Choose decimation/interpolation algorithm based on scale
        interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
        scaled = cv2.resize(logo_rgba, (new_w, new_h), interpolation=interp)
        return scaled

    def _compute_placement_coordinates(
        self,
        logo_w: int,
        logo_h: int,
        strategy: str = "random",
    ) -> Tuple[int, int]:
        """
        Determines the (x, y) top-left anchor coordinate on the canvas.
        Strategies: 'center', 'left', 'right', 'random'.
        """
        max_x = max(0, self.canvas_w - logo_w)
        max_y = max(0, self.canvas_h - logo_h)

        if strategy == "center":
            x = max_x // 2
            y = max_y // 2
        elif strategy == "left":
            x = min(10, max_x)
            y = max_y // 2
        elif strategy == "right":
            x = max(0, max_x - 10)
            y = max_y // 2
        else:  # random offset within boundaries
            x = self.rng.randint(0, max_x) if max_x > 0 else 0
            y = self.rng.randint(0, max_y) if max_y > 0 else 0

        return x, y

    def _alpha_blend_overlay(
        self,
        canvas_bgr: np.ndarray,
        logo_rgba: np.ndarray,
        x: int,
        y: int,
    ) -> np.ndarray:
        """
        Mathematically rigorous Alpha Blending (Porter-Duff 'over' compositing).

        Formula:
            I_out = alpha * I_foreground + (1.0 - alpha) * I_background
        where alpha in [0.0, 1.0].
        """
        logo_h, logo_w = logo_rgba.shape[:2]

        # Extract Region of Interest (ROI) from background canvas
        roi = canvas_bgr[y : y + logo_h, x : x + logo_w]

        # Separate color channels (BGR) and normalized alpha channel (A)
        logo_bgr = logo_rgba[:, :, :3].astype(np.float32)

        if logo_rgba.shape[2] == 4:
            alpha = (logo_rgba[:, :, 3].astype(np.float32) / 255.0)[:, :, np.newaxis]
        else:
            # Fallback if image lacks alpha channel
            alpha = np.ones((logo_h, logo_w, 1), dtype=np.float32)

        roi_float = roi.astype(np.float32)

        # Vectorized Alpha Blending
        blended = (alpha * logo_bgr) + ((1.0 - alpha) * roi_float)

        # Clip values to [0, 255] and cast back to uint8
        canvas_bgr[y : y + logo_h, x : x + logo_w] = np.clip(blended, 0, 255).astype(np.uint8)
        return canvas_bgr

    def _apply_jpeg_compression_artifacts(
        self,
        img_bgr: np.ndarray,
        quality: int,
    ) -> np.ndarray:
        """
        Simulates lossy JPEG Discrete Cosine Transform (DCT) block quantization artifacts.
        Compresses image in-memory and decodes it back.
        """
        encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)]
        success, encoded_buffer = cv2.imencode(".jpg", img_bgr, encode_params)

        if not success:
            logger.warning("In-memory JPEG encoding failed. Returning original image.")
            return img_bgr

        decoded_bgr = cv2.imdecode(encoded_buffer, cv2.IMREAD_COLOR)
        return decoded_bgr

    def _apply_gaussian_blur(
        self,
        img_bgr: np.ndarray,
        kernel_size: int = 3,
    ) -> np.ndarray:
        """Applies Gaussian spatial smoothing to simulate low-resolution screen captures."""
        # Kernel dimensions must be positive odd integers
        k = kernel_size if kernel_size % 2 != 0 else kernel_size + 1
        return cv2.GaussianBlur(img_bgr, (k, k), sigmaX=0)

    def generate_synthetic_variant(
        self,
        logo_rgba: np.ndarray,
    ) -> np.ndarray:
        """
        Generates a single synthetic phishing logo patch:
        1. Background canvas creation.
        2. Affine scaling.
        3. Alpha compositing.
        4. Gaussian blur & JPEG degradation.
        """
        # 1. Canvas
        canvas = self._create_background_canvas()

        # 2. Rescale logo
        scaled_logo = self._scale_logo(logo_rgba)
        s_h, s_w = scaled_logo.shape[:2]

        # 3. Placement
        placement_mode = self.rng.choice(["center", "left", "right", "random"])
        pos_x, pos_y = self._compute_placement_coordinates(s_w, s_h, strategy=placement_mode)

        # 4. Alpha Blending
        composited = self._alpha_blend_overlay(canvas, scaled_logo, pos_x, pos_y)

        # 5. Visual Degradations (Simulated Carelessness / Evasion)
        # A. Random Gaussian blur (50% probability)
        if self.rng.random() > 0.40:
            k_size = self.rng.choice([3, 5])
            composited = self._apply_gaussian_blur(composited, kernel_size=k_size)

        # B. Lossy JPEG compression (Quality: 25 - 65)
        quality = self.rng.randint(25, 65)
        degraded = self._apply_jpeg_compression_artifacts(composited, quality=quality)

        return degraded

    def process_all_logos(
        self,
        input_dir: Path,
        output_dir: Path,
        variations_per_logo: int = 8,
    ) -> int:
        """
        Batch processor: Generates variations for every valid .png in input_dir.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        logo_files = sorted([p for p in input_dir.glob("*.png")])

        if not logo_files:
            logger.error("No .png files found in %s", input_dir)
            return 0

        logger.info("Found %d canonical logo(s) in %s", len(logo_files), input_dir)
        total_created = 0

        for file_path in logo_files:
            brand_name = file_path.stem.lower()

            # Must load image with cv2.IMREAD_UNCHANGED to preserve 4th alpha channel
            logo_rgba = cv2.imread(str(file_path), cv2.IMREAD_UNCHANGED)

            if logo_rgba is None:
                logger.error("Failed to load %s via cv2.", file_path.name)
                continue

            # Ensure image has an alpha channel; if 3-channel, synthesize an opaque alpha channel
            if logo_rgba.ndim == 2:
                # Grayscale to BGRA
                logo_rgba = cv2.cvtColor(logo_rgba, cv2.COLOR_GRAY2BGRA)
            elif logo_rgba.shape[2] == 3:
                # BGR to BGRA with 255 alpha
                b, g, r = cv2.split(logo_rgba)
                alpha = np.full(b.shape, 255, dtype=np.uint8)
                logo_rgba = cv2.merge([b, g, r, alpha])

            logger.info("Processing '%s' (Original shape: %s)...", brand_name, logo_rgba.shape)

            for idx in range(variations_per_logo):
                synthetic_img = self.generate_synthetic_variant(logo_rgba)

                output_filename = f"{brand_name}_syn_var_{idx:02d}.png"
                output_filepath = output_dir / output_filename

                cv2.imwrite(str(output_filepath), synthetic_img)
                total_created += 1

        logger.info(
            "Batch generation complete. Successfully created %d synthetic logos in %s",
            total_created,
            output_dir,
        )
        return total_created


# ---------------------------------------------------------------------------
# CLI Execution
# ---------------------------------------------------------------------------
def main() -> None:
    generator = SyntheticEvasionGenerator(
        canvas_size=(224, 224),
        random_seed=42,
    )

    print("\n" + "=" * 75)
    print("STARTING SYNTHETIC EVASION DATASET GENERATION (cv2 & numpy)")
    print("=" * 75)

    count = generator.process_all_logos(
        input_dir=LOGOS_DIR,
        output_dir=OUTPUT_DIR,
        variations_per_logo=25,  # Generates 25 realistic evasion variations per government logo
    )

    print("=" * 75)
    print(f"Total Synthetic Variations Generated : {count}")
    print(f"Destination Directory                 : {OUTPUT_DIR}")
    print("=" * 75 + "\n")


if __name__ == "__main__":
    main()
