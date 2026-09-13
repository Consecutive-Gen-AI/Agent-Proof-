"""Unit tests for missing work and omission detection."""

from agentproof.core.models import (
    ChangeSummary,
    FileCategory,
    FileChange,
    FileStatus,
    MissingWorkCategory,
    RiskSeverity,
)
from agentproof.missing.analyzer import MissingWorkAnalyzer


def test_missing_database_migration():
    analyzer = MissingWorkAnalyzer()
    summary = ChangeSummary(
        total_files=1,
        files=[
            FileChange(
                path="src/models/user_account.py",
                status=FileStatus.MODIFIED,
                category=FileCategory.SOURCE,
                patch_snippet="class UserAccount(Base):\n    email = Column(String)\n",
            )
        ],
    )

    report = analyzer.analyze(summary)
    codes = [f.code for f in report.findings]
    assert "MISSING_DATABASE_MIGRATION" in codes

    finding = next(f for f in report.findings if f.code == "MISSING_DATABASE_MIGRATION")
    assert finding.severity == RiskSeverity.HIGH
    assert finding.category == MissingWorkCategory.MIGRATION
    assert len(finding.why_it_matters) > 0


def test_missing_cli_test():
    analyzer = MissingWorkAnalyzer()
    summary = ChangeSummary(
        total_files=1,
        files=[
            FileChange(
                path="src/agentproof/cli/main.py",
                status=FileStatus.MODIFIED,
                category=FileCategory.SOURCE,
            )
        ],
    )

    report = analyzer.analyze(summary)
    codes = [f.code for f in report.findings]
    assert "MISSING_CLI_TEST" in codes


def test_missing_lockfile_update():
    analyzer = MissingWorkAnalyzer()
    summary = ChangeSummary(
        total_files=1,
        files=[
            FileChange(
                path="pyproject.toml",
                status=FileStatus.MODIFIED,
                category=FileCategory.DEPENDENCY,
                patch_snippet="[tool.poetry.dependencies]\nrequests = '^2.28.0'\n",
            )
        ],
    )

    report = analyzer.analyze(summary)
    codes = [f.code for f in report.findings]
    assert "MISSING_LOCKFILE_UPDATE" in codes


def test_missing_security_validation():
    analyzer = MissingWorkAnalyzer()
    summary = ChangeSummary(
        total_files=1,
        files=[
            FileChange(
                path="src/auth/jwt_token.py",
                status=FileStatus.MODIFIED,
                category=FileCategory.SECURITY_SENSITIVE,
            )
        ],
    )

    report = analyzer.analyze(summary)
    codes = [f.code for f in report.findings]
    assert "MISSING_SECURITY_VALIDATION" in codes


def test_no_missing_work_on_complete_change():
    analyzer = MissingWorkAnalyzer()
    summary = ChangeSummary(
        total_files=2,
        files=[
            FileChange(
                path="src/calc.py",
                status=FileStatus.MODIFIED,
                category=FileCategory.SOURCE,
            ),
            FileChange(
                path="tests/test_calc.py",
                status=FileStatus.MODIFIED,
                category=FileCategory.TEST,
            ),
        ],
    )

    report = analyzer.analyze(summary)
    assert report.findings_count == 0
