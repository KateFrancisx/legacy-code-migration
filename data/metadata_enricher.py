#!/usr/bin/env python3

"""
metadata_enricher.py

Converts high-confidence records from pairs_quality.jsonl into a
RAG-ready JSONL format.

IMPORTANT:
- Does NOT guess missing metadata.
- Uses only information present in the input or obtained directly
  from GitHub when --github is enabled.
- Anything unavailable is written as null.
- Only records with quality.label == "high_confidence" are exported.

USAGE
-----

Without GitHub API:
    python metadata_enricher.py \
        --input pairs_quality.jsonl \
        --output rag_ready_298.jsonl

With GitHub API:
    set GITHUB_TOKEN=ghp_xxxxxxxxxxxxx

    python metadata_enricher.py \
        --input pairs_quality.jsonl \
        --output rag_ready_298.jsonl \
        --github

Expected output:
    rag_ready_298.jsonl

The output follows the metadata schema requested for the RAG database.
"""

import argparse
import hashlib
import json
import os
import sys
import time
from typing import Optional

import requests


# ============================================================
# GITHUB CLIENT
# ============================================================

API_ROOT = "https://api.github.com"


class GitHubClient:

    def __init__(self, token: str):

        self.session = requests.Session()

        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        })

    def get(self, url, params=None):

        for attempt in range(5):

            try:

                response = self.session.get(
                    url,
                    params=params,
                    timeout=30
                )

                if response.status_code == 403:

                    remaining = response.headers.get(
                        "X-RateLimit-Remaining"
                    )

                    if remaining == "0":

                        reset = int(
                            response.headers.get(
                                "X-RateLimit-Reset",
                                time.time() + 60
                            )
                        )

                        wait = max(
                            reset - time.time(),
                            5
                        )

                        print(
                            f"Rate limited. Waiting {wait:.0f}s..."
                        )

                        time.sleep(wait)
                        continue

                if response.status_code == 404:
                    return None

                response.raise_for_status()

                return response.json()

            except (
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout
            ) as e:

                if attempt == 4:
                    print(
                        f"GitHub request failed: {e}",
                        file=sys.stderr
                    )
                    return None

                wait = 2 ** attempt

                print(
                    f"Connection error. Retrying in {wait}s..."
                )

                time.sleep(wait)

        return None

    # --------------------------------------------------------

    def get_pr(self, repo, pr_number):

        return self.get(
            f"{API_ROOT}/repos/{repo}/pulls/{pr_number}"
        )

    # --------------------------------------------------------

    def get_commit(self, repo, sha):

        return self.get(
            f"{API_ROOT}/repos/{repo}/commits/{sha}"
        )

    # --------------------------------------------------------

    def get_file(self, repo, path, sha):

        return self.get(
            f"{API_ROOT}/repos/{repo}/contents/{path}",
            params={"ref": sha}
        )


# ============================================================
# UTILITY FUNCTIONS
# ============================================================

def make_id(record):

    """
    Creates a deterministic ID.

    We do NOT use a random UUID because running the script twice
    should produce the same ID for the same migration pair.
    """

    values = [
        record.get("repo"),
        record.get("pr_number"),
        record.get("file_path"),
        record.get("function_name"),
        record.get("base_sha"),
        record.get("head_sha"),
    ]

    raw = "|".join(
        "" if value is None else str(value)
        for value in values
    )

    digest = hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()

    return "github_py23_" + digest[:16]


# ============================================================

def get_project_name(repo):

    """
    owner/repository -> repository

    This is safe because it is directly derived from repo.
    """

    if not repo:
        return None

    if "/" not in repo:
        return None

    return repo.split("/", 1)[1]


# ============================================================

def get_repository_url(repo):

    if not repo:
        return None

    return f"https://github.com/{repo}"


# ============================================================

def get_source_url(record):

    repo = record.get("repo")
    sha = record.get("base_sha")
    path = record.get("file_path")

    if not repo or not sha or not path:
        return None

    return (
        f"https://github.com/{repo}"
        f"/blob/{sha}/{path}"
    )


# ============================================================

def get_target_url(record):

    repo = record.get("repo")
    sha = record.get("head_sha")
    path = record.get("file_path")

    if not repo or not sha or not path:
        return None

    return (
        f"https://github.com/{repo}"
        f"/blob/{sha}/{path}"
    )


# ============================================================

def get_class_from_function_name(function_name):

    """
    Your miner represents class methods as:

        ClassName.method_name

    Therefore this is safe to derive.

    For module-level functions, classes = null.
    """

    if not function_name:
        return None

    if "." not in function_name:
        return None

    class_name = function_name.rsplit(".", 1)[0]

    if not class_name:
        return None

    return [class_name]


