#!/usr/bin/env python3
"""
github_migration_miner.py  (v2 — with file-level context caching)

Mines GitHub for merged Python 2 -> 3 migration commits/PRs and extracts:
  1. Function-level (original, migrated) code pairs      -> pairs.jsonl
  2. Full before/after file snapshots for context         -> data/files/...
  3. Import statements for each file version, attached     -> pairs.jsonl fields

This two-tier design keeps pairs.jsonl lightweight (good for RAG embedding
and verifier training) while preserving full file bodies on disk for
context lookups and for Experiment 4 (snippet-level vs repo-level migration).

USAGE
-----
1. Create a GitHub personal access token (classic, default/public_repo scope
   is enough for public repos): https://github.com/settings/tokens
2. export GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
3. pip install -r requirements.txt
4. Quick test run (recommended first):
     python github_migration_miner.py --out test_pairs.jsonl \
         --repos psf/requests --max-prs-per-repo 5
5. Full run:
     python github_migration_miner.py --out pairs.jsonl --max-prs-per-repo 30

OUTPUT LAYOUT
-------------
<dir of --out>/
├── pairs.jsonl                          (or whatever --out points to)
└── files/
    └── <owner>__<repo>/
        └── <sha>/
            └── <file_path>              (full file content at that commit)

Each line in pairs.jsonl:
{
  "repo": "owner/name",
  "pr_number": 1234,
  "pr_title": "...",
  "base_sha": "...",
  "head_sha": "...",
  "file_path": "src/foo.py",
  "function_name": "do_thing",
  "original_code": "def do_thing(x):\n    print x\n",
  "migrated_code": "def do_thing(x):\n    print(x)\n",
  "imports_original": ["import urllib2"],
  "imports_migrated": ["import urllib.request"],
  "original_file_ref": "files/psf__requests/abc123/requests/utils.py",
  "migrated_file_ref": "files/psf__requests/def456/requests/utils.py",
  "source": "mined"
}

NOTES / LIMITATIONS
--------------------
- Heuristic miner, not diff-hunk-precise: matches functions by name, so a
  rename is missed (acceptable trade-off for v1).
- Only module-level functions and one level of class methods are extracted;
  deeply nested functions are skipped for simplicity.
- Full file snapshots are written once per (repo, sha, file_path) even if
  multiple functions from that file end up in pairs.jsonl, so disk usage
  stays proportional to unique files touched, not to pair count.
- Respects GitHub's secondary/search rate limits with basic backoff.
"""

import argparse
import ast
import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass, asdict, field
from typing import Dict, Iterable, List, Optional, Tuple

import requests

API_ROOT = "https://api.github.com"

# ---------------------------------------------------------------------------
# Configuration — edit these for your first pass
# ---------------------------------------------------------------------------

TARGET_REPOS = [
    "psf/requests",
    "pallets/flask",
    "django/django",
    "sqlalchemy/sqlalchemy",
    "boto/boto",
    "benoitc/gunicorn",
    "paramiko/paramiko",
    "pytest-dev/pytest",
    "tornadoweb/tornado",
    "scrapy/scrapy",
]

SEARCH_KEYWORDS = [
    "port to python 3",
    "porting to python 3",
    "python 2 and 3",
    "python 2/3 compat",
    "py2/py3",
    "unicode_literals",
    "2to3",
    "six.moves",
]

# Restrict search to the era when repos were actually migrating off Python 2
# (roughly 2012-2019). Without this, keyword search on long-lived repos
# mostly surfaces recent, unrelated PRs like "drop support for Python 3.8"
# which happen to contain the substring "python 3" but are NOT migrations
# away from Python 2.
SEARCH_MERGED_BEFORE = "2019-12-31"

MIN_FUNCTION_LINES = 2
MAX_FUNCTION_LINES = 120

FILES_CACHE_DIR = "files"  # created under the same directory as --out

# ---------------------------------------------------------------------------


@dataclass
class MigrationPair:
    repo: str
    pr_number: int
    pr_title: str
    base_sha: str
    head_sha: str
    file_path: str
    function_name: str
    original_code: str
    migrated_code: str
    imports_original: List[str] = field(default_factory=list)
    imports_migrated: List[str] = field(default_factory=list)
    original_file_ref: str = ""
    migrated_file_ref: str = ""
    source: str = "mined"


