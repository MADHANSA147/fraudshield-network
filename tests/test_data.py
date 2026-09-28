import csv

import numpy as np

from fraudshield.data import FEATURES, load_paysim, temporal_group_split


def test_paysim_contract_and_temporal_sender_purge(tmp_path):
    path = tmp_path / "paysim-format-test-only.csv"
    with path.open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=["step", "type", "amount", "oldbalanceOrg", "nameOrig", "isFraud"])
        writer.writeheader()
        for i in range(200):
            writer.writerow({"step": i, "type": "TRANSFER" if i % 2 else "PAYMENT",
                             "amount": 100 + i, "oldbalanceOrg": 200, "isFraud": i % 5 == 0,
                             "nameOrig": "shared-sender" if i in (0, 199) else "sender-" + str(i)})
    # CSV boolean serialization is not accepted as a numeric label.
    content = path.read_text().replace("True", "1").replace("False", "0")
    path.write_text(content)
    records, source = load_paysim(path)
    splits, info = temporal_group_split(records)
    assert source["rows"] == 200
    assert info["purged_cross_time_senders_rows"] == 2
    assert sum(len(y) for split in splits.values() for _, y in split.values()) == 198
    assert all(x.shape[1] == len(FEATURES) and np.isfinite(x).all()
               for split in splits.values() for x, _ in split.values())
