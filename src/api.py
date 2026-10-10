"""
FastAPI Threat Detection Inference Service for Visual Phishing.
Simulated Deployment for Government Cybersecurity Operations (Komdigi / Gov-CSIRT).

Pipeline:
1. Ingest screenshot via multipart form upload.
2. Detect and extract candidate brand logos using YOLOv8.
3. Compute deep metric embeddings using trained Siamese Vision Transformer (ViT-B/16).
4. Perform 1-to-N cosine distance comparison against pre-indexed official government logos.
5. Classify visual brand spoofing and compute threat verdict.
"""

from contextlib import asynccontextmanager
import logging
from pathlib import Path
import time
from typing import Any, Dict, List, Optional

import cv2
import numpy as np
from PIL import Image
import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision import models, transforms
from torchvision.models import ViT_B_16_Weights
from ultralytics import YOLO

from fastapi import FastAPI, File, HTTPException, Query, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("VisualPhishingAPI")

# Paths and configuration
import sys
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

MODELS_DIR = BASE_DIR / "models"
LOGOS_DIR = BASE_DIR / "data" / "raw" / "logos"

# Candidate weights files (prioritizes .pt then .pth)
SIAMESE_MODEL_PATH = (
    MODELS_DIR / "best_siamese_vit.pt"
    if (MODELS_DIR / "best_siamese_vit.pt").exists()
    else MODELS_DIR / "best_siamese_vit.pth"
)
YOLO_MODEL_PATH = "yolov8n.pt"


# ---------------------------------------------------------------------------
# 1. Siamese ViT Architecture
# ---------------------------------------------------------------------------
class SiameseViT(nn.Module):
    """Shared-weight Vision Transformer with metric projection head."""

    def __init__(self, embedding_dim: int = 128) -> None:
        super().__init__()
        # Initialize backbone structure without requiring online weights download during API boot
        self.backbone = models.vit_b_16(weights=None)
        in_features = self.backbone.heads.head.in_features

        self.backbone.heads = nn.Sequential(
            nn.Linear(in_features, 384),
            nn.GELU(),
            nn.Dropout(p=0.1),
            nn.Linear(384, embedding_dim),
        )

    def forward_one(self, x: torch.Tensor) -> torch.Tensor:
        """Extract and project embedding onto unit hypersphere (L2-normalized)."""
        features = self.backbone(x)
        return F.normalize(features, p=2, dim=1)


# Global in-memory cache for deep learning models and reference embeddings
state: Dict[str, Any] = {
    "device": torch.device("cuda" if torch.cuda.is_available() else "cpu"),
    "yolo_detector": None,
    "siamese_model": None,
    "reference_embeddings": {},  # Dict[brand_name, torch.Tensor]
    "vit_transforms": None,
}


def get_vit_transforms() -> transforms.Compose:
    """ImageNet standardization pipeline matching training preprocessing."""
    return transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225],
        ),
    ])


def load_siamese_weights(model_path: Path, device: torch.device) -> SiameseViT:
    """Load fine-tuned Siamese ViT state dictionary."""
    if not model_path.exists():
        logger.warning("Checkpoint %s not found. Initializing initialized architecture.", model_path)
        model = SiameseViT(embedding_dim=128).to(device)
        model.eval()
        return model

    logger.info("Loading Siamese ViT weights from: %s", model_path)
    checkpoint = torch.load(model_path, map_location=device)

    emb_dim = checkpoint.get("hyperparameters", {}).get("embedding_dim", 128)
    model = SiameseViT(embedding_dim=emb_dim).to(device)

    state_dict = checkpoint.get("model_state_dict", checkpoint)
    model.load_state_dict(state_dict)
    model.eval()
    return model


def precompute_reference_logos(
    model: SiameseViT,
    logos_dir: Path,
    transform: transforms.Compose,
    device: torch.device,
) -> Dict[str, torch.Tensor]:
    """Precompute and cache L2-normalized embeddings for canonical government logos."""
    valid_exts = {".png", ".jpg", ".jpeg", ".webp"}
    embeddings: Dict[str, torch.Tensor] = {}

    if not logos_dir.exists():
        logger.warning("Reference logos directory '%s' does not exist.", logos_dir)
        return embeddings

    logo_files = [p for p in logos_dir.glob("*") if p.suffix.lower() in valid_exts]
    logger.info("Pre-computing embeddings for %d official government logos...", len(logo_files))

    with torch.no_grad():
        for file_path in logo_files:
            brand_name = file_path.stem.lower()
            try:
                img = Image.open(file_path).convert("RGB")
                tensor = transform(img).unsqueeze(0).to(device)
                emb = model.forward_one(tensor)  # Shape: (1, embedding_dim)
                embeddings[brand_name] = emb.cpu()
                logger.info("-> Indexed reference logo: %s", brand_name)
            except Exception as exc:
                logger.error("Failed to index logo %s: %s", file_path.name, exc)

    return embeddings


