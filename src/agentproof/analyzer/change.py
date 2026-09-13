"""Static change analyzer: file categorization, risk signals, and drift heuristics."""

from __future__ import annotations

import os
import re
from typing import List, Tuple

from agentproof.core.models import (
    ChangeSummary,
    FileCategory,
    FileChange,
    RiskSeverity,
    RiskWarning,
)

# Known dependency file patterns
DEPENDENCY_FILENAMES = {
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "requirements.txt",
    "requirements-dev.txt",
    "pipfile",
    "pipfile.lock",
    "poetry.lock",
    "cargo.toml",
    "cargo.lock",
    "go.mod",
    "go.sum",
    "gemfile",
    "gemfile.lock",
    "pom.xml",
    "build.gradle",
}

# Configuration file patterns
CONFIG_EXTENSIONS = {".yaml", ".yml", ".json", ".toml", ".ini", ".cfg", ".conf"}
CONFIG_SUBSTRINGS = {"docker-compose", "dockerfile", "tsconfig", "webpack", "vite.config", "rollup.config"}

# Source code file extensions
SOURCE_EXTENSIONS = {
    ".py", ".ts", ".js", ".jsx", ".tsx", ".rs", ".go", ".c", ".cpp", ".h", ".hpp",
    ".java", ".kt", ".rb", ".cs", ".php", ".swift", ".m", ".sh", ".bash", ".ps1"
}

# Documentation extensions and filenames
DOC_EXTENSIONS = {".md", ".rst", ".txt", ".adoc"}
DOC_FILENAMES = {"readme", "license", "contributing", "changelog", "code_of_conduct"}

# Sensitive keywords indicating security or authorization boundary
SECURITY_KEYWORDS = {"auth", "token", "credential", "secret", "password", "crypto", "permission", "rbac", "oauth"}


class ChangeAnalyzer:
    """Analyzes a ChangeSummary to classify files and flag potential risks."""

    def categorize_file(self, rel_path: str) -> FileCategory:
        """Determine semantic category of a file based on path and name."""
        norm_path = rel_path.replace("\\", "/").lower()
        filename = os.path.basename(norm_path)
        base_name, ext = os.path.splitext(filename)

        # 1. Security-sensitive files
        if norm_path.startswith(".github/workflows/") or any(kw in norm_path for kw in SECURITY_KEYWORDS):
            return FileCategory.SECURITY_SENSITIVE

        # 2. Test files
        is_test_dir = "/tests/" in norm_path or norm_path.startswith("tests/") or "/test/" in norm_path or norm_path.startswith("test/")
        is_test_file = (
            filename.startswith("test_")
            or filename.endswith("_test.py")
            or ".spec." in filename
            or ".test." in filename
            or filename.endswith("_test.go")
        )
        if is_test_dir or is_test_file:
            return FileCategory.TEST

        # 3. Dependency manifests
        if filename in DEPENDENCY_FILENAMES or filename.startswith("requirements"):
            return FileCategory.DEPENDENCY

        # 4. Documentation
        if ext in DOC_EXTENSIONS or base_name in DOC_FILENAMES:
            return FileCategory.DOCUMENTATION

        # 5. Configuration files
        if (
            norm_path.startswith(".github/")
            or filename.startswith(".")
            or any(sub in filename for sub in CONFIG_SUBSTRINGS)
            or ext in CONFIG_EXTENSIONS
        ):
            return FileCategory.CONFIGURATION

        # 6. Source code
        if ext in SOURCE_EXTENSIONS:
            return FileCategory.SOURCE

        return FileCategory.OTHER

    def analyze(self, summary: ChangeSummary) -> Tuple[ChangeSummary, List[RiskWarning]]:
        """
        Populate categories for each file in the summary, compute category totals,
        and generate risk warnings.
        """
        categories_count: dict[str, int] = {}
        warnings: List[RiskWarning] = []

        source_files: List[str] = []
        test_files: List[str] = []
        dep_files: List[str] = []
        security_files: List[str] = []
        ci_files: List[str] = []

        for f in summary.files:
            category = self.categorize_file(f.path)
            f.category = category
            cat_name = category.value
            categories_count[cat_name] = categories_count.get(cat_name, 0) + 1

            if category == FileCategory.SOURCE:
                source_files.append(f.path)
            elif category == FileCategory.TEST:
                test_files.append(f.path)
            elif category == FileCategory.DEPENDENCY:
                dep_files.append(f.path)
            elif category == FileCategory.SECURITY_SENSITIVE:
                security_files.append(f.path)

            if f.path.replace("\\", "/").startswith(".github/workflows/"):
                ci_files.append(f.path)

        summary.categories_count = categories_count

        # Detection 1: Untested code changes (Missing Work)
        if source_files and not test_files:
            warnings.append(
                RiskWarning(
                    code="UNTESTED_SOURCE_CHANGE",
                    severity=RiskSeverity.WARNING,
                    message=f"{len(source_files)} source file(s) modified/added without accompanying test changes.",
                    related_files=source_files[:10],
                )
            )

        # Detection 2: Dependency changes
        if dep_files:
            warnings.append(
                RiskWarning(
                    code="DEPENDENCY_MODIFIED",
                    severity=RiskSeverity.INFO,
                    message=f"Dependency manifests/lockfiles modified ({', '.join(dep_files)}). Verify supply-chain safety.",
                    related_files=dep_files,
                )
            )

        # Detection 3: CI/CD workflow changes
        if ci_files:
            warnings.append(
                RiskWarning(
                    code="CI_WORKFLOW_MODIFIED",
                    severity=RiskSeverity.WARNING,
                    message=f"CI/CD automation files modified ({', '.join(ci_files)}). Ensure workflow permissions are safe.",
                    related_files=ci_files,
                )
            )

        # Detection 4: Security-sensitive changes
        if security_files:
            warnings.append(
                RiskWarning(
                    code="SECURITY_SENSITIVE_MODIFIED",
                    severity=RiskSeverity.HIGH,
                    message=f"Security-sensitive files modified ({', '.join(security_files)}). Requires strict manual review.",
                    related_files=security_files,
                )
            )

        # Detection 5: Excessively large diff (Drift/Blast radius)
        if summary.total_files > 25 or (summary.total_additions + summary.total_deletions) > 600:
            warnings.append(
                RiskWarning(
                    code="LARGE_DIFF",
                    severity=RiskSeverity.WARNING,
                    message=(
                        f"Large change detected: {summary.total_files} files, "
                        f"+{summary.total_additions}/-{summary.total_deletions} lines. High blast radius."
                    ),
                    related_files=[f.path for f in summary.files[:10]],
                )
            )

        return summary, warnings
