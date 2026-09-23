import csv
import json
import hashlib
from pathlib import Path
from collections import Counter, defaultdict

# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
INPUT_FILE = BASE_DIR / "output" / "verifier_dataset.csv"
REPORT_FILE = BASE_DIR / "output" / "dataset_audit_report.json"


# ============================================================
# HELPERS
# ============================================================

def normalize_code(code):
    """Normalize whitespace for duplicate-code checks."""
    if code is None:
        return ""
    return "\n".join(
        line.strip()
        for line in str(code).strip().splitlines()
        if line.strip()
    )


def code_hash(code):
    normalized = normalize_code(code)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def print_counter(title, counter):
    print(f"\n{title}")
    print("-" * len(title))

    for key, value in counter.most_common():
        print(f"{str(key):35} {value}")


# ============================================================
# LOAD DATA
# ============================================================

if not INPUT_FILE.exists():
    print(f"ERROR: Dataset not found:")
    print(INPUT_FILE)
    raise SystemExit(1)

print("=" * 70)
print("CODEMIGRATE - SEMANTIC EQUIVALENCE DATASET AUDIT")
print("=" * 70)

print(f"\nInput:")
print(INPUT_FILE)

with open(INPUT_FILE, "r", encoding="utf-8-sig", newline="") as f:
    reader = csv.DictReader(f)
    rows = list(reader)

print(f"\nTotal rows: {len(rows)}")


# ============================================================
# REQUIRED COLUMNS
# ============================================================

required_columns = {
    "id",
    "family_id",
    "original_code",
    "migrated_code",
    "label",
    "source",
    "mutation_type",
    "pattern",
    "difficulty",
    "verification_status",
    "split",
}

actual_columns = set(rows[0].keys()) if rows else set()

missing_columns = required_columns - actual_columns
extra_columns = actual_columns - required_columns

print("\nCOLUMN CHECK")
print("-" * 40)

if missing_columns:
    print("Missing columns:")
    for col in sorted(missing_columns):
        print(f"  - {col}")
else:
    print("All required columns present.")

if extra_columns:
    print("\nAdditional columns:")
    for col in sorted(extra_columns):
        print(f"  - {col}")


# ============================================================
# BASIC DISTRIBUTIONS
# ============================================================

label_counts = Counter(row["label"] for row in rows)
source_counts = Counter(row["source"] for row in rows)
split_counts = Counter(row["split"] for row in rows)
difficulty_counts = Counter(row["difficulty"] for row in rows)
verification_counts = Counter(row["verification_status"] for row in rows)
pattern_counts = Counter(row["pattern"] for row in rows)
mutation_counts = Counter(row["mutation_type"] for row in rows)

print_counter("LABEL DISTRIBUTION", label_counts)
print_counter("SOURCE DISTRIBUTION", source_counts)
print_counter("SPLIT DISTRIBUTION", split_counts)
print_counter("DIFFICULTY DISTRIBUTION", difficulty_counts)
print_counter("VERIFICATION STATUS", verification_counts)

print_counter("PATTERN DISTRIBUTION", pattern_counts)
print_counter("MUTATION TYPE DISTRIBUTION", mutation_counts)


# ============================================================
# MISSING VALUES
# ============================================================

missing_values = defaultdict(list)

for i, row in enumerate(rows):
    for column in required_columns:
        value = row.get(column)

        if value is None or str(value).strip() == "":
            missing_values[column].append(i)


print("\nMISSING VALUE CHECK")
print("-" * 40)

if missing_values:
    for column, indices in missing_values.items():
        print(f"{column}: {len(indices)} missing")
else:
    print("No missing required values.")


# ============================================================
# DUPLICATE IDS
# ============================================================

id_map = defaultdict(list)

for i, row in enumerate(rows):
    id_map[row["id"]].append(i)

duplicate_ids = {
    key: value
    for key, value in id_map.items()
    if len(value) > 1
}

print("\nDUPLICATE ID CHECK")
print("-" * 40)
print(f"Duplicate IDs: {len(duplicate_ids)}")


# ============================================================
# DUPLICATE CODE PAIRS
# ============================================================

pair_map = defaultdict(list)

