"""
build_dataset.py

Assembles the full labeled dataset for Module 20 (DL verifier training):
    (original_code, migrated_code, label, source, mutation_type, difficulty, family_id)

Sources included in THIS synthetic batch:
    1. real_curated   -- hand-verified correct migrations (positives)      [label=yes]
    2. mutation       -- mutation-injected hard negatives                  [label=no]
    3. mismatch       -- random cross-pairing, easy negatives              [label=no]
    4. llm_adversarial-- PLACEHOLDER stubs marked as TODO (needs live LLM  [label=no]
                          call against your Gemini pipeline -- see note
                          at bottom of file). Not fabricated here.

NOT included (by design -- these require your actual pipeline):
    - real_pass  (positives confirmed by YOUR differential testing module)
    - real_fail  (negatives = migrations YOUR pipeline actually produced
                  and that failed diff testing)
  -> Both have a `source` value reserved in the schema so you can append
     them later without reshaping anything.

Splitting: by FAMILY (base_pair id), so all mutants of the same base
function land in the same split -- prevents train/test leakage.
"""

import json
import csv
import random
import uuid
from pathlib import Path

from base_pairs import BASE_PAIRS
from mutate import generate_mutants
from load_rag_pairs import load_rag_pairs
from generic_mutate import generate_generic_mutants

random.seed(42)

OUT_DIR = Path("output")
OUT_DIR.mkdir(exist_ok=True)

# Path to your mined+quality-checked corpus. Yours lives one folder up
# from verifier_dataset/, at CodeMigration/data/rag_ready_298.jsonl --
# change this if you move the file or your layout differs.
RAG_PAIRS_PATH = Path("../data/rag_ready_298.jsonl")


def make_row(original_code, migrated_code, label, source, family_id,
             mutation_type=None, difficulty="easy", pattern=None,
             verification_status="weak"):
    return dict(
        id=str(uuid.uuid4()),
        family_id=family_id,
        original_code=original_code,
        migrated_code=migrated_code,
        label=label,                      # "equivalent" | "not_equivalent"
        source=source,                    # real_curated | mutation | mismatch | llm_adversarial | real_pass | real_fail
        mutation_type=mutation_type,
        pattern=pattern,
        difficulty=difficulty,            # easy | hard
        verification_status=verification_status,  # weak | strong | pending
        split=None,                       # filled in later
    )


def build_positives():
    rows = []
    for bp in BASE_PAIRS:
        rows.append(make_row(
            original_code=bp["original_code"],
            migrated_code=bp["migrated_code"],
            label="equivalent",
            source="real_curated",
            family_id=bp["id"],
            difficulty="easy",
            pattern=bp["pattern"],
            # Hand-curated + these are well-known correct idioms -> mark strong.
            # Real pipeline positives should still get re-verified via diff
            # testing when that module lands (source stays real_curated,
            # not real_pass, until your pipeline itself confirms one).
            verification_status="strong",
        ))
    return rows


def build_mined_positives(path=RAG_PAIRS_PATH):
    """Real positives mined from GitHub migration PRs, already filtered
    by your check_pair_quality.py step. See load_rag_pairs.py.
    Returns (rows, families) -- families is reused by the mutation/mismatch
    generators below so mined pairs get mutated too, not just the 20
    synthetic ones."""
    if not Path(path).exists():
        print(f"[build_mined_positives] {path} not found -- skipping "
              f"(only synthetic base pairs will be used).")
        return [], []

    mined = load_rag_pairs(path)
    # Reshape into the same {id, pattern, original_code, migrated_code}
    # shape as BASE_PAIRS entries, so generate_mutants() and the mismatch
    # generator work identically on both sources.
    families = [dict(
        id=f"mined__{m['id']}",
        pattern=m["pattern"],
        original_code=m["original_code"],
        migrated_code=m["migrated_code"],
    ) for m in mined]

    rows = []
    for m, fam in zip(mined, families):
        r = make_row(
            original_code=fam["original_code"],
            migrated_code=fam["migrated_code"],
            label="equivalent",
            source="real_mined",
            family_id=fam["id"],
            difficulty="easy",
            pattern=fam["pattern"],
            # Trust level comes from your own quality check, not a fresh
            # judgment here -- see QUALITY_TO_VERIFICATION_STATUS in
            # load_rag_pairs.py. high_confidence -> "strong" belief this
            # is a real correct migration, but NOT behaviorally executed
            # (unlike the synthetic set's offline harness). Be explicit
            # about that distinction in any dataset writeup.
            verification_status="strong",
        )
        r["repo"] = m.get("repo")
        r["function_name"] = m.get("function_name")
        r["source_url"] = m.get("source_url")
        rows.append(r)

    return rows, families


def build_mutation_negatives(families=BASE_PAIRS):
    rows = []
    for bp in families:
        for m in generate_mutants(bp):
            rows.append(make_row(
                original_code=bp["original_code"],
                migrated_code=m["mutated_code"],
                label="not_equivalent",
                source="mutation",
                family_id=bp["id"],
                mutation_type=m["mutation_type"],
                difficulty=m["difficulty"],
                pattern=bp["pattern"],
                # NOT strong: we injected a known-risky pattern but haven't
                # run behavioral verification yet. Promote after running
                # verify_mutants.py (see that script).
                verification_status="pending",
            ))
    return rows


