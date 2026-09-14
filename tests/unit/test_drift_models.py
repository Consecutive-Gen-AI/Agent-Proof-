"""Unit tests for V3 domain models and serialization."""

from agentproof.core.models import (
    DriftFinding,
    DriftLevel,
    DriftReport,
    MissingWorkCategory,
    MissingWorkFinding,
    MissingWorkReport,
    RiskSeverity,
    TaskContext,
    Verdict,
    VerificationReport,
)


def test_task_context_serialization():
    ctx = TaskContext(
        raw_text="Fix authentication token expiration",
        normalized_keywords=["authentication", "token", "expiration"],
        referenced_paths=["auth/token.py"],
        referenced_symbols=["TokenValidator"],
        expected_domains=["auth"],
        inferred_scope="NARROW",
        confidence="HIGH",
    )
    d = ctx.to_dict()
    assert d["raw_text"] == "Fix authentication token expiration"
    assert d["inferred_scope"] == "NARROW"
    assert d["confidence"] == "HIGH"

    restored = TaskContext.from_dict(d)
    assert restored.raw_text == ctx.raw_text
    assert restored.normalized_keywords == ctx.normalized_keywords
    assert restored.referenced_paths == ["auth/token.py"]


def test_drift_report_serialization():
    finding = DriftFinding(
        file_path="docker-compose.yml",
        drift_level=DriftLevel.HIGH,
        what_was_detected="Unexpected file modified",
        why_it_was_considered_drift="No relationship to task",
        supporting_evidence=["Evidence line 1"],
        severity=RiskSeverity.HIGH,
        confidence="HIGH",
    )
    report = DriftReport(
        drift_level=DriftLevel.HIGH,
        confidence="HIGH",
        aligned_files=["auth/token.py"],
        unexpected_files=["docker-compose.yml"],
        findings=[finding],
        summary="Drift detected",
    )
    d = report.to_dict()
    assert d["drift_level"] == "HIGH"
    assert len(d["findings"]) == 1

    restored = DriftReport.from_dict(d)
    assert restored.drift_level == DriftLevel.HIGH
    assert len(restored.findings) == 1
    assert restored.findings[0].file_path == "docker-compose.yml"


def test_missing_work_report_serialization():
    finding = MissingWorkFinding(
        code="MISSING_DATABASE_MIGRATION",
        category=MissingWorkCategory.MIGRATION,
        title="Missing schema migration",
        what_was_detected="Model modified without migration",
        why_it_matters="Runtime schema mismatch",
        evidence=["Model: user.py"],
        affected_files=["user.py"],
        severity=RiskSeverity.HIGH,
    )
    report = MissingWorkReport(
        findings_count=1,
        findings=[finding],
        summary="1 gap detected",
    )
    d = report.to_dict()
    assert d["findings_count"] == 1
    assert d["findings"][0]["code"] == "MISSING_DATABASE_MIGRATION"

    restored = MissingWorkReport.from_dict(d)
    assert restored.findings_count == 1
    assert restored.findings[0].code == "MISSING_DATABASE_MIGRATION"


def test_verification_report_v3_serialization():
    task = TaskContext(raw_text="Fix auth")
    drift = DriftReport(drift_level=DriftLevel.NONE, summary="Clean")
    missing = MissingWorkReport(findings_count=0, summary="No gaps")

    report = VerificationReport(
        schema_version="1.2.0",
        target_dir="/path/to/repo",
        task_context=task,
        drift=drift,
        missing_work=missing,
        verdict=Verdict.VERIFIED,
    )
    d = report.to_dict()
    assert d["schema_version"] == "1.2.0"
    assert d["task_context"]["raw_text"] == "Fix auth"
    assert d["drift"]["drift_level"] == "NONE"
    assert d["missing_work"]["findings_count"] == 0

    restored = VerificationReport.from_dict(d)
    assert restored.schema_version == "1.2.0"
    assert restored.task_context is not None
    assert restored.task_context.raw_text == "Fix auth"
    assert restored.drift is not None
    assert restored.drift.drift_level == DriftLevel.NONE
