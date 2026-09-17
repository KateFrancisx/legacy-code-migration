#!/usr/bin/env python3
"""
Migration Job Selector

Takes a version-enriched manifest (output of version_detector.py) plus a
"job spec" describing what THIS migration run targets, and returns the
subset of files that should actually be sent through extraction + LLM
migration.

This is the seam that lets you switch from Python 2->3 to, say, Java 8->17
later WITHOUT touching the scanner, the version detector, or this file's
logic — you just pass a different MigrationJobSpec.

Usage (as a library):
    from migration_job_selector import MigrationJobSpec, select_files

    spec = MigrationJobSpec(language="Python", from_version="2", to_version="3")
    targets = select_files(manifest, spec)

Usage (as a CLI, for quick inspection):
    python migration_job_selector.py manifest_versioned.json \
        --language Python --from-version 2 --to-version 3
"""

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class MigrationJobSpec:
    """Describes ONE migration run. This is the only thing that changes
    when you move to a new language pair — nothing else in the pipeline
    needs to know the difference."""
    language: str                       # e.g. "Python", "Java"
    from_version: str                   # e.g. "2"
    to_version: str                     # e.g. "3"
    min_confidence: str = "medium"      # "low" | "medium" | "high" — see CONFIDENCE_RANK
    include_ambiguous: bool = False     # whether to include files version_detector
                                         # couldn't confidently classify


CONFIDENCE_RANK = {"low": 0, "medium": 1, "high": 2}


def select_files(manifest: dict, spec: MigrationJobSpec) -> dict:
    """
    Returns a dict with three buckets:
      - "targets": files that match the job spec and are confident enough
                   to migrate automatically
      - "needs_review": files that match language+from_version but fall
                   below the confidence bar, or were ambiguous
      - "skipped": everything else (wrong language, already on target
                   version, non-code, etc.) with a reason per file
    """
    targets, needs_review, skipped = [], [], []
    min_rank = CONFIDENCE_RANK[spec.min_confidence]

    for entry in manifest["files"]:
        if entry["category"] != "code":
            skipped.append({**entry, "skip_reason": "not_code"})
            continue

        if entry["language"] != spec.language:
            skipped.append({**entry, "skip_reason": "wrong_language"})
            continue

        vd = entry.get("version_detection")
        if vd is None:
            skipped.append({**entry, "skip_reason": "no_version_detection_available"})
            continue

        version = vd["version"]

        if version == spec.to_version:
            skipped.append({**entry, "skip_reason": "already_on_target_version"})
            continue

        if version in ("unknown", "ambiguous"):
            if spec.include_ambiguous:
                needs_review.append({**entry, "review_reason": f"version_{version}"})
            else:
                skipped.append({**entry, "skip_reason": f"version_{version}_excluded"})
            continue

        if version != spec.from_version:
            skipped.append({**entry, "skip_reason": f"version_{version}_not_in_job_scope"})
            continue

        # Matches language + from_version at this point.
        if CONFIDENCE_RANK.get(vd["confidence"], 0) < min_rank:
            needs_review.append({**entry, "review_reason": "low_detection_confidence"})
        else:
            targets.append(entry)

    return {
        "job_spec": {
            "language": spec.language,
            "from_version": spec.from_version,
            "to_version": spec.to_version,
            "min_confidence": spec.min_confidence,
        },
        "counts": {
            "targets": len(targets),
            "needs_review": len(needs_review),
            "skipped": len(skipped),
        },
        "targets": targets,
        "needs_review": needs_review,
        "skipped": skipped,
    }


def main():
    parser = argparse.ArgumentParser(description="Select migration targets from a versioned manifest")
    parser.add_argument("manifest_path")
    parser.add_argument("--language", required=True)
    parser.add_argument("--from-version", required=True)
    parser.add_argument("--to-version", required=True)
    parser.add_argument("--min-confidence", default="medium", choices=["low", "medium", "high"])
    parser.add_argument("--include-ambiguous", action="store_true")
    parser.add_argument("-o", "--output", default="migration_job.json")
    args = parser.parse_args()

    with open(args.manifest_path) as f:
        manifest = json.load(f)

    spec = MigrationJobSpec(
        language=args.language,
        from_version=args.from_version,
        to_version=args.to_version,
        min_confidence=args.min_confidence,
        include_ambiguous=args.include_ambiguous,
    )

    result = select_files(manifest, spec)

    with open(args.output, "w") as f:
        json.dump(result, f, indent=2)

    c = result["counts"]
    print(f"Targets: {c['targets']}  |  Needs review: {c['needs_review']}  |  Skipped: {c['skipped']}")
    print(f"Job file written to {args.output}")


if __name__ == "__main__":
    main()
