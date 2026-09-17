#!/usr/bin/env python3
"""
check_pair_quality.py

Runs cheap, automated heuristic checks over pairs.jsonl to flag how
likely each (original_code, migrated_code) pair is to be a genuine
Python 2 -> 3 migration, vs. unrelated noise that happened to land in a
matched PR.

This does NOT replace manual review or the eventual DL verifier model
(Module 20) -- it's a triage pass so you only have to eyeball the
ambiguous cases instead of all of them.

USAGE
-----
python check_pair_quality.py --in data/pairs.jsonl --out data/pairs_quality.jsonl --sample 15

OUTPUT
------
- data/pairs_quality.jsonl : every input pair + a "quality" block:
    {
      "quality": {
        "label": "high_confidence" | "needs_review" | "likely_noise",
        "original_fails_py3_parse": true/false,
        "migrated_parses_py3": true/false,
        "py2_markers_in_original": ["unicode(", "except ... ,"],
        "py2_markers_remaining_in_migrated": [],
        "similarity_ratio": 0.62
      },
      ...original fields...
    }
- Console summary: counts per label
- A random sample (--sample N) of "needs_review" pairs printed for you
  to manually eyeball
"""

import argparse
import ast
import difflib
import json
import re
import random
from typing import List

# Regex markers for common Python-2-only idioms that remain *syntactically
# valid* Python 3 (so ast.parse alone won't catch them).
PY2_MARKERS = [
    (r"\bunicode\s*\(", "unicode("),
    (r"\bxrange\s*\(", "xrange("),
    (r"\braw_input\s*\(", "raw_input("),
    (r"\.iteritems\s*\(", ".iteritems("),
    (r"\.itervalues\s*\(", ".itervalues("),
    (r"\.iterkeys\s*\(", ".iterkeys("),
    (r"\.has_key\s*\(", ".has_key("),
    (r"except\s+\w+(?:\.\w+)*\s*,\s*\w+\s*:", "except X, e:"),
    (r"\bbasestring\b", "basestring"),
    (r"\blong\s*\(", "long("),
    # six branch conditionals -- if these remain in the MIGRATED version,
    # that's a real sign of leftover/incomplete conditional logic.
    (r"\bsix\.PY2\b", "six.PY2"),
    (r"\bsix\.PY3\b", "six.PY3"),
    (r"\binspect\.getargspec\s*\(", "inspect.getargspec("),
    # Deprecated unittest aliases removed during the same migration era
    # (heavily featured in PRs like "Fix unittest DeprecationWarnings").
    # Presence in original + absence in migrated is a strong, deliberate
    # migration signal -- even though the resulting diff is often tiny
    # and would otherwise look like trivial noise by text similarity.
    (r"\.assertEquals\s*\(", ".assertEquals("),
    (r"\.assertNotEquals\s*\(", ".assertNotEquals("),
    (r"\.assertAlmostEquals\s*\(", ".assertAlmostEquals("),
    (r"\.assertNotAlmostEquals\s*\(", ".assertNotAlmostEquals("),
    (r"\.failUnlessEqual\s*\(", ".failUnlessEqual("),
    (r"\.failIfEqual\s*\(", ".failIfEqual("),
    (r"\.failUnless\s*\(", ".failUnless("),
    (r"\.failIf\s*\(", ".failIf("),
]

# six type-alias / utility calls (six.text_type, six.string_types, etc.)
# are legitimate, INTENDED to remain in fully-migrated, dual-compatible
# code for years -- their presence is not a sign of incomplete migration.
# Still detected and reported as "in_original" signal (their disappearance
# from a docstring-free unicode()/basestring() call is a good positive
# signal), but never counted against the migrated version.
SIX_COMPAT_MARKERS = [
    (r"\bsix\.text_type\b", "six.text_type"),
    (r"\bsix\.string_types\b", "six.string_types"),
    (r"\bsix\.binary_type\b", "six.binary_type"),
    (r"\bsix\.moves\b", "six.moves"),
    (r"\bsix\.u\s*\(", "six.u("),
    (r"\bsix\.b\s*\(", "six.b("),
    (r"\bsix\.iteritems\s*\(", "six.iteritems("),
]

# Markers excluded from noise/similarity scoring because they generate too
# many false positives in real code (e.g. docstring formatting, not actual
# Python 2 syntax). Still detected and reported, just not weighted as a
# migration signal on their own.
NOISY_MARKERS = {"backtick repr"}


def find_py2_markers(code: str) -> List[str]:
    found = []
    for pattern, label in PY2_MARKERS:
        if re.search(pattern, code):
            found.append(label)
    return found


def find_six_compat_markers(code: str) -> List[str]:
    found = []
    for pattern, label in SIX_COMPAT_MARKERS:
        if re.search(pattern, code):
            found.append(label)
    return found


def parses_as_py3(code: str) -> bool:
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False


def similarity(a: str, b: str) -> float:
    return round(difflib.SequenceMatcher(None, a, b).ratio(), 3)


