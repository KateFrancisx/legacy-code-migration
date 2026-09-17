#!/usr/bin/env python3
"""
Full Pipeline — ONE command, ONE output file.

Takes a repo path, runs scan -> version detect -> select -> extract
entirely in memory, and writes ONLY the final extracted-features file
for that specific repo. This is what a real "user uploads a repo" flow
looks like -- no leftover manifest/versioned/job files unless you
explicitly ask to keep them (useful for debugging).

Usage:
    python scripts/run_pipeline.py <repo_path>

    (defaults to --language Python --from-version 2 --to-version 3,
    since that's the current migration pair)

Output:
    outputs/<repo_name>_features.json   <- the ONLY file written by default

Debugging flag:
    --keep-intermediate   also writes manifest.json and migration_job.json
                           alongside the features file
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.scanner.repo_scanner import scan_repository
from pipeline.version_detection.version_detector import enrich_manifest
from pipeline.selection.migration_job_selector import MigrationJobSpec, select_files
from pipeline.extraction.python_extractor import PythonExtractor

# Registry pattern -- add "Java": JavaExtractor() etc. here later, nothing
# else in this file changes.
EXTRACTORS = {
    "Python": PythonExtractor(),
}


def run_migration_job(repo_path: str, language: str = "Python", from_version: str = "2",
                       to_version: str = "3", min_confidence: str = "medium",
                       include_ambiguous: bool = False, output_dir: str = "outputs",
                       keep_intermediate: bool = False) -> list:
    """The single entry point. Returns the list of extracted feature
    dicts, and writes exactly one file (the features file) unless
    keep_intermediate=True."""

    repo_path = Path(repo_path).resolve()
    out_dir = Path(output_dir)
    out_dir.mkdir(exist_ok=True)
    repo_name = repo_path.name

    print(f"[1/4] Scanning {repo_path} ...")
    manifest = scan_repository(str(repo_path))
    print(f"      {manifest['total_files']} files, languages: {', '.join(manifest['summary']['languages_detected']) or 'none'}")

    print("[2/4] Detecting versions ...")
    manifest = enrich_manifest(manifest, repo_path)

    print("[3/4] Selecting migration targets ...")
    spec = MigrationJobSpec(language=language, from_version=from_version, to_version=to_version,
                             min_confidence=min_confidence, include_ambiguous=include_ambiguous)
    job = select_files(manifest, spec)
    c = job["counts"]
    print(f"      Targets: {c['targets']}  Needs review: {c['needs_review']}  Skipped: {c['skipped']}")

    print("[4/4] Extracting functions + features ...")
    extractor = EXTRACTORS.get(language)
    if extractor is None:
        print(f"      No extractor registered for '{language}' yet -- skipping extraction.")
        all_records = []
    else:
        all_records = []
        for entry in job["targets"]:
            file_path = repo_path / entry["path"]
            try:
                source = file_path.read_text(errors="ignore")
            except OSError as e:
                print(f"      [WARN] could not read {file_path}: {e}")
                continue
            file_version = entry.get("version_detection", {}).get("version", from_version)
            records = extractor.extract(entry["path"], source, file_version)
            all_records.extend(records)
        print(f"      {len(all_records)} functions extracted from {c['targets']} target files")

    feature_dicts = [r.to_dict() for r in all_records]

    features_path = out_dir / f"{repo_name}_features.json"
    features_path.write_text(json.dumps(feature_dicts, indent=2))

    if keep_intermediate:
        (out_dir / f"{repo_name}_manifest.json").write_text(json.dumps(manifest, indent=2))
        (out_dir / f"{repo_name}_migration_job.json").write_text(json.dumps(job, indent=2))
        print(f"      (intermediate files also written, since --keep-intermediate was set)")

    print(f"\nDone. {len(feature_dicts)} extracted features written to {features_path}")
    return feature_dicts


def main():
    parser = argparse.ArgumentParser(description="Full pipeline: repo path in, features file out")
    parser.add_argument("repo_path", help="Path to the repo/folder to analyze")
    parser.add_argument("--language", default="Python")
    parser.add_argument("--from-version", default="2")
    parser.add_argument("--to-version", default="3")
    parser.add_argument("--min-confidence", default="medium", choices=["low", "medium", "high"])
    parser.add_argument("--include-ambiguous", action="store_true")
    parser.add_argument("--output-dir", default="outputs")
    parser.add_argument("--keep-intermediate", action="store_true",
                         help="Also write manifest/job files for debugging")
    args = parser.parse_args()

    run_migration_job(
        repo_path=args.repo_path,
        language=args.language,
        from_version=args.from_version,
        to_version=args.to_version,
        min_confidence=args.min_confidence,
        include_ambiguous=args.include_ambiguous,
        output_dir=args.output_dir,
        keep_intermediate=args.keep_intermediate,
    )


if __name__ == "__main__":
    main()