for i, row in enumerate(rows):

    original_hash = code_hash(row["original_code"])
    migrated_hash = code_hash(row["migrated_code"])

    pair_key = (original_hash, migrated_hash)

    pair_map[pair_key].append(i)

duplicate_pairs = {
    key: value
    for key, value in pair_map.items()
    if len(value) > 1
}

print("\nDUPLICATE CODE-PAIR CHECK")
print("-" * 40)
print(f"Duplicate code-pair groups: {len(duplicate_pairs)}")


# ============================================================
# SAME ORIGINAL CODE ACROSS SPLITS
# ============================================================

original_map = defaultdict(list)

for i, row in enumerate(rows):

    original_hash = code_hash(row["original_code"])

    original_map[original_hash].append({
        "row_index": i,
        "id": row["id"],
        "family_id": row["family_id"],
        "split": row["split"],
        "label": row["label"],
        "source": row["source"],
    })


cross_split_originals = {}

for original_hash, items in original_map.items():

    splits = set(item["split"] for item in items)

    if len(splits) > 1:
        cross_split_originals[original_hash] = items


print("\nORIGINAL-CODE CROSS-SPLIT CHECK")
print("-" * 40)
print(f"Unique original functions: {len(original_map)}")
print(f"Cross-split original functions: {len(cross_split_originals)}")

if cross_split_originals:

    print("\nExamples:")

    for n, (original_hash, items) in enumerate(
        cross_split_originals.items()
    ):

        if n >= 10:
            break

        print(f"\nExample {n + 1}")

        for item in items:
            print(
                f"  row={item['row_index']} "
                f"id={item['id']} "
                f"family={item['family_id']} "
                f"split={item['split']} "
                f"label={item['label']} "
                f"source={item['source']}"
            )


# ============================================================
# FAMILY SPLIT CHECK
# ============================================================

family_map = defaultdict(list)

for i, row in enumerate(rows):

    family_map[row["family_id"]].append({
        "row_index": i,
        "id": row["id"],
        "split": row["split"],
        "label": row["label"],
    })


family_leakage = {}

for family_id, items in family_map.items():

    splits = set(item["split"] for item in items)

    if len(splits) > 1:
        family_leakage[family_id] = items


print("\nFAMILY LEAKAGE CHECK")
print("-" * 40)
print(f"Unique families: {len(family_map)}")
print(f"Families crossing splits: {len(family_leakage)}")

if family_leakage:
    print("\nWARNING: Some family_ids occur in multiple splits.")

    for n, (family_id, items) in enumerate(family_leakage.items()):

        if n >= 10:
            break

        print(f"\nFamily: {family_id}")

        for item in items:
            print(
                f"  row={item['row_index']} "
                f"split={item['split']} "
                f"label={item['label']}"
            )


# ============================================================
# LABEL/SOURCE COMBINATION
# ============================================================

label_source = Counter(
    (row["label"], row["source"])
    for row in rows
)

print("\nLABEL × SOURCE")
print("-" * 40)

for (label, source), count in label_source.most_common():
    print(f"{label:20} {source:20} {count}")


# ============================================================
# LABEL/VERIFICATION COMBINATION
# ============================================================

label_verification = Counter(
    (row["label"], row["verification_status"])
    for row in rows
)

print("\nLABEL × VERIFICATION STATUS")
print("-" * 40)

for (label, status), count in label_verification.most_common():
    print(f"{label:20} {status:20} {count}")


# ============================================================
# SUSPICIOUS NEGATIVES
# ============================================================

pending_negatives = []

for i, row in enumerate(rows):

    if (
        row["label"] == "not_equivalent"
        and row["verification_status"] == "pending"
    ):
        pending_negatives.append({
            "row_index": i,
            "id": row["id"],
            "family_id": row["family_id"],
            "source": row["source"],
            "mutation_type": row["mutation_type"],
            "pattern": row["pattern"],
            "difficulty": row["difficulty"],
            "split": row["split"],
        })


print("\nPENDING NEGATIVE CHECK")
print("-" * 40)
print(f"Pending negative rows: {len(pending_negatives)}")


# ============================================================
# CODE LENGTH
# ============================================================

original_lengths = []
migrated_lengths = []

for row in rows:

    original_lengths.append(
        len(row["original_code"])
    )

    migrated_lengths.append(
        len(row["migrated_code"])
    )


