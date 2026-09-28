import math

import numpy as np
import opendp.prelude as dp
from scipy.stats import beta
from sklearn.metrics import average_precision_score, roc_auc_score, roc_curve

dp.enable_features("contrib")


def threshold_from_public_development(y, scores, target_fpr=0.01):
    if len(np.unique(y)) != 2:
        raise ValueError("Development set needs both classes")
    fpr, tpr, thresholds = roc_curve(y, scores)
    feasible = np.where((fpr <= target_fpr) & np.isfinite(thresholds))[0]
    return float(thresholds[feasible[np.argmax(tpr[feasible])]]) if len(feasible) else 1.0


def confusion(y, scores, threshold):
    y, predicted = np.asarray(y).astype(bool), np.asarray(scores) >= threshold
    return [int(np.sum(y & predicted)), int(np.sum(~y & predicted)),
            int(np.sum(~y & ~predicted)), int(np.sum(y & ~predicted))]


def binomial_bounds(k, n, alpha=0.025):
    if n <= 0:
        return [0.0, 1.0]
    return [float(beta.ppf(alpha, k, n - k + 1)) if k else 0.0,
            float(beta.ppf(1 - alpha, k + 1, n - k)) if k < n else 1.0]


def metrics(y, scores, threshold):
    tp, fp, tn, fn = confusion(y, scores, threshold)
    recall, fpr = tp / max(1, tp + fn), fp / max(1, fp + tn)
    return {"pr_auc": float(average_precision_score(y, scores)) if tp + fn else None,
            "roc_auc": float(roc_auc_score(y, scores)) if len(np.unique(y)) == 2 else None,
            "recall": recall, "fpr": fpr, "precision": tp / max(1, tp + fp),
            "false_alerts_per_1000": 1000 * fpr, "threshold": threshold,
            "recall_interval": binomial_bounds(tp, tp + fn), "fpr_interval": binomial_bounds(fp, fp + tn),
            "counts": {"tp": tp, "fp": fp, "tn": tn, "fn": fn}, "source": "public_benchmark"}


def count_mechanism(epsilon):
    if not math.isfinite(epsilon) or epsilon <= 0:
        raise ValueError("Invalid validation epsilon")
    count = dp.t.make_count_by_categories(
        input_domain=dp.vector_domain(dp.atom_domain(T=int)),
        input_metric=dp.symmetric_distance(), categories=[0, 1, 2, 3], null_category=False,
        MO="L1Distance<i32>")
    measurement = count >> dp.m.then_laplace(scale=(1 / epsilon) * (1 + 1e-10))
    if not measurement.check(1, epsilon):
        raise ValueError("Validation mechanism exceeds approved epsilon")
    return measurement


def private_confusion(y, scores, threshold, epsilon):
    predicted = np.asarray(scores) >= threshold
    labels = np.asarray(y).astype(bool)
    categories = np.where(labels, np.where(predicted, 0, 3), np.where(predicted, 1, 2))
    mechanism = count_mechanism(epsilon)
    return {"noisy_counts": list(mechanism(categories.tolist())), "epsilon": epsilon,
            "sensitivity": 1, "adjacency": "add_remove_one_transaction", "mechanism": "OpenDP discrete Laplace"}


def private_rates(releases, alpha=0.05):
    if not releases or not 0 < alpha < 1:
        raise ValueError("Validation releases and a valid uncertainty level are required")
    counts = np.sum([r["noisy_counts"] for r in releases], axis=0)
    # Split failure probability between all noise tails and four binomial tails.
    radius = sum(math.ceil(math.log(16 * len(releases) / alpha) / r["epsilon"]) + 1 for r in releases)
    lower, upper = np.maximum(0, counts - radius), np.maximum(0, counts + radius)

    def rate_bounds(num, other):
        low = binomial_bounds(int(lower[num]), int(lower[num] + upper[other]), alpha / 8)[0]
        high = binomial_bounds(int(upper[num]), int(upper[num] + lower[other]), alpha / 8)[1]
        return [low, high]

    return {"noisy_counts": counts.tolist(), "count_error_radius": radius,
            "recall_interval": rate_bounds(0, 3), "fpr_interval": rate_bounds(1, 2),
            "denominators_supported": bool(lower[0] + lower[3] > 0 and lower[1] + lower[2] > 0),
            "source": "governed_validation", "confidence": 1 - alpha,
            "uncertainty": "simultaneous noise and binomial bounds"}
