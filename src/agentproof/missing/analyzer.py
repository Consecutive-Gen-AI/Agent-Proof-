"""Evidence-based Missing Work Analyzer detecting gaps, omitted tests, migrations, and validations."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import List, Optional, Set

from agentproof.core.models import (
    ChangeImpact,
    ChangeSummary,
    FileCategory,
    FileStatus,
    MissingWorkCategory,
    MissingWorkFinding,
    MissingWorkReport,
    RiskSeverity,
    TaskContext,
)

# Common manifest to lockfile associations
MANIFEST_TO_LOCKFILE = {
    "package.json": {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb"},
    "pyproject.toml": {"poetry.lock", "Pipfile.lock", "requirements.lock"},
    "Cargo.toml": {"Cargo.lock"},
    "go.mod": {"go.sum"},
    "Gemfile": {"Gemfile.lock"},
}

MIGRATION_INDICATORS = {"migration", "migrations", "alembic", "prisma/migrations", "db/migrate"}


class MissingWorkAnalyzer:
    """Detects essential engineering work omitted from the change set."""

    def analyze(
        self,
        summary: ChangeSummary,
        task: Optional[TaskContext] = None,
        impact: Optional[ChangeImpact] = None,
    ) -> MissingWorkReport:
        """Evaluate change summary and impact to detect omissions."""
        if summary.total_files == 0:
            return MissingWorkReport(findings_count=0, findings=[], summary="Clean working tree. No missing work detected.")

        findings: List[MissingWorkFinding] = []

        changed_paths = {f.path.replace("\\", "/").lower(): f for f in summary.files}
        source_files = [f for f in summary.files if f.category == FileCategory.SOURCE]
        test_files = [f for f in summary.files if f.category == FileCategory.TEST]
        security_files = [f for f in summary.files if f.category == FileCategory.SECURITY_SENSITIVE]
        dep_files = [f for f in summary.files if f.category == FileCategory.DEPENDENCY]

        # 1. Missing tests for changed source files
        if source_files and not test_files:
            findings.append(
                MissingWorkFinding(
                    code="MISSING_TESTS_FOR_CHANGE",
                    category=MissingWorkCategory.TESTS,
                    title="No tests modified or added for source code changes",
                    what_was_detected=f"{len(source_files)} source file(s) modified/added with zero corresponding test updates.",
                    why_it_matters="Code modifications without automated test coverage risk regressions and cannot be independently verified.",
                    evidence=[f"{f.path} (+{f.additions}/-{f.deletions})" for f in source_files[:5]],
                    affected_files=[f.path for f in source_files[:10]],
                    severity=RiskSeverity.WARNING,
                )
            )

        # 2. Missing database migration when models / schemas are modified
        model_files = [
            f for f in summary.files
            if any(k in f.path.lower() for k in ("models/", "schema/", "entities/", "database/models"))
            or (f.patch_snippet and any(k in f.patch_snippet for k in ("Column(", "Table(", "relationship(", "model ", "schema ")))
        ]
        has_migration = any(
            any(ind in p for ind in MIGRATION_INDICATORS)
            for p in changed_paths
        )
        if model_files and not has_migration:
            findings.append(
                MissingWorkFinding(
                    code="MISSING_DATABASE_MIGRATION",
                    category=MissingWorkCategory.MIGRATION,
                    title="Database model or schema modified without corresponding migration",
                    what_was_detected=f"Data models altered in {len(model_files)} file(s), but no schema migration was included.",
                    why_it_matters="Altering database entities without an automated migration script causes runtime schema mismatches and deployment failures.",
                    evidence=[f"Model file: {f.path}" for f in model_files[:4]],
                    affected_files=[f.path for f in model_files],
                    severity=RiskSeverity.HIGH,
                )
            )

        # 3. Missing CLI tests when CLI behavior is modified
        cli_files = [f for f in summary.files if "cli/" in f.path.replace("\\", "/").lower() or "main.py" in f.path.lower()]
        cli_test_files = [f for f in test_files if "cli" in f.path.lower()]
        if cli_files and not cli_test_files:
            findings.append(
                MissingWorkFinding(
                    code="MISSING_CLI_TEST",
                    category=MissingWorkCategory.CLI,
                    title="CLI command or parser modified without corresponding CLI test update",
                    what_was_detected=f"CLI layer changed ({', '.join(f.path for f in cli_files[:3])}), but no CLI test suite was updated.",
                    why_it_matters="Command-line interface changes can break parameter parsing, flag defaults, or exit codes for scripts and users.",
                    evidence=[f"Modified CLI component: {f.path}" for f in cli_files[:4]],
                    affected_files=[f.path for f in cli_files],
                    severity=RiskSeverity.WARNING,
                )
            )

        # 4. Missing lockfile update when dependency manifest is modified in a lockfile-managed project
        for manifest, lockfiles in MANIFEST_TO_LOCKFILE.items():
            manifest_in_change = any(os.path.basename(p) == manifest for p in changed_paths)
            lockfile_in_change = any(os.path.basename(p) in lockfiles for p in changed_paths)

            # Evidence-based: only expect a lockfile if one already exists in the repo
            # or manifest indicates tool usage (e.g. poetry in pyproject.toml)
            repo_uses_lockfile = any(
                (Path(f.path).parent / lf).name in lockfiles for f in summary.files for lf in lockfiles
            )
            if manifest_in_change and not lockfile_in_change:
                # Check if repository root or manifest specifies a lockfile tool
                full_manifest_p = next((f for f in summary.files if os.path.basename(f.path) == manifest), None)
                uses_poetry = full_manifest_p and full_manifest_p.patch_snippet and "tool.poetry" in full_manifest_p.patch_snippet

                if uses_poetry:
                    findings.append(
                        MissingWorkFinding(
                            code="MISSING_LOCKFILE_UPDATE",
                            category=MissingWorkCategory.DEPENDENCY,
                            title=f"Dependency manifest '{manifest}' changed without lockfile update",
                            what_was_detected=f"Poetry manifest '{manifest}' was modified, but expected lockfile ({', '.join(lockfiles)}) was not updated.",
                            why_it_matters="Unsynchronized lockfiles cause non-deterministic builds and CI environment divergence across developer machines.",
                            evidence=[f"Manifest modified: {manifest}", f"Expected one of: {', '.join(lockfiles)}"],
                            affected_files=[manifest],
                            severity=RiskSeverity.WARNING,
                        )
                    )

        # 5. Missing security validation tests when security-sensitive files are modified
        if security_files:
            security_tests = [
                f for f in test_files
                if any(kw in f.path.lower() for kw in ("auth", "token", "security", "permission", "crypto"))
            ]
            if not security_tests:
                findings.append(
                    MissingWorkFinding(
                        code="MISSING_SECURITY_VALIDATION",
                        category=MissingWorkCategory.SECURITY,
                        title="Security-sensitive code modified without security/auth regression tests",
                        what_was_detected=f"Changes in security-sensitive files ({', '.join(f.path for f in security_files[:3])}) lack corresponding security tests.",
                        why_it_matters="Security boundary modifications without automated regression tests introduce potential authorization bypasses or token flaws.",
                        evidence=[f"Security file: {f.path}" for f in security_files[:4]],
                        affected_files=[f.path for f in security_files],
                        severity=RiskSeverity.HIGH,
                    )
                )

        # 6. Missing error handling tests when new exceptions/errors are introduced
        error_introducing_files: List[str] = []
        for f in source_files:
            if f.patch_snippet and any(
                kw in f.patch_snippet for kw in ("raise ", "throw ", "try:", "except:", "catch ")
            ):
                error_introducing_files.append(f.path)

        if error_introducing_files:
            # Check if any test in test_files has assertions for exceptions
            has_error_tests = any(
                t.patch_snippet and any(kw in t.patch_snippet for kw in ("raises", "assert_raises", "toThrow", "fail("))
                for t in test_files
            )
            if not has_error_tests:
                findings.append(
                    MissingWorkFinding(
                        code="MISSING_ERROR_HANDLING_OR_TEST",
                        category=MissingWorkCategory.ERROR_HANDLING,
                        title="New error-raising or exception paths introduced without failure-path tests",
                        what_was_detected=f"Error-handling or exception paths added in {len(error_introducing_files)} file(s), but no negative/error tests were updated.",
                        why_it_matters="Error branches that are untested often fail with unhandled runtime crashes or invalid error messages in production.",
                        evidence=[f"File introducing error path: {p}" for p in error_introducing_files[:4]],
                        affected_files=error_introducing_files[:6],
                        severity=RiskSeverity.WARNING,
                    )
                )

        # 7. Removed behavior without test updates
        deleting_files = [f for f in source_files if f.deletions > 25 and f.deletions > f.additions * 1.5]
        test_dels = sum(t.deletions for t in test_files)
        if deleting_files and test_dels == 0:
            findings.append(
                MissingWorkFinding(
                    code="REMOVED_BEHAVIOR_WITHOUT_TEST_UPDATE",
                    category=MissingWorkCategory.TESTS,
                    title="Substantial code removed without updating test assertions",
                    what_was_detected=f"Significant lines removed from {len(deleting_files)} source file(s) with 0 test deletions or updates.",
                    why_it_matters="Deleting implementation code without test adjustments often leaves obsolete tests, stale fixtures, or untested dead interfaces.",
                    evidence=[f"{f.path} (-{f.deletions} lines)" for f in deleting_files[:4]],
                    affected_files=[f.path for f in deleting_files],
                    severity=RiskSeverity.INFO,
                )
            )

        summary_msg = (
            f"{len(findings)} potential gap(s) or missing work item(s) detected."
            if findings
            else "No missing work or verification gaps detected."
        )

        return MissingWorkReport(
            findings_count=len(findings),
            findings=findings,
            summary=summary_msg,
        )
