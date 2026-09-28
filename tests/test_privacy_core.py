import numpy as np
import pytest
import torch

from fraudshield.contracts import Plan
from fraudshield.data import FEATURES, features, fixture
from fraudshield.evaluation import count_mechanism, private_rates
from fraudshield.ledger import BudgetExceeded, PrivacyLedger
from fraudshield.security import load_key, public_key, sign, verify
from fraudshield.training import Detector, SlotDataset, train_private
from fraudshield.accounting import epsilon


def test_feature_contract_excludes_future_information():
    row = {"amount": 100, "type": "TRANSFER", "step": 2, "oldbalanceOrg": 200}
    assert np.array_equal(features(row), features({**row, "newbalanceOrig": 50000, "isFraud": 1}))
    assert features(row).shape == (len(FEATURES),)


def test_slots_are_fixed_and_empty_records_have_zero_gradients():
    model = Detector()
    x, y = fixture(3, 42)
    dataset = SlotDataset(x, y, 8)
    assert len(dataset) == 8
    loss = torch.nn.functional.binary_cross_entropy_with_logits(model(dataset.x), dataset.y, reduction="none")
    (loss[3:] * dataset.valid[3:]).sum().backward()
    assert all(torch.count_nonzero(p.grad) == 0 for p in model.parameters())


def test_ledger_idempotency_restart_and_fail_closed(tmp_path):
    ledger = PrivacyLedger(tmp_path / "privacy.db", "stable-lineage", 1, 1e-6)
    event = {"kind": "validation", "epsilon": .6}
    assert not ledger.reserve("one", {"model": "a"}, event)["cached"]
    assert ledger.reserve("one", {"model": "a"}, event)["cached"]
    restarted = PrivacyLedger(tmp_path / "privacy.db", "stable-lineage", 1, 1e-6)
    with pytest.raises(BudgetExceeded):
        restarted.reserve("renamed-run", {"model": "b"}, event)
    with pytest.raises(ValueError):
        restarted.reserve("one", {"model": "different"}, event)
    with pytest.raises(ValueError):
        PrivacyLedger(tmp_path / "privacy.db", "stable-lineage", 8, 1e-6)
    assert restarted.summary()["epsilon"] == .6


def test_opendp_count_sensitivity_and_noise_bounds():
    measurement = count_mechanism(.5)
    assert measurement.check(1, .5)
    assert len(measurement([0, 0, 1, 3])) == 4
    result = private_rates([{"noisy_counts": [-10, -20, 0, 0], "epsilon": .5}] * 3)
    assert not result["denominators_supported"]
    assert result["fpr_interval"][1] == 1


def test_signed_payload_is_bound_to_approved_key(tmp_path):
    key = load_key(tmp_path / "identity.key")
    envelope = sign({"epsilon": 3}, key)
    assert verify(envelope, public_key(key))["epsilon"] == 3
    envelope["payload"]["epsilon"] = 0
    with pytest.raises(Exception):
        verify(envelope, public_key(key))


def test_real_opacus_steps_and_cached_result(tmp_path):
    plan = Plan(capacity=128, batch_size=16, local_steps=2, rounds=1)
    ledger = PrivacyLedger(tmp_path / "ledger.db", "fixed", 8, plan.delta)
    x, y = fixture(80, 1)
    torch.manual_seed(8)
    model = Detector()
    initial = {k: v.clone() for k, v in model.state_dict().items()}
    result, statement = train_private(model, x, y, plan, 2.0, ledger, "job:1", tmp_path)
    assert statement["events"][0]["steps"] == 2
    assert 0 < statement["epsilon"] < 8
    other = Detector()
    other.load_state_dict(initial)
    repeated, _ = train_private(other, x, y, plan, 2.0, ledger, "job:1", tmp_path)
    assert all(torch.equal(a, b) for a, b in zip(result.parameters(), repeated.parameters()))


