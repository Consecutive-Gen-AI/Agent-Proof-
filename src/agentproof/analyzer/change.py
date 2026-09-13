"""Static change analyzer: file categorization, risk signals, and drift heuristics."""

from __future__ import annotations

import os
from typing import List, Tuple

from agentproof.core.models import (
    ChangeSummary,
    FileCategory,
    FileStatus,
    RiskFinding,
    RiskSeverity,
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
    """Analyzes a ChangeSummary to classify files and generate evidence-backed risk findings."""

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

    def analyze(self, summary: ChangeSummary) -> Tuple[ChangeSummary, List[RiskFinding]]:
        """
        Populate categories for each file in the summary, compute category totals,
        and generate evidence-backed risk findings.
        """
        categories_count: dict[str, int] = {}
        findings: List[RiskFinding] = []

        source_files: List[str] = []
        test_files: List[str] = []
        dep_files: List[str] = []
        config_files: List[str] = []
        security_files: List[str] = []
        ci_files: List[str] = []
        api_files: List[str] = []
        renamed_files: List[Tuple[str, str]] = []
        deleted_files: List[str] = []

        test_adds = 0
        test_dels = 0

        for f in summary.files:
            category = self.categorize_file(f.path)
            f.category = category
            cat_name = category.value
            categories_count[cat_name] = categories_count.get(cat_name, 0) + 1

            rel_p = f.path.replace("\\", "/")

            if category == FileCategory.SOURCE:
                source_files.append(rel_p)
                # Check for API surface modifications (e.g. __init__.py, public exports)
                if os.path.basename(rel_p) == "__init__.py" or "api" in rel_p.lower():
                    api_files.append(rel_p)
            elif category == FileCategory.TEST:
                test_files.append(rel_p)
                test_adds += f.additions
                test_dels += f.deletions
            elif category == FileCategory.DEPENDENCY:
                dep_files.append(rel_p)
            elif category == FileCategory.CONFIGURATION:
                config_files.append(rel_p)
            elif category == FileCategory.SECURITY_SENSITIVE:
                security_files.append(rel_p)

            if rel_p.startswith(".github/workflows/"):
                ci_files.append(rel_p)

            if f.status == FileStatus.RENAMED and f.old_path:
                renamed_files.append((f.old_path, rel_p))
            elif f.status == FileStatus.DELETED:
                deleted_files.append(rel_p)

        summary.categories_count = categories_count

        # 1. Detection: Untested code changes (Missing Work)
        if source_files and not test_files:
            findings.append(
                RiskFinding(
                    code="UNTESTED_SOURCE_CHANGE",
                    severity=RiskSeverity.WARNING,
                    message=f"{len(source_files)} source file(s) modified/added without accompanying test changes.",
                    related_files=source_files[:10],
                    what_was_detected=f"{len(source_files)} source file(s) modified without corresponding test file modifications.",
                    why_it_matters="Unverified code modifications carry a significantly higher defect rate and lack reproducible regression protection.",
                    evidence=[f"{p} (+{f.additions}/-{f.deletions})" for p, f in [(f.path, f) for f in summary.files if f.category == FileCategory.SOURCE][:5]],
                )
            )

        # 2. Detection: Tests reduced or removed
        deletedTests = [p for p in deleted_files if "test" in p.lower()]
        if deletedTests or (test_dels > 15 and test_dels > test_adds * 2):
            evidence_items = []
            if deletedTests:
                evidence_items.append(f"Deleted test files: {', '.join(deletedTests)}")
            evidence_items.append(f"Test lines changed: +{test_adds} / -{test_dels}")

            findings.append(
                RiskFinding(
                    code="TESTS_REDUCED",
                    severity=RiskSeverity.WARNING,
                    message=f"Test coverage was reduced (-{test_dels} test lines deleted vs +{test_adds} added).",
                    related_files=test_files + deletedTests,
                    what_was_detected="Test files were deleted or test lines were reduced substantially.",
                    why_it_matters="Removing tests weakens verification safety nets and may conceal regressions or boundary-condition failures.",
                    evidence=evidence_items,
                )
            )

        # 3. Detection: Public API surface modified
        if api_files:
            findings.append(
                RiskFinding(
                    code="API_SURFACE_MODIFIED",
                    severity=RiskSeverity.INFO,
                    message=f"Public API surface or module entrypoint altered ({', '.join(api_files[:5])}).",
                    related_files=api_files,
                    what_was_detected=f"Modifications detected in public module interfaces or API files: {', '.join(api_files[:3])}.",
                    why_it_matters="Changes to public interfaces can break downstream consumers and require semantic versioning considerations.",
                    evidence=[f"Modified {p}" for p in api_files[:5]],
                )
            )

        # 4. Detection: Renamed or deleted important files
        important_deleted_or_renamed = [
            p for p in deleted_files if p in DEPENDENCY_FILENAMES or p.endswith(".py") or p.endswith(".ts")
        ]
        if important_deleted_or_renamed or renamed_files:
            evidence_items = []
            if important_deleted_or_renamed:
                evidence_items.append(f"Deleted: {', '.join(important_deleted_or_renamed[:5])}")
            if renamed_files:
                evidence_items.append(f"Renamed: {', '.join(f'{old} -> {new}' for old, new in renamed_files[:5])}")

            findings.append(
                RiskFinding(
                    code="IMPORTANT_FILE_DELETED_OR_RENAMED",
                    severity=RiskSeverity.WARNING,
                    message=f"Core files were deleted or renamed ({len(important_deleted_or_renamed) + len(renamed_files)} file(s)).",
                    related_files=important_deleted_or_renamed + [new for _, new in renamed_files],
                    what_was_detected="Source files or dependency files were deleted or renamed.",
                    why_it_matters="Renaming or deleting modules can cause broken imports, broken builds, or stale references in dependent components.",
                    evidence=evidence_items,
                )
            )

        # 5. Detection: Dependency changes
        if dep_files:
            findings.append(
                RiskFinding(
                    code="DEPENDENCY_MODIFIED",
                    severity=RiskSeverity.INFO,
                    message=f"Dependency manifests/lockfiles modified ({', '.join(dep_files)}). Verify supply-chain safety.",
                    related_files=dep_files,
                    what_was_detected=f"Modifications detected in dependency declarations: {', '.join(dep_files)}.",
                    why_it_matters="Dependency modifications alter the software supply chain and can introduce transitive bugs or security advisories.",
                    evidence=[f"Manifest: {p}" for p in dep_files],
                )
            )

        # 6. Detection: CI/CD workflow changes
        if ci_files:
            findings.append(
                RiskFinding(
                    code="CI_WORKFLOW_MODIFIED",
                    severity=RiskSeverity.WARNING,
                    message=f"CI/CD automation files modified ({', '.join(ci_files)}). Ensure workflow permissions are safe.",
                    related_files=ci_files,
                    what_was_detected=f"CI/CD pipeline configuration altered: {', '.join(ci_files)}.",
                    why_it_matters="CI changes can alter testing gates, deploy keys, or automation permissions.",
                    evidence=[f"Workflow file: {p}" for p in ci_files],
                )
            )

        # 7. Detection: Security-sensitive changes
        if security_files:
            findings.append(
                RiskFinding(
                    code="SECURITY_SENSITIVE_MODIFIED",
                    severity=RiskSeverity.HIGH,
                    message=f"Security-sensitive files modified ({', '.join(security_files)}). Requires strict manual review.",
                    related_files=security_files,
                    what_was_detected=f"Changes detected in security/auth boundaries: {', '.join(security_files)}.",
                    why_it_matters="Flaws in authentication, token validation, or cryptography can lead to privilege escalation or unauthorized data access.",
                    evidence=[f"Security file: {p}" for p in security_files],
                )
            )

        # 8. Detection: Configuration files modified
        if config_files and not ci_files and not dep_files:
            findings.append(
                RiskFinding(
                    code="CONFIGURATION_MODIFIED",
                    severity=RiskSeverity.INFO,
                    message=f"Configuration files altered ({', '.join(config_files[:5])}).",
                    related_files=config_files,
                    what_was_detected=f"Project configuration files modified: {', '.join(config_files[:5])}.",
                    why_it_matters="Configuration changes affect runtime parameters, environment flags, and build tooling behaviors.",
                    evidence=[f"Config file: {p}" for p in config_files[:5]],
                )
            )

        # 9. Detection: Excessively large diff (Drift/Blast radius)
        if summary.total_files > 25 or (summary.total_additions + summary.total_deletions) > 600:
            findings.append(
                RiskFinding(
                    code="LARGE_DIFF",
                    severity=RiskSeverity.WARNING,
                    message=(
                        f"Large change detected: {summary.total_files} files, "
                        f"+{summary.total_additions}/-{summary.total_deletions} lines. High blast radius."
                    ),
                    related_files=[f.path for f in summary.files[:10]],
                    what_was_detected=f"Large diff with {summary.total_files} files and {summary.total_additions + summary.total_deletions} total line changes.",
                    why_it_matters="High-volume diffs have wider blast radius, higher defect probability, and are harder to audit exhaustively.",
                    evidence=[f"Files: {summary.total_files}", f"Additions: +{summary.total_additions}", f"Deletions: -{summary.total_deletions}"],
                )
            )

        return summary, findings
