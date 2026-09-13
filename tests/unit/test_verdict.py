"""Unit tests for verdict evaluation logic."""

from agentproof.core.models import (
    CheckCategory,
    CheckResult,
    CheckStatus,
    RiskSeverity,
    RiskWarning,
    Verdict,
)
from agentproof.core.verdict import evaluate_verdict


def _make_check(name: str, status: CheckStatus, category: CheckCategory = CheckCategory.TEST) -> CheckResult:
    return CheckResult(
        name=name,
        category=category,
        command=[name],
        status=status,
        exit_code=0 if status == CheckStatus.PASS else 1,
        duration_ms=10,
    )


def test_verdict_failed_when_any_check_fails():
    checks = [
        _make_check("pytest", CheckStatus.FAIL),
        _make_check("ruff", CheckStatus.PASS, CheckCategory.LINT),
    ]
    verdict, reasoning = evaluate_verdict(checks, [])
    assert verdict == Verdict.FAILED
    assert "pytest" in reasoning


def test_verdict_failed_when_check_times_out():
    checks = [
        _make_check("pytest", CheckStatus.TIMEOUT),
    ]
    verdict, reasoning = evaluate_verdict(checks, [])
    assert verdict == Verdict.FAILED
    assert "timed out" in reasoning


def test_verdict_error_when_check_errors():
    checks = [
        _make_check("pytest", CheckStatus.ERROR),
    ]
    verdict, reasoning = evaluate_verdict(checks, [])
    assert verdict == Verdict.ERROR
    assert "Check execution error" in reasoning


def test_verdict_inconclusive_when_no_checks_run():
    checks = []
    verdict, reasoning = evaluate_verdict(checks, [])
    assert verdict == Verdict.INCONCLUSIVE
    assert "No verification checks" in reasoning


def test_verdict_inconclusive_when_checks_unavailable():
    checks = [
        _make_check("pytest", CheckStatus.UNAVAILABLE),
    ]
    verdict, reasoning = evaluate_verdict(checks, [])
    assert verdict == Verdict.INCONCLUSIVE
    assert "unavailable" in reasoning.lower()


def test_verdict_verified_when_all_pass_no_warnings():
    checks = [
        _make_check("pytest", CheckStatus.PASS, CheckCategory.TEST),
        _make_check("ruff", CheckStatus.PASS, CheckCategory.LINT),
    ]
    verdict, reasoning = evaluate_verdict(checks, [])
    assert verdict == Verdict.VERIFIED
    assert "All independent checks passed" in reasoning


def test_verdict_verified_with_warnings_on_risk():
    checks = [
        _make_check("pytest", CheckStatus.PASS),
    ]
    warnings = [
        RiskWarning(
            code="UNTESTED_SOURCE_CHANGE",
            severity=RiskSeverity.WARNING,
            message="No test files modified",
        )
    ]
    verdict, reasoning = evaluate_verdict(checks, warnings)
    assert verdict == Verdict.VERIFIED_WITH_WARNINGS
    assert "caution is required" in reasoning


def test_verdict_verified_with_warnings_on_high_risk():
    checks = [
        _make_check("pytest", CheckStatus.PASS),
    ]
    warnings = [
        RiskWarning(
            code="SECURITY_SENSITIVE_MODIFIED",
            severity=RiskSeverity.HIGH,
            message="Security file modified",
        )
    ]
    verdict, reasoning = evaluate_verdict(checks, warnings)
    assert verdict == Verdict.VERIFIED_WITH_WARNINGS
    assert "high-risk" in reasoning
