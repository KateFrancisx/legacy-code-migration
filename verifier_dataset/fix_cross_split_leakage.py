from pathlib import Path
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]

INPUT_PATH = (
    PROJECT_ROOT
    / "verifier_dataset"
    / "output"
    / "verifier_dataset_final.csv"
)

OUTPUT_PATH = (
    PROJECT_ROOT
    / "verifier_dataset"
    / "output"
    / "verifier_dataset_ready.csv"
)


# The six original functions that appeared across multiple splits.
# Keep all examples belonging to the same original function
# in one split.

MOVES = {
    "27e4f": "train",
    "abc885": "val",
    "3d228": "train",
    "d16e69": "train",
    "a84e39": "val",
    "626ca": "val",
}


def main():

    df = pd.read_csv(INPUT_PATH)

    print("=" * 60)
    print("FIXING CROSS-SPLIT LEAKAGE")
    print("=" * 60)

    print(f"Input rows: {len(df)}")

    # --------------------------------------------------------
    # Locate the six affected rows using their ID prefixes.
    # --------------------------------------------------------

    for prefix, new_split in MOVES.items():

        matches = df[df["id"].astype(str).str.startswith(prefix)]

        if len(matches) == 0:
            print(f"[WARNING] Could not find ID: {prefix}")
            continue

        for idx in matches.index:

            old_split = df.loc[idx, "split"]

            df.loc[idx, "split"] = new_split

            print(
                f"{df.loc[idx, 'id']}: "
                f"{old_split} -> {new_split}"
            )

    # --------------------------------------------------------
    # Verify split counts
    # --------------------------------------------------------

    print()
    print("Final split counts:")
    print(df["split"].value_counts())

    # --------------------------------------------------------
    # Verify no original function crosses splits
    # --------------------------------------------------------

    cross_split = (
        df.groupby("original_code")["split"]
        .nunique()
    )

    leakage_count = int((cross_split > 1).sum())

    print()
    print(
        "Cross-split original functions:",
        leakage_count
    )

    if leakage_count != 0:
        raise RuntimeError(
            "Cross-split leakage still exists!"
        )

    # --------------------------------------------------------
    # Save corrected dataset
    # --------------------------------------------------------

    df.to_csv(
        OUTPUT_PATH,
        index=False
    )

    print()
    print(f"Saved: {OUTPUT_PATH}")

    print()
    print("=" * 60)
    print("FINAL DATASET")
    print("=" * 60)

    print(f"Rows: {len(df)}")

    print("\nSplits:")
    print(df["split"].value_counts())

    print("\nLabels:")
    print(df["label"].value_counts())


if __name__ == "__main__":
    main()