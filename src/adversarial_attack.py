"""
Adversarial Attack Generation for Visual Phishing Evasion Simulation.
Implements Projected Gradient Descent (PGD / L_inf Norm) using native PyTorch autograd.

Mathematical Foundations (Madry et al., 2018):
Objective: Find an adversarial perturbation delta such that ||delta||_inf <= epsilon,
maximizing the loss of the surrogate vision model while remaining imperceptible to humans.

Update Rule:
x^(t+1) = Clip_[0, 1] ( Clip_[x - eps, x + eps] ( x^t + alpha * sign(nabla_x L(f(x^t), y)) ) )

Key Parameters:
- epsilon = 8/255 (~0.0314): Maximum L_inf pixel perturbation budget.
- alpha = 2/255 (~0.0078): Gradient ascent step size per iteration.
- steps = 10: Number of projected gradient descent iterations.
"""

import logging
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from PIL import Image
import torch
import torch.nn as nn
from torchvision import models, transforms
from torchvision.models import ResNet18_Weights

# Structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("AdversarialAttack")

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
LOGOS_DIR = BASE_DIR / "data" / "raw" / "logos"
OUTPUT_DIR = BASE_DIR / "data" / "processed" / "adversarial_logos"


# ---------------------------------------------------------------------------
# 1. Native PyTorch PGD Attack (Madry et al. L-infinity Formulation)
# ---------------------------------------------------------------------------
class ProjectedGradientDescentAttack:
    """
    Projected Gradient Descent (PGD) Adversarial Attack.
    Implemented directly in PyTorch autograd to eliminate scipy/DLL dependencies.
    """

    def __init__(
        self,
        model: nn.Module,
        eps: float = 8.0 / 255.0,
        alpha: float = 2.0 / 255.0,
        steps: int = 10,
        random_start: bool = True,
        device: torch.device = torch.device("cpu"),
    ) -> None:
        """
        Args:
            model: Surrogate vision model acting as the target.
            eps: L_inf perturbation radius (8/255 is the computer vision standard for imperceptibility).
            alpha: Step size for gradient ascent.
            steps: Number of PGD iterations.
            random_start: Whether to initialize perturbation randomly within [-eps, eps].
            device: Computation device (CPU or CUDA).
        """
        self.model = model
        self.model.eval()
        self.eps = eps
        self.alpha = alpha
        self.steps = steps
        self.random_start = random_start
        self.device = device
        self.loss_fn = nn.CrossEntropyLoss()

        # ImageNet normalization layer embedded directly in PyTorch computation graph
        # so gradients can flow back to raw pixel space [0, 1]
        self.normalize = transforms.Normalize(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225],
        )

    def perturb(self, x: torch.Tensor, target_label: Optional[torch.Tensor] = None) -> torch.Tensor:
        """
        Generates an adversarial tensor x_adv from input tensor x in range [0, 1].

        Args:
            x: Input tensor of shape (1, 3, H, W) normalized to [0, 1].
            target_label: Target or ground-truth class index. If None, uses top-1 predicted class.

        Returns:
            Adversarial tensor x_adv bounded to [0, 1] with ||x_adv - x||_inf <= eps.
        """
        x = x.clone().detach().to(self.device)

        # Infer surrogate model prediction if label is not provided
        if target_label is None:
            with torch.no_grad():
                logits = self.model(self.normalize(x))
                target_label = torch.argmax(logits, dim=1)

        target_label = target_label.to(self.device)

        # 1. Random Start: Uniform initialization within the L_inf epsilon-ball
        if self.random_start:
            delta = torch.empty_like(x).uniform_(-self.eps, self.eps)
            x_adv = torch.clamp(x + delta, min=0.0, max=1.0).detach()
        else:
            x_adv = x.clone().detach()

        # 2. Multi-step Gradient Ascent Loop
        for step in range(self.steps):
            x_adv.requires_grad = True

            # Forward pass through normalized surrogate model
            outputs = self.model(self.normalize(x_adv))
            loss = self.loss_fn(outputs, target_label)

            # Gradient computation: nabla_x L(theta, x_adv, y)
            self.model.zero_grad()
            loss.backward()

            with torch.no_grad():
                grad_sign = x_adv.grad.sign()

                # Step 1: Gradient ascent step in direction of loss maximization
                x_adv = x_adv + self.alpha * grad_sign

                # Step 2: Projection onto the L_inf epsilon-ball centered at original image x
                eta = torch.clamp(x_adv - x, min=-self.eps, max=self.eps)
                x_adv = torch.clamp(x + eta, min=0.0, max=1.0).detach()

        return x_adv


