"""Re-export CSV + per-split JSONL from the verified master JSON,
so the verification_status updates made in-place by verify_mutants.py
are reflected everywhere, not just in verifier_dataset.json."""

import json
import csv
from pathlib import Path
from collections import Counter

OUT_DIR = Path("output")
rows = json.loads((OUT_DIR / "verifier_dataset.json").read_text())

fieldnames = []
for r in rows:
    for k in r.keys():
        if k not in fieldnames:
            fieldnames.append(k)
with open(OUT_DIR / "verifier_dataset.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    for r in rows:
        writer.writerow(r)

for split in ("train", "val", "test"):
    split_rows = [r for r in rows if r["split"] == split]
    with open(OUT_DIR / f"{split}.jsonl", "w") as f:
        for r in split_rows:
            f.write(json.dumps(r) + "\n")

print("Final dataset summary")
print("======================")
print(f"Total rows: {len(rows)}")
print("label:              ", dict(Counter(r["label"] for r in rows)))
print("source:             ", dict(Counter(r["source"] for r in rows)))
print("split:              ", dict(Counter(r["split"] for r in rows)))
print("difficulty:         ", dict(Counter(r["difficulty"] for r in rows)))
print("verification_status:", dict(Counter(r["verification_status"] for r in rows)))
print()
for split in ("train", "val", "test"):
    split_rows = [r for r in rows if r["split"] == split]
    print(f"{split}: n={len(split_rows)}, "
          f"pos={sum(1 for r in split_rows if r['label']=='equivalent')}, "
          f"neg={sum(1 for r in split_rows if r['label']=='not_equivalent')}")
