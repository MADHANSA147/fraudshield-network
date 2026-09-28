from fraudshield.contracts import Plan
from fraudshield.federation import Federation
from fraudshield.security import load_key


def test_three_process_flower_secagg(tmp_path):
    plan = Plan(capacity=128, batch_size=16, local_steps=2, rounds=1)
    federation = Federation(plan, "integration", tmp_path / "institutions", 2.0, load_key(tmp_path / "server.key"))
    rounds = []
    try:
        federation.start()
        result = federation.train(lambda r, receipts, size: rounds.append((r, receipts, size)))
        assert len(result) == 6
        assert len(rounds) == 1
        assert len(rounds[0][1]) == 3
        assert len(federation.grid.trace) == 12
        assert all(entry["array_records"] == 0 for entry in federation.grid.trace)
        releases = federation.validate(result, .5)
        assert len(releases) == 3
        assert all("noisy_counts" in r["payload"] for r in releases)
        repeated = federation.validate(result, .5)
        assert repeated == releases  # Noise is cached, not redrawn on retry.
        for conn, process in list(federation.workers.values())[:1]:
            process.terminate()
            process.join(3)
        import pytest
        with pytest.raises((BrokenPipeError, EOFError, OSError, RuntimeError)):
            federation.train(lambda *args: None)
    finally:
        federation.close()
