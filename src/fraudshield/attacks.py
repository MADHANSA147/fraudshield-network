"""Public-data diagnostics. Attacker observations and inconclusive controls are explicit."""
import numpy as np
import torch
from sklearn.metrics import roc_auc_score, roc_curve
from sklearn.model_selection import train_test_split

from .training import Detector, arrays, predict, set_arrays, train_public


def loss_scores(model, x, y):
    # Work in logit space: clipping sigmoid probabilities destroys the high-
    # confidence ordering on deliberately overfit membership controls.
    model.eval()
    with torch.no_grad():
        logits = model(torch.as_tensor(x, dtype=torch.float32)).reshape(-1)
        labels = torch.as_tensor(y, dtype=torch.float32)
        return -torch.nn.functional.softplus((1 - 2 * labels) * logits).numpy()


def attack_metrics(labels, scores):
    fpr, tpr, _ = roc_curve(labels, scores)
    labels, scores = np.asarray(labels), np.asarray(scores)
    rng = np.random.default_rng(9281)
    estimates = []
    positive, negative = np.where(labels == 1)[0], np.where(labels == 0)[0]
    for _ in range(200):
        chosen = np.r_[rng.choice(positive, len(positive), replace=True),
                       rng.choice(negative, len(negative), replace=True)]
        bfpr, btpr, _ = roc_curve(labels[chosen], scores[chosen])
        estimates.append((roc_auc_score(labels[chosen], scores[chosen]), np.max(btpr[bfpr <= .01])))
    bounds = np.quantile(estimates, [.025, .975], axis=0)
    return {"roc_auc": float(roc_auc_score(labels, scores)),
            "tpr_at_1pct_fpr": float(np.max(tpr[fpr <= .01])),
            "roc_auc_bootstrap_95": bounds[:, 0].tolist(),
            "tpr_at_1pct_fpr_bootstrap_95": bounds[:, 1].tolist(),
            "uncertainty_method": "200 stratified bootstrap resamples; small-sample low-FPR resolution is limited",
            "members": int(np.sum(labels)), "nonmembers": int(np.sum(1 - labels))}


def membership_report(target, members, nonmembers, seed=42, shadows=4):
    rng = np.random.default_rng(seed)
    # Match class proportions rather than confounding membership with target labels.
    mx, my = members
    nx, ny = nonmembers
    mi, ni = [], []
    for label in (0, 1):
        m, n = np.where(my == label)[0], np.where(ny == label)[0]
        k = min(len(m), len(n), 64)
        mi.extend(rng.choice(m, k, replace=False))
        ni.extend(rng.choice(n, k, replace=False))
    if len(mi) < 16:
        return {"status": "INCONCLUSIVE", "reason": "Insufficient matched members and nonmembers"}
    x, y = np.concatenate([mx[mi], nx[ni]]), np.concatenate([my[mi], ny[ni]])
    membership = np.r_[np.ones(len(mi)), np.zeros(len(ni))]
    train_idx, test_idx = train_test_split(np.arange(len(y)), test_size=.5, stratify=membership, random_state=seed)
    target_scores = loss_scores(target, x, y)
    shadow_scores, shadow_membership = [], []
    for i in range(shadows):
        mask = rng.random(len(y)) < .5
        shadow = train_public(x[mask], y[mask], seed=seed + i, steps=80, positive_weight=1)
        shadow_scores.append(loss_scores(shadow, x, y))
        shadow_membership.append(mask)
    ss, sm = np.asarray(shadow_scores), np.asarray(shadow_membership)
    in_values = ss[:, train_idx][sm[:, train_idx]]
    out_values = ss[:, train_idx][~sm[:, train_idx]]
    mu_in, mu_out = float(np.mean(in_values)), float(np.mean(out_values))
    sd_in, sd_out = max(float(np.std(in_values)), .05), max(float(np.std(out_values)), .05)
    score = target_scores[test_idx]
    likelihood_ratio = (-.5 * ((score - mu_in) / sd_in)**2 - np.log(sd_in)
                        + .5 * ((score - mu_out) / sd_out)**2 + np.log(sd_out))
    # Deliberately overfit public random-label control; independent of protected-model results.
    control_x = rng.normal(size=(96, x.shape[1])).astype(np.float32)
    control_y = rng.integers(0, 2, 96).astype(np.float32)
    control = train_public(control_x[:32], control_y[:32], seed=seed + 500, steps=500, positive_weight=1)
    control_result = attack_metrics(np.r_[np.ones(32), np.zeros(64)], loss_scores(control, control_x, control_y))
    control_pass = control_result["roc_auc"] >= .7 and control_result["tpr_at_1pct_fpr"] >= .1
    return {"status": "COMPLETE" if control_pass else "INCONCLUSIVE",
            "source": "public_fixture", "positive_control": {**control_result, "passed": control_pass},
            "loss_attack": attack_metrics(membership[test_idx], target_scores[test_idx]),
            "shadow_likelihood_attack": attack_metrics(membership[test_idx], likelihood_ratio),
            "shadow_models": shadows, "calibration_disjoint_from_attack_test": True,
            "scope": "Limited pooled shadow-score likelihood attack; not a full per-example LiRA reproduction",
            "uncertainty": "Small public engineering sample; no universal attack-resistance claim"}


def single_gradient_leakage(seed=42):
    torch.manual_seed(seed)
    model = torch.nn.Linear(4, 1)
    record = torch.randn(1, 4)
    torch.nn.functional.binary_cross_entropy_with_logits(model(record), torch.ones(1, 1)).backward()
    reconstructed = model.weight.grad / model.bias.grad.reshape(1, 1)
    return {"source": "public_synthetic_diagnostic", "observation": "Unprotected single-example linear-layer gradient",
            "max_absolute_reconstruction_error": float((record - reconstructed).abs().max()),
            "applies_to_multistep_federated_delta": False}


def poisoning_diagnostic(model, x, y):
    before = predict(model, x)
    malicious = Detector()
    # Final-round public stress fixture: two unchanged honest proposals and one
    # malicious scaled proposal. Apply the actual equal-weight aggregation rule.
    set_arrays(malicious, [(a + a + np.clip(-10 * a, -8, 8)) / 3 for a in arrays(model)])
    after = predict(malicious, x)
    return {"source": "public_diagnostic", "attack": "One-of-three final-round model scaling stress test",
            "assumption": "Two honest proposals equal the reference model; one scaled by -10 then range-clipped",
            "clean_accuracy_at_half": float(np.mean((before >= .5) == y)),
            "attacked_accuracy_at_half": float(np.mean((after >= .5) == y)),
            "byzantine_defense_claimed": False}
