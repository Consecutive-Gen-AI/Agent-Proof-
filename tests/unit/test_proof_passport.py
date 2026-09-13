"""Unit tests for AgentProof Proof Passport."""

from agentproof.core.models import (
    ChangeSummary,
    CheckCategory,
    CheckResult,
    CheckStatus,
    DriftFinding,
    DriftLevel,
    DriftReport,
    FileCategory,
    FileChange,
    FileStatus,
    MissingWorkCategory,
    MissingWorkFinding,
    MissingWorkReport,
    RiskSeverity,
    RiskWarning,
    TaskContext,
    Verdict,
    VerificationReport,
)
from agentproof.passport.generator import PassportGenerator
from agentproof.passport.models import ProofPassport


def test_passport_generation_and_round_trip():
    task = TaskContext(
        raw_text="Fix authentication token expiration",
        inferred_scope="medium",
        expected_domains=["auth"],
    )
    change = ChangeSummary(
        total_files=2,
        total_additions=50,
        total_deletions=10,
        files=[
            FileChange(path="auth/token.py", status=FileStatus.MODIFIED, additions=40, deletions=5, category=FileCategory.SOURCE),
            FileChange(path="tests/test_token.py", status=FileStatus.MODIFIED, additions=10, deletions=5, category=FileCategory.TEST),
        ],
    )
    check = CheckResult(
        name="pytest",
        category=CheckCategory.TEST,
        command=["pytest"],
        status=CheckStatus.PASS,
        exit_code=0,
        duration_ms=450,
        output_summary="2 passed in 0.4s",
    )

    warning = RiskWarning(
        code="SECURITY_SENSITIVE_MODIFIED",
        severity=RiskSeverity.INFO,
        message="Security sensitive file modified",
        what_was_detected="Modified auth/token.py",
        why_it_matters="Token authentication logic modified",
    )
    report = VerificationReport(
        schema_version="1.2.0",
        target_dir="/mock/project",
        git_branch="feature/auth",
        git_commit="fedcba9876543210",
        task_context=task,
        change_summary=change,
        checks=[check],
        warnings=[warning],
        verdict=Verdict.VERIFIED_WITH_WARNINGS,
        reasoning="Checks passed with informational security finding.",
        timestamp="2026-09-13T12:30:00Z",
    )

    generator = PassportGenerator(report)
    passport = generator.generate()

    assert passport.metadata.schema_version == "1.0.0"
    assert passport.passport_id.startswith("pass-")
    assert passport.repository.branch == "feature/auth"
    assert passport.repository.commit == "fedcba9876543210"
    assert passport.task is not None
    assert passport.task.description == "Fix authentication token expiration"
    assert passport.change.files_count == 2
    assert passport.change.additions == 50
    assert len(passport.checks) == 1
    assert passport.checks[0].name == "pytest"
    assert passport.checks[0].status == "PASS"
    assert passport.verdict.status == "VERIFIED_WITH_WARNINGS"
    assert len(passport.metadata.passport_integrity_hash) == 64

    # JSON Round-Trip
    json_str = passport.to_json()
    reloaded = ProofPassport.from_json(json_str)

    assert reloaded.passport_id == passport.passport_id
    assert reloaded.repository.target_dir == passport.repository.target_dir
    assert reloaded.change.files_count == 2
    assert reloaded.verdict.status == "VERIFIED_WITH_WARNINGS"
    assert len(reloaded.evidence) >= 1
    assert reloaded.metadata.passport_integrity_hash == passport.metadata.passport_integrity_hash


def test_passport_clean_repository():
    report = VerificationReport(
        schema_version="1.2.0",
        target_dir="/clean/repo",
        git_branch="main",
        git_commit="0123456789abcdef",
        change_summary=ChangeSummary(),
        checks=[CheckResult(name="pytest", category=CheckCategory.TEST, command=["pytest"], status=CheckStatus.PASS, exit_code=0, duration_ms=20)],
        verdict=Verdict.VERIFIED,

        reasoning="Working tree is clean. All checks passed.",
        timestamp="2026-09-13T12:35:00Z",
    )

    passport = PassportGenerator(report).generate()
    assert passport.change.files_count == 0
    assert passport.verdict.status == "VERIFIED"
    assert len(passport.findings) == 0


def test_passport_captures_drift_and_missing_work():
    drift = DriftReport(
        drift_level=DriftLevel.HIGH,
        unexpected_files=["frontend/theme.css"],
        findings=[
            DriftFinding(
                file_path="frontend/theme.css",
                drift_level=DriftLevel.HIGH,
                what_was_detected="Modified frontend/theme.css",
                why_it_was_considered_drift="No relationship to backend auth",
                severity=RiskSeverity.WARNING,
            )
        ],
    )
    missing = MissingWorkReport(
        findings_count=1,
        findings=[
            MissingWorkFinding(
                code="MISSING_CLI_TEST",
                category=MissingWorkCategory.CLI,
                title="Missing CLI Test",
                what_was_detected="CLI flag added without test",
                why_it_matters="Command-line flags need regression coverage",
                severity=RiskSeverity.WARNING,
            )
        ],
    )
    report = VerificationReport(
        schema_version="1.2.0",
        target_dir="/drift/repo",
        drift=drift,
        missing_work=missing,
        verdict=Verdict.VERIFIED_WITH_WARNINGS,
        reasoning="High drift and 1 missing work finding detected.",
        timestamp="2026-09-13T12:40:00Z",
    )

    passport = PassportGenerator(report).generate()
    assert passport.drift.level == "HIGH"
    assert passport.drift.unexpected_files_count == 1
    assert passport.missing_work.gaps_count == 1

    # Findings unified in passport
    finding_categories = [f.category for f in passport.findings]
    assert "DRIFT" in finding_categories
    assert "MISSING_WORK" in finding_categories
