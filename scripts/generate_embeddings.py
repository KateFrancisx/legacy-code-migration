from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

# ---------------------------------------------------------
# Make project root importable when running:
#
# python scripts\generate_embeddings.py
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from pipeline.embeddings.codebert_embedder import (
    CodeBERTEmbedder,
    EMBEDDING_DIMENSION,
    MODEL_NAME,
)


def load_json(path: Path) -> Any:
    """
    Load a JSON file.
    """

    print(f"Reading: {path}")

    with path.open(
        "r",
        encoding="utf-8",
    ) as f:
        return json.load(f)


def save_json(path: Path, data: Any) -> None:
    """
    Save JSON with readable formatting.
    """

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            data,
            f,
            indent=2,
            ensure_ascii=False,
        )


def find_function_records(data: Any) -> List[Dict[str, Any]]:
    """
    Locate function records inside the extracted JSON.

    Supported formats:

    1. Direct list:

        [
            {
                "function_name": "...",
                "original_code": "..."
            }
        ]

    2. Dictionary containing a functions list:

        {
            "functions": [
                {
                    "function_name": "...",
                    "original_code": "..."
                }
            ]
        }

    3. Dictionary containing function records under
       another common container.
    """

    # -----------------------------------------------------
    # Case 1:
    # JSON itself is a list of function objects
    # -----------------------------------------------------

    if isinstance(data, list):

        functions = [
            item
            for item in data
            if isinstance(item, dict)
            and "original_code" in item
        ]

        if functions:
            return functions

    # -----------------------------------------------------
    # Case 2:
    # JSON is a dictionary
    # -----------------------------------------------------

    if isinstance(data, dict):

        # Most likely structure
        if isinstance(data.get("functions"), list):

            functions = [
                item
                for item in data["functions"]
                if isinstance(item, dict)
                and "original_code" in item
            ]

            if functions:
                return functions

        # Another possible structure
        if isinstance(data.get("function_records"), list):

            functions = [
                item
                for item in data["function_records"]
                if isinstance(item, dict)
                and "original_code" in item
            ]

            if functions:
                return functions

    raise ValueError(
        "Could not find function records containing "
        "'original_code' in the input JSON."
    )


def generate_embeddings(
    input_path: Path,
    output_path: Path,
    batch_size: int = 16,
) -> None:
    """
    Read extracted function JSON, generate CodeBERT
    embeddings, and save the enriched JSON.
    """

    # -----------------------------------------------------
    # Load extracted functions
    # -----------------------------------------------------

    data = load_json(input_path)

    functions = find_function_records(data)

    total_functions = len(functions)

    print()
    print("=" * 60)
    print("CODEBERT EMBEDDING GENERATION")
    print("=" * 60)
    print(f"Input file:          {input_path}")
    print(f"Functions found:     {total_functions}")
    print(f"Batch size:          {batch_size}")
    print(f"Model:               {MODEL_NAME}")
    print(f"Embedding dimension: {EMBEDDING_DIMENSION}")
    print("=" * 60)
    print()

    # -----------------------------------------------------
    # Load CodeBERT
    # -----------------------------------------------------

    embedder = CodeBERTEmbedder()

    # -----------------------------------------------------
    # Process functions in batches
    # -----------------------------------------------------

    for start in range(
        0,
        total_functions,
        batch_size,
    ):

        end = min(
            start + batch_size,
            total_functions,
        )

        batch_functions = functions[start:end]

        # Get source code
        code_batch = [
            function.get("original_code", "")
            for function in batch_functions
        ]

        # Generate embeddings
        embeddings = embedder.embed_batch(
            code_batch
        )

        # -------------------------------------------------
        # Store embedding in each function record
        # -------------------------------------------------

        for function, embedding in zip(
            batch_functions,
            embeddings,
        ):

            function["embedding_model"] = MODEL_NAME
            function["embedding_dimension"] = len(embedding)
            function["embedding"] = embedding

        print(
            f"Processed "
            f"{end}/{total_functions} functions"
        )

    # -----------------------------------------------------
    # Save result
    # -----------------------------------------------------

    save_json(
        output_path,
        data,
    )

    print()
    print("=" * 60)
    print("EMBEDDING GENERATION COMPLETE")
    print("=" * 60)
    print(f"Output: {output_path}")
    print(f"Functions embedded: {total_functions}")
    print(f"Vector dimension: {EMBEDDING_DIMENSION}")
    print("=" * 60)


def main():

    parser = argparse.ArgumentParser(
        description=(
            "Generate CodeBERT embeddings for "
            "extracted source-code functions."
        )
    )

    parser.add_argument(
        "input",
        help=(
            "Path to extracted functions JSON, "
            "for example outputs/test_functions.json"
        ),
    )

    parser.add_argument(
        "-o",
        "--output",
        help=(
            "Output JSON path. "
            "If omitted, '_embedded' is added "
            "to the input filename."
        ),
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=16,
        help="Number of functions processed at once.",
    )

    args = parser.parse_args()

    input_path = Path(args.input)

    if not input_path.exists():

        raise FileNotFoundError(
            f"Input file does not exist: {input_path}"
        )

    # -----------------------------------------------------
    # Automatically determine output filename
    # -----------------------------------------------------

    if args.output:

        output_path = Path(args.output)

    else:

        output_path = (
            input_path.parent
            / f"{input_path.stem}_embedded"
            f"{input_path.suffix}"
        )

    # -----------------------------------------------------
    # Generate embeddings
    # -----------------------------------------------------

    generate_embeddings(
        input_path=input_path,
        output_path=output_path,
        batch_size=args.batch_size,
    )


if __name__ == "__main__":
    main()