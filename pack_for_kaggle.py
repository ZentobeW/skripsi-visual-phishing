"""
Kaggle Project Packager.
Bundles src/, data/ (logos, triplets, synthetics), and requirements.txt
into a lightweight zip file (~60MB) ready to upload to Kaggle or Google Colab.
"""

from pathlib import Path
import zipfile

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_ZIP = BASE_DIR / "skripsi_visual_phishing.zip"

INCLUDE_DIRS = [
    "src",
    "data/raw/logos",
    "data/processed/synthetic_logos",
    "data/processed/cropped_logos",
    "data/processed/adversarial_logos",
]

INCLUDE_FILES = [
    "data/processed/triplets.csv",
    "requirements.txt",
]

def create_kaggle_bundle():
    print(f"Creating Kaggle package: {OUTPUT_ZIP.name}...")
    with zipfile.ZipFile(OUTPUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        # Include specific files
        for f_str in INCLUDE_FILES:
            f_path = BASE_DIR / f_str
            if f_path.exists():
                zf.write(f_path, arcname=f_str)
                print(f"  + Added file: {f_str}")

        # Include specific directories
        for d_str in INCLUDE_DIRS:
            d_path = BASE_DIR / d_str
            if d_path.exists():
                count = 0
                for file_path in d_path.rglob("*"):
                    if file_path.is_file() and not file_path.name.startswith("."):
                        arcname = file_path.relative_to(BASE_DIR).as_posix()
                        zf.write(file_path, arcname=arcname)
                        count += 1
                print(f"  + Added folder: {d_str}/ ({count} files)")

    size_mb = OUTPUT_ZIP.stat().st_size / (1024 * 1024)
    print(f"\n[OK] Package created successfully!")
    print(f"Location : {OUTPUT_ZIP}")
    print(f"Size     : {size_mb:.2f} MB")

if __name__ == "__main__":
    create_kaggle_bundle()