# ---------------------------------------------------------------------------
# 2. Quantitative Imperceptibility Metrics (For Skripsi Chapter 4)
# ---------------------------------------------------------------------------
def compute_distortion_metrics(
    orig_tensor: torch.Tensor,
    adv_tensor: torch.Tensor,
) -> Dict[str, float]:
    """
    Computes mathematical perturbation metrics:
    1. L_inf distance: Maximum absolute pixel change in [0, 255].
    2. MSE (Mean Squared Error).
    3. PSNR (Peak Signal-to-Noise Ratio): In dB (> 35 dB indicates human imperceptibility).
    """
    orig_np = orig_tensor.squeeze(0).permute(1, 2, 0).cpu().numpy()
    adv_np = adv_tensor.squeeze(0).permute(1, 2, 0).cpu().numpy()

    # Absolute difference
    diff = np.abs(adv_np - orig_np)
    linf_norm = float(np.max(diff) * 255.0)

    # Mean Squared Error
    mse = float(np.mean((adv_np - orig_np) ** 2))

    # Peak Signal-to-Noise Ratio
    if mse == 0:
        psnr = 100.0
    else:
        psnr = float(10.0 * math.log10(1.0 / mse))

    return {
        "linf_pixel_budget": round(linf_norm, 2),
        "mse": round(mse, 6),
        "psnr_db": round(psnr, 2),
    }


# ---------------------------------------------------------------------------
# 3. Batch Attack Execution
# ---------------------------------------------------------------------------
def run_adversarial_generation(
    logos_dir: Path,
    output_dir: Path,
    eps: float = 8.0 / 255.0,
    steps: int = 10,
) -> None:
    """Processes all canonical government logos and saves adversarial counterparts."""
    output_dir.mkdir(parents=True, exist_ok=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info("Using device for adversarial PGD generation: %s", device)

    # 1. Load Pretrained Surrogate Model (ResNet-18)
    logger.info("Loading pretrained surrogate model (ResNet-18)...")
    surrogate_model = models.resnet18(weights=ResNet18_Weights.DEFAULT).to(device)
    surrogate_model.eval()

    # 2. Initialize PGD Attack
    attacker = ProjectedGradientDescentAttack(
        model=surrogate_model,
        eps=eps,
        alpha=2.0 / 255.0,
        steps=steps,
        random_start=True,
        device=device,
    )

    logo_files = sorted([p for p in logos_dir.glob("*.png")])
    if not logo_files:
        logger.error("No logo files found in %s", logos_dir)
        return

    logger.info("Found %d canonical logo(s) to perturb in %s", len(logo_files), logos_dir)

    print("\n" + "=" * 80)
    print("STARTING ADVERSARIAL PERTURBATION GENERATION (PGD L-infinity)")
    print("=" * 80)

    transform_to_tensor = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),  # Maps to [0.0, 1.0]
    ])

    results_table = []

    for file_path in logo_files:
        brand_name = file_path.stem.lower()

        # Load RGB image
        img = Image.open(file_path).convert("RGB")
        img_tensor = transform_to_tensor(img).unsqueeze(0).to(device)

        # 3. Apply PGD Attack
        adv_tensor = attacker.perturb(img_tensor)

        # 4. Measure Distortion Rigor
        metrics = compute_distortion_metrics(img_tensor, adv_tensor)

        # 5. Save Perturbed Image
        adv_np = adv_tensor.squeeze(0).permute(1, 2, 0).cpu().numpy()
        adv_img = Image.fromarray((adv_np * 255.0).astype(np.uint8))

        output_filename = f"{brand_name}_pgd_eps8.png"
        output_filepath = output_dir / output_filename
        adv_img.save(output_filepath)

        results_table.append({
            "Brand": brand_name,
            "Saved File": output_filename,
            "Max Pixel Delta (L_inf)": f"{metrics['linf_pixel_budget']:.1f}/255",
            "MSE": f"{metrics['mse']:.6f}",
            "PSNR (dB)": f"{metrics['psnr_db']:.2f} dB",
        })

    # Print Report
    print(f"{'Brand':<12} | {'Saved File':<24} | {'L_inf Delta':<12} | {'MSE':<10} | {'PSNR (dB)':<10}")
    print("-" * 80)
    for row in results_table:
        print(f"{row['Brand']:<12} | {row['Saved File']:<24} | {row['Max Pixel Delta (L_inf)']:<12} | {row['MSE']:<10} | {row['PSNR (dB)']:<10}")
    print("=" * 80)
    print(f"COMPLETE: All adversarial logos saved in {output_dir}")
    print("Visual Inspection: PSNR > 35 dB proves noise is imperceptible to human eyes.\n")


if __name__ == "__main__":
    run_adversarial_generation(
        logos_dir=LOGOS_DIR,
        output_dir=OUTPUT_DIR,
        eps=8.0 / 255.0,  # Standard 8/255 L_inf budget
        steps=10,
    )