@pytest.mark.parametrize("event", [
    {"kind": "validation", "epsilon": -1},
    {"kind": "validation", "epsilon": float("nan")},
    {"kind": "training", "sigma": float("inf"), "q": .1, "steps": 1},
    {"kind": "training", "sigma": 1, "q": 2, "steps": 1},
    {"kind": "training", "sigma": 1, "q": .1, "steps": 1.5},
])
def test_bad_accounting_events_fail_closed(event):
    with pytest.raises(ValueError):
        epsilon([event], 1e-6)


def test_concurrent_reservations_cannot_overspend(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    ledger = PrivacyLedger(tmp_path / "concurrent.db", "dataset", 1, 1e-6)
    def reserve(index):
        try:
            ledger.reserve(str(index), {}, {"kind": "validation", "epsilon": .6})
            return True
        except BudgetExceeded:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(reserve, [0, 1])) == 1
    assert ledger.summary()["epsilon"] == .6


def test_crash_reservation_stays_spent(tmp_path):
    from fraudshield.security import digest
    from fraudshield.training import array_hash, arrays
    plan = Plan(capacity=128, batch_size=16, local_steps=1, rounds=1)
    model = Detector()
    ledger = PrivacyLedger(tmp_path / "crash.db", "dataset", 8, plan.delta)
    event = {"kind": "training", "sigma": 2., "q": plan.sample_rate, "steps": 1}
    ledger.reserve("crash", {"plan": plan.model_dump(), "input": array_hash(arrays(model))}, event)
    x, y = fixture(16, 8)
    with pytest.raises(RuntimeError, match="charged"):
        train_private(model, x, y, plan, 2., ledger, "crash", tmp_path)
    assert not (tmp_path / (digest("crash") + ".safetensors")).exists()
    assert ledger.summary()["epsilon"] > 0


def test_empty_poisson_batch_still_adds_noise_and_spends(tmp_path, monkeypatch):
    from opacus.utils.uniform_sampler import UniformWithReplacementSampler
    from fraudshield.training import arrays
    monkeypatch.setattr(UniformWithReplacementSampler, "__iter__", lambda self: iter([[]]))
    plan = Plan(capacity=128, batch_size=8, rounds=1, local_steps=1)
    ledger = PrivacyLedger(tmp_path / "empty.db", "dataset", 8, plan.delta)
    x, y = fixture(12, 3)
    model = Detector()
    initial = arrays(model)
    updated, statement = train_private(model, x, y, plan, 2, ledger, "empty", tmp_path)
    assert statement["events"][0]["steps"] == 1
    assert any(not np.array_equal(a, b) for a, b in zip(initial, arrays(updated)))


def test_opacus_clips_individual_gradients_before_aggregation():
    from opacus import PrivacyEngine
    from torch.utils.data import DataLoader, TensorDataset
    model = torch.nn.Linear(2, 1)
    x = torch.tensor([[100., 0.], [0., 1.]])
    y = torch.tensor([[1.], [0.]])
    manual = []
    for i in range(2):
        loss = torch.nn.functional.binary_cross_entropy_with_logits(model(x[i:i+1]), y[i:i+1])
        grads = torch.autograd.grad(loss, list(model.parameters()))
        norm = torch.sqrt(sum((g**2).sum() for g in grads))
        manual.append([g * min(1., float(1 / (norm + 1e-6))) for g in grads])
    engine = PrivacyEngine()
    private, optimizer, _ = engine.make_private(module=model, optimizer=torch.optim.SGD(model.parameters(), lr=.1),
        data_loader=DataLoader(TensorDataset(x, y), batch_size=2), noise_multiplier=1, max_grad_norm=1)
    torch.nn.functional.binary_cross_entropy_with_logits(private(x), y).backward()
    optimizer.clip_and_accumulate()
    for index, parameter in enumerate(private.parameters()):
        assert torch.allclose(parameter.summed_grad, sum(g[index] for g in manual), atol=1e-6)
    private.remove_hooks()