class GitHubClient:
    def __init__(self, token: str):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
        )

    def _get(self, url: str, params: Optional[dict] = None) -> requests.Response:
        max_retries = 5
        for attempt in range(1, max_retries + 1):
            try:
                resp = self.session.get(url, params=params, timeout=30)
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                if attempt == max_retries:
                    raise
                wait = min(2 ** attempt, 30)
                print(
                    f"  connection dropped ({e.__class__.__name__}), "
                    f"retrying in {wait}s (attempt {attempt}/{max_retries}) ...",
                    file=sys.stderr,
                )
                time.sleep(wait)
                continue

            if resp.status_code == 403 and "rate limit" in resp.text.lower():
                reset = int(resp.headers.get("X-RateLimit-Reset", time.time() + 60))
                wait = max(reset - time.time(), 5)
                print(f"  rate limited, sleeping {wait:.0f}s ...", file=sys.stderr)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp
        raise RuntimeError(f"Failed to GET {url} after {max_retries} attempts")

    def search_merged_prs(self, repo: str, keyword: str, max_results: int) -> List[dict]:
        query = (
            f'repo:{repo} is:pr is:merged "{keyword}" in:title,body '
            f"merged:<{SEARCH_MERGED_BEFORE}"
        )
        results = []
        page = 1
        while len(results) < max_results:
            resp = self._get(
                f"{API_ROOT}/search/issues",
                params={"q": query, "per_page": 50, "page": page},
            )
            items = resp.json().get("items", [])
            if not items:
                break
            results.extend(items)
            page += 1
            time.sleep(1)  # search API has a tighter rate limit
            if page > 5:
                break
        return results[:max_results]

    def get_pr(self, repo: str, pr_number: int) -> dict:
        return self._get(f"{API_ROOT}/repos/{repo}/pulls/{pr_number}").json()

    def get_pr_files(self, repo: str, pr_number: int) -> List[dict]:
        files = []
        page = 1
        while True:
            resp = self._get(
                f"{API_ROOT}/repos/{repo}/pulls/{pr_number}/files",
                params={"per_page": 100, "page": page},
            )
            batch = resp.json()
            if not batch:
                break
            files.extend(batch)
            page += 1
        return files

    def get_file_content(self, repo: str, path: str, ref: str) -> Optional[str]:
        max_retries = 5
        resp = None
        for attempt in range(1, max_retries + 1):
            try:
                resp = self.session.get(
                    f"{API_ROOT}/repos/{repo}/contents/{path}",
                    params={"ref": ref},
                    timeout=30,
                )
                break
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                if attempt == max_retries:
                    print(f"    giving up on {path}@{ref}: {e}", file=sys.stderr)
                    return None
                wait = min(2 ** attempt, 30)
                print(
                    f"  connection dropped fetching {path}, retrying in {wait}s "
                    f"(attempt {attempt}/{max_retries}) ...",
                    file=sys.stderr,
                )
                time.sleep(wait)

        if resp is None or resp.status_code != 200:
            return None
        data = resp.json()
        if data.get("encoding") != "base64":
            return None
        import base64

        try:
            return base64.b64decode(data["content"]).decode("utf-8", errors="strict")
        except (UnicodeDecodeError, ValueError):
            return None


def extract_functions(source: str) -> Dict[str, str]:
    """Return {qualified_function_name: exact_source_text} for module-level
    functions and one level of class methods."""
    functions: Dict[str, str] = {}
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return functions

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            seg = ast.get_source_segment(source, node)
            if seg:
                functions[node.name] = seg
        elif isinstance(node, ast.ClassDef):
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    seg = ast.get_source_segment(source, child)
                    if seg:
                        functions[f"{node.name}.{child.name}"] = seg
    return functions


def extract_imports(source: str) -> List[str]:
    """Return a list of import statements (exact source text) at module
    level, e.g. ['import urllib2', 'from os import path']."""
    imports: List[str] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return imports

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            seg = ast.get_source_segment(source, node)
            if seg:
                imports.append(seg.strip())
    return imports


def diff_functions(
    original_src: str, migrated_src: str
) -> List[Tuple[str, str, str]]:
    """Return [(function_name, original_code, migrated_code)] for functions
    present in both versions whose source text changed."""
    orig_funcs = extract_functions(original_src)
    new_funcs = extract_functions(migrated_src)

    pairs = []
    for name, orig_code in orig_funcs.items():
        new_code = new_funcs.get(name)
        if new_code is None or new_code == orig_code:
            continue
        n_lines = new_code.count("\n") + 1
        if not (MIN_FUNCTION_LINES <= n_lines <= MAX_FUNCTION_LINES):
            continue
        pairs.append((name, orig_code, new_code))
    return pairs


def content_hash(a: str, b: str) -> str:
    return hashlib.sha256((a + "\x00" + b).encode("utf-8")).hexdigest()


def safe_repo_dirname(repo: str) -> str:
    return repo.replace("/", "__")


def cache_file(
    base_dir: str, repo: str, sha: str, file_path: str, content: str
) -> str:
    """Write full file content to <base_dir>/files/<repo>/<sha>/<file_path>
    and return the relative path written to, reusing it if already cached."""
    rel_path = os.path.join(
        FILES_CACHE_DIR, safe_repo_dirname(repo), sha, file_path.lstrip("/")
    )
    full_path = os.path.join(base_dir, rel_path)
    if not os.path.exists(full_path):
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
    return rel_path


