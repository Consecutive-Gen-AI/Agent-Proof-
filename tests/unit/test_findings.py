"""Unit tests for expanded V2 risk findings."""

from agentproof.analyzer.change import ChangeAnalyzer
from agentproof.core.models import (
    ChangeSummary,
    FileCategory,
    FileChange,
    FileStatus,
    RiskSeverity,
)


def test_finding_tests_reduced():
    analyzer = ChangeAnalyzer()
    summary = ChangeSummary(
        total_files=1,
        total_additions=2,
        total_deletions=40,
        files=[
            FileChange(
                path="tests/test_core.py",
                status=FileStatus.MODIFIED,
                additions=2,
                deletions=40,
                category=FileCategory.TEST,
            )
        ],
    )
    _, findings = analyzer.analyze(summary)
    finding = next((f for f in findings if f.code == "TESTS_REDUCED"), None)
    assert finding is not None
    assert finding.severity == RiskSeverity.WARNING
    assert "reduced" in finding.what_was_detected.lower()
    assert len(finding.why_it_matters) > 0
    assert len(finding.evidence) > 0


def test_finding_api_surface_modified():
    analyzer = ChangeAnalyzer()
    summary = ChangeSummary(
        total_files=1,
        files=[
            FileChange(
                path="src/agentproof/__init__.py",
                status=FileStatus.MODIFIED,
                additions=5,
                deletions=0,
                category=FileCategory.SOURCE,
            )
        ],
    )
    _, findings = analyzer.analyze(summary)
    finding = next((f for f in findings if f.code == "API_SURFACE_MODIFIED"), None)
    assert finding is not None
    assert "public" in finding.what_was_detected.lower()
    assert len(finding.why_it_matters) > 0


def test_finding_important_file_renamed():
    analyzer = ChangeAnalyzer()
    summary = ChangeSummary(
        total_files=1,
        files=[
            FileChange(
                path="src/new_core.py",
                old_path="src/core.py",
                status=FileStatus.RENAMED,
                additions=0,
                deletions=0,
                category=FileCategory.SOURCE,
            )
        ],
    )
    _, findings = analyzer.analyze(summary)
    finding = next((f for f in findings if f.code == "IMPORTANT_FILE_DELETED_OR_RENAMED"), None)
    assert finding is not None
    assert any("src/core.py -> src/new_core.py" in ev for ev in finding.evidence)
