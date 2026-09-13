"""Deterministic change impact analyzer for identifying affected modules, callers, and tests."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Dict, List, Set

from agentproof.core.models import (
    ChangeImpact,
    ChangeSummary,
    FileCategory,
    ImpactRelation,
    ImpactedComponent,
)

# Directories to ignore during reference scanning
IGNORED_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__", "build", "dist",
    ".pytest_cache", ".eggs", ".idea", ".vscode"
}


class ImpactAnalyzer:
    """Discovers components impacted by changed files and symbols."""

    def __init__(self, root_dir: str | Path) -> None:
        self.root_dir = Path(root_dir).resolve()

    def _get_project_files(self) -> List[Path]:
        """Collect searchable source and test files in repository."""
        files: List[Path] = []
        for dirpath, dirnames, filenames in os.walk(self.root_dir):
            # Prune ignored directories in-place
            dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS and not d.startswith(".")]
            for f in filenames:
                ext = os.path.splitext(f)[1].lower()
                if ext in (".py", ".ts", ".js", ".tsx", ".jsx", ".go", ".rs"):
                    full_p = Path(dirpath) / f
                    # Skip huge generated files > 1MB
                    try:
                        if full_p.stat().st_size <= 1024 * 1024:
                            files.append(full_p)
                    except Exception:
                        pass
        return files

    def analyze(self, summary: ChangeSummary) -> ChangeImpact:
        """
        Analyze the repository to determine what components, callers,
        and tests are affected by the changes in summary.
        """
        if summary.total_files == 0:
            return ChangeImpact(
                changed_modules=[],
                impacted_source_files=[],
                impacted_test_files=[],
                impacted_configs=[],
                total_impact_score="LOW",
                untested_impacts=[],
            )

        # 1. Identify changed module identifiers and symbols
        changed_paths = [f.path.replace("\\", "/") for f in summary.files]
        changed_modules: List[str] = []
        target_tokens: Dict[str, Set[str]] = {}  # token -> set of changed file paths

        for f in summary.files:
            rel_p = f.path.replace("\\", "/")
            base_name = os.path.splitext(os.path.basename(rel_p))[0]
            if base_name != "__init__":
                changed_modules.append(base_name)
                target_tokens.setdefault(base_name, set()).add(rel_p)

            # Add symbol names
            for sym in f.changed_symbols:
                if len(sym.name) >= 3:  # avoid short common variable names
                    target_tokens.setdefault(sym.name, set()).add(rel_p)

            # If dependency file changed, record it
            if f.category == FileCategory.DEPENDENCY:
                changed_modules.append(f.path)

        project_files = self._get_project_files()
        impacted_source_map: Dict[str, ImpactedComponent] = {}
        impacted_test_map: Dict[str, ImpactedComponent] = {}
        impacted_configs: List[str] = []

        # 2. Check for dependency/config impacts
        has_dep_change = any(f.category == FileCategory.DEPENDENCY for f in summary.files)
        has_config_change = any(f.category == FileCategory.CONFIGURATION for f in summary.files)

        for f in summary.files:
            if f.category == FileCategory.CONFIGURATION:
                impacted_configs.append(f.path)

        # 3. Scan files for imports or references to changed modules / symbols
        for full_p in project_files:
            rel_p = str(full_p.relative_to(self.root_dir)).replace("\\", "/")
            if rel_p in changed_paths:
                continue  # Skip files that are already part of the change set

            is_test_file = (
                "/tests/" in rel_p or rel_p.startswith("tests/")
                or "/test/" in rel_p or rel_p.startswith("test/")
                or "test_" in os.path.basename(rel_p)
                or ".test." in rel_p
                or ".spec." in rel_p
            )

            # Check naming pattern for test file matching (e.g. test_calc.py for calc.py)
            matched_by_name = False
            for mod in changed_modules:
                if is_test_file and mod in os.path.basename(rel_p):
                    matched_by_name = True
                    impacted_test_map[rel_p] = ImpactedComponent(
                        file_path=rel_p,
                        relation=ImpactRelation.TEST_FOR_MODULE,
                        impacted_by=mod,
                        description=f"Direct test suite for module '{mod}'",
                    )
                    break

            if matched_by_name:
                continue

            # Read content to search for import / reference
            try:
                content = full_p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            for token, causes in target_tokens.items():
                # Use word-boundary search to avoid false substrings
                pattern = r"\b" + re.escape(token) + r"\b"
                if re.search(pattern, content):
                    caused_by = ", ".join(sorted(causes))
                    if is_test_file:
                        if rel_p not in impacted_test_map:
                            impacted_test_map[rel_p] = ImpactedComponent(
                                file_path=rel_p,
                                relation=ImpactRelation.TEST_FOR_MODULE,
                                impacted_by=caused_by,
                                description=f"Test references symbol/module '{token}'",
                            )
                    else:
                        if rel_p not in impacted_source_map:
                            relation = ImpactRelation.DIRECT_IMPORT if "import " in content else ImpactRelation.CALLER
                            impacted_source_map[rel_p] = ImpactedComponent(
                                file_path=rel_p,
                                relation=relation,
                                impacted_by=caused_by,
                                description=f"Imports or calls '{token}'",
                            )
                    break

        impacted_source = list(impacted_source_map.values())
        impacted_tests = list(impacted_test_map.values())

        # 4. Check for untested impacts (source files impacted whose tests did not run or don't exist)
        untested_impacts: List[str] = []
        for src in impacted_source:
            # Does this impacted source file have an associated test?
            base = os.path.splitext(os.path.basename(src.file_path))[0]
            has_matching_test = any(base in t.file_path for t in impacted_tests)
            if not has_matching_test:
                untested_impacts.append(src.file_path)

        # 5. Determine total impact score
        total_count = len(impacted_source) + len(impacted_tests) + len(impacted_configs)
        if has_dep_change or has_config_change or total_count >= 8:
            impact_score = "HIGH"
        elif total_count >= 3:
            impact_score = "MEDIUM"
        else:
            impact_score = "LOW"

        return ChangeImpact(
            changed_modules=sorted(list(set(changed_modules))),
            impacted_source_files=impacted_source,
            impacted_test_files=impacted_tests,
            impacted_configs=impacted_configs,
            total_impact_score=impact_score,
            untested_impacts=untested_impacts[:10],
        )