def mine_repo(
    client: GitHubClient,
    repo: str,
    max_prs: int,
    seen_hashes: set,
    base_dir: str,
) -> Iterable[MigrationPair]:
    pr_numbers = set()
    for kw in SEARCH_KEYWORDS:
        print(f"[{repo}] searching: {kw!r}")
        for item in client.search_merged_prs(repo, kw, max_results=max_prs):
            pr_numbers.add(item["number"])
        if len(pr_numbers) >= max_prs:
            break

    print(f"[{repo}] found {len(pr_numbers)} candidate PRs")

    for pr_number in list(pr_numbers)[:max_prs]:
        try:
            pr = client.get_pr(repo, pr_number)
        except requests.HTTPError as e:
            print(f"  skip PR #{pr_number}: {e}", file=sys.stderr)
            continue

        base_sha = pr["base"]["sha"]
        head_sha = pr["merge_commit_sha"] or pr["head"]["sha"]

        try:
            files = client.get_pr_files(repo, pr_number)
        except requests.HTTPError as e:
            print(f"  skip PR #{pr_number} files: {e}", file=sys.stderr)
            continue

        py_files = [f for f in files if f["filename"].endswith(".py")]
        if not py_files:
            continue

        print(f"  PR #{pr_number}: {pr['title'][:70]!r} ({len(py_files)} .py files)")

        for f in py_files:
            path = f["filename"]
            original_src = client.get_file_content(repo, path, base_sha)
            migrated_src = client.get_file_content(repo, path, head_sha)
            if not original_src or not migrated_src:
                print(f"    {path}: could not fetch one or both versions, skipping")
                continue

            orig_func_count = len(extract_functions(original_src))
            func_pairs = diff_functions(original_src, migrated_src)
            if not func_pairs:
                print(
                    f"    {path}: {orig_func_count} functions found, "
                    f"0 changed (no matching-name diffs, or outside "
                    f"{MIN_FUNCTION_LINES}-{MAX_FUNCTION_LINES} line range)"
                )
                continue
            else:
                print(f"    {path}: {len(func_pairs)} changed function(s) found")

            # Cache full file bodies once per (repo, sha, path), reused
            # across every function pair extracted from this file.
            original_ref = cache_file(base_dir, repo, base_sha, path, original_src)
            migrated_ref = cache_file(base_dir, repo, head_sha, path, migrated_src)

            imports_original = extract_imports(original_src)
            imports_migrated = extract_imports(migrated_src)

            for name, orig_code, new_code in func_pairs:
                h = content_hash(orig_code, new_code)
                if h in seen_hashes:
                    continue
                seen_hashes.add(h)
                yield MigrationPair(
                    repo=repo,
                    pr_number=pr_number,
                    pr_title=pr["title"],
                    base_sha=base_sha,
                    head_sha=head_sha,
                    file_path=path,
                    function_name=name,
                    original_code=orig_code,
                    migrated_code=new_code,
                    imports_original=imports_original,
                    imports_migrated=imports_migrated,
                    original_file_ref=original_ref,
                    migrated_file_ref=migrated_ref,
                )

        time.sleep(0.5)  # be polite between PRs


def main():
    parser = argparse.ArgumentParser(
        description="Mine GitHub for Python 2->3 migration pairs (with file context caching)"
    )
    parser.add_argument("--out", default="pairs.jsonl", help="output .jsonl path")
    parser.add_argument(
        "--max-prs-per-repo", type=int, default=30, help="max candidate PRs to inspect per repo"
    )
    parser.add_argument(
        "--repos", nargs="*", default=None, help="override TARGET_REPOS, e.g. --repos psf/requests"
    )
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("ERROR: set GITHUB_TOKEN environment variable first.", file=sys.stderr)
        sys.exit(1)

    client = GitHubClient(token)
    repos = args.repos if args.repos else TARGET_REPOS

    # base_dir is the directory the output file lives in; the files/ cache
    # is created alongside it.
    out_path = args.out
    base_dir = os.path.dirname(os.path.abspath(out_path)) or "."

    seen_hashes = set()
    total = 0
    with open(out_path, "a", encoding="utf-8") as out_f:
        for repo in repos:
            try:
                for pair in mine_repo(client, repo, args.max_prs_per_repo, seen_hashes, base_dir):
                    out_f.write(json.dumps(asdict(pair), ensure_ascii=False) + "\n")
                    out_f.flush()
                    total += 1
            except requests.HTTPError as e:
                print(f"repo {repo} failed: {e}", file=sys.stderr)
                continue

    print(f"\nDone. Wrote {total} pairs to {out_path}")
    print(f"Full file snapshots cached under: {os.path.join(base_dir, FILES_CACHE_DIR)}")


if __name__ == "__main__":
    main()