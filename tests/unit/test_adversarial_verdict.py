"""Unit tests for Verdict synthesis with Adversarial Verification in V5."""

from agentproof.adversarial.models import (
    AdversarialFinding,
    AdversarialReport,
    AttackCase,
    AttackCategory,
    AttackResultStatus,
)
from agentproof.core.models import (
    CheckCategory,
    CheckResult,
    CheckStatus,
    RiskSeverity,
    Verdict,
)
from agentproof.core.verdict import evaluate_verdict


def _make_passing_check(name: str = "pytest") -> CheckResult:
    return CheckResult(
        name=name,
        category=CheckCategory.TEST,
        command=["pytest"],
        duration_ms=100,
        status=CheckStatus.PASS,
        exit_code=0,
    )


def test_verdict_blocked_when_adversarial_fails():
    normal_checks = [_make_passing_check()]
    case_fail = AttackCase(
        id="adv_fail_1",
        category=AttackCategory.BOUNDARY_VALUE,
        target_file="math.py",
        target_symbol="calc",
        rationale="Boundary check",
        execution_snippet="pass",
        expected_behavior="Rejected",
        result=AttackResultStatus.FAIL,
    )
    finding = AdversarialFinding(
        attack_case_id="adv_fail_1",
        category=AttackCategory.BOUNDARY_VALUE,
        severity=RiskSeverity.HIGH,
        target="calc",
        description="Boundary check failed",
        expected_behavior="Rejected",
        observed_behavior="Accepted",
        attack_case=case_fail,
    )

    adv_report = AdversarialReport(
        cases_generated=1,
        cases_passed=0,
        cases_failed=1,
        cases=[case_fail],
        findings=[finding],
    )

    verdict, reasoning = evaluate_verdict(
        checks=normal_checks,
        warnings=[],
        adversarial=adv_report,
    )

    assert verdict == Verdict.BLOCKED
    assert "Verification BLOCKED" in reasoning
    assert "BOUNDARY_VALUE on calc" in reasoning


def test_verdict_failed_takes_precedence_over_blocked():
    failing_checks = [
        CheckResult(
            name="pytest",
            category=CheckCategory.TEST,
            command=["pytest"],
            duration_ms=100,
            status=CheckStatus.FAIL,
            exit_code=1,
        )
    ]
    adv_report = AdversarialReport(
        cases_generated=1,
        cases_failed=1,
        findings=[
            AdversarialFinding(
                attack_case_id="c1",
                category=AttackCategory.ERROR_PATH,
                severity=RiskSeverity.HIGH,
                target="fn",
                description="Error path not caught",
                expected_behavior="Catch",
                observed_behavior="Crash",
            )
        ],
    )

    verdict, reasoning = evaluate_verdict(
        checks=failing_checks,
        warnings=[],
        adversarial=adv_report,
    )

    assert verdict == Verdict.FAILED
    assert "Check(s) failed: pytest" in reasoning


def test_verdict_verified_with_adversarial_positive_note():
    normal_checks = [_make_passing_check()]
    adv_report = AdversarialReport(
        cases_generated=4,
        cases_passed=4,
        cases_failed=0,
    )

    verdict, reasoning = evaluate_verdict(
        checks=normal_checks,
        warnings=[],
        adversarial=adv_report,
    )

    assert verdict == Verdict.VERIFIED
    assert "adversarial checks passed (4 passed)" in reasoning
    assert "PROVEN CORRECT" not in reasoning  # Honest wording principle
