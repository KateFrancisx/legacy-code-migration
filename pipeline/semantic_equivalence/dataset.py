from pathlib import Path

import pandas as pd
import torch
from torch.utils.data import Dataset
from transformers import AutoTokenizer


# ============================================================
# Configuration
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATASET_PATH = (
    PROJECT_ROOT
    / "verifier_dataset"
    / "output"
    / "verifier_dataset_ready.csv"
)

MODEL_NAME = "microsoft/codebert-base"

MAX_LENGTH = 512


# ============================================================
# Label mapping
# ============================================================

LABEL_MAP = {
    "not_equivalent": 0,
    "equivalent": 1,
}


# ============================================================
# CodeBERT Dataset
# ============================================================

class SemanticEquivalenceDataset(Dataset):
    """
    Dataset for CodeBERT semantic equivalence classification.

    Input:
        Original Python function
        Migrated Python function

    Output:
        CodeBERT tokenized representation
        Binary label

    Labels:
        0 -> Not Equivalent
        1 -> Equivalent
    """

    def __init__(
        self,
        split: str,
        tokenizer=None,
        max_length: int = MAX_LENGTH,
    ):
        self.split = split
        self.max_length = max_length

        # ----------------------------------------------------
        # Load dataset
        # ----------------------------------------------------

        if not DATASET_PATH.exists():
            raise FileNotFoundError(
                f"Dataset not found:\n{DATASET_PATH}"
            )

        self.data = pd.read_csv(DATASET_PATH)

        # ----------------------------------------------------
        # Validate required columns
        # ----------------------------------------------------

        required_columns = {
            "id",
            "original_code",
            "migrated_code",
            "label",
            "split",
        }

        missing_columns = required_columns - set(self.data.columns)

        if missing_columns:
            raise ValueError(
                f"Missing required columns: {sorted(missing_columns)}"
            )

        # ----------------------------------------------------
        # Select split
        # ----------------------------------------------------

        self.data = self.data[
            self.data["split"] == split
        ].reset_index(drop=True)

        if len(self.data) == 0:
            raise ValueError(
                f"No samples found for split='{split}'"
            )

        # ----------------------------------------------------
        # Tokenizer
        # ----------------------------------------------------

        if tokenizer is None:
            tokenizer = AutoTokenizer.from_pretrained(
                MODEL_NAME
            )

        self.tokenizer = tokenizer

        # ----------------------------------------------------
        # Convert labels
        # ----------------------------------------------------

        self.data["label_id"] = self.data["label"].map(
            LABEL_MAP
        )

        if self.data["label_id"].isna().any():
            invalid_labels = (
                self.data.loc[
                    self.data["label_id"].isna(),
                    "label",
                ]
                .unique()
                .tolist()
            )

            raise ValueError(
                f"Unknown labels found: {invalid_labels}"
            )

        self.data["label_id"] = (
            self.data["label_id"]
            .astype(int)
        )

        # ----------------------------------------------------
        # Basic dataset information
        # ----------------------------------------------------

        print(
            f"[Dataset] Split: {split}"
        )

        print(
            f"[Dataset] Samples: {len(self.data)}"
        )

        print(
            "[Dataset] Labels:",
            self.data["label"].value_counts().to_dict()
        )

    # ========================================================
    # Dataset length
    # ========================================================

    def __len__(self):
        return len(self.data)

    # ========================================================
    # Get one sample
    # ========================================================

    def __getitem__(self, index):

        row = self.data.iloc[index]

        original_code = str(
            row["original_code"]
        )

        migrated_code = str(
            row["migrated_code"]
        )

        # ----------------------------------------------------
        # CodeBERT sequence pair
        #
        # [CLS]
        # original code
        # [SEP]
        # migrated code
        # [SEP]
        # ----------------------------------------------------

        encoding = self.tokenizer(
            original_code,
            migrated_code,
            padding="max_length",
            truncation=True,
            max_length=self.max_length,
            return_tensors="pt",
        )

        # Remove batch dimension
        input_ids = encoding["input_ids"].squeeze(0)
        attention_mask = encoding["attention_mask"].squeeze(0)

        label = torch.tensor(
            row["label_id"],
            dtype=torch.long,
        )

        return {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "labels": label,
        }


# ============================================================
# Utility function
# ============================================================

def load_datasets():
    """
    Load train, validation and test datasets.
    """

    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_NAME
    )

    train_dataset = SemanticEquivalenceDataset(
        split="train",
        tokenizer=tokenizer,
    )

    val_dataset = SemanticEquivalenceDataset(
        split="val",
        tokenizer=tokenizer,
    )

    test_dataset = SemanticEquivalenceDataset(
        split="test",
        tokenizer=tokenizer,
    )

    return (
        train_dataset,
        val_dataset,
        test_dataset,
        tokenizer,
    )


# ============================================================
# Quick test
# ============================================================

if __name__ == "__main__":

    train_dataset, val_dataset, test_dataset, tokenizer = (
        load_datasets()
    )

    print()
    print("=" * 60)
    print("SEMANTIC EQUIVALENCE DATASET TEST")
    print("=" * 60)

    print(f"Train samples : {len(train_dataset)}")
    print(f"Val samples   : {len(val_dataset)}")
    print(f"Test samples  : {len(test_dataset)}")

    sample = train_dataset[0]

    print()
    print("Sample output:")
    print("input_ids shape     :", sample["input_ids"].shape)
    print("attention_mask shape:", sample["attention_mask"].shape)
    print("label               :", sample["labels"].item())

    print()
    print("Decoded sample:")
    print(
        tokenizer.decode(
            sample["input_ids"],
            skip_special_tokens=False,
        )
    )