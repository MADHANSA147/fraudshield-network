"""Public development only. Does not open any final test partition."""
import json
from pathlib import Path
import numpy as np
from fraudshield.accounting import calibrate
from fraudshield.benchmark import public_federated_ablation
from fraudshield.contracts import Plan
from fraudshield.data import fixture
from fraudshield.evaluation import metrics, threshold_from_public_development
from fraudshield.security import atomic_json
from fraudshield.training import predict

if __name__ == "__main__":
    directory = Path("var/public-development-pilot")
    plan = Plan(capacity=8192, batch_size=128, rounds=5, local_steps=100,
                epsilon_cap=4, learning_rate=.5, positive_weight=1, seed=142)
    datasets = [fixture(plan.capacity * 3 // 4, plan.seed + i * 101, i) for i in range(3)]
    development = [fixture(4096, plan.seed + 10000 + i * 101, i) for i in range(3)]
    dx, dy = np.concatenate([x for x, _ in development]), np.concatenate([y for _, y in development])
    sigma = calibrate(plan)
    model, trace = public_federated_ablation(datasets, plan, sigma=sigma, directory=directory)
    scores = predict(model, dx)
    threshold = threshold_from_public_development(dy, scores, plan.max_fpr)
    report = {"source": "generated_public_development_only", "plan": plan.model_dump(), "sigma": sigma,
              "development_metrics": metrics(dy, scores, threshold),
              "final_test_opened": False, "secure_aggregation": False}
    atomic_json(Path("docs/benchmark/development-pilot.json"), report)
    print(json.dumps(report), flush=True)
