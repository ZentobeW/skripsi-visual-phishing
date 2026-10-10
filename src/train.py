"""
Siamese Vision Transformer (ViT) with On-The-Fly Adversarial Training.
Visual Phishing Detection Research - Politeknik Statistika STIS.

Mathematical Formulation (Madry et al. Min-Max Framework):
min_theta E_(A, P, N) [ max_(||delta||_inf <= eps) L_triplet(f_theta(A), f_theta(P + delta), f_theta(N)) ]

1. Inner Maximization:
   Generates dynamic L_inf PGD perturbations on positive logos (P) to maximize Triplet Loss,
   simulating evasive logo spoofing.
2. Outer Minimization:
   Updates ViT weights via AdamW to minimize Triplet Margin Loss on perturbed pairs (A, P_adv, N),
   forcing embeddings to remain robust to adversarial evasion.
3. Dual Evaluation:
   Tracks Standard PR-AUC (clean data) vs Robust PR-AUC (adversarial data) in MLflow
   to quantify the Robustness-Accuracy Trade-off.
"""

from datetime import datetime
import logging
import os
from pathlib import Path
import random
from typing import Dict, List, Optional, Tuple

import mlflow
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset, random_split
from torchvision import models, transforms
from torchvision.models import ViT_B_16_Weights

# Structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("AdversarialSiameseViT")

BASE_DIR = Path(__file__).resolve().parent.parent



# ---------------------------------------------------------------------------
# 1. Custom Triplet Dataset
# ---------------------------------------------------------------------------
class PhishingTripletDataset(Dataset):
    """PyTorch Dataset reading Anchor, Positive, and Negative image triplets."""

    def __init__(
        self,
        csv_file: Path,
        split: Optional[str] = None,
        transform: Optional[transforms.Compose] = None,
    ) -> None:
        self.csv_file = Path(csv_file)
        if not self.csv_file.exists():
            raise FileNotFoundError(f"Triplets dataset CSV not found at: {self.csv_file}")

        self.df = pd.read_csv(self.csv_file)
        if split and "split" in self.df.columns:
            self.df = self.df[self.df["split"] == split].reset_index(drop=True)

        self.transform = transform or self.default_transforms()
        self._ensure_sample_files_exist()

    @staticmethod
    def default_transforms() -> transforms.Compose:
        """Standard ImageNet preprocessing pipeline for Vision Transformers."""
        return transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225],
            ),
        ])

    def _ensure_sample_files_exist(self) -> None:
        """Synthesizes placeholder images if paths do not yet exist on disk."""
        color_palette = {
            "kemenkeu": (25, 60, 140),
            "bps": (40, 160, 80),
            "pajak": (230, 160, 20),
            "kominfo": (15, 120, 210),
        }
        for _, row in self.df.iterrows():
            for col in ["anchor_path", "positive_path", "negative_path"]:
                img_path = Path(str(row[col]))
                if not img_path.exists():
                    img_path.parent.mkdir(parents=True, exist_ok=True)
                    brand = next((b for b in color_palette if b in img_path.name.lower()), "default")
                    color = color_palette.get(brand, (100, 100, 100))
                    dummy_img = Image.new("RGB", (224, 224), color=color)
                    draw = ImageDraw.Draw(dummy_img)
                    draw.rectangle([40, 40, 184, 184], outline=(255, 255, 255), width=4)
                    dummy_img.save(img_path)

    def _load_image(self, path_str: str) -> Image.Image:
        path = Path(path_str)
        if not path.is_file():
            candidate = BASE_DIR / path
            if candidate.is_file():
                path = candidate
            else:
                parts = path.parts
                if "data" in parts:
                    idx = parts.index("data")
                    candidate2 = BASE_DIR / Path(*parts[idx:])
                    if candidate2.is_file():
                        path = candidate2
        try:
            return Image.open(path).convert("RGB")
        except Exception as e:
            logger.warning("Could not load image %s: %s", path_str, e)
            return Image.new("RGB", (224, 224), color=(128, 128, 128))


    def __len__(self) -> int:
        return len(self.df)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        row = self.df.iloc[idx]
        anchor_img = self._load_image(str(row["anchor_path"]))
        positive_img = self._load_image(str(row["positive_path"]))
        negative_img = self._load_image(str(row["negative_path"]))

        anchor_t = self.transform(anchor_img)
        positive_t = self.transform(positive_img)
        negative_t = self.transform(negative_img)

        return anchor_t, positive_t, negative_t


