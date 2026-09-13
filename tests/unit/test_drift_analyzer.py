"""Unit tests for agent drift detection."""

from agentproof.core.models import (
    ChangeSummary,
    DriftLevel,
    FileCategory,
    FileChange,
    FileStatus,
    RiskSeverity,
)
from agentproof.drift.analyzer import DriftAnalyzer
from agentproof.task.context import TaskParser


def test_drift_clean_alignment():
    parser = TaskParser()
    task = parser.parse("Fix token expiration in auth session")
    analyzer = DriftAnalyzer()

    summary = ChangeSummary(
        total_files=2,
        files=[
            FileChange(
                path="src/auth/session.py",
                status=FileStatus.MODIFIED,
                category=FileCategory.SOURCE,
            ),
            FileChange(
                path="tests/test_session.py",
                status=FileStatus.MODIFIED,
                category=FileCategory.TEST,
            ),
        ],
    )

    report = analyzer.analyze(summary, task)
    assert report.drift_level == DriftLevel.NONE
    assert len(report.unexpected_files) == 0
    assert "session.py" in report.aligned_files[0]


def test_drift_detected_on_unrelated_files():
    parser = TaskParser()
    task = parser.parse("Fix authentication token expiration")
    analyzer = DriftAnalyzer()

    summary = ChangeSummary(
        total_files=2,
        files=[
            FileChange(
                path="src/auth/token.py",
                status=FileStatus.MODIFIED,
                category=FileCategory.SOURCE,
            ),
            FileChange(
                path="deployment/docker-compose.yml",
                status=FileStatus.MODIFIED,
                category=FileCategory.CONFIGURATION,
            ),
        ],
    )

    report = analyzer.analyze(summary, task)
    assert report.drift_level in (DriftLevel.MEDIUM, DriftLevel.HIGH)
    assert "deployment/docker-compose.yml" in report.unexpected_files
    assert len(report.findings) >= 1

    finding = report.findings[0]
    assert finding.file_path == "deployment/docker-compose.yml"
    assert "docker-compose.yml" in finding.what_was_detected
    assert len(finding.why_it_was_considered_drift) > 0


def test_drift_when_no_task_provided():
    analyzer = DriftAnalyzer()
    summary = ChangeSummary(
        total_files=1,
        files=[FileChange(path="src/main.py", status=FileStatus.MODIFIED)],
    )

    report = analyzer.analyze(summary, task=None)
    assert report.drift_level == DriftLevel.UNKNOWN
    assert "No task context" in report.summary


def test_drift_on_clean_repository():
    parser = TaskParser()
    task = parser.parse("Implement something")
    analyzer = DriftAnalyzer()
    summary = ChangeSummary(total_files=0)

    report = analyzer.analyze(summary, task)
    assert report.drift_level == DriftLevel.NONE
    assert len(report.unexpected_files) == 0