def classify(pair: dict) -> dict:
    original = pair["original_code"]
    migrated = pair["migrated_code"]

    original_parses = parses_as_py3(original)
    migrated_parses = parses_as_py3(migrated)

    markers_in_original = find_py2_markers(original)
    markers_remaining = find_py2_markers(migrated)
    six_compat_in_original = find_six_compat_markers(original)
    six_compat_in_migrated = find_six_compat_markers(migrated)

    # Filter out noisy markers (e.g. docstring backticks) before they
    # influence classification -- still reported in the output for
    # transparency, just not trusted as a real migration signal.
    signal_markers_original = [m for m in markers_in_original if m not in NOISY_MARKERS]
    signal_markers_remaining = [m for m in markers_remaining if m not in NOISY_MARKERS]

    sim = similarity(original, migrated)

    # --- classification logic ---
    if not migrated_parses:
        # Migrated version doesn't even parse as valid Python 3 -- almost
        # certainly not a usable pair (could be a partial diff, a syntax
        # error introduced, or we grabbed the wrong version).
        label = "likely_noise"
    elif not original_parses:
        # Original fails Python 3 parsing (e.g. real print-statement,
        # except-comma syntax) but migrated parses cleanly -> strongest
        # positive signal of a genuine migration.
        label = "high_confidence"
    elif signal_markers_original and not signal_markers_remaining:
        # Original had known Py2-only API markers, migrated has none left
        # -> also strong positive signal.
        label = "high_confidence"
    elif six_compat_in_original and not signal_markers_remaining:
        # Original used basestring/unicode/etc alongside six type-alias
        # calls, migrated dropped the Py2-only forms and kept the six
        # compat calls (which are meant to persist long-term) -> good.
        label = "high_confidence"
    elif signal_markers_remaining:
        # Migrated code still contains Py2-only markers -> migration looks
        # incomplete or this isn't really a migration diff.
        label = "needs_review"
    elif sim > 0.97:
        # Both parse fine, no markers either side, and the code is nearly
        # identical -> likely a trivial/unrelated change, not a migration.
        # NOTE: checked only after the marker-based checks above, so a
        # genuine but minimal rename (e.g. assertEquals -> assertEqual)
        # is never miscaught here even though its text similarity is high.
        label = "likely_noise"
    else:
        # Both parse fine, no clear markers, but a real change happened.
        # Could be a genuine API-level migration we don't have a marker
        # for, or could be unrelated. Needs a human look.
        label = "needs_review"

    return {
        "label": label,
        "original_fails_py3_parse": not original_parses,
        "migrated_parses_py3": migrated_parses,
        "py2_markers_in_original": markers_in_original,
        "py2_markers_remaining_in_migrated": markers_remaining,
        "similarity_ratio": sim,
    }


def main():
    parser = argparse.ArgumentParser(description="Heuristic quality check for migration pairs")
    parser.add_argument("--in", dest="infile", default="data/pairs.jsonl")
    parser.add_argument("--out", dest="outfile", default="data/pairs_quality.jsonl")
    parser.add_argument("--sample", type=int, default=10, help="how many needs_review pairs to print")
    parser.add_argument("--noise-sample", type=int, default=0, help="how many likely_noise pairs to print")
    args = parser.parse_args()

    pairs = []
    bad_lines = 0
    with open(args.infile, "r", encoding="utf-8-sig") as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                pairs.append(json.loads(line))
            except json.JSONDecodeError as e:
                bad_lines += 1
                print(f"  WARNING: skipping malformed line {line_num}: {e}", file=__import__("sys").stderr)

    if bad_lines:
        print(f"\nSkipped {bad_lines} malformed line(s) out of the file.\n")

    counts = {"high_confidence": 0, "needs_review": 0, "likely_noise": 0}
    results = []
    for pair in pairs:
        quality = classify(pair)
        counts[quality["label"]] += 1
        results.append({"quality": quality, **pair})

    with open(args.outfile, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    total = len(pairs)
    print(f"\nChecked {total} pairs from {args.infile}\n")
    for label, count in counts.items():
        pct = (count / total * 100) if total else 0
        print(f"  {label:16s}: {count:5d}  ({pct:.1f}%)")
    print(f"\nFull results written to {args.outfile}")

    review_candidates = [r for r in results if r["quality"]["label"] == "needs_review"]
    if review_candidates and args.sample > 0:
        sample = random.sample(review_candidates, min(args.sample, len(review_candidates)))
        print(f"\n--- {len(sample)} random 'needs_review' pairs for manual check ---\n")
        for r in sample:
            print(f"repo={r['repo']}  pr=#{r['pr_number']}  func={r['function_name']}")
            print(f"markers_in_original={r['quality']['py2_markers_in_original']}  "
                  f"similarity={r['quality']['similarity_ratio']}")
            print("--- ORIGINAL ---")
            print(r["original_code"][:400])
            print("--- MIGRATED ---")
            print(r["migrated_code"][:400])
            print("=" * 70)

    noise_candidates = [r for r in results if r["quality"]["label"] == "likely_noise"]
    if noise_candidates and args.noise_sample > 0:
        sample = random.sample(noise_candidates, min(args.noise_sample, len(noise_candidates)))
        print(f"\n--- {len(sample)} random 'likely_noise' pairs for manual check ---\n")
        for r in sample:
            print(f"repo={r['repo']}  pr=#{r['pr_number']}  func={r['function_name']}")
            print(f"similarity={r['quality']['similarity_ratio']}")
            print("--- ORIGINAL ---")
            print(r["original_code"][:250])
            print("--- MIGRATED ---")
            print(r["migrated_code"][:250])
            print("=" * 70)


if __name__ == "__main__":
    main()