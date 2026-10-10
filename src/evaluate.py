"""
Zero-Day Statistical Evaluation Module for Visual Phishing Detection.
Designed for Open-Set Evaluation & Skripsi Komputasi Statistik STIS.

Methodology implemented:
1. Brand-Disjoint Validation/Testing split (Zero-Day Evaluation).
2. Threshold Calibration on Validation set (Neyman-Pearson criterion: max Recall @ FPR <= 1%).
3. Performance Metrics on Hold-Out Test set: PR-AUC, F1-Score, Recall @ Target FPR.
4. Non-Parametric Bootstrap Confidence Intervals (B = 1000 resamples at 95% CI).
"""

import logging
from pathlib import Path
from typing import Callable, Dict, List, Tuple

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F

import sys
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

try:
    from src.train import SiameseViT
except ModuleNotFoundError:
    from train import SiameseViT

# Structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ZeroDayEvaluation")


# ---------------------------------------------------------------------------
# 1. Pure NumPy Statistical Metric Calculators
# ---------------------------------------------------------------------------
def calculate_pr_auc(y_true: np.ndarray, y_scores: np.ndarray) -> float:
    """Calculates PR-AUC using trapezoidal numerical integration."""
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
        return float(trapz_func(precision, recall))
    return float(np.sum((recall[1:] - recall[:-1]) * precision[1:]))


def calculate_metrics_at_threshold(
    y_true: np.ndarray,
    y_scores: np.ndarray,
    threshold: float,
) -> Dict[str, float]:
    """Calculates Precision, Recall, Specificity, and FPR at a fixed threshold."""
    y_pred = (y_scores >= threshold).astype(int)

    tp = np.sum((y_pred == 1) & (y_true == 1))
    fp = np.sum((y_pred == 1) & (y_true == 0))
    tn = np.sum((y_pred == 0) & (y_true == 0))
    fn = np.sum((y_pred == 0) & (y_true == 1))

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "precision": float(precision),
        "recall": float(recall),
        "fpr": float(fpr),
        "f1": float(f1),
    }


# ---------------------------------------------------------------------------
# 2. Threshold Calibration (Validation Set Only)
# ---------------------------------------------------------------------------
def calibrate_threshold_at_target_fpr(
    val_y_true: np.ndarray,
    val_y_scores: np.ndarray,
    target_fpr: float = 0.01,
) -> Tuple[float, Dict[str, float]]:
    """
    Neyman-Pearson Threshold Calibration.
    Finds the operational threshold tau on the Validation set such that FPR <= target_fpr (e.g. 1%),
    preventing security analyst alert fatigue.
    """
    threshold_candidates = np.linspace(-1.0, 1.0, num=2000)
    best_threshold = 1.0
    best_metrics = {}

    for tau in sorted(threshold_candidates, reverse=True):
        m = calculate_metrics_at_threshold(val_y_true, val_y_scores, tau)
        if m["fpr"] <= target_fpr:
            best_threshold = tau
            best_metrics = m
            break

    logger.info(
        "Threshold Calibrated on Validation Set: tau = %.4f (Val Recall: %.4f @ Val FPR: %.4f)",
        best_threshold,
        best_metrics.get("recall", 0.0),
        best_metrics.get("fpr", 0.0),
    )
    return best_threshold, best_metrics


# ---------------------------------------------------------------------------
# 3. Non-Parametric Bootstrap Confidence Intervals (STIS Rigor)
# ---------------------------------------------------------------------------
def bootstrap_metric_ci(
    y_true: np.ndarray,
    y_scores: np.ndarray,
    metric_fn: Callable[[np.ndarray, np.ndarray], float],
    n_bootstraps: int = 1000,
    alpha: float = 0.05,
    seed: int = 42,
) -> Tuple[float, float, float]:
    """
    Computes Empirical Bootstrap Percentile Confidence Interval:
      [theta_hat, Lower 95% Bound, Upper 95% Bound]
    """
    rng = np.random.RandomState(seed)
    n_samples = len(y_true)
    point_estimate = metric_fn(y_true, y_scores)

    bootstrap_estimates = []
    for _ in range(n_bootstraps):
        # Resampling with replacement
        indices = rng.choice(n_samples, size=n_samples, replace=True)
        # Ensure at least one positive and one negative sample in the bootstrap draw
        if len(np.unique(y_true[indices])) < 2:
            continue
        score = metric_fn(y_true[indices], y_scores[indices])
        bootstrap_estimates.append(score)

    bootstrap_arr = np.array(bootstrap_estimates)
    lower_bound = float(np.percentile(bootstrap_arr, 100 * (alpha / 2)))
    upper_bound = float(np.percentile(bootstrap_arr, 100 * (1 - alpha / 2)))

    return point_estimate, lower_bound, upper_bound


