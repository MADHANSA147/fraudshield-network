import math

from opacus.accountants import PRVAccountant, RDPAccountant
from opacus.accountants.utils import get_noise_multiplier


def epsilon(events: list[dict], delta: float, cross_check=False) -> float:
    if not 0 < delta < 1:
        raise ValueError("Invalid delta")
    accountant = RDPAccountant() if cross_check else PRVAccountant()
    pure = 0.0
    any_training = False
    for event in events:
        if event["kind"] == "validation":
            if not math.isfinite(event["epsilon"]) or event["epsilon"] <= 0:
                raise ValueError("Invalid validation mechanism event")
            pure += event["epsilon"]
        elif event["kind"] == "training":
            if not (math.isfinite(event["sigma"]) and event["sigma"] > 0
                    and 0 < event["q"] <= 1 and isinstance(event["steps"], int)
                    and not isinstance(event["steps"], bool) and event["steps"] > 0):
                raise ValueError("Invalid mechanism event")
            for _ in range(event["steps"]):
                accountant.step(noise_multiplier=event["sigma"], sample_rate=event["q"])
            any_training = True
        else:
            raise ValueError("Unknown mechanism")
    value = pure + (accountant.get_epsilon(delta=delta) if any_training else 0.0)
    if not math.isfinite(value) or value < 0:
        raise ValueError("Accountant did not return a finite privacy bound")
    return float(value)


def calibrate(plan) -> float:
    # Leave numerical slack. The complete composed run is checked again before execution.
    sigma = get_noise_multiplier(target_epsilon=plan.epsilon_cap - plan.evaluation_epsilon - 0.03,
                                 target_delta=plan.delta, sample_rate=plan.sample_rate,
                                 steps=plan.rounds * plan.local_steps, accountant="prv",
                                 epsilon_tolerance=0.005)
    events = [{"kind": "training", "q": plan.sample_rate, "sigma": sigma,
               "steps": plan.rounds * plan.local_steps},
              {"kind": "validation", "epsilon": plan.evaluation_epsilon}]
    if epsilon(events, plan.delta) > plan.epsilon_cap:
        raise ValueError("Calibrated plan exceeds cap")
    return float(sigma)