def summarize_lengths(values):

    values = sorted(values)

    if not values:
        return {}

    n = len(values)

    return {
        "min": values[0],
        "max": values[-1],
        "mean": round(sum(values) / n, 2),
        "median": values[n // 2],
        "p90": values[min(int(n * 0.90), n - 1)],
        "p95": values[min(int(n * 0.95), n - 1)],
        "p99": values[min(int(n * 0.99), n - 1)],
    }


original_length_stats = summarize_lengths(original_lengths)
migrated_length_stats = summarize_lengths(migrated_lengths)

print("\nCODE LENGTH")
print("-" * 40)

print("Original:")
print(original_length_stats)

print("\nMigrated:")
print(migrated_length_stats)


# ============================================================
# VERY LONG FUNCTIONS
# ============================================================

long_code_rows = []

for i, row in enumerate(rows):

    original_len = len(row["original_code"])
    migrated_len = len(row["migrated_code"])

    if original_len > 6000 or migrated_len > 6000:

        long_code_rows.append({
            "row_index": i,
            "id": row["id"],
            "original_chars": original_len,
            "migrated_chars": migrated_len,
            "split": row["split"],
            "label": row["label"],
        })


print("\nLONG CODE CHECK")
print("-" * 40)
print(
    f"Rows with original or migrated code > 6000 chars: "
    f"{len(long_code_rows)}"
)


# ============================================================
# CLASS BALANCE BY SPLIT
# ============================================================

print("\nCLASS BALANCE BY SPLIT")
print("-" * 40)

split_label_counts = defaultdict(Counter)

for row in rows:
    split_label_counts[row["split"]][row["label"]] += 1

for split in ["train", "val", "test"]:

    counts = split_label_counts[split]

    total = sum(counts.values())

    if total == 0:
        continue

    equivalent = counts["equivalent"]
    not_equivalent = counts["not_equivalent"]

    print(
        f"{split:6} "
        f"total={total:4} "
        f"equivalent={equivalent:4} "
        f"not_equivalent={not_equivalent:4}"
    )


# ============================================================
# BUILD REPORT
# ============================================================

report = {
    "input_file": str(INPUT_FILE),
    "total_rows": len(rows),

    "columns": {
        "missing": sorted(missing_columns),
        "extra": sorted(extra_columns),
    },

    "distributions": {
        "label": dict(label_counts),
        "source": dict(source_counts),
        "split": dict(split_counts),
        "difficulty": dict(difficulty_counts),
        "verification_status": dict(verification_counts),
        "pattern": dict(pattern_counts),
        "mutation_type": dict(mutation_counts),
    },

    "quality_checks": {
        "duplicate_ids": len(duplicate_ids),
        "duplicate_code_pairs": len(duplicate_pairs),
        "cross_split_original_functions": len(
            cross_split_originals
        ),
        "family_leakage": len(family_leakage),
        "pending_negatives": len(pending_negatives),
        "long_code_rows": len(long_code_rows),
    },

    "code_length": {
        "original": original_length_stats,
        "migrated": migrated_length_stats,
    },

    "cross_split_original_examples": list(
        cross_split_originals.values()
    )[:20],

    "family_leakage_examples": list(
        family_leakage.items()
    )[:20],

    "pending_negative_examples": pending_negatives[:50],

    "long_code_examples": long_code_rows[:50],
}


with open(REPORT_FILE, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2)


# ============================================================
# FINAL SUMMARY
# ============================================================

print("\n" + "=" * 70)
print("AUDIT COMPLETE")
print("=" * 70)

print(f"""
Dataset:
    {len(rows)} rows

Duplicates:
    Duplicate IDs             : {len(duplicate_ids)}
    Duplicate code pairs      : {len(duplicate_pairs)}

Leakage:
    Cross-split originals     : {len(cross_split_originals)}
    Family leakage            : {len(family_leakage)}

Verification:
    Pending negatives         : {len(pending_negatives)}

Long code:
    >6000 characters         : {len(long_code_rows)}

Report:
    {REPORT_FILE}
""")

print("=" * 70)
print("IMPORTANT: Original dataset was NOT modified.")
print("=" * 70)