#!/usr/bin/env python3
"""
Module 1 + Module 2: Repository Scanner + Language Detection
--------------------------------------------------------------
Phase 1 MVP scope:
  - Recursively walk a repo directory
  - Classify every file as a known code language, a "non-code" asset,
    or unknown
  - Emit a machine-readable manifest (JSON) matching the shape described
    in the project spec (section 7), plus a summary block

Explicitly OUT of scope for this script (comes later):
  - Syntax-based / parser-based language detection
  - AST extraction (Module 4)
  - Dependency / import graph building (Module 3)

Usage:
    python repo_scanner.py /path/to/legacy_project -o manifest.json
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Config: extension -> language map
# Extend this dict as you add support for more languages. Keeping it as a
# single source of truth means Module 9 (model router) can later reuse it
# directly instead of re-deriving language names elsewhere.
# ---------------------------------------------------------------------------

LANGUAGE_MAP = {
    ".py": "Python",
    ".java": "Java",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".cpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".hpp": "C++",
    ".c": "C",
    ".h": "C",
    ".cs": "C#",
    ".php": "PHP",
    ".go": "Go",
    ".rs": "Rust",
    ".rb": "Ruby",
    ".sql": "SQL",
    ".sh": "Shell",
    ".bash": "Shell",
    ".pl": "Perl",
    ".kt": "Kotlin",
    ".swift": "Swift",
    ".scala": "Scala",
}

# Config files are "code-adjacent" — not migration targets themselves in the
# MVP, but relevant to repository mapping later. Tracked separately so the
# report can say "3 config files detected" instead of lumping them in with
# "unknown".
CONFIG_EXTENSIONS = {
    ".yaml": "YAML",
    ".yml": "YAML",
    ".xml": "XML",
    ".json": "JSON",
    ".toml": "TOML",
    ".ini": "INI",
    ".cfg": "Config",
    ".env": "Env",
}

# Files that never need migration — tracked as "non_code" per spec section 8.
NON_CODE_EXTENSIONS = {
    ".md": "Documentation",
    ".rst": "Documentation",
    ".txt": "Text",
    ".png": "Image",
    ".jpg": "Image",
    ".jpeg": "Image",
    ".gif": "Image",
    ".svg": "Image",
    ".pdf": "Document",
    ".lock": "Lockfile",
}

# Directories to skip outright — build artifacts, VCS metadata, dependency
# caches. Never worth scanning and can be huge.
EXCLUDED_DIRS = {
    ".git", ".svn", ".hg",
    "node_modules", "__pycache__", ".venv", "venv", "env",
    "dist", "build", "target", ".idea", ".vscode",
    ".pytest_cache", ".mypy_cache", "coverage",
}


def classify_file(path: Path) -> dict:
    """Classify a single file by extension. Returns a manifest entry."""
    ext = path.suffix.lower()

    if ext in LANGUAGE_MAP:
        return {
            "language": LANGUAGE_MAP[ext],
            "category": "code",
            "detection_method": "extension",
            "confidence": "high",
        }
    if ext in CONFIG_EXTENSIONS:
        return {
            "language": CONFIG_EXTENSIONS[ext],
            "category": "config",
            "detection_method": "extension",
            "confidence": "high",
        }
    if ext in NON_CODE_EXTENSIONS:
        return {
            "language": NON_CODE_EXTENSIONS[ext],
            "category": "non_code",
            "detection_method": "extension",
            "confidence": "high",
        }

    # Extension-less files (e.g. `Makefile`, `Dockerfile`) — cheap shebang
    # sniff as a fallback before giving up. This is the one bit of
    # content-based detection worth doing even in the MVP, since scripts
    # without extensions are common in legacy repos.
    if ext == "":
        lang = _sniff_shebang(path)
        if lang:
            return {
                "language": lang,
                "category": "code",
                "detection_method": "shebang",
                "confidence": "medium",
            }
        if path.name in ("Dockerfile", "Makefile", "Jenkinsfile"):
            return {
                "language": path.name,
                "category": "config",
                "detection_method": "filename",
                "confidence": "high",
            }

    return {
        "language": "Unknown",
        "category": "unknown",
        "detection_method": "none",
        "confidence": "low",
    }


def _sniff_shebang(path: Path) -> str | None:
    """Peek at the first line of an extension-less file for a shebang."""
    try:
        with open(path, "r", errors="ignore") as f:
            first_line = f.readline().strip()
    except (OSError, UnicodeDecodeError):
        return None

    if not first_line.startswith("#!"):
        return None
    if "python" in first_line:
        return "Python"
    if "bash" in first_line or "/sh" in first_line:
        return "Shell"
    if "node" in first_line:
        return "JavaScript"
    if "perl" in first_line:
        return "Perl"
    if "ruby" in first_line:
        return "Ruby"
    return None


def scan_repository(root: str) -> dict:
    """Walk the repo and build the full manifest."""
    root_path = Path(root).resolve()
    if not root_path.is_dir():
        raise NotADirectoryError(f"{root} is not a valid directory")

    files = []
    for dirpath, dirnames, filenames in os.walk(root_path):
        # prune excluded dirs in-place so os.walk doesn't descend into them
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]

        for fname in filenames:
            fpath = Path(dirpath) / fname
            rel_path = fpath.relative_to(root_path).as_posix()

            try:
                size_bytes = fpath.stat().st_size
            except OSError:
                size_bytes = None

            entry = classify_file(fpath)
            entry.update({
                "path": rel_path,
                "size_bytes": size_bytes,
            })
            files.append(entry)

    summary = _build_summary(files)

    return {
        "repository": root_path.name,
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "total_files": len(files),
        "summary": summary,
        "files": files,
    }


def _build_summary(files: list) -> dict:
    lang_counts: dict = {}
    category_counts = {"code": 0, "config": 0, "non_code": 0, "unknown": 0}

    for f in files:
        lang_counts[f["language"]] = lang_counts.get(f["language"], 0) + 1
        category_counts[f["category"]] = category_counts.get(f["category"], 0) + 1

    return {
        "languages_detected": sorted(
            [lang for lang in lang_counts if lang != "Unknown"]
        ),
        "language_file_counts": lang_counts,
        "category_counts": category_counts,
    }


def main():
    parser = argparse.ArgumentParser(description="Repository scanner + language detector")
    parser.add_argument("repo_path", help="Path to the legacy repository root")
    parser.add_argument(
        "-o", "--output", default="manifest.json",
        help="Output JSON manifest path (default: manifest.json)"
    )
    parser.add_argument(
        "--pretty", action="store_true", default=True,
        help="Pretty-print the JSON output"
    )
    args = parser.parse_args()

    try:
        manifest = scan_repository(args.repo_path)
    except NotADirectoryError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    with open(args.output, "w") as f:
        json.dump(manifest, f, indent=2 if args.pretty else None)

    print(f"Scanned {manifest['total_files']} files in '{manifest['repository']}'")
    print(f"Languages detected: {', '.join(manifest['summary']['languages_detected']) or 'none'}")
    print(f"Manifest written to {args.output}")


if __name__ == "__main__":
    main()
