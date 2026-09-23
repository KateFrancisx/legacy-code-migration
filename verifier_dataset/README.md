# Module 20 Verifier Dataset — synthetic v0

## What this is

A working, runnable pipeline that generates a labeled
`(original_code, migrated_code, label)` dataset for training/evaluating
your DL semantic-equivalence verifier — decoupled from your differential
testing module, which is still in progress.

Current batch: **56 rows** (20 positives, 36 negatives), split by function
family so no leakage between train/val/test.

## Files

| File | Purpose |
|---|---|
| `base_pairs.py` | 20 hand-curated, correct Python 2→3 migration pairs, covering 20 distinct migration patterns (iteritems, print stmt, except-as, division, xrange, unicode, map/zip iterators, has_key, next(), raise syntax, cmp→key, basestring, long, urllib/StringIO reorg, etc). These are the **positives**. |
| `mutate.py` | 18 mutator functions, each re-introducing ONE realistic migration bug into a correct snippet (tagged with a `mutation_type`). These generate the **hard negatives**. |
| `build_dataset.py` | Assembles positives + mutation negatives + random-mismatch easy negatives, assigns train/val/test splits **by family** (all mutants of one base function stay together), writes JSON/CSV/JSONL. |
| `verify_mutants.py` | Disposable offline harness — actually **executes** the correct code vs. each mutant on sample inputs and confirms they diverge in behavior before trusting the negative label. Caught and helped fix 3 mislabeled mutants in this batch already. |
| `export_final.py` | Re-exports CSV/JSONL after verification updates the master JSON in place. |
| `output/` | The generated dataset: `verifier_dataset.json` (full), `verifier_dataset.csv` (flat), `train.jsonl` / `val.jsonl` / `test.jsonl` (ready for a training loop). |

## Run order

```bash
python3 build_dataset.py      # assembles + splits
python3 verify_mutants.py     # confirms mutation negatives actually diverge
python3 export_final.py       # re-syncs csv/jsonl with verification results
```

## Schema (per row)

```json
{
  "id": "uuid",
  "family_id": "dict_iteritems_01",
  "original_code": "...python2...",
  "migrated_code": "...python3...",
  "label": "equivalent | not_equivalent",
  "source": "real_curated | mutation | mismatch | llm_adversarial | real_pass | real_fail",
  "mutation_type": "dict_iteritems_not_converted | null",
  "pattern": "dict_iteritems",
  "difficulty": "easy | hard",
  "verification_status": "strong | pending | flagged_for_review",
  "split": "train | val | test"
}
```

## Current composition

- **20 positives** (`real_curated`) — one per migration pattern, label=equivalent
- **21 mutation negatives** (`mutation`) — 18 confirmed diverging by the offline harness, 3 need `urllib`/stdin so are `manual_review` (network/input-dependent — can't verify offline)
- **15 mismatch negatives** (`mismatch`) — trivial easy negatives from random cross-pairing

## What's intentionally NOT in here yet (needs your live pipeline / API)

- **`real_pass`** — positives confirmed by *your* differential testing module once it's built. Same schema, just append rows with `source="real_pass"`.
- **`real_fail`** — negatives = real migrations *your* pipeline produced that failed diff testing. Free negatives once you have them — append with `source="real_fail"`.
- **`llm_adversarial`** — `build_llm_adversarial_stubs()` in `build_dataset.py` is a stub returning `[]` on purpose — no fabricated model output. Wire it to your Gemini pipeline with a prompt like: *"produce a plausible but subtly incorrect Python 3 migration of this snippet"*, then append the results with `source="llm_adversarial"`.

## To scale this up

1. **More base pairs**: add entries to `BASE_PAIRS` in `base_pairs.py` — pull real examples from GitHub migration PRs/commits (search `"port to python 3"`, `"drop python 2 support"`) or run `2to3` on real repos.
2. **More mutators**: add functions to `MUTATORS` in `mutate.py` for patterns not yet covered (e.g. `__future__` imports, metaclass syntax, `super()` no-args, byte string literals, `configparser`/`Queue` renames).
3. **Extend `SAMPLES` in `verify_mutants.py`** whenever you add a base pair, so new mutants get behaviorally confirmed instead of sitting at `pending`.
4. Once your diff-testing module lands, promote `real_curated` positives to `real_pass` after re-confirming them through it, and start appending real pipeline failures as `real_fail`.

## Known limitation to flag

At 56 rows this is a **structural skeleton**, not enough volume to actually train a DL verifier — it's sized to prove the pipeline works end-to-end (schema, splitting-by-family, mutation generation, offline verification) so you can scale it by (a) adding more base pairs from real repos and (b) wiring up the `llm_adversarial` stub, without reshaping anything downstream.
