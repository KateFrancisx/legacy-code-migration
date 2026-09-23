"""
load_rag_pairs.py

Adapts your already-mined, already-quality-checked GitHub pairs
(rag_ready_298.jsonl) into the same row schema build_dataset.py uses,
so they can be merged in as real positives -- tagged source="real_mined"
to distinguish them from the hand-curated synthetic ones ("real_curated").

Your fields already line up almost exactly:
    original_code, migrated_code  -> used as-is
    id                            -> used as family_id (so all mutants of
                                      this specific mined function stay in
                                      the same split)
    quality                       -> filtered against QUALITY_ALLOWLIST,
                                      also drives verification_status
    repo, function_name, file_path, source_url, commit, pr_number
                                   -> kept as provenance metadata

No mutation happens here -- this file only LOADS and FILTERS. Mutation
still happens later in build_dataset.py via mutate.py, same as for the
synthetic pairs.
"""

import json
from pathlib import Path

# Only pull rows at this confidence tier by default. Your file may also
# contain "medium_confidence" / "low_confidence" -- loosen this if you
# want more volume at the cost of noisier positives.
QUALITY_ALLOWLIST = {"high_confidence"}

# Map your "quality" field to our verification_status. high_confidence
# mined pairs are a good positive signal but were NOT behaviorally
# verified (no test execution) -- so "strong" here means "strong belief
# it's a real correct migration", not "executed and confirmed" like the
# offline harness does for the synthetic set. Be honest about this
# distinction when you write up the dataset card / methodology section.
QUALITY_TO_VERIFICATION_STATUS = {
    "high_confidence": "strong",
    "medium_confidence": "pending",
    "low_confidence": "pending",
}


def load_rag_pairs(path, quality_allowlist=QUALITY_ALLOWLIST, limit=None):
    """
    Returns a list of dicts shaped like base_pairs.BASE_PAIRS entries,
    plus extra provenance fields build_dataset.py will pass through.
    """
    path = Path(path)
    rows = []
    skipped_quality = 0
    skipped_no_code = 0

    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)

            quality = rec.get("quality")
            if quality_allowlist is not None and quality not in quality_allowlist:
                skipped_quality += 1
                continue

            original_code = rec.get("original_code")
            migrated_code = rec.get("migrated_code")
            if not original_code or not migrated_code:
                skipped_no_code += 1
                continue

            rows.append(dict(
                id=rec.get("id"),
                # No hand-picked "pattern" label for mined data -- derive a
                # loose tag from py2 markers if present, else generic.
                pattern=_infer_pattern(rec),
                original_code=original_code,
                migrated_code=migrated_code,
                # provenance, carried through as extra metadata columns
                repo=rec.get("repo"),
                function_name=rec.get("function_name"),
                file_path=rec.get("file_path"),
                source_url=rec.get("source_url"),
                commit=rec.get("commit"),
                pr_number=rec.get("pr_number"),
                quality=quality,
                similarity_ratio=(rec.get("verification") or {}).get("similarity_ratio"),
            ))

            if limit and len(rows) >= limit:
                break

    print(f"Loaded {len(rows)} rows from {path.name} "
          f"(skipped {skipped_quality} by quality filter, "
          f"{skipped_no_code} missing code)")
    return rows


def _infer_pattern(rec):
    markers = (rec.get("migration_context") or {}).get("py2_markers_in_original") or []
    if markers:
        return "mined:" + ",".join(sorted(set(markers)))[:60]
    return "mined:unknown"


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "data/rag_ready_298.jsonl"
    rows = load_rag_pairs(path)
    if rows:
        print("\nExample loaded row (code truncated):")
        r = dict(rows[0])
        r["original_code"] = r["original_code"][:120] + "..."
        r["migrated_code"] = r["migrated_code"][:120] + "..."
        print(json.dumps(r, indent=2))