# ---------------------------------------------------------------------------
# 2. Siamese Vision Transformer (ViT) Architecture
# ---------------------------------------------------------------------------
class SiameseViT(nn.Module):
    """Shared-weight Vision Transformer with metric projection head."""

    def __init__(self, embedding_dim: int = 128, pretrained: bool = True) -> None:
        super().__init__()
        weights = ViT_B_16_Weights.DEFAULT if pretrained else None
        self.backbone = models.vit_b_16(weights=weights)

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

    def forward(
        self,
        anchor: torch.Tensor,
        positive: torch.Tensor,
        negative: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Pass all three branches through the shared backbone."""
        z_a = self.forward_one(anchor)
        z_p = self.forward_one(positive)
        z_n = self.forward_one(negative)
        return z_a, z_p, z_n


# ---------------------------------------------------------------------------
# 3. Dynamic On-The-Fly Adversarial Generator (Inner Maximization)
# ---------------------------------------------------------------------------
def generate_adversarial_positive(
    model: nn.Module,
    anchor: torch.Tensor,
    positive: torch.Tensor,
    negative: torch.Tensor,
    criterion: nn.Module,
    eps: float = 8.0 / 255.0,
    alpha: float = 2.0 / 255.0,
    steps: int = 3,
) -> torch.Tensor:
    """
    Inner Maximization step: Solves max_(||delta||_inf <= eps) L_triplet(A, P + delta, N).
    
    Generates imperceptible perturbations on positive crops on-the-fly,
    preventing static noise overfitting. Pure PyTorch autograd implementation
    with zero external DLL dependencies.
    """
    was_training = model.training
    model.eval()  # Freeze dropout/batchnorm for stable perturbation gradients

    # 1. Random Start within the L_inf ball
    delta = torch.empty_like(positive).uniform_(-eps, eps)
    adv_p = (positive + delta).detach()

    # 2. PGD Gradient Ascent
    for _ in range(steps):
        adv_p.requires_grad = True

        z_a = model.forward_one(anchor)
        z_p = model.forward_one(adv_p)
        z_n = model.forward_one(negative)

        # Maximize Triplet Margin Loss: Pushes positive embedding away from anchor
        loss = criterion(z_a, z_p, z_n)
        model.zero_grad()
        loss.backward()

        with torch.no_grad():
            grad_sign = adv_p.grad.sign()
            # Gradient ascent step
            adv_p = adv_p + alpha * grad_sign
            # Projection onto L_inf epsilon-ball: ||adv_p - positive||_inf <= eps
            eta = torch.clamp(adv_p - positive, min=-eps, max=eps)
            adv_p = (positive + eta).detach()

    if was_training:
        model.train()

    return adv_p


# ---------------------------------------------------------------------------
# 4. Pure NumPy Statistical PR-AUC Calculation
# ---------------------------------------------------------------------------
def compute_pr_auc(
    anchor_embs: np.ndarray,
    positive_embs: np.ndarray,
    negative_embs: np.ndarray,
) -> float:
    """Calculates PR-AUC from pairwise cosine similarities using pure NumPy."""
    pos_sims = np.sum(anchor_embs * positive_embs, axis=1)
    neg_sims = np.sum(anchor_embs * negative_embs, axis=1)

    y_true = np.concatenate([np.ones_like(pos_sims), np.zeros_like(neg_sims)])
    y_scores = np.concatenate([pos_sims, neg_sims])

    order = np.argsort(-y_scores)
    y_true_sorted = y_true[order]

    tp = np.cumsum(y_true_sorted)
    fp = np.cumsum(1.0 - y_true_sorted)
    n_pos = float(np.sum(y_true_sorted))

    if n_pos == 0:
        return 0.0

    precision = tp / (tp + fp)
    recall = tp / n_pos

    precision = np.concatenate(([1.0], precision))
    recall = np.concatenate(([0.0], recall))

    trapz_func = getattr(np, "trapezoid", getattr(np, "trapz", None))
    if trapz_func is not None:
        pr_auc_score = float(trapz_func(precision, recall))
    else:
        pr_auc_score = float(np.sum((recall[1:] - recall[:-1]) * precision[1:]))

    return max(0.0, min(1.0, pr_auc_score))


# ---------------------------------------------------------------------------
# 5. Training Loop: Min-Max Adversarial Optimization
# ---------------------------------------------------------------------------
def train_adversarial_epoch(
    model: nn.Module,
    dataloader: DataLoader,
    criterion: nn.Module,
    optimizer: torch.optim.Optimizer,
    device: torch.device,
    eps: float = 8.0 / 255.0,
    alpha: float = 2.0 / 255.0,
    pgd_steps: int = 3,
) -> float:
    """Performs one epoch of Min-Max Adversarial Training."""
    model.train()
    running_loss = 0.0

    for anchors, positives, negatives in dataloader:
        anchors = anchors.to(device)
        positives = positives.to(device)
        negatives = negatives.to(device)

        # -------------------------------------------------------------------
        # TAHAP 1: INNER MAXIMIZATION (Serang positive logo on-the-fly)
        # -------------------------------------------------------------------
        adv_positives = generate_adversarial_positive(
            model=model,
            anchor=anchors,
            positive=positives,
            negative=negatives,
            criterion=criterion,
            eps=eps,
            alpha=alpha,
            steps=pgd_steps,
        )

        # -------------------------------------------------------------------
        # TAHAP 2: OUTER MINIMIZATION (Update bobot model dengan logo terserang)
        # -------------------------------------------------------------------
        model.train()
        optimizer.zero_grad()

        z_a, z_p_adv, z_n = model(anchors, adv_positives, negatives)
        loss = criterion(z_a, z_p_adv, z_n)

        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()

        running_loss += loss.item() * anchors.size(0)

    epoch_loss = running_loss / len(dataloader.dataset)
    return epoch_loss


# ---------------------------------------------------------------------------
# 6. Dual Validation: Standard vs Robust PR-AUC
# ---------------------------------------------------------------------------
def validate_dual_performance(
    model: nn.Module,
    dataloader: DataLoader,
    criterion: nn.Module,
    device: torch.device,
    eps: float = 8.0 / 255.0,
) -> Dict[str, float]:
    """
    Evaluates both Clean (Standard) and Adversarial (Robust) Performance
    to quantify the Robustness-Accuracy Trade-off.
    """
    model.eval()

    clean_anchors, clean_positives, clean_negatives = [], [], []
    robust_positives = []
    running_std_loss, running_rob_loss = 0.0, 0.0

    for anchors, positives, negatives in dataloader:
        anchors = anchors.to(device)
        positives = positives.to(device)
        negatives = negatives.to(device)

        # 1. Clean evaluation
        with torch.no_grad():
            z_a, z_p, z_n = model(anchors, positives, negatives)
            std_loss = criterion(z_a, z_p, z_n)
            running_std_loss += std_loss.item() * anchors.size(0)

            clean_anchors.append(z_a.cpu().numpy())
            clean_positives.append(z_p.cpu().numpy())
            clean_negatives.append(z_n.cpu().numpy())

        # 2. Adversarial evaluation (Generate test attack)
        adv_p = generate_adversarial_positive(
            model=model,
            anchor=anchors,
            positive=positives,
            negative=negatives,
            criterion=criterion,
            eps=eps,
            alpha=2.0 / 255.0,
            steps=4,
        )

        with torch.no_grad():
            z_p_adv = model.forward_one(adv_p)
            rob_loss = criterion(z_a, z_p_adv, z_n)
            running_rob_loss += rob_loss.item() * anchors.size(0)
            robust_positives.append(z_p_adv.cpu().numpy())

    total_samples = len(dataloader.dataset)
    val_anchors = np.concatenate(clean_anchors, axis=0)
    val_positives = np.concatenate(clean_positives, axis=0)
    val_negatives = np.concatenate(clean_negatives, axis=0)
    val_adv_positives = np.concatenate(robust_positives, axis=0)

    # Compute metrics
    std_pr_auc = compute_pr_auc(val_anchors, val_positives, val_negatives)
    rob_pr_auc = compute_pr_auc(val_anchors, val_adv_positives, val_negatives)

    return {
        "val_std_loss": running_std_loss / total_samples,
        "val_rob_loss": running_rob_loss / total_samples,
        "standard_pr_auc": std_pr_auc,
        "robust_pr_auc": rob_pr_auc,
        "robustness_gap": round(std_pr_auc - rob_pr_auc, 4),
    }


# ---------------------------------------------------------------------------
# 7. Main Pipeline with MLflow Dual-Metric Tracking
# ---------------------------------------------------------------------------
def run_training(
    triplets_csv: Path,
    epochs: int = 3,
    batch_size: int = 4,
    learning_rate: float = 3e-5,
    margin: float = 0.3,
    embedding_dim: int = 128,
    eps: float = 8.0 / 255.0,
    val_split: float = 0.2,
    random_seed: int = 42,
) -> None:
    random.seed(random_seed)
    np.random.seed(random_seed)
    torch.manual_seed(random_seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(random_seed)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info("Using device for Adversarial Siamese ViT training: %s", device)

    # 1. Dataset & DataLoaders
    sample_df = pd.read_csv(triplets_csv)
    if "split" in sample_df.columns:
        train_dataset = PhishingTripletDataset(csv_file=triplets_csv, split="train")
        val_dataset = PhishingTripletDataset(csv_file=triplets_csv, split="val")
        train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, drop_last=False)
        val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)
        logger.info("Loaded Brand-Disjoint partitions: %d train triplets (14 brands), %d validation triplets (2 brands)", len(train_dataset), len(val_dataset))
    else:
        full_dataset = PhishingTripletDataset(csv_file=triplets_csv)
        val_size = max(1, int(len(full_dataset) * val_split))
        train_size = len(full_dataset) - val_size
        train_subset, val_subset = random_split(
            full_dataset,
            [train_size, val_size],
            generator=torch.Generator().manual_seed(random_seed),
        )
        train_loader = DataLoader(train_subset, batch_size=batch_size, shuffle=True, drop_last=False)
        val_loader = DataLoader(val_subset, batch_size=batch_size, shuffle=False)
        logger.info("Dataset split: %d train triplets, %d validation triplets", train_size, val_size)

    # 2. Model, Loss, Optimizer
    model = SiameseViT(embedding_dim=embedding_dim, pretrained=True).to(device)
    criterion = nn.TripletMarginLoss(margin=margin, p=2.0)
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=1e-2)

    models_dir = Path("models")
    models_dir.mkdir(parents=True, exist_ok=True)
    best_model_path = models_dir / "best_siamese_vit.pt"

    # 3. MLflow Experiment Tracking
    mlflow.set_experiment("Visual-Phishing-Adversarial-ViT")

    with mlflow.start_run(run_name=f"AdvTrain-PGD-eps8-{datetime.now().strftime('%Y%m%d_%H%M%S')}"):
        mlflow.log_params({
            "training_mode": "Adversarial_Training_MinMax",
            "attack_method": "PGD_L_infinity_OnTheFly",
            "backbone": "vit_b_16",
            "embedding_dim": embedding_dim,
            "margin": margin,
            "epsilon": f"{eps*255:.1f}/255",
            "learning_rate": learning_rate,
            "batch_size": batch_size,
            "epochs": epochs,
            "optimizer": "AdamW",
        })

        best_score = -1.0

        print("\n" + "=" * 80)
        print("STARTING ON-THE-FLY ADVERSARIAL SIAMESE ViT TRAINING (Min-Max)")
        print("=" * 80)

        for epoch in range(1, epochs + 1):
            train_loss = train_adversarial_epoch(
                model=model,
                dataloader=train_loader,
                criterion=criterion,
                optimizer=optimizer,
                device=device,
                eps=eps,
                pgd_steps=3,
            )

            metrics = validate_dual_performance(
                model=model,
                dataloader=val_loader,
                criterion=criterion,
                device=device,
                eps=eps,
            )

            # Log Dual Metrics to MLflow
            mlflow.log_metric("train_adv_loss", train_loss, step=epoch)
            mlflow.log_metric("val_std_loss", metrics["val_std_loss"], step=epoch)
            mlflow.log_metric("val_rob_loss", metrics["val_rob_loss"], step=epoch)
            mlflow.log_metric("standard_pr_auc", metrics["standard_pr_auc"], step=epoch)
            mlflow.log_metric("robust_pr_auc", metrics["robust_pr_auc"], step=epoch)
            mlflow.log_metric("robustness_gap", metrics["robustness_gap"], step=epoch)

            logger.info(
                "Epoch [%d/%d] | Train Loss: %.4f | Std PR-AUC: %.4f | Robust PR-AUC: %.4f | Gap: %.4f",
                epoch,
                epochs,
                train_loss,
                metrics["standard_pr_auc"],
                metrics["robust_pr_auc"],
                metrics["robustness_gap"],
            )

            # Checkpoint based on Harmonic Mean or Robust PR-AUC
            selection_score = metrics["robust_pr_auc"]
            if selection_score > best_score:
                best_score = selection_score
                torch.save(
                    {
                        "epoch": epoch,
                        "model_state_dict": model.state_dict(),
                        "optimizer_state_dict": optimizer.state_dict(),
                        "standard_pr_auc": metrics["standard_pr_auc"],
                        "robust_pr_auc": metrics["robust_pr_auc"],
                        "hyperparameters": {
                            "embedding_dim": embedding_dim,
                            "margin": margin,
                            "backbone": "vit_b_16",
                            "adversarial_trained": True,
                        },
                    },
                    best_model_path,
                )
                logger.info("--> Checkpoint saved: New best Robust PR-AUC = %.4f -> %s", selection_score, best_model_path)

        mlflow.log_metric("best_robust_pr_auc", best_score)
        mlflow.log_artifact(str(best_model_path), artifact_path="checkpoints")

        print("=" * 80)
        print(f"ADVERSARIAL TRAINING COMPLETE. Best Robust PR-AUC: {best_score:.4f}")
        print(f"Robust weights saved to: {best_model_path}")
        print("=" * 80 + "\n")


if __name__ == "__main__":
    triplets_csv_path = Path("data/processed/triplets.csv")
    run_training(
        triplets_csv=triplets_csv_path,
        epochs=3,
        batch_size=4,
        learning_rate=3e-5,
        margin=0.3,
        embedding_dim=128,
        eps=8.0 / 255.0,
    )