def build_generic_mutation_negatives(families, max_per_type=1, seed=42):
    """AST-based mutators that work on ANY function (not gated by string
    patterns), used to fill out negatives for mined functions that don't
    match any migration-specific pattern from mutate.py. This is what
    fixes the 318:50 imbalance -- most of the 298 mined functions get at
    least one mutant from here even though mutate.py produced none."""
    rows = []
    for fam in families:
        mutants = generate_generic_mutants(
            fam["migrated_code"], max_per_type=max_per_type, seed=seed)
        for m in mutants:
            rows.append(make_row(
                original_code=fam["original_code"],
                migrated_code=m["mutated_code"],
                label="not_equivalent",
                source="generic_mutation",
                family_id=fam["id"],
                mutation_type=m["mutation_type"],
                difficulty=m["difficulty"],
                pattern=fam["pattern"],
                # Generic AST mutation is even less certain than the
                # pattern-based mutators (no domain knowledge that this
                # is migration-relevant) -- always pending until manually
                # spot-checked or run through a real test harness.
                verification_status="pending",
            ))
    return rows


def build_mismatch_negatives(families=BASE_PAIRS, n=15):
    """Easy negatives: original from one family paired with migrated code
    from a *different* family. Trivially non-equivalent."""
    rows = []
    pairs = list(families)
    if len(pairs) < 2:
        return rows
    attempts = 0
    made = 0
    while made < n and attempts < n * 10:
        attempts += 1
        a, b = random.sample(pairs, 2)
        rows.append(make_row(
            original_code=a["original_code"],
            migrated_code=b["migrated_code"],
            label="not_equivalent",
            source="mismatch",
            family_id=f"mismatch__{a['id']}__{b['id']}",
            mutation_type="cross_function_mismatch",
            difficulty="easy",
            pattern=f"{a['pattern']}_vs_{b['pattern']}",
            verification_status="strong",  # trivially true by construction
        ))
        made += 1
    return rows


def build_llm_adversarial_stubs():
    """
    PLACEHOLDER ONLY.

    Real llm_adversarial negatives should be generated by prompting your
    Gemini pipeline (or another model) with something like:

        "Here is a Python 2 function and a Python 3 migration of it that
         LOOKS correct but contains a subtle bug that changes its behavior
         for some inputs. Identify or construct such a migration."

    That requires a live API call, which this offline script does not make
    (no fabricated model output is included here). This function returns
    an empty list -- wire it up to your actual Gemini call and re-run.
    """
    return []


def assign_splits(rows, train=0.7, val=0.15, test=0.15):
    """Split by family_id so mutants of the same base function never
    cross a split boundary."""
    families = sorted(set(r["family_id"] for r in rows))
    random.shuffle(families)
    n = len(families)
    n_train = int(n * train)
    n_val = int(n * val)
    train_fams = set(families[:n_train])
    val_fams = set(families[n_train:n_train + n_val])
    test_fams = set(families[n_train + n_val:])

    for r in rows:
        if r["family_id"] in train_fams:
            r["split"] = "train"
        elif r["family_id"] in val_fams:
            r["split"] = "val"
        else:
            r["split"] = "test"
    return rows


def summarize(rows):
    from collections import Counter
    print(f"Total rows: {len(rows)}")
    print("By label:   ", dict(Counter(r["label"] for r in rows)))
    print("By source:  ", dict(Counter(r["source"] for r in rows)))
    print("By split:   ", dict(Counter(r["split"] for r in rows)))
    print("By difficulty:", dict(Counter(r["difficulty"] for r in rows)))
    print("By verification_status:", dict(Counter(r["verification_status"] for r in rows)))


def main():
    mined_positive_rows, mined_families = build_mined_positives()
    all_families = list(BASE_PAIRS) + mined_families

    rows = []
    rows += build_positives()
    rows += mined_positive_rows
    rows += build_mutation_negatives(families=all_families)
    rows += build_generic_mutation_negatives(families=all_families, max_per_type=1)
    rows += build_mismatch_negatives(families=all_families, n=15)
    rows += build_llm_adversarial_stubs()

    rows = assign_splits(rows)
    summarize(rows)

    # Write JSON (full fidelity)
    json_path = OUT_DIR / "verifier_dataset.json"
    with open(json_path, "w") as f:
        json.dump(rows, f, indent=2)

    # Write CSV (flat, for quick inspection / pandas). Union of keys across
    # all rows, since mined rows carry extra provenance columns
    # (repo/function_name/source_url) synthetic rows don't have.
    csv_path = OUT_DIR / "verifier_dataset.csv"
    fieldnames = []
    for r in rows:
        for k in r.keys():
            if k not in fieldnames:
                fieldnames.append(k)
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    # Also write per-split JSONL, the format most DL training loops want
    for split in ("train", "val", "test"):
        split_rows = [r for r in rows if r["split"] == split]
        with open(OUT_DIR / f"{split}.jsonl", "w") as f:
            for r in split_rows:
                f.write(json.dumps(r) + "\n")

    print(f"\nWrote: {json_path}")
    print(f"Wrote: {csv_path}")
    print(f"Wrote: {OUT_DIR}/train.jsonl, val.jsonl, test.jsonl")


if __name__ == "__main__":
    main()
