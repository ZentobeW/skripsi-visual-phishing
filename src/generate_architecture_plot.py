"""
Generate publication-quality system architecture figure for Bab 3.
Draws an end-to-end flowchart of the Visual Phishing Detection Pipeline:
Ingestion -> YOLOv8 -> Triplet/Evasion -> Siamese ViT Min-Max -> Inference API.
"""

from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.patches as patches

BASE_DIR = Path(__file__).resolve().parent.parent
FIGURES_DIR = BASE_DIR / "docs" / "figures"
FIGURES_DIR.mkdir(parents=True, exist_ok=True)
OUT_PATH = FIGURES_DIR / "fig3_1_system_architecture.png"


def draw_architecture_diagram():
    fig, ax = plt.subplots(figsize=(12, 7.5), dpi=300)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")

    # Background subtle styling
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor("#FFFFFF")

    # Title
    ax.text(
        50, 97,
        "Arsitektur Sistem Deteksi Visual Phishing dengan Siamese ViT & Adversarial Training",
        ha="center", va="top", fontsize=13, fontweight="bold", color="#1A2530", family="sans-serif"
    )

    # 4 Modular Panels / Stages
    panel_colors = ["#EBF5FB", "#E8F8F5", "#FEF9E7", "#F4ECF7"]
    panel_borders = ["#2980B9", "#16A085", "#D4AC0D", "#8E44AD"]
    stage_titles = [
        "TAHAP 1: AKUISISI & CRAWLER",
        "TAHAP 2: EKSTRAKSI & SINTESIS",
        "TAHAP 3: SIAMESE ViT MIN-MAX",
        "TAHAP 4: INFERENSI & API"
    ]

    xs = [4, 28, 52, 76]
    w = 20
    h = 84
    y = 8

    for i in range(4):
        # Panel Background
        rect = patches.FancyBboxPatch(
            (xs[i], y), w, h,
            boxstyle="round,pad=0.8,rounding_size=2",
            facecolor=panel_colors[i], edgecolor=panel_borders[i],
            linewidth=1.5, alpha=0.85
        )
        ax.add_patch(rect)

        # Header Badge
        badge = patches.FancyBboxPatch(
            (xs[i] + 1, y + h - 6), w - 2, 5,
            boxstyle="round,pad=0.2,rounding_size=1",
            facecolor=panel_borders[i], edgecolor="none"
        )
        ax.add_patch(badge)
        ax.text(
            xs[i] + w/2, y + h - 3.5,
            stage_titles[i],
            ha="center", va="center", fontsize=8.5, fontweight="bold", color="#FFFFFF", family="sans-serif"
        )

    # Content Boxes Helper
    def add_box(x, y, width, height, title, subtitle="", bgcolor="#FFFFFF", border="#BDC3C7"):
        b = patches.FancyBboxPatch(
            (x, y), width, height,
            boxstyle="round,pad=0.4,rounding_size=1.2",
            facecolor=bgcolor, edgecolor=border, linewidth=1.2
        )
        ax.add_patch(b)
        if subtitle:
            ax.text(x + width/2, y + height*0.65, title, ha="center", va="center", fontsize=8, fontweight="bold", color="#2C3E50")
            ax.text(x + width/2, y + height*0.28, subtitle, ha="center", va="center", fontsize=7, color="#566573")
        else:
            ax.text(x + width/2, y + height/2, title, ha="center", va="center", fontsize=8, fontweight="bold", color="#2C3E50")

    # Connectors Helper
    def add_arrow(x1, y1, x2, y2, color="#34495E"):
        ax.annotate(
            "", xy=(x2, y2), xytext=(x1, y1),
            arrowprops=dict(arrowstyle="->", color=color, lw=1.5, shrinkA=2, shrinkB=2)
        )

    # Stage 1 Items
    add_box(6, 70, 16, 9, "Threat Intel Feeds", "OpenPhish & PhishTank", bgcolor="#FFFFFF", border="#2980B9")
    add_arrow(14, 70, 14, 62, color="#2980B9")
    add_box(6, 53, 16, 9, "Sandbox Crawler", "Playwright (Render Delay 3s)", bgcolor="#FFFFFF", border="#2980B9")
    add_arrow(14, 53, 14, 45, color="#2980B9")
    add_box(6, 36, 16, 9, "Full-Page Screenshot", "1920x1080 Headless Viewport", bgcolor="#FFFFFF", border="#2980B9")

    add_box(6, 17, 16, 11, "Pangkalan Data Resmi", "Logo Legal Kem/Lembaga RI\n(Anchor & Negative Pool)", bgcolor="#FFFFFF", border="#2980B9")

    # Arrow Stage 1 -> Stage 2
    add_arrow(22, 40.5, 30, 74.5, color="#27AE60")
    add_arrow(22, 22.5, 30, 22.5, color="#27AE60")

    # Stage 2 Items
    add_box(30, 70, 16, 9, "Detektor YOLOv8", "Pelokalan Bounding Box Logo", bgcolor="#FFFFFF", border="#16A085")
    add_arrow(38, 70, 38, 62, color="#16A085")
    add_box(30, 53, 16, 9, "Logo Crop Candidates", "Pemotongan Area Kandidat", bgcolor="#FFFFFF", border="#16A085")
    add_arrow(38, 53, 38, 45, color="#16A085")
    add_box(30, 36, 16, 9, "Synthetic Evasion", "Alpha Blending + JPEG Noise", bgcolor="#FFFFFF", border="#16A085")
    add_arrow(38, 36, 38, 28, color="#16A085")
    add_box(30, 17, 16, 11, "Triplet Dataset Builder", "(Anchor, Positive, Negative)\nBrand-Disjoint Partition", bgcolor="#FFFFFF", border="#16A085")

    # Arrow Stage 2 -> Stage 3
    add_arrow(46, 22.5, 54, 74.5, color="#D4AC0D")

    # Stage 3 Items
    add_box(54, 70, 16, 9, "Siamese ViT-B/16", "Shared Weight Backbone", bgcolor="#FFFFFF", border="#D4AC0D")
    add_arrow(62, 70, 62, 62, color="#D4AC0D")
    add_box(54, 53, 16, 9, "Inner Maximization", "PGD Perturbation (eps=8/255)", bgcolor="#FDF2E9", border="#E67E22")
    add_arrow(62, 53, 62, 45, color="#D4AC0D")
    add_box(54, 36, 16, 9, "Triplet Margin Loss", "L2-Normalized Embedding 128-D", bgcolor="#FFFFFF", border="#D4AC0D")
    add_arrow(62, 36, 62, 28, color="#D4AC0D")
    add_box(54, 17, 16, 11, "Outer Minimization", "Pembaruan Bobot via AdamW\n(Min-Max Optimization)", bgcolor="#FFFFFF", border="#D4AC0D")

    # Arrow Stage 3 -> Stage 4
    add_arrow(70, 22.5, 78, 74.5, color="#8E44AD")

    # Stage 4 Items
    add_box(78, 70, 16, 9, "Kalibrasi Threshold", "Neyman-Pearson (FPR <= 1%)", bgcolor="#FFFFFF", border="#8E44AD")
    add_arrow(86, 70, 86, 62, color="#8E44AD")
    add_box(78, 53, 16, 9, "RAM Vector Index", "Precomputed Official Logos", bgcolor="#FFFFFF", border="#8E44AD")
    add_arrow(86, 53, 86, 45, color="#8E44AD")
    add_box(78, 36, 16, 9, "FastAPI Microservice", "POST /analyze_screenshot", bgcolor="#FFFFFF", border="#8E44AD")
    add_arrow(86, 36, 86, 28, color="#8E44AD")
    add_box(78, 17, 16, 11, "Vonis Keamanan SOC", "Cosine Distance vs tau*\n[PHISHING / LEGITIMATE]", bgcolor="#FDEDEC", border="#C0392B")

    plt.tight_layout()
    plt.savefig(str(OUT_PATH), dpi=300, bbox_inches="tight")
    plt.close()
    print(f"[SUCCESS] Architecture diagram generated: {OUT_PATH}")


if __name__ == "__main__":
    draw_architecture_diagram()
