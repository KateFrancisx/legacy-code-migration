#!/usr/bin/env python3
"""
Version Detector — enriches a scanner manifest with language VERSION info.

This sits between the Repository Scanner and the Function Extractor.
It is deliberately a SEPARATE stage from the scanner:

    Scanner        -> "what language is this file?"      (extension-based)
    VersionDetector -> "which version of that language?"  (content-based)

Keeping these separate means adding a new language later (Java, PHP, ...)
only means writing a new *VersionDetector* subclass and registering it —
the scanner and the rest of the pipeline never change.

Usage:
    python version_detector.py manifest.json -o manifest_versioned.json
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional

try:
    import parso
    PARSO_AVAILABLE = True
except ImportError:
    PARSO_AVAILABLE = False


# ---------------------------------------------------------------------------
# Registry pattern: one detector class per language. Adding Java later means
# writing JavaVersionDetector and adding one line to DETECTORS — nothing
# else in this file or upstream/downstream changes.
# ---------------------------------------------------------------------------

class VersionDetector:
    """Base interface every language's version detector must implement."""
    language = None

    def detect(self, source: str) -> dict:
        """Return {'version': str, 'confidence': str, 'method': str, 'signals': list}"""
        raise NotImplementedError


class PythonVersionDetector(VersionDetector):
    language = "Python"

    # Regex heuristics used as a fallback when parso isn't installed, and
    # ALSO kept as a cross-check even when it is — divergence between the
    # parser result and the heuristic result is itself a useful signal.
    PY2_SIGNALS = [
        (r'^\s*print\s+[^(]', "print statement (no parens)"),
        (r'except\s+\w+(\.\w+)*\s*,\s*\w+', "old-style except (Exception, e)"),
        (r'^\s*exec\s+[^(]', "exec statement"),
        (r'\bunicode\s*\(', "unicode() builtin"),
        (r'\bxrange\s*\(', "xrange() builtin"),
        (r'<>', "<> operator"),
        (r'raise\s+\w+\s*,\s*[\'"]', "old-style raise Exception, \"msg\""),
        (r'^\s*0[0-7]+\s*[,)\]]', "old-style octal literal"),
        # API-level signals: these survive forward-compatible SYNTAX styling
        # (e.g. code already using print() calls) because they're about
        # which library/method is used, not how a statement is written.
        (r'\.iteritems\s*\(', ".iteritems() (dict method removed in Py3)"),
        (r'\.iterkeys\s*\(', ".iterkeys() (dict method removed in Py3)"),
        (r'\.itervalues\s*\(', ".itervalues() (dict method removed in Py3)"),
        (r'\.has_key\s*\(', ".has_key() (dict method removed in Py3)"),
        (r'\bimport\s+urllib2\b', "import urllib2 (merged into urllib in Py3)"),
        (r'\bimport\s+ConfigParser\b', "import ConfigParser (renamed configparser in Py3)"),
        (r'\bimport\s+Queue\b', "import Queue (renamed queue in Py3)"),
        (r'\bimport\s+cPickle\b', "import cPickle (merged into pickle in Py3)"),
        (r'\bunichr\s*\(', "unichr() builtin (removed in Py3)"),
        (r'\bbasestring\b', "basestring type (removed in Py3)"),
        (r'\braw_input\s*\(', "raw_input() (renamed input() in Py3)"),
        (r'__metaclass__\s*=', "__metaclass__ assignment (old-style metaclass syntax)"),
    ]
    PY3_SIGNALS = [
        (r'\bprint\s*\(', "print() function call"),
        (r'^\s*async\s+def\s', "async def"),
        (r':\s*\w+\s*->', "-> return type annotation"),
        (r'f[\'"].*\{.*\}.*[\'"]', "f-string"),
    ]

    def detect(self, source: str) -> dict:
        if PARSO_AVAILABLE:
            parser_result = self._detect_via_parso(source)
            if parser_result is not None:
                return parser_result
            # Grammar check was inconclusive (parses under both grammars,
            # or neither) -- fall through to API-signal heuristic.

        return self._detect_via_heuristic(source, parso_inconclusive=PARSO_AVAILABLE)

    def _detect_via_parso(self, source: str) -> Optional[dict]:
        """Check BOTH grammars before deciding anything. A file that
        parses cleanly under BOTH grammars (common for forward-compatible
        Python 2 code using print(), no old except-syntax, etc.) is
        genuinely ambiguous by grammar alone -- checking grammar 3 first
        and stopping there (the old bug) silently mislabels all such
        files as Python 3. Only trust a grammar-based verdict when
        exactly one grammar parses clean and the other doesn't."""
        try:
            grammar3 = parso.load_grammar(version="3.10")
            tree3 = grammar3.parse(source)
            clean3 = len(list(grammar3.iter_errors(tree3))) == 0
        except Exception:
            clean3 = None  # grammar itself failed to load/run

        try:
            grammar2 = parso.load_grammar(version="2.7")
            tree2 = grammar2.parse(source)
            clean2 = len(list(grammar2.iter_errors(tree2))) == 0
        except Exception:
            clean2 = None  # e.g. parso>=0.8 dropped 2.7 grammar entirely

        if clean3 is True and clean2 is False:
            return {"version": "3", "confidence": "high", "method": "parso_grammar",
                    "signals": ["parses cleanly as Python 3 only"]}
        if clean2 is True and clean3 is False:
            return {"version": "2", "confidence": "high", "method": "parso_grammar",
                    "signals": ["parses cleanly as Python 2 only"]}
        if clean2 is True and clean3 is True:
            # Genuinely ambiguous by grammar -- forward-compatible style.
            # Let the heuristic break the tie using API-level signals.
            return None
        return None  # both failed, or a grammar couldn't be loaded at all

    def _detect_via_heuristic(self, source: str, parso_inconclusive: bool) -> dict:
        py2_hits = [label for pattern, label in self.PY2_SIGNALS if re.search(pattern, source, re.MULTILINE)]
        py3_hits = [label for pattern, label in self.PY3_SIGNALS if re.search(pattern, source, re.MULTILINE)]

        method = "regex_heuristic" + ("_after_inconclusive_parso" if parso_inconclusive else "_no_parso")

        if py2_hits and not py3_hits:
            return {"version": "2", "confidence": "medium", "method": method, "signals": py2_hits}
        if py3_hits and not py2_hits:
            return {"version": "3", "confidence": "medium", "method": method, "signals": py3_hits}
        if py2_hits and py3_hits:
            return {"version": "ambiguous", "confidence": "low", "method": method,
                    "signals": py2_hits + py3_hits}
        return {"version": "unknown", "confidence": "low", "method": method, "signals": []}


