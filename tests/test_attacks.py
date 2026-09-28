import numpy as np
import torch
from fraudshield.attacks import loss_scores


def test_membership_scores_preserve_high_confidence_ordering():
    model = torch.nn.Linear(1, 1)
    with torch.no_grad():
        model.weight.fill_(1)
        model.bias.zero_()
    x = np.array([[20], [40]], dtype=np.float32)
    scores = loss_scores(model, x, np.ones(2, dtype=np.float32))
    assert np.isfinite(scores).all()
    assert scores[0] < scores[1] < 0
