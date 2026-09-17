#!/usr/bin/env python3
"""
Extraction interface — the contract every language-specific extractor
must satisfy.

WHY THIS FILE EXISTS SEPARATELY:
Everything downstream (embeddings, RAG, LLM prompt, diffing, differential
testing) consumes FunctionRecord objects, not raw source code. If every
language extractor returns the SAME shape, none of that downstream code
needs to know or care whether the original was Python, Java, or PHP.

Adding a new language later = writing a new subclass of FunctionExtractor
that fills in FunctionRecord fields correctly for that language's grammar.
Nothing else changes.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FunctionRecord:
    """Language-agnostic representation of one extracted function/method.
    Field names match the migration_examples DB schema directly where
    that stage's data is actually available at EXTRACTION time. Columns
    that only make sense after LLM migration, verification, or embedding
    (migrated_code, verified, embedding, etc.) are NOT part of this record
    -- they get added by those later stages, not here."""

    # --- identity / RAG chunk fields ---
    chunk_id: str                       # stable id, e.g. "path::qualified_name::L10-L25"
    chunk_type: str                     # "function" (constant for this extractor)
    function_name: str
    function_full_name: str             # e.g. "MyClass.my_method" or just "my_func"

    # --- location ---
    file_path: str                      # relative path within the repo
    start_line: int
    end_line: int

    # --- content ---
    original_code: str                  # exact original source text
    params: list = field(default_factory=list)

    # --- structured context columns ---
    imports_original: list = field(default_factory=list)   # imports visible in this file
    classes: Optional[dict] = None                          # {"name":..., "bases":[...]} or None
    functions: list = field(default_factory=list)           # function/method names called in body
    static_analysis: dict = field(default_factory=dict)     # {"loc":.., "branch_count":.., "param_count":..}

    # --- language context ---
    source_language: str = ""           # e.g. "Python"
    language_version: str = ""          # e.g. "2" -- not a DB column, kept for pipeline use

    def to_dict(self) -> dict:
        """Matches migration_examples columns. Fields this stage can't
        know yet (migration/verification/embedding) are explicit None so
        the shape is obvious when this gets inserted into the DB later."""
        core = {
            "chunk_id": self.chunk_id,
            "chunk_type": self.chunk_type,
            "function_name": self.function_name,
            "function_full_name": self.function_full_name,
            "original_code": self.original_code,
            "migrated_code": None,          # filled by LLM migration stage
            "source_language": self.source_language,
            "target_language": None,        # filled by LLM migration stage
            "source_lib": None,             # filled later, needs library-mapping logic
            "target_lib": None,
            "file_path": self.file_path,
            "source_file": self.file_path,
            "target_file": None,
            "imports_original": self.imports_original,
            "imports_migrated": None,
            "classes": self.classes,
            "functions": self.functions,
            "static_analysis": self.static_analysis,
            "verified": None,               # filled by verification stage
            "verification": None,
            "quality": None,
            "embedding_model": None,        # filled by embedding stage
            "embedding_dimension": None,
            "metadata": {"params": self.params, "start_line": self.start_line,
                         "end_line": self.end_line, "language_version": self.language_version},
        }
        core["full_record"] = core.copy()   # nothing lost, per your schema's design intent
        return core


class FunctionExtractor:
    """Base interface. Every language plugs in here.

    Example registration (in a future extractor_registry.py):
        EXTRACTORS = {
            "Python": PythonExtractor(),
            "Java": JavaExtractor(),   # added later, same interface
        }
    """

    language: str = None

    def extract(self, file_path: str, source: str, language_version: str) -> list[FunctionRecord]:
        """Must return a list of FunctionRecord for every function/method
        found in `source`. Implementations should never raise on files
        they can't fully parse — return what they can and note failures
        via logging, so one bad file doesn't kill a whole repo run."""
        raise NotImplementedError