"""Deterministic Task-to-Change Drift Analyzer."""

from __future__ import annotations

import os
from typing import List, Optional, Set, Tuple

from agentproof.core.models import (
    ChangeImpact,
    ChangeSummary,
    DriftFinding,
    DriftLevel,
    DriftReport,
    FileCategory,
    FileChange,
    RiskSeverity,
    TaskContext,
)


class DriftAnalyzer:
    """Analyzes whether changes remain within intended task boundaries or drift into unrelated files."""

    def __init__(self) -> None:
        pass

    def _file_matches_task(
        self,
        file_change: FileChange,
        task: TaskContext,
        impact: Optional[ChangeImpact],
        all_changed_paths: Set[str],
    ) -> Tuple[bool, str]:
        """
        Determine if a changed file is aligned with the task, either directly
        or through an impact/test relationship.

        Returns (is_aligned, reason).
        """
        norm_path = file_change.path.replace("\\", "/").lower()
        base_name = os.path.splitext(os.path.basename(norm_path))[0]

        # 1. Direct match: path explicitly referenced in task text
        for ref_p in task.referenced_paths:
            ref_norm = ref_p.lower()
            if ref_norm in norm_path or norm_path in ref_norm:
                return True, f"File explicitly referenced in task ('{ref_p}')"

        # 2. Direct match: keywords appear in file path
        matched_kws = [kw for kw in task.normalized_keywords if kw in norm_path]
        if matched_kws:
            return True, f"Path contains task keywords ({', '.join(matched_kws)})"

        # 3. Direct match: changed symbols match task keywords or referenced symbols
        for sym in file_change.changed_symbols:
            sym_lower = sym.name.lower()
            for ref_s in task.referenced_symbols:
                if ref_s.lower() in sym_lower:
                    return True, f"Changed symbol '{sym.name}' matches referenced task symbol '{ref_s}'"
            for kw in task.normalized_keywords:
                if kw in sym_lower:
                    return True, f"Changed symbol '{sym.name}' matches task keyword '{kw}'"

        # 4. Domain match: domain keyword in path or categories
        if "auth" in task.expected_domains and file_change.category == FileCategory.SECURITY_SENSITIVE:
            return True, "File is security/auth-sensitive, matching task domain 'auth'"
        if "cli" in task.expected_domains and ("cli" in norm_path or "main" in base_name):
            return True, "File matches CLI task domain"
        if "database" in task.expected_domains and ("model" in norm_path or "schema" in norm_path or "migration" in norm_path):
            return True, "File matches database/model task domain"
        if "ui" in task.expected_domains and ("frontend" in norm_path or "ui" in norm_path or "css" in norm_path):
            return True, "File matches UI/frontend task domain"
        if "deployment" in task.expected_domains and ("docker" in norm_path or ".github" in norm_path):
            return True, "File matches deployment task domain"

        # 5. Impact-aligned: is it a test for one of the directly matched files?
        if file_change.category == FileCategory.TEST:
            # Check if this test tests any of the other changed files
            for other_p in all_changed_paths:
                other_base = os.path.splitext(os.path.basename(other_p.lower()))[0]
                if other_base and other_base in norm_path:
                    return True, f"Test suite for modified file '{other_p}'"

        # 6. Impact-aligned: is it in the impact graph?
        if impact:
            for imp_test in impact.impacted_test_files:
                if imp_test.file_path.lower() == norm_path:
                    return True, f"Related test identified via impact analysis ({imp_test.description})"
            for imp_src in impact.impacted_source_files:
                if imp_src.file_path.lower() == norm_path:
                    return True, f"Caller/dependent module identified via impact analysis"

        # 7. Minor repository infrastructure files that are naturally incidental
        if norm_path in (".gitignore", "readme.md") and file_change.additions + file_change.deletions < 15:
            return True, "Incidental minor documentation or gitignore update"

        return False, "No detected relationship to task keywords, referenced symbols, domain, or impact graph."

    def analyze(
        self,
        summary: ChangeSummary,
        task: Optional[TaskContext],
        impact: Optional[ChangeImpact] = None,
    ) -> DriftReport:
        """Evaluate task-to-change drift."""
        if not task or not task.raw_text.strip():
            return DriftReport(
                task_context=None,
                drift_level=DriftLevel.UNKNOWN,
                confidence="LOW",
                aligned_files=[f.path for f in summary.files],
                unexpected_files=[],
                findings=[],
                summary="No task context was provided to evaluate scope drift (use --task to enable).",
            )

        if summary.total_files == 0:
            return DriftReport(
                task_context=task,
                drift_level=DriftLevel.NONE,
                confidence="HIGH",
                aligned_files=[],
                unexpected_files=[],
                findings=[],
                summary="Working tree is clean. Zero scope drift.",
            )

        all_paths = {f.path for f in summary.files}
        aligned_files: List[str] = []
        unexpected_files: List[str] = []
        findings: List[DriftFinding] = []

        for f in summary.files:
            is_aligned, reason = self._file_matches_task(f, task, impact, all_paths)
            if is_aligned:
                aligned_files.append(f.path)
            else:
                unexpected_files.append(f.path)
                # Determine severity: code/infra = HIGH or WARNING, docs = INFO
                if f.category in (FileCategory.SOURCE, FileCategory.SECURITY_SENSITIVE):
                    sev = RiskSeverity.HIGH
                elif f.category in (FileCategory.CONFIGURATION, FileCategory.DEPENDENCY):
                    sev = RiskSeverity.WARNING
                else:
                    sev = RiskSeverity.INFO

                findings.append(
                    DriftFinding(
                        file_path=f.path,
                        drift_level=DriftLevel.HIGH if sev == RiskSeverity.HIGH else DriftLevel.MEDIUM,
                        what_was_detected=f"Unexpected file modification: '{f.path}' (+{f.additions}/-{f.deletions}).",
                        why_it_was_considered_drift=f"No detected alignment with requested task '{task.raw_text}'. {reason}",
                        supporting_evidence=[
                            f"Task domains: {', '.join(task.expected_domains) or 'general'}",
                            f"Task keywords: {', '.join(task.normalized_keywords[:6]) or 'none'}",
                            f"File category: {f.category.value}",
                            reason,
                        ],
                        severity=sev,
                        confidence=task.confidence,
                    )
                )

        # Compute overall drift rating
        if not unexpected_files:
            drift_level = DriftLevel.NONE
            summary_msg = f"Change aligns cleanly with task '{task.raw_text}' across all {len(aligned_files)} modified file(s)."
        elif len(unexpected_files) == 1 and any(findings[0].severity == RiskSeverity.INFO for _ in [1]):
            drift_level = DriftLevel.LOW
            summary_msg = f"Minor scope drift detected in {len(unexpected_files)} incidental file(s)."
        elif any(f.severity == RiskSeverity.HIGH for f in findings) or len(unexpected_files) >= 2:
            drift_level = DriftLevel.HIGH
            summary_msg = (
                f"Significant scope drift detected: {len(unexpected_files)} file(s) modified outside expected "
                f"scope for task '{task.raw_text}'."
            )
        else:
            drift_level = DriftLevel.MEDIUM
            summary_msg = (
                f"Moderate scope drift detected: {len(unexpected_files)} unexpected file(s) modified."
            )

        return DriftReport(
            task_context=task,
            drift_level=drift_level,
            confidence=task.confidence,
            aligned_files=aligned_files,
            unexpected_files=unexpected_files,
            findings=findings,
            summary=summary_msg,
        )