# ---------------------------------------------------------------------------
# 4. Zero-Day Evaluation Harness
# ---------------------------------------------------------------------------
def run_zero_day_evaluation(
    val_y_true: np.ndarray,
    val_y_scores: np.ndarray,
    test_y_true: np.ndarray,
    test_y_scores: np.ndarray,
    target_fpr: float = 0.01,
) -> pd.DataFrame:
    """
    Executes complete statistical evaluation:
    1. Calibrates threshold on Validation set.
    2. Freezes threshold.
    3. Evaluates Hold-Out Test set.
    4. Computes 95% Bootstrap Confidence Intervals.
    """
    # 1. Calibrate on Validation
    optimal_tau, _ = calibrate_threshold_at_target_fpr(val_y_true, val_y_scores, target_fpr=target_fpr)

    # 2. Metric functions for bootstrapping on Hold-out Test
    def get_pr_auc(yt, ys):
        return calculate_pr_auc(yt, ys)

    def get_recall_at_tau(yt, ys):
        return calculate_metrics_at_threshold(yt, ys, threshold=optimal_tau)["recall"]

    def get_fpr_at_tau(yt, ys):
        return calculate_metrics_at_threshold(yt, ys, threshold=optimal_tau)["fpr"]

    def get_f1_at_tau(yt, ys):
        return calculate_metrics_at_threshold(yt, ys, threshold=optimal_tau)["f1"]

    # 3. Compute Bootstrap Estimates
    pr_auc_est, pr_auc_low, pr_auc_high = bootstrap_metric_ci(test_y_true, test_y_scores, get_pr_auc)
    rec_est, rec_low, rec_high = bootstrap_metric_ci(test_y_true, test_y_scores, get_recall_at_tau)
    fpr_est, fpr_low, fpr_high = bootstrap_metric_ci(test_y_true, test_y_scores, get_fpr_at_tau)
    f1_est, f1_low, f1_high = bootstrap_metric_ci(test_y_true, test_y_scores, get_f1_at_tau)

    # 4. Formulate LaTeX / Skripsi Table
    results = [
        {
            "Metrik Evaluasi": "PR-AUC (Primary Metric)",
            "Estimasi Titik": f"{pr_auc_est:.4f}",
            "95% CI (B=1000)": f"[{pr_auc_low:.4f}, {pr_auc_high:.4f}]",
            "Keterangan": "Ketahanan diskriminasi pada distribusi tak seimbang",
        },
        {
            "Metrik Evaluasi": f"Recall @ Target FPR <= {target_fpr*100:.0f}%",
            "Estimasi Titik": f"{rec_est:.4f}",
            "95% CI (B=1000)": f"[{rec_low:.4f}, {rec_high:.4f}]",
            "Keterangan": f"Daya tangkap serangan phishing pada toleransi salah tangkap {target_fpr*100:.0f}%",
        },
        {
            "Metrik Evaluasi": f"F1-Score (tau={optimal_tau:.4f})",
            "Estimasi Titik": f"{f1_est:.4f}",
            "95% CI (B=1000)": f"[{f1_low:.4f}, {f1_high:.4f}]",
            "Keterangan": "Keseimbangan presisi & recall pada threshold terkunci",
        },
        {
            "Metrik Evaluasi": "False Positive Rate (Aktual Test)",
            "Estimasi Titik": f"{fpr_est:.4f}",
            "95% CI (B=1000)": f"[{fpr_low:.4f}, {fpr_high:.4f}]",
            "Keterangan": "Tingkat false alarm aktual di lingkungan zero-day",
        },
    ]

    df_results = pd.DataFrame(results)
    return df_results


if __name__ == "__main__":
    # Simulasi pembuktian statistik
    np.random.seed(42)
    # Validation synthetic pairs
    v_true = np.array([1] * 50 + [0] * 200)
    v_scores = np.concatenate([np.random.normal(0.85, 0.1, 50), np.random.normal(0.2, 0.15, 200)])

    # Hold-out Zero-day Test synthetic pairs
    t_true = np.array([1] * 40 + [0] * 160)
    t_scores = np.concatenate([np.random.normal(0.82, 0.12, 40), np.random.normal(0.25, 0.18, 160)])

    df = run_zero_day_evaluation(v_true, v_scores, t_true, t_scores, target_fpr=0.01)

    print("\n" + "=" * 80)
    print("TABEL HASIL PENGUJIAN STATISTIK ZERO-DAY (BAB 4 SKRIPSI)")
    print("=" * 80)
    print(df.to_string(index=False))
    print("=" * 80 + "\n")
