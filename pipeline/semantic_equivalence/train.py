from pathlib import Path

import torch
from torch.utils.data import DataLoader
from torch.optim import AdamW

from transformers import get_linear_schedule_with_warmup

from dataset import load_datasets
from model import CodeBERTSemanticClassifier


# ============================================================
# Configuration
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

MODEL_NAME = "microsoft/codebert-base"

OUTPUT_DIR = (
    PROJECT_ROOT
    / "outputs"
    / "semantic_equivalence"
)

BATCH_SIZE = 4
EPOCHS = 3

LEARNING_RATE = 2e-5

WEIGHT_DECAY = 0.01

WARMUP_RATIO = 0.1

MAX_GRAD_NORM = 1.0


# ============================================================
# Device
# ============================================================

DEVICE = torch.device(
    "cuda"
    if torch.cuda.is_available()
    else "cpu"
)


# ============================================================
# Training
# ============================================================

def train_one_epoch(
    model,
    dataloader,
    optimizer,
    scheduler,
):

    model.train()

    total_loss = 0.0

    for step, batch in enumerate(dataloader):

        input_ids = batch["input_ids"].to(
            DEVICE
        )

        attention_mask = batch["attention_mask"].to(
            DEVICE
        )

        labels = batch["labels"].to(
            DEVICE
        )

        # ----------------------------------------------------
        # Clear previous gradients
        # ----------------------------------------------------

        optimizer.zero_grad()

        # ----------------------------------------------------
        # Forward pass
        # ----------------------------------------------------

        outputs = model(
            input_ids=input_ids,
            attention_mask=attention_mask,
            labels=labels,
        )

        loss = outputs["loss"]

        # ----------------------------------------------------
        # Backpropagation
        # ----------------------------------------------------

        loss.backward()

        # ----------------------------------------------------
        # Gradient clipping
        # ----------------------------------------------------

        torch.nn.utils.clip_grad_norm_(
            model.parameters(),
            MAX_GRAD_NORM,
        )

        # ----------------------------------------------------
        # Update model
        # ----------------------------------------------------

        optimizer.step()

        scheduler.step()

        total_loss += loss.item()

        # ----------------------------------------------------
        # Progress
        # ----------------------------------------------------

        if (step + 1) % 25 == 0:

            print(
                f"  Step {step + 1}/{len(dataloader)} "
                f"| Loss: {loss.item():.4f}"
            )

    return total_loss / len(dataloader)


# ============================================================
# Validation
# ============================================================

def evaluate_loss(
    model,
    dataloader,
):

    model.eval()

    total_loss = 0.0

    with torch.no_grad():

        for batch in dataloader:

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
                labels=labels,
            )

            total_loss += outputs["loss"].item()

    return total_loss / len(dataloader)


# ============================================================
# Main
# ============================================================

def main():

    print("=" * 70)
    print("CODEBERT SEMANTIC EQUIVALENCE TRAINING")
    print("=" * 70)

    print()
    print("Device:", DEVICE)

    # --------------------------------------------------------
    # Output directory
    # --------------------------------------------------------

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # --------------------------------------------------------
    # Load datasets
    # --------------------------------------------------------

    print()
    print("Loading datasets...")

    (
        train_dataset,
        val_dataset,
        test_dataset,
        tokenizer,
    ) = load_datasets()

    # --------------------------------------------------------
    # DataLoaders
    # --------------------------------------------------------

    train_loader = DataLoader(
        train_dataset,
        batch_size=BATCH_SIZE,
        shuffle=True,
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=BATCH_SIZE,
        shuffle=False,
    )

    # --------------------------------------------------------
    # Load model
    # --------------------------------------------------------

    print()
    print("Loading CodeBERT model...")

    model = CodeBERTSemanticClassifier(
        model_name=MODEL_NAME
    )

    model.to(DEVICE)

    # --------------------------------------------------------
    # Optimizer
    # --------------------------------------------------------

    optimizer = AdamW(
        model.parameters(),
        lr=LEARNING_RATE,
        weight_decay=WEIGHT_DECAY,
    )

    # --------------------------------------------------------
    # Scheduler
    # --------------------------------------------------------

    total_training_steps = (
        len(train_loader) * EPOCHS
    )

    warmup_steps = int(
        total_training_steps * WARMUP_RATIO
    )

    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=warmup_steps,
        num_training_steps=total_training_steps,
    )

    # --------------------------------------------------------
    # Training information
    # --------------------------------------------------------

    print()
    print("Training configuration:")
    print(
        f"  Training samples : {len(train_dataset)}"
    )
    print(
        f"  Validation samples : {len(val_dataset)}"
    )
    print(
        f"  Batch size : {BATCH_SIZE}"
    )
    print(
        f"  Epochs : {EPOCHS}"
    )
    print(
        f"  Learning rate : {LEARNING_RATE}"
    )
    print(
        f"  Total steps : {total_training_steps}"
    )
    print(
        f"  Warmup steps : {warmup_steps}"
    )

    # --------------------------------------------------------
    # Training loop
    # --------------------------------------------------------

    best_val_loss = float("inf")

    print()
    print("=" * 70)
    print("STARTING TRAINING")
    print("=" * 70)

    for epoch in range(EPOCHS):

        print()
        print(
            f"Epoch {epoch + 1}/{EPOCHS}"
        )

        print("-" * 50)

        train_loss = train_one_epoch(
            model,
            train_loader,
            optimizer,
            scheduler,
        )

        val_loss = evaluate_loss(
            model,
            val_loader,
        )

        print()
        print(
            f"Train Loss: {train_loss:.4f}"
        )

        print(
            f"Val Loss:   {val_loss:.4f}"
        )

        # ----------------------------------------------------
        # Save best model
        # ----------------------------------------------------

        if val_loss < best_val_loss:

            best_val_loss = val_loss

            best_model_dir = (
                OUTPUT_DIR / "best_model"
            )

            best_model_dir.mkdir(
                parents=True,
                exist_ok=True,
            )

            torch.save(
                model.state_dict(),
                best_model_dir / "model.pt",
            )

            tokenizer.save_pretrained(
                best_model_dir
            )

            print()
            print(
                "Saved new best model."
            )

    # --------------------------------------------------------
    # Save final model
    # --------------------------------------------------------

    final_model_dir = (
        OUTPUT_DIR / "final_model"
    )

    final_model_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    torch.save(
        model.state_dict(),
        final_model_dir / "model.pt",
    )

    tokenizer.save_pretrained(
        final_model_dir
    )

    print()
    print("=" * 70)
    print("TRAINING COMPLETE")
    print("=" * 70)

    print()
    print(
        f"Best validation loss: "
        f"{best_val_loss:.4f}"
    )

    print()
    print(
        f"Best model saved to:"
    )

    print(
        best_model_dir
    )

    print()
    print(
        f"Final model saved to:"
    )

    print(
        final_model_dir
    )


if __name__ == "__main__":
    main()