from pathlib import Path
from typing import Dict

import torch
from transformers import AutoTokenizer

from .model import CodeBERTSemanticClassifier


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

MODEL_NAME = "microsoft/codebert-base"

MAX_LENGTH = 512

DEVICE = torch.device(
    "cuda"
    if torch.cuda.is_available()
    else "cpu"
)


# ============================================================
# Semantic Equivalence Predictor
# ============================================================

class SemanticEquivalencePredictor:
    """
    Production inference component for semantic equivalence.

    Input:
        Original legacy function
        Migrated modern function

    Output:
        Equivalent / Not Equivalent
        Confidence score
    """

    def __init__(
        self,
        model_dir: Path = MODEL_DIR,
    ):
        self.model_dir = Path(model_dir)

        self.device = DEVICE

        # ----------------------------------------------------
        # Load tokenizer
        # ----------------------------------------------------

        print(
            "[SemanticEquivalence] Loading tokenizer..."
        )

        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_dir
        )

        # ----------------------------------------------------
        # Load model architecture
        # ----------------------------------------------------

        print(
            "[SemanticEquivalence] Loading CodeBERT..."
        )

        self.model = CodeBERTSemanticClassifier(
            model_name=MODEL_NAME
        )

        # ----------------------------------------------------
        # Load trained weights
        # ----------------------------------------------------

        model_path = (
            self.model_dir / "model.pt"
        )

        if not model_path.exists():
            raise FileNotFoundError(
                "Semantic equivalence model not found:\n"
                f"{model_path}\n\n"
                "Train the model first using train.py."
            )

        state_dict = torch.load(
            model_path,
            map_location=self.device,
        )

        self.model.load_state_dict(
            state_dict
        )

        self.model.to(self.device)

        self.model.eval()

        print(
            "[SemanticEquivalence] Model ready."
        )

    # ========================================================
    # Predict
    # ========================================================

    def predict(
        self,
        original_code: str,
        migrated_code: str,
    ) -> Dict:

        if not original_code:
            raise ValueError(
                "original_code cannot be empty."
            )

        if not migrated_code:
            raise ValueError(
                "migrated_code cannot be empty."
            )

        # ----------------------------------------------------
        # Tokenize original + migrated code
        # ----------------------------------------------------

        encoding = self.tokenizer(
            original_code,
            migrated_code,
            padding="max_length",
            truncation=True,
            max_length=MAX_LENGTH,
            return_tensors="pt",
        )

        input_ids = encoding[
            "input_ids"
        ].to(self.device)

        attention_mask = encoding[
            "attention_mask"
        ].to(self.device)

        # ----------------------------------------------------
        # Model inference
        # ----------------------------------------------------

        with torch.no_grad():

            outputs = self.model(
                input_ids=input_ids,
                attention_mask=attention_mask,
            )

            logits = outputs["logits"]

            probabilities = torch.softmax(
                logits,
                dim=1,
            )[0]

        # ----------------------------------------------------
        # Prediction
        # ----------------------------------------------------

        predicted_class = torch.argmax(
            probabilities
        ).item()

        not_equivalent_probability = (
            probabilities[0].item()
        )

        equivalent_probability = (
            probabilities[1].item()
        )

        # ----------------------------------------------------
        # Convert class → human-readable result
        # ----------------------------------------------------

        equivalent = (
            predicted_class == 1
        )

        if equivalent:
            prediction = "equivalent"
            confidence = equivalent_probability
        else:
            prediction = "not_equivalent"
            confidence = not_equivalent_probability

        # ----------------------------------------------------
        # Return pipeline-friendly result
        # ----------------------------------------------------

        return {
            "prediction": prediction,
            "equivalent": equivalent,
            "confidence": round(
                confidence,
                4,
            ),
            "probabilities": {
                "equivalent": round(
                    equivalent_probability,
                    4,
                ),
                "not_equivalent": round(
                    not_equivalent_probability,
                    4,
                ),
            },
        }


# ============================================================
# Convenience function
# ============================================================

_predictor = None


def predict_semantic_equivalence(
    original_code: str,
    migrated_code: str,
) -> Dict:
    """
    Pipeline-facing function.

    The model is loaded once and reused for subsequent
    predictions.
    """

    global _predictor

    if _predictor is None:
        _predictor = SemanticEquivalencePredictor()

    return _predictor.predict(
        original_code=original_code,
        migrated_code=migrated_code,
    )


# ============================================================
# Standalone test
# ============================================================

if __name__ == "__main__":

    original = """
def calculate_total(a, b):
    return a + b
"""

    migrated = """
def calculate_total(a, b):
    return a + b
"""

    result = predict_semantic_equivalence(
        original_code=original,
        migrated_code=migrated,
    )

    print()
    print("=" * 60)
    print("SEMANTIC EQUIVALENCE PREDICTION")
    print("=" * 60)

    print(result)