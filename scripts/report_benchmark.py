"""Render the actual saved public benchmark, including failed candidates."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

parser = argparse.ArgumentParser()
parser.add_argument("summary", type=Path)
parser.add_argument("--output", type=Path, default=Path("docs/benchmark"))
args = parser.parse_args()
report = json.loads(args.summary.read_text())
configuration = report.get("configuration", {"rounds": 3, "local_steps": 12, "capacity": 2048, "learning_rate": .1})
rows = report["results"]
args.output.mkdir(parents=True, exist_ok=True)
fig, axes = plt.subplots(1, 2, figsize=(10, 4), constrained_layout=True)
colors = ["#28604e", "#788dd2", "#b98231"]
budgets = sorted({r["planned_epsilon"] for r in rows})
for color, seed in zip(colors, sorted({r["seed"] for r in rows})):
    values = sorted([r for r in rows if r["seed"] == seed and r["metrics"]], key=lambda r: r["epsilon"])
    axes[0].plot([r["epsilon"] for r in values], [r["metrics"]["pr_auc"] for r in values],
                 "o-", label="seed " + str(seed), color=color)
    axes[1].plot([r["epsilon"] for r in values], [r["metrics"]["recall"] for r in values],
                 "o-", label="seed " + str(seed), color=color)
for axis, label in zip(axes, ["Public test PR-AUC", "Public test fraud recall"]):
    axis.set(xlabel="Accounted epsilon (delta = 1e-6)", ylabel=label, ylim=(0, 1))
    axis.grid(alpha=.2)
    axis.legend()
fig.suptitle("Generated public fixture: recorded privacy–utility comparison")
fig.savefig(args.output / "privacy-utility.svg")
svg = args.output / "privacy-utility.svg"
svg.write_text("\n".join(line.rstrip() for line in svg.read_text().splitlines()) + "\n")
fig.savefig(args.output / "privacy-utility.png", dpi=160)
lines = ["# Recorded public engineering benchmark", "",
         "Source: generated fixture, not PaySim or real-bank data.",
         f'{configuration["rounds"]} rounds; {configuration["local_steps"]} local steps per round; '
         f'capacity {configuration["capacity"]}; expected batch 128; clipping norm 1; '
         f'learning rate {configuration["learning_rate"]}; validation epsilon 0.5.',
         "Three seeds per budget; each is an independent public simulation, not a reset private budget.", "",
         "These models do not satisfy the release policy. No qualifying fraud-detection performance is claimed.",
         "Variation across these runs does not establish a monotonic privacy–utility relationship.", "",
         "![Measured privacy–utility plot](privacy-utility.svg)", "",
         "| Planned epsilon | Accounted epsilon | Mean PR-AUC ± sample SD | Mean recall | Runs |",
         "|---|---|---|---|---|"]
for budget in budgets:
    subset = [r for r in rows if r["planned_epsilon"] == budget and r["metrics"]]
    auc = [r["metrics"]["pr_auc"] for r in subset]
    lines.append("| " + str(budget) + " | " + f'{np.mean([r["epsilon"] for r in subset]):.4f}'
                 + " | " + f"{np.mean(auc):.4f} ± {np.std(auc, ddof=1):.4f}"
                 + " | " + f'{np.mean([r["metrics"]["recall"] for r in subset]):.2%}'
                 + " | " + str(len(subset)) + " |")
lines += ["", "Mean full-job wall time: " + f'{np.mean([r["duration_seconds"] for r in rows]):.1f} seconds.',
          "Full-job time includes public baselines and attacks; it is not isolated secure-aggregation latency.",
          "Communication counts are local framed protocol bytes; TLS framing overhead is not included in this study.",
          "Each JSON result retains institution metrics, receipts, attack controls, baselines, and release reasons.",
          "No dataset occupancy or raw records are used as billing telemetry.", ""]
(args.output / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
print(args.output.resolve())
