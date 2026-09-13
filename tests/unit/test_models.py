"""Unit tests for domain models and serialization."""

from agentproof.core.models import (
    ChangeSummary,
    CheckCategory,
    CheckResult,
    CheckStatus,
    FileCategory,
    FileChange,
    FileStatus,
    RiskSeverity,
    RiskWarning,
    Verdict,
    VerificationReport,
)


def test_file_change_serialization():
    fc = FileChange(
        path="src/agentproof/core.py",
        status=FileStatus.MODIFIED,
        additions=12,
        deletions=3,
        category=FileCategory.SOURCE,
        patch_snippet="@@ -1,3 +1,12 @@",
    )
    d = fc.to_dict()
    assert d["path"] == "src/agentproof/core.py"
    assert d["status"] == "MODIFIED"
    assert d["additions"] == 12
    assert d["deletions"] == 3
    assert d["category"] == "SOURCE"

    restored = FileChange.from_dict(d)
    assert restored.path == fc.path
    assert restored.status == fc.status
    assert restored.additions == fc.additions
    assert restored.deletions == fc.deletions
    assert restored.category == fc.category
    assert restored.patch_snippet == fc.patch_snippet


def test_change_summary_serialization():
    fc = FileChange(path="test.py", status=FileStatus.ADDED, additions=5, deletions=0)
    cs = ChangeSummary(
        total_files=1,
        total_additions=5,
        total_deletions=0,
        file_types={".py": 1},
        categories_count={"TEST": 1},
        files=[fc],
    )
    d = cs.to_dict()
    assert d["total_files"] == 1
    assert d["file_types"] == {".py": 1}

    restored = ChangeSummary.from_dict(d)
    assert restored.total_files == 1
    assert len(restored.files) == 1
    assert restored.files[0].path == "test.py"


def test_check_result_serialization():
    cr = CheckResult(
        name="pytest",
        category=CheckCategory.TEST,
        command=["python", "-m", "pytest"],
        status=CheckStatus.PASS,
        exit_code=0,
        duration_ms=150,
        stdout="1 passed",
        stderr="",
        timestamp="2026-09-13T12:00:00Z",
    )
    d = cr.to_dict()
    assert d["name"] == "pytest"
    assert d["status"] == "PASS"
    assert d["exit_code"] == 0

    restored = CheckResult.from_dict(d)
    assert restored.name == cr.name
    assert restored.status == cr.status
    assert restored.duration_ms == 150


def test_risk_warning_serialization():
    rw = RiskWarning(
        code="UNTESTED_CHANGE",
        severity=RiskSeverity.WARNING,
        message="Source changed with no tests",
        related_files=["app.py"],
    )
    d = rw.to_dict()
    assert d["code"] == "UNTESTED_CHANGE"
    assert d["severity"] == "WARNING"

    restored = RiskWarning.from_dict(d)
    assert restored.code == rw.code
    assert restored.related_files == ["app.py"]


def test_verification_report_round_trip():
    report = VerificationReport(
        schema_version="1.0.0",
        target_dir="/tmp/repo",
        git_branch="feature/auth",
        git_commit="abcdef123456",
        change_summary=ChangeSummary(total_files=0),
        checks=[],
        warnings=[],
        verdict=Verdict.VERIFIED,
        reasoning="All checks passed clean",
        timestamp="2026-09-13T12:00:00Z",
    )
    d = report.to_dict()
    assert d["verdict"] == "VERIFIED"
    assert d["git_branch"] == "feature/auth"

    restored = VerificationReport.from_dict(d)
    assert restored.verdict == Verdict.VERIFIED
    assert restored.reasoning == report.reasoning
