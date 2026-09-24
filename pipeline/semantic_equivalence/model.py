import torch
import torch.nn as nn

from transformers import AutoModel


# ============================================================
# Configuration
# ============================================================

MODEL_NAME = "microsoft/codebert-base"

NUM_LABELS = 2


# ============================================================
# CodeBERT Semantic Equivalence Classifier
# ============================================================

class CodeBERTSemanticClassifier(nn.Module):
    """
    CodeBERT-based binary classifier for semantic equivalence.

    Input:
        Original Python function
        +
        Migrated Python function

    Output:
        Logits for two classes:

        0 -> Not Equivalent
        1 -> Equivalent
    """

    def __init__(
        self,
        model_name: str = MODEL_NAME,
        num_labels: int = NUM_LABELS,
        dropout: float = 0.1,
    ):
        super().__init__()

        self.num_labels = num_labels

        # ----------------------------------------------------
        # Load pretrained CodeBERT
        # ----------------------------------------------------

        self.codebert = AutoModel.from_pretrained(
            model_name
        )

        # CodeBERT hidden representation size
        hidden_size = self.codebert.config.hidden_size

        # ----------------------------------------------------
        # Classification head
        # ----------------------------------------------------

        self.dropout = nn.Dropout(dropout)

        self.classifier = nn.Linear(
            hidden_size,
            num_labels,
        )

    # ========================================================
    # Forward pass
    # ========================================================

    def forward(
        self,
        input_ids,
        attention_mask,
        labels=None,
    ):
        """
        Forward pass through CodeBERT.

        Parameters
        ----------
        input_ids:
            Token IDs produced by CodeBERT tokenizer.

        attention_mask:
            Indicates real tokens vs padding.

        labels:
            Optional ground-truth labels.

        Returns
        -------
        dict containing:
            logits
            loss (if labels provided)
        """

        # ----------------------------------------------------
        # CodeBERT
        # ----------------------------------------------------

        outputs = self.codebert(
            input_ids=input_ids,
            attention_mask=attention_mask,
        )

        # ----------------------------------------------------
        # Take [CLS] representation
        # ----------------------------------------------------
        #
        # For sequence classification, the first token
        # representation is used as the representation of
        # the complete input sequence.
        # ----------------------------------------------------

        pooled_output = outputs.last_hidden_state[:, 0, :]

        # ----------------------------------------------------
        # Dropout
        # ----------------------------------------------------

        pooled_output = self.dropout(
            pooled_output
        )

        # ----------------------------------------------------
        # Classification
        # ----------------------------------------------------

        logits = self.classifier(
            pooled_output
        )

        # ----------------------------------------------------
        # Loss
        # ----------------------------------------------------

        loss = None

        if labels is not None:

            loss_function = nn.CrossEntropyLoss()

            loss = loss_function(
                logits,
                labels,
            )

        return {
            "loss": loss,
            "logits": logits,
        }


# ============================================================
# Utility
# ============================================================

def load_model(
    model_name: str = MODEL_NAME,
):
    """
    Load a fresh CodeBERT semantic classifier.
    """

    model = CodeBERTSemanticClassifier(
        model_name=model_name
    )

    return model


# ============================================================
# Quick model test
# ============================================================

if __name__ == "__main__":

    print("=" * 60)
    print("CODEBERT SEMANTIC EQUIVALENCE MODEL TEST")
    print("=" * 60)

    print()
    print(f"Model: {MODEL_NAME}")

    # --------------------------------------------------------
    # Load model
    # --------------------------------------------------------

    model = load_model()

    # --------------------------------------------------------
    # Parameter information
    # --------------------------------------------------------

    total_parameters = sum(
        p.numel()
        for p in model.parameters()
    )

    trainable_parameters = sum(
        p.numel()
        for p in model.parameters()
        if p.requires_grad
    )

    print()
    print(
        f"Total parameters: "
        f"{total_parameters:,}"
    )

    print(
        f"Trainable parameters: "
        f"{trainable_parameters:,}"
    )

    # --------------------------------------------------------
    # Dummy input
    # --------------------------------------------------------
    #
    # We are only checking that the forward pass works.
    # Actual dataset samples will be used during training.
    # --------------------------------------------------------

    batch_size = 2
    sequence_length = 512

    input_ids = torch.randint(
        low=0,
        high=1000,
        size=(
            batch_size,
            sequence_length,
        ),
    )

    attention_mask = torch.ones(
        (
            batch_size,
            sequence_length,
        ),
        dtype=torch.long,
    )

    labels = torch.tensor(
        [1, 0],
        dtype=torch.long,
    )

    # --------------------------------------------------------
    # Forward pass
    # --------------------------------------------------------

    model.eval()

    with torch.no_grad():

        outputs = model(
            input_ids=input_ids,
            attention_mask=attention_mask,
            labels=labels,
        )

    print()
    print(
        "Input shape:",
        input_ids.shape,
    )

    print(
        "Logits shape:",
        outputs["logits"].shape,
    )

    print(
        "Loss:",
        outputs["loss"].item(),
    )

    print()
    print("Logits:")
    print(outputs["logits"])

    # --------------------------------------------------------
    # Prediction
    # --------------------------------------------------------

    predictions = torch.argmax(
        outputs["logits"],
        dim=1,
    )

    print()
    print("Predictions:")
    print(predictions.tolist())

    print()
    print("=" * 60)
    print("MODEL TEST COMPLETE")
    print("=" * 60)