# ============================================================

def get_function_list(record):

    """
    The input pair definitely contains the paired function.

    We therefore return that function.

    We DO NOT claim that this is the complete list of functions
    in the file.
    """

    function_name = record.get("function_name")

    if not function_name:
        return None

    return [function_name]


# ============================================================

def derive_libraries(imports):

    """
    IMPORTANT:

    We intentionally return None.

    An import statement is not necessarily a library identity.

    Example:

        from django.http import HttpResponse

    could be interpreted at different levels.

    Since the user explicitly requested NO GUESSING,
    source_lib / target_lib remain null unless a trusted
    library mapping is explicitly provided.
    """

    return None


# ============================================================

def build_migration_context(record, quality):

    """
    Only stores facts already present in the dataset.

    No semantic interpretation is invented here.
    """

    context = {}

    if record.get("pr_title") is not None:
        context["pr_title"] = record["pr_title"]

    if record.get("source") is not None:
        context["source"] = record["source"]

    if record.get("base_sha") is not None:
        context["base_sha"] = record["base_sha"]

    if record.get("head_sha") is not None:
        context["head_sha"] = record["head_sha"]

    if record.get("original_file_ref") is not None:
        context["original_file_ref"] = record[
            "original_file_ref"
        ]

    if record.get("migrated_file_ref") is not None:
        context["migrated_file_ref"] = record[
            "migrated_file_ref"
        ]

    # Quality-check evidence

    if quality:

        if quality.get("py2_markers_in_original") is not None:

            context["py2_markers_in_original"] = quality[
                "py2_markers_in_original"
            ]

        if quality.get(
            "py2_markers_remaining_in_migrated"
        ) is not None:

            context[
                "py2_markers_remaining_in_migrated"
            ] = quality[
                "py2_markers_remaining_in_migrated"
            ]

    return context if context else None


# ============================================================
# GITHUB ENRICHMENT
# ============================================================

def get_github_metadata(record, github):

    """
    Retrieves additional facts directly from GitHub.

    If GitHub cannot provide a field, the field remains None.

    Nothing is inferred.
    """

    if github is None:
        return {
            "commit": None,
            "github_pr_title": None,
            "github_pr_url": None,
        }

    repo = record.get("repo")
    pr_number = record.get("pr_number")

    if not repo or not pr_number:
        return {
            "commit": None,
            "github_pr_title": None,
            "github_pr_url": None,
        }

    pr = github.get_pr(repo, pr_number)

    if not pr:
        return {
            "commit": None,
            "github_pr_title": None,
            "github_pr_url": None,
        }

    # GitHub provides the actual merge commit SHA here.
    merge_sha = pr.get("merge_commit_sha")

    # IMPORTANT:
    # "commit" is kept as a commit object/name only if GitHub actually
    # provides a commit message.
    commit_data = None

    if merge_sha:

        commit_obj = github.get_commit(
            repo,
            merge_sha
        )

        if commit_obj:

            message = (
                commit_obj
                .get("commit", {})
                .get("message")
            )

            if message:
                commit_data = message.splitlines()[0]

    return {
        "commit": commit_data,
        "github_pr_title": pr.get("title"),
        "github_pr_url": pr.get("html_url"),
    }


# ============================================================
# BUILD OUTPUT RECORD
# ============================================================

