"""High-level structure engine analyzing repository code and symbols."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from agentproof.structure.models import (
    AnalysisLevel,
    CodeSymbol,
    FileStructure,
    ProjectStructure,
    SupportedLanguage,
)
from agentproof.structure.parser import StructureParser

# Directories to ignore during repo-wide parsing
IGNORED_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__", "build", "dist",
    ".pytest_cache", ".eggs", ".idea", ".vscode", "target", "vendor", "bin"
}


class StructureEngine:
    """Orchestrates multi-language AST extraction and code-structure relationships."""

    def __init__(self, parser: Optional[StructureParser] = None) -> None:
        self.parser = parser or StructureParser()
        self._cache: Dict[str, Tuple[str, FileStructure]] = {}  # file_path -> (content_sha, FileStructure)

    def analyze_file(self, full_path: Path | str, rel_path: Optional[str] = None) -> FileStructure:
        """Parse a single file and cache its structural representation."""
        p = Path(full_path).resolve()
        rel_key = rel_path or str(p)

        if not p.is_file():
            return FileStructure(
                file_path=rel_key,
                language=SupportedLanguage.UNSUPPORTED,
                analysis_level=AnalysisLevel.UNSUPPORTED,
            )

        try:
            content = p.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return FileStructure(
                file_path=rel_key,
                language=SupportedLanguage.from_extension(p.suffix),
                analysis_level=AnalysisLevel.UNSUPPORTED,
                parse_error=f"Could not read file: {e}",
            )

        # Check content hash cache
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        if rel_key in self._cache and self._cache[rel_key][0] == content_hash:
            return self._cache[rel_key][1]

        structure = self.parser.parse_source(rel_key, content)
        self._cache[rel_key] = (content_hash, structure)
        return structure

    def analyze_source_text(self, file_path: str, content: str) -> FileStructure:
        """Parse source text directly without filesystem dependency."""
        return self.parser.parse_source(file_path, content)

    parse_file = analyze_file

    def analyze_project(
        self,
        repo_root: Path | str,
        files: Optional[List[str]] = None,
        max_file_size_bytes: int = 1024 * 1024,
    ) -> ProjectStructure:
        """
        Analyze all supported code files in a project, or a specified subset,
        building an aggregated ProjectStructure.
        """
        root = Path(repo_root).resolve()
        project = ProjectStructure()

        if files is not None:
            candidate_paths = [root / f for f in files]
        else:
            candidate_paths = []
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS and not d.startswith(".")]
                for fname in filenames:
                    ext = Path(fname).suffix.lower()
                    if SupportedLanguage.from_extension(ext) != SupportedLanguage.UNSUPPORTED:
                        candidate_paths.append(Path(dirpath) / fname)

        for full_p in candidate_paths:
            if not full_p.is_file():
                continue
            try:
                if full_p.stat().st_size > max_file_size_bytes:
                    continue
            except Exception:
                continue

            try:
                rel_p = str(full_p.relative_to(root)).replace("\\", "/")
            except ValueError:
                rel_p = str(full_p).replace("\\", "/")

            fs = self.analyze_file(full_p, rel_path=rel_p)
            project.files[rel_p] = fs

        return project

    def get_overlapping_symbols(
        self,
        full_path: Path | str,
        rel_path: str,
        changed_lines: Set[int],
    ) -> List[CodeSymbol]:
        """
        Identify symbols that overlap with git-modified line numbers.
        If changed_lines is empty (e.g. newly added file), all declared symbols are returned.
        """
        fs = self.analyze_file(full_path, rel_path=rel_path)
        if not changed_lines:
            return fs.symbols

        overlapping: List[CodeSymbol] = []
        for sym in fs.symbols:
            if any(sym.line_start <= line <= sym.line_end for line in changed_lines):
                overlapping.append(sym)
        return overlapping