# ---------------------------------------------------------------------------
# 2. FastAPI Application & Lifespan Management
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup & shutdown lifespan event handler.
    Loads YOLOv8, loads Siamese ViT, and precomputes reference embeddings once.
    """
    logger.info("=== Initializing Visual Phishing Detection Service ===")
    dev = state["device"]
    logger.info("Computation device: %s", dev)

    # 1. Load YOLOv8 Detector
    logger.info("Loading YOLO detector (%s)...", YOLO_MODEL_PATH)
    state["yolo_detector"] = YOLO(YOLO_MODEL_PATH)

    # 2. Load fine-tuned Siamese ViT
    state["vit_transforms"] = get_vit_transforms()
    state["siamese_model"] = load_siamese_weights(SIAMESE_MODEL_PATH, dev)

    # 3. Precompute Reference Logo Embeddings
    state["reference_embeddings"] = precompute_reference_logos(
        model=state["siamese_model"],
        logos_dir=LOGOS_DIR,
        transform=state["vit_transforms"],
        device=dev,
    )

    logger.info("=== Service Ready: %d Reference Logos Active ===", len(state["reference_embeddings"]))
    yield
    logger.info("=== Shutting down Visual Phishing Detection Service ===")


app = FastAPI(
    title="Visual Phishing Detection API (Komdigi / Gov-CSIRT Simulation)",
    description=(
        "Deep Learning service utilizing YOLOv8 and a Siamese Vision Transformer (ViT-B/16) "
        "to detect visual brand spoofing on suspect phishing web pages."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Standard CORS Middleware for Dashboard / Extension integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# 3. Request / Response Schemas
# ---------------------------------------------------------------------------
class BoundingBox(BaseModel):
    x1: int
    y1: int
    x2: int
    y2: int
    confidence: float


class AnalysisResponse(BaseModel):
    status: str = Field(..., description="'SUCCESS', 'NO_LOGO_DETECTED', or 'ERROR'")
    verdict: str = Field(..., description="'SUSPICIOUS_PHISHING', 'LEGITIMATE', or 'NO_BRAND_DETECTED'")
    detected_brand: Optional[str] = Field(None, description="Matched government brand name")
    cosine_distance: Optional[float] = Field(None, description="Cosine distance to closest reference logo [0.0 - 2.0]")
    similarity_score: Optional[float] = Field(None, description="Cosine similarity score [-1.0 to 1.0]")
    threshold_used: float = Field(..., description="Calibrated distance threshold applied")
    execution_time_ms: float = Field(..., description="Inference pipeline latency in milliseconds")
    bounding_box: Optional[BoundingBox] = None
    all_brand_distances: Dict[str, float] = Field(default_factory=dict, description="Pairwise distances across all indexed brands")
    message: str


# ---------------------------------------------------------------------------
# 4. API Endpoints
# ---------------------------------------------------------------------------
@app.get("/health", tags=["Monitoring"])
async def health_check() -> Dict[str, Any]:
    """Health and model readiness check."""
    return {
        "status": "HEALTHY",
        "device": str(state["device"]),
        "models_loaded": {
            "yolo_detector": state["yolo_detector"] is not None,
            "siamese_vit": state["siamese_model"] is not None,
        },
        "indexed_reference_brands": list(state["reference_embeddings"].keys()),
    }


@app.get("/brands", tags=["Threat Intelligence"])
async def list_indexed_brands() -> Dict[str, Any]:
    """List all official government brands currently registered in the database."""
    return {
        "count": len(state["reference_embeddings"]),
        "brands": list(state["reference_embeddings"].keys()),
    }


@app.post("/analyze_screenshot", response_model=AnalysisResponse, tags=["Inference"])
async def analyze_screenshot(
    file: UploadFile = File(..., description="Screenshot image file (PNG, JPG, WEBP)"),
    threshold: float = Query(
        0.35,
        ge=0.0,
        le=2.0,
        description="Cosine distance threshold. Distances below this value are classified as visual matches.",
    ),
    is_official_domain: bool = Query(
        False,
        description="Whether the visited website domain is verified as an official .go.id government portal.",
    ),
) -> AnalysisResponse:
    """
    Analyze a suspect web screenshot for visual phishing.

    Pipeline:
    1. Decode uploaded screenshot into OpenCV matrix.
    2. Run YOLOv8 to localize the brand logo bounding box.
    3. Crop candidate logo patch and extract Siamese ViT embedding.
    4. Compute minimum cosine distance against indexed government logos.
    5. Issue cybersecurity verdict: If an official government logo is rendered
       on an unauthorized domain, classify as 'SUSPICIOUS_PHISHING'.
    """
    start_time = time.perf_counter()

    # 1. Ingest and decode image
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img_bgr is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is not a valid or decodable image.",
        )

    h_img, w_img = img_bgr.shape[:2]

    # 2. YOLOv8 Logo Localization
    yolo: YOLO = state["yolo_detector"]
    yolo_results = yolo.predict(source=img_bgr, conf=0.15, verbose=False)

    if not yolo_results or len(yolo_results[0].boxes) == 0:
        elapsed = (time.perf_counter() - start_time) * 1000
        return AnalysisResponse(
            status="NO_LOGO_DETECTED",
            verdict="NO_BRAND_DETECTED",
            detected_brand=None,
            cosine_distance=None,
            similarity_score=None,
            threshold_used=threshold,
            execution_time_ms=round(elapsed, 2),
            bounding_box=None,
            all_brand_distances={},
            message="No candidate logos detected on the web screenshot.",
        )

    # Select the candidate box with the highest confidence
    boxes = yolo_results[0].boxes
    best_idx = int(torch.argmax(boxes.conf).item())
    best_box = boxes[best_idx]
    conf = float(best_box.conf[0])
    xyxy = best_box.xyxy[0].cpu().numpy()

    # Clip coordinates to image boundary
    x1 = max(0, int(round(xyxy[0])))
    y1 = max(0, int(round(xyxy[1])))
    x2 = min(w_img, int(round(xyxy[2])))
    y2 = min(h_img, int(round(xyxy[3])))

    bbox_data = BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2, confidence=round(conf, 4))

    # 3. Crop and transform candidate logo patch
    crop_bgr = img_bgr[y1:y2, x1:x2]
    crop_rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
    crop_pil = Image.fromarray(crop_rgb)

    transform = state["vit_transforms"]
    device = state["device"]
    siamese_model: SiameseViT = state["siamese_model"]

    input_tensor = transform(crop_pil).unsqueeze(0).to(device)

    # 4. Extract Query Embedding & Compute Pairwise Metric
    with torch.no_grad():
        query_emb = siamese_model.forward_one(input_tensor).cpu()  # Shape: (1, 128)

    ref_embeddings: Dict[str, torch.Tensor] = state["reference_embeddings"]

    if not ref_embeddings:
        elapsed = (time.perf_counter() - start_time) * 1000
        return AnalysisResponse(
            status="ERROR",
            verdict="NO_BRAND_DETECTED",
            detected_brand=None,
            cosine_distance=None,
            similarity_score=None,
            threshold_used=threshold,
            execution_time_ms=round(elapsed, 2),
            bounding_box=bbox_data,
            all_brand_distances={},
            message="No reference government logos currently indexed in the system.",
        )

    distances: Dict[str, float] = {}
    for brand, ref_emb in ref_embeddings.items():
        # Cosine distance = 1 - cosine_similarity.
        # Since vectors are L2-normalized: cosine_similarity = dot_product
        cosine_sim = float(torch.sum(query_emb * ref_emb).item())
        cosine_dist = max(0.0, 1.0 - cosine_sim)
        distances[brand] = round(cosine_dist, 4)

    # Identify closest matching brand
    best_brand = min(distances, key=distances.get)
    min_distance = distances[best_brand]
    similarity_score = round(1.0 - min_distance, 4)

    # 5. Security Decision Engine (Komdigi Phishing Triage)
    # If the visual distance is below threshold, a protected brand is visually present
    is_visual_match = min_distance <= threshold

    if is_visual_match:
        if is_official_domain:
            verdict = "LEGITIMATE"
            msg = f"Visual match for official '{best_brand.upper()}' brand verified on an authentic domain."
        else:
            verdict = "SUSPICIOUS_PHISHING"
            msg = (
                f"ALERT: Visual spoofing detected! Protected '{best_brand.upper()}' logo "
                f"is rendered on an unauthorized or suspect domain (Distance: {min_distance:.4f})."
            )
    else:
        verdict = "LEGITIMATE"
        msg = f"No protected government brand visual match identified (Closest: '{best_brand}', Distance: {min_distance:.4f})."

    elapsed = (time.perf_counter() - start_time) * 1000

    return AnalysisResponse(
        status="SUCCESS",
        verdict=verdict,
        detected_brand=best_brand if is_visual_match else None,
        cosine_distance=min_distance,
        similarity_score=similarity_score,
        threshold_used=threshold,
        execution_time_ms=round(elapsed, 2),
        bounding_box=bbox_data,
        all_brand_distances=distances,
        message=msg,
    )


# ---------------------------------------------------------------------------
# CLI Entrypoint for Local Testing
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    import uvicorn

    project_root = str(BASE_DIR)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    print("\nStarting Visual Phishing Detection API on http://127.0.0.1:8000...")
    print("Interactive OpenAPI Documentation: http://127.0.0.1:8000/docs\n")
    uvicorn.run(
        "src.api:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        app_dir=project_root,
    )