def build_record(record, github=None):

    quality = record.get("quality") or {}

    github_data = get_github_metadata(
        record,
        github
    )

    repo = record.get("repo")

    function_name = record.get(
        "function_name"
    )

    class_list = get_class_from_function_name(
        function_name
    )

    function_list = get_function_list(
        record
    )

    # --------------------------------------------------------
    # verification
    # --------------------------------------------------------

    verification = {
        "method": "check_pair_quality.py",
        "status": quality.get("label"),

        "original_fails_py3_parse":
            quality.get(
                "original_fails_py3_parse"
            ),

        "migrated_parses_py3":
            quality.get(
                "migrated_parses_py3"
            ),

        "py2_markers_in_original":
            quality.get(
                "py2_markers_in_original"
            ),

        "py2_markers_remaining_in_migrated":
            quality.get(
                "py2_markers_remaining_in_migrated"
            ),

        "similarity_ratio":
            quality.get(
                "similarity_ratio"
            ),
    }

    # --------------------------------------------------------
    # metadata
    # --------------------------------------------------------

    metadata = {

        "data_source": "GitHub",

        "mining_source":
            record.get("source"),

        "pair_level": "function",

        "base_sha":
            record.get("base_sha"),

        "head_sha":
            record.get("head_sha"),

        "original_file_ref":
            record.get("original_file_ref"),

        "migrated_file_ref":
            record.get("migrated_file_ref"),

        "quality_check_method":
            "check_pair_quality.py",

        "quality_check_label":
            quality.get("label"),
    }

    # --------------------------------------------------------
    # FINAL RECORD
    # --------------------------------------------------------

    output = {

        "id":
            make_id(record),

        "function_name":
            function_name,

        "original_code":
            record.get("original_code"),

        "migrated_code":
            record.get("migrated_code"),

        "source_language":
            "Python 2",

        "target_language":
            "Python 3",

        # STRICT:
        # Do not guess library identities.
        "source_lib":
            derive_libraries(
                record.get(
                    "imports_original"
                )
            ),

        "target_lib":
            derive_libraries(
                record.get(
                    "imports_migrated"
                )
            ),

        "repo":
            repo,

        "file_path":
            record.get("file_path"),

        "pr_number":
            record.get("pr_number"),

        # Actual commit message is obtained only if GitHub
        # returns it successfully.
        "commit":
            github_data.get("commit"),

        # This is the actual head SHA stored by the miner.
        "commit_hash":
            record.get("head_sha"),

        # Your miner matches functions by exact function name.
        "match_type":
            "exact_function_name",

        "imports_original":
            record.get(
                "imports_original"
            ),

        "imports_migrated":
            record.get(
                "imports_migrated"
            ),

        "classes":
            class_list,

        "functions":
            function_list,

        "migration_context":
            build_migration_context(
                record,
                quality
            ),

        "verification":
            verification,

        # IMPORTANT:
        # High-confidence != behaviorally verified.
        # Therefore this remains null.
        "verified":
            None,

        "quality":
            quality.get("label"),

        "source_url":
            get_source_url(record),

        "target_url":
            get_target_url(record),

        "project_name":
            get_project_name(repo),

        "repository_url":
            get_repository_url(repo),

        "metadata":
            metadata,
    }

    return output


# ============================================================
# MAIN
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Create strict RAG metadata records from "
            "pairs_quality.jsonl"
        )
    )

    parser.add_argument(
        "--input",
        required=True,
        help="Input pairs_quality.jsonl"
    )

    parser.add_argument(
        "--output",
        required=True,
        help="Output RAG-ready JSONL"
    )

    parser.add_argument(
        "--github",
        action="store_true",
        help=(
            "Use GitHub API to retrieve additional "
            "metadata such as merge commit message"
        )
    )

    args = parser.parse_args()

    # --------------------------------------------------------
    # GitHub setup
    # --------------------------------------------------------

    github = None

    if args.github:

        token = os.environ.get(
            "GITHUB_TOKEN"
        )

        if not token:

            print(
                "ERROR: --github was specified but "
                "GITHUB_TOKEN is not set.",
                file=sys.stderr
            )

            sys.exit(1)

        github = GitHubClient(token)

    # --------------------------------------------------------
    # Read input
    # --------------------------------------------------------

    total = 0
    high_confidence = 0
    skipped = 0

    records = []

    with open(
        args.input,
        "r",
        encoding="utf-8-sig"
    ) as f:

        for line_number, line in enumerate(
            f,
            start=1
        ):

            line = line.strip()

            if not line:
                continue

            total += 1

            try:

                record = json.loads(line)

            except json.JSONDecodeError as e:

                print(
                    f"WARNING: malformed JSON at line "
                    f"{line_number}: {e}",
                    file=sys.stderr
                )

                skipped += 1
                continue

            quality = record.get(
                "quality"
            ) or {}

            if quality.get("label") != "high_confidence":

                continue

            high_confidence += 1

            records.append(record)

    # --------------------------------------------------------
    # Write output
    # --------------------------------------------------------

    with open(
        args.output,
        "w",
        encoding="utf-8"
    ) as out:

        for index, record in enumerate(
            records,
            start=1
        ):

            print(
                f"Processing {index}/{len(records)}...",
                end="\r"
            )

            enriched = build_record(
                record,
                github
            )

            out.write(
                json.dumps(
                    enriched,
                    ensure_ascii=False
                ) + "\n"
            )

    print()
    print("=" * 60)
    print("DONE")
    print("=" * 60)

    print(
        f"Input records:       {total}"
    )

    print(
        f"High-confidence:     {high_confidence}"
    )

    print(
        f"Skipped malformed:   {skipped}"
    )

    print(
        f"Output:              {args.output}"
    )

    print()
    print(
        "Strict NULL policy applied."
    )

    if not args.github:

        print(
            "GitHub API enrichment: DISABLED"
        )

    else:

        print(
            "GitHub API enrichment: ENABLED"
        )


if __name__ == "__main__":
    main()