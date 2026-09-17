from __future__ import annotations

from typing import List

import torch
import torch.nn.functional as F
from transformers import AutoModel, AutoTokenizer


MODEL_NAME = "microsoft/codebert-base"
EMBEDDING_DIMENSION = 768
MAX_LENGTH = 512


class CodeBERTEmbedder:
    """
    Generates semantic embeddings for source-code functions
    using Microsoft's CodeBERT base model.

    Model:
        microsoft/codebert-base

    Output:
        768-dimensional normalized vector
    """

    def __init__(
        self,
        model_name: str = MODEL_NAME,
        max_length: int = MAX_LENGTH,
    ):
        self.model_name = model_name
        self.max_length = max_length

        # Select GPU if available, otherwise CPU
        self.device = torch.device(
            "cuda" if torch.cuda.is_available() else "cpu"
        )

        print(f"Loading CodeBERT: {self.model_name}")
        print(f"Device: {self.device}")

        # Load tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_name
        )

        # Load pretrained CodeBERT
        self.model = AutoModel.from_pretrained(
            self.model_name
        )

        # Move model to GPU/CPU
        self.model.to(self.device)

        # We are generating embeddings, not training
        self.model.eval()

        print("CodeBERT loaded successfully.")
        print(f"Expected embedding dimension: {EMBEDDING_DIMENSION}")

    def _mean_pooling(
        self,
        model_output,
        attention_mask: torch.Tensor,
    ) -> torch.Tensor:
        """
        Mean-pool token embeddings while ignoring padding tokens.

        Input:
            model_output.last_hidden_state
                shape = [batch_size, sequence_length, hidden_size]

            attention_mask
                shape = [batch_size, sequence_length]

        Output:
            shape = [batch_size, hidden_size]
        """

        token_embeddings = model_output.last_hidden_state

        # Expand attention mask from:
        # [batch_size, sequence_length]
        #
        # to:
        # [batch_size, sequence_length, hidden_size]
        input_mask_expanded = (
            attention_mask
            .unsqueeze(-1)
            .expand(token_embeddings.size())
            .float()
        )

        # Sum token embeddings
        sum_embeddings = torch.sum(
            token_embeddings * input_mask_expanded,
            dim=1,
        )

        # Count valid tokens
        sum_mask = torch.clamp(
            input_mask_expanded.sum(dim=1),
            min=1e-9,
        )

        # Mean pooling
        return sum_embeddings / sum_mask

    def embed_batch(
        self,
        code_list: List[str],
    ) -> List[List[float]]:
        """
        Generate embeddings for a batch of source-code functions.

        Args:
            code_list:
                List of source-code strings.

        Returns:
            List of 768-dimensional normalized vectors.
        """

        if not code_list:
            return []

        # Make sure every item is a string
        code_list = [
            code if isinstance(code, str) else str(code)
            for code in code_list
        ]

        # Tokenize all functions in the batch
        inputs = self.tokenizer(
            code_list,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=self.max_length,
        )

        # Move tensors to GPU/CPU
        inputs = {
            key: value.to(self.device)
            for key, value in inputs.items()
        }

        # Disable gradient calculation
        with torch.no_grad():
            outputs = self.model(**inputs)

        # Mean pooling
        embeddings = self._mean_pooling(
            outputs,
            inputs["attention_mask"],
        )

        # L2 normalization
        #
        # This is useful for cosine similarity / FAISS
        embeddings = F.normalize(
            embeddings,
            p=2,
            dim=1,
        )

        # GPU tensor -> CPU -> Python list
        embeddings = embeddings.cpu().tolist()

        return embeddings

    def embed(
        self,
        code: str,
    ) -> List[float]:
        """
        Generate an embedding for one function.
        """

        result = self.embed_batch([code])

        return result[0]