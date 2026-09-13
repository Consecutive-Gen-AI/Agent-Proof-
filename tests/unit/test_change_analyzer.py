"""Unit tests for static change analyzer and risk heuristics."""

from agentproof.analyzer.change import ChangeAnalyzer
from agentproof.core.models import (
    ChangeSummary,
    FileCategory,
    FileChange,
    FileStatus,
    RiskSeverity,
)


def test_categorize_files():
    analyzer = ChangeAnalyzer()

    assert analyzer.categorize_file("src/app.py") == FileCategory.SOURCE
    assert analyzer.categorize_file("tests/test_app.py") == FileCategory.TEST
    assert analyzer.categorize_file("frontend/component.test.ts") == FileCategory.TEST
    assert analyzer.categorize_file("package.json") == FileCategory.DEPENDENCY
    assert analyzer.categorize_file("pyproject.toml") == FileCategory.DEPENDENCY
    assert analyzer.categorize_file("requirements.txt") == FileCategory.DEPENDENCY
    assert analyzer.categorize_file("README.md") == FileCategory.DOCUMENTATION
    assert analyzer.categorize_file(".github/workflows/ci.yml") == FileCategory.SECURITY_SENSITIVE
    assert analyzer.categorize_file("src/auth/tokens.py") == FileCategory.SECURITY_SENSITIVE
    assert analyzer.categorize_file("docker-compose.yml") == FileCategory.CONFIGURATION


def test_untested_source_change_warning():
    analyzer = ChangeAnalyzer()
    summary = ChangeSummary(
        total_files=1,
        total_additions=10,
        total_deletions=0,
        files=[
            FileChange(path="src/service.py", status=FileStatus.ADDED, additions=10, deletions=0)
        ],
    )
    summary, warnings = analyzer.analyze(summary)
    codes = [w.code for w in warnings]
    assert "UNTESTED_SOURCE_CHANGE" in codes


def test_no_untested_warning_when_tests_included():
    analyzer = ChangeAnalyzer()
    summary = ChangeSummary(
        total_files=2,
        total_additions=20,
        total_deletions=0,
        files=[
            FileChange(path="src/service.py", status=FileStatus.MODIFIED, additions=10, deletions=0),
            FileChange(path="tests/test_service.py", status=FileStatus.MODIFIED, additions=10, deletions=0),
        ],
    )
    summary, warnings = analyzer.analyze(summary)
    codes = [w.code for w in warnings]
    assert "UNTESTED_SOURCE_CHANGE" not in codes


def test_security_sensitive_warning():
    analyzer = ChangeAnalyzer()
    summary = ChangeSummary(
        total_files=1,
        total_additions=5,
        total_deletions=0,
        files=[
            FileChange(path="src/auth_handler.py", status=FileStatus.MODIFIED, additions=5, deletions=0)
        ],
    )
    summary, warnings = analyzer.analyze(summary)
    codes = [w.code for w in warnings]
    assert "SECURITY_SENSITIVE_MODIFIED" in codes
    assert any(w.severity == RiskSeverity.HIGH for w in warnings)


def test_large_diff_warning():
    analyzer = ChangeAnalyzer()
    files = [
        FileChange(path=f"file_{i}.txt", status=FileStatus.MODIFIED, additions=25, deletions=5)
        for i in range(30)
    ]
    summary = ChangeSummary(
        total_files=30,
        total_additions=750,
        total_deletions=150,
        files=files,
    )
    summary, warnings = analyzer.analyze(summary)
    codes = [w.code for w in warnings]
    assert "LARGE_DIFF" in codes
