from pathlib import Path

import json
import torch
from torch.utils.data import DataLoader

from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    confusion_matrix,
    classification_report,
)

from dataset import SemanticEquivalenceDataset
from model import CodeBERTSemanticClassifier
from transformers import AutoTokenizer


# ============================================================
# Configuration
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

MODEL_DIR = (
    PROJECT_ROOT
    / "outputs"
    / "semantic_equivalence"
    / "best_model"
)

RESULTS_DIR = (
    PROJECT_ROOT
    / "outputs"
    / "semantic_equivalence"
)

RESULTS_FILE = (
    RESULTS_DIR
    / "evaluation_results.json"
)

MODEL_NAME = "microsoft/codebert-base"

BATCH_SIZE = 4

DEVICE = torch.device(
    "cuda"
    if torch.cuda.is_available()
    else "cpu"
)


# ============================================================
# Load model
# ============================================================

def load_trained_model():

    print("Loading tokenizer...")

    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_DIR
    )

    print("Loading trained CodeBERT model...")

    model = CodeBERTSemanticClassifier(
        model_name=MODEL_NAME
    )

    model_path = MODEL_DIR / "model.pt"

    if not model_path.exists():
        raise FileNotFoundError(
            f"Model weights not found:\n{model_path}"
        )

    state_dict = torch.load(
        model_path,
        map_location=DEVICE,
    )

    model.load_state_dict(state_dict)

    model.to(DEVICE)

    model.eval()

    return model, tokenizer


# ============================================================
# Evaluate
# ============================================================

def evaluate():

    print("=" * 70)
    print("CODEBERT SEMANTIC EQUIVALENCE EVALUATION")
    print("=" * 70)

    print()
    print("Device:", DEVICE)

    # --------------------------------------------------------
    # Load model
    # --------------------------------------------------------

    model, tokenizer = load_trained_model()

    # --------------------------------------------------------
    # Load TEST dataset only
    # --------------------------------------------------------

    print()
    print("Loading test dataset...")

    test_dataset = SemanticEquivalenceDataset(
        split="test",
        tokenizer=tokenizer,
    )

    test_loader = DataLoader(
        test_dataset,
        batch_size=BATCH_SIZE,
        shuffle=False,
    )

    # --------------------------------------------------------
    # Prediction
    # --------------------------------------------------------

    all_labels = []
    all_predictions = []
    all_probabilities = []

    print()
    print("Running inference...")

    with torch.no_grad():

        for batch in test_loader:

            input_ids = batch["input_ids"].to(
                DEVICE
            )

            attention_mask = batch["attention_mask"].to(
                DEVICE
            )

            labels = batch["labels"].to(
                DEVICE
            )

            outputs = model(
                input_ids=input_ids,
                attention_mask=attention_mask,
            )

            logits = outputs["logits"]

            # ------------------------------------------------
            # Convert logits → probabilities
            # ------------------------------------------------

            probabilities = torch.softmax(
                logits,
                dim=1,
            )

            # Probability of Equivalent class
            equivalent_probability = (
                probabilities[:, 1]
            )

            predictions = torch.argmax(
                probabilities,
                dim=1,
            )

            all_labels.extend(
                labels.cpu().numpy().tolist()
            )

            all_predictions.extend(
                predictions.cpu().numpy().tolist()
            )

            all_probabilities.extend(
                equivalent_probability
                .cpu()
                .numpy()
                .tolist()
            )

    # ========================================================
    # Metrics
    # ========================================================

    accuracy = accuracy_score(
        all_labels,
        all_predictions,
    )

    precision = precision_score(
        all_labels,
        all_predictions,
        zero_division=0,
    )

    recall = recall_score(
        all_labels,
        all_predictions,
        zero_division=0,
    )

    f1 = f1_score(
        all_labels,
        all_predictions,
        zero_division=0,
    )

    roc_auc = roc_auc_score(
        all_labels,
        all_probabilities,
    )

    # --------------------------------------------------------
    # Confusion matrix
    # --------------------------------------------------------

    cm = confusion_matrix(
        all_labels,
        all_predictions,
    )

    # --------------------------------------------------------
    # Classification report
    # --------------------------------------------------------

    report = classification_report(
        all_labels,
        all_predictions,
        target_names=[
            "Not Equivalent",
            "Equivalent",
        ],
        zero_division=0,
    )

    # ========================================================
    # Print results
    # ========================================================

    print()
    print("=" * 70)
    print("TEST RESULTS")
    print("=" * 70)

    print()
    print(
        f"Test samples : {len(all_labels)}"
    )

    print(
        f"Accuracy     : {accuracy:.4f}"
    )

    print(
        f"Precision    : {precision:.4f}"
    )

    print(
        f"Recall       : {recall:.4f}"
    )

    print(
        f"F1 Score     : {f1:.4f}"
    )

    print(
        f"ROC-AUC      : {roc_auc:.4f}"
    )

    print()
    print("Confusion Matrix:")
    print(
        "                  Predicted"
    )
    print(
        "                Not Eq    Eq"
    )
    print(
        f"Actual Not Eq   {cm[0][0]:6d}  {cm[0][1]:6d}"
    )
    print(
        f"Actual Eq       {cm[1][0]:6d}  {cm[1][1]:6d}"
    )

    print()
    print("Classification Report:")
    print(report)

    # ========================================================
    # Save results
    # ========================================================

    results = {
        "model": MODEL_NAME,
        "checkpoint": str(MODEL_DIR),
        "test_samples": len(all_labels),
        "metrics": {
            "accuracy": float(accuracy),
            "precision": float(precision),
            "recall": float(recall),
            "f1": float(f1),
            "roc_auc": float(roc_auc),
        },
        "confusion_matrix": cm.tolist(),
        "classification_report": report,
    }

    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        RESULTS_FILE,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            results,
            f,
            indent=4,
        )

    print()
    print(
        f"Results saved to:\n{RESULTS_FILE}"
    )

    print()
    print("=" * 70)
    print("EVALUATION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    evaluate()