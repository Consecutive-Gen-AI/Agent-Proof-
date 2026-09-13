"""Unit tests for Change Impact Analysis."""

from pathlib import Path
from agentproof.core.models import (
    ChangeSummary,
    FileCategory,
    FileChange,
    FileStatus,
    SymbolChange,
    SymbolType,
)
from agentproof.impact.analyzer import ImpactAnalyzer


def test_impact_analysis_detects_callers_and_tests(tmp_path: Path):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()

    # Changed module
    service_file = src_dir / "user_service.py"
    service_file.write_text("class UserService:\n    pass\n", encoding="utf-8")

    # Dependent source caller
    api_file = src_dir / "api.py"
    api_file.write_text("from user_service import UserService\n", encoding="utf-8")

    # Test file
    test_file = tests_dir / "test_user_service.py"
    test_file.write_text("from user_service import UserService\ndef test_user(): pass\n", encoding="utf-8")

    analyzer = ImpactAnalyzer(tmp_path)
    summary = ChangeSummary(
        total_files=1,
        files=[
            FileChange(
                path="src/user_service.py",
                status=FileStatus.MODIFIED,
                category=FileCategory.SOURCE,
                changed_symbols=[
                    SymbolChange(name="UserService", symbol_type=SymbolType.CLASS, file_path="src/user_service.py")
                ],
            )
        ],
    )

    impact = analyzer.analyze(summary)
    assert "user_service" in impact.changed_modules

    # Check that api.py is marked as an impacted caller
    impacted_src = [c.file_path for c in impact.impacted_source_files]
    assert any("api.py" in p for p in impacted_src)

    # Check that test_user_service.py is identified as related test suite
    impacted_tests = [c.file_path for c in impact.impacted_test_files]
    assert any("test_user_service.py" in p for p in impacted_tests)


def test_clean_summary_impact(tmp_path: Path):
    analyzer = ImpactAnalyzer(tmp_path)
    summary = ChangeSummary(total_files=0)
    impact = analyzer.analyze(summary)
    assert impact.total_impact_score == "LOW"
    assert len(impact.impacted_source_files) == 0
