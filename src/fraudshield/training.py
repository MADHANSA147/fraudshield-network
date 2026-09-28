from pathlib import Path

import numpy as np
import torch
from opacus import PrivacyEngine
from safetensors.torch import load_file, save_file
from torch import nn
from torch.utils.data import DataLoader, Dataset

from .data import FEATURES
from .security import digest


class Detector(nn.Module):
    def __init__(self, linear=False):
        super().__init__()
        self.layers = (nn.Linear(len(FEATURES), 1) if linear else
                       nn.Sequential(nn.Linear(len(FEATURES), 32), nn.ReLU(),
                                     nn.Linear(32, 16), nn.ReLU(), nn.Linear(16, 1)))

    def forward(self, x):
        return self.layers(x).squeeze(-1)


class SlotDataset(Dataset):
    def __init__(self, x, y, capacity):
        if len(x) != len(y) or len(x) > capacity or capacity < 1:
            raise ValueError("Records do not fit approved capacity")
        if not np.isfinite(x).all() or not np.isin(y, [0, 1]).all():
            raise ValueError("Invalid record values")
        self.x = torch.zeros(capacity, len(FEATURES))
        self.y = torch.zeros(capacity)
        self.valid = torch.zeros(capacity)
        self.x[:len(x)] = torch.as_tensor(x)
        self.y[:len(y)] = torch.as_tensor(y)
        self.valid[:len(y)] = 1

    def __len__(self):
        return len(self.x)

    def __getitem__(self, index):
        return self.x[index], self.y[index], self.valid[index]


def arrays(model):
    return [v.detach().cpu().numpy().copy() for v in model.state_dict().values()]


def array_hash(values):
    return digest(b"".join(str((a.shape, a.dtype)).encode() + a.tobytes() for a in values))


def set_arrays(model, values):
    current = model.state_dict()
    if len(values) != len(current):
        raise ValueError("Model schema mismatch")
    tensors = {}
    for (key, value), incoming in zip(current.items(), values, strict=True):
        a = np.asarray(incoming)
        if tuple(value.shape) != a.shape or not np.isfinite(a).all():
            raise ValueError("Nonfinite or incompatible model")
        tensors[key] = torch.as_tensor(a, dtype=value.dtype)
    model.load_state_dict(tensors, strict=True)


def train_private(model, x, y, plan, sigma, ledger, reservation, directory: Path):
    torch.set_num_threads(1)
    engine = PrivacyEngine(accountant="prv", secure_mode=plan.mode == "confidential")
    original_hash = array_hash(arrays(model))
    event = {"kind": "training", "sigma": sigma, "q": plan.sample_rate, "steps": plan.local_steps}
    reserved = ledger.reserve(reservation, {"plan": plan.model_dump(), "input": original_hash}, event)
    cache = directory / (digest(reservation) + ".safetensors")
    if reserved["cached"]:
        if not cache.exists() or not reserved.get("output"):
            raise RuntimeError("Previous attempt was charged; output unavailable. Use a new attempt.")
        model.load_state_dict(load_file(str(cache)))
        if array_hash(arrays(model)) != reserved["output"]:
            raise ValueError("Cached output integrity failure")
        return model, ledger.summary()
    loader = DataLoader(SlotDataset(x, y, plan.capacity), batch_size=plan.batch_size)
    optimizer = torch.optim.SGD(model.parameters(), lr=plan.learning_rate)
    private_model, private_optimizer, private_loader = engine.make_private(
        module=model, optimizer=optimizer, data_loader=loader,
        noise_multiplier=sigma, max_grad_norm=plan.clipping_norm, poisson_sampling=True)
    if private_loader.sample_rate != plan.sample_rate or private_optimizer.expected_batch_size != plan.batch_size:
        raise RuntimeError("Sampling/normalization does not match reserved mechanism")
    criterion = nn.BCEWithLogitsLoss(reduction="none", pos_weight=torch.tensor(plan.positive_weight))
    private_model.train()
    executed = 0
    # Repeat the sampler without caching batches: cycle(loader) would reuse sampled records.
    while executed < plan.local_steps:
        for xb, yb, valid in private_loader:
            private_optimizer.zero_grad()
            individual = criterion(private_model(xb), yb) * valid
            loss = individual.mean() if len(individual) else individual.sum()
            loss.backward()
            private_optimizer.step()
            executed += 1
            if executed == plan.local_steps:
                break
    if sum(entry[2] for entry in engine.accountant.history) != plan.local_steps:
        raise RuntimeError("Executed accountant steps differ from reservation")
    output = private_model._module
    private_model.remove_hooks()
    directory.mkdir(parents=True, exist_ok=True)
    save_file(output.state_dict(), str(cache))
    ledger.complete(reservation, array_hash(arrays(output)))
    return output, ledger.summary()


def train_public(x, y, *, seed=42, steps=100, linear=False, positive_weight=5.0):
    torch.set_num_threads(1)
    torch.manual_seed(seed)
    model = Detector(linear=linear)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
    xt, yt = torch.as_tensor(x), torch.as_tensor(y)
    criterion = nn.BCEWithLogitsLoss(pos_weight=torch.tensor(positive_weight))
    generator = torch.Generator().manual_seed(seed)
    for _ in range(steps):
        indices = torch.randint(len(x), (min(256, len(x)),), generator=generator)
        optimizer.zero_grad()
        loss = criterion(model(xt[indices]), yt[indices])
        loss.backward()
        optimizer.step()
    return model


def predict(model, x):
    model.eval()
    with torch.no_grad():
        return torch.sigmoid(model(torch.as_tensor(x, dtype=torch.float32))).numpy()