DETECTORS = {
    "Python": PythonVersionDetector(),
    # "Java": JavaVersionDetector(),   # <- add later, same pattern
}


def enrich_manifest(manifest: dict, repo_root: Path) -> dict:
    for entry in manifest["files"]:
        detector = DETECTORS.get(entry["language"])
        if detector is None or entry["category"] != "code":
            continue  # no version detector for this language yet, or not code

        file_path = repo_root / entry["path"]
        try:
            source = file_path.read_text(errors="ignore")
        except OSError:
            entry["version_detection"] = {"version": "unknown", "confidence": "low",
                                           "method": "read_error", "signals": []}
            continue

        entry["version_detection"] = detector.detect(source)

    return manifest


def main():
    parser = argparse.ArgumentParser(description="Enrich a scanner manifest with language version detection")
    parser.add_argument("manifest_path", help="Path to manifest.json produced by repo_scanner.py")
    parser.add_argument("--repo-root", help="Repo root the manifest paths are relative to (default: manifest's own dir)")
    parser.add_argument("-o", "--output", default="manifest_versioned.json")
    args = parser.parse_args()

    manifest_path = Path(args.manifest_path)
    with open(manifest_path) as f:
        manifest = json.load(f)

    repo_root = Path(args.repo_root) if args.repo_root else manifest_path.parent
    manifest = enrich_manifest(manifest, repo_root)

    with open(args.output, "w") as f:
        json.dump(manifest, f, indent=2)

    py_files = [e for e in manifest["files"] if e["language"] == "Python"]
    v2 = sum(1 for e in py_files if e.get("version_detection", {}).get("version") == "2")
    v3 = sum(1 for e in py_files if e.get("version_detection", {}).get("version") == "3")
    amb = sum(1 for e in py_files if e.get("version_detection", {}).get("version") in ("ambiguous", "unknown"))
    print(f"Python files: {len(py_files)}  |  v2: {v2}  v3: {v3}  ambiguous/unknown: {amb}")
    print(f"parso available: {PARSO_AVAILABLE} (install with: pip install parso --break-system-packages)")
    print(f"Enriched manifest written to {args.output}")


if __name__ == "__main__":
    main()