"""Unit tests for safe execution of adversarial test cases."""

from pathlib import Path
from agentproof.adversarial.models import (
    AttackCase,
    AttackCategory,
    AttackResultStatus,
)
from agentproof.adversarial.runner import AdversarialRunner
from agentproof.core.models import RiskSeverity


def test_runner_passing_attack(tmp_path: Path):
    runner = AdversarialRunner(repo_root=tmp_path, timeout=5)

    case = AttackCase(
        id="adv_test_pass_1",
        category=AttackCategory.EMPTY_INPUT,
        target_file="dummy.py",
        target_symbol="sanitize_input",
        rationale="Verify empty string does not crash",
        execution_snippet="val = ''; assert len(val) == 0; print('SAFE: empty rejected')",
        expected_behavior="Empty string handled cleanly",
    )

    report = runner.run_all([case])
    assert report.cases_generated == 1
    assert report.cases_passed == 1
    assert report.cases_failed == 0
    assert case.result == AttackResultStatus.PASS
    assert case.exit_code == 0
    assert case.integrity_hash is not None


def test_runner_failing_attack_generates_finding(tmp_path: Path):
    runner = AdversarialRunner(repo_root=tmp_path, timeout=5)

    case = AttackCase(
        id="adv_test_fail_1",
        category=AttackCategory.BOUNDARY_VALUE,
        target_file="payment.py",
        target_symbol="process_payment",
        rationale="Negative amount must be rejected",
        execution_snippet="amount = -50\nassert amount > 0, 'Negative amount accepted!'",
        expected_behavior="Negative amount rejected",
    )

    report = runner.run_all([case])
    assert report.cases_generated == 1
    assert report.cases_passed == 0
    assert report.cases_failed == 1
    assert case.result == AttackResultStatus.FAIL
    assert len(report.findings) == 1

    finding = report.findings[0]
    assert finding.category == AttackCategory.BOUNDARY_VALUE
    assert finding.severity == RiskSeverity.HIGH
    assert finding.target == "process_payment"
    assert "Negative amount accepted" in finding.observed_behavior
    assert finding.expected_behavior == "Negative amount rejected"


def test_runner_timeout_attack(tmp_path: Path):
    # Set short 1s timeout
    runner = AdversarialRunner(repo_root=tmp_path, timeout=1)

    case = AttackCase(
        id="adv_test_timeout_1",
        category=AttackCategory.MALFORMED_INPUT,
        target_file="loop.py",
        target_symbol="infinite_parser",
        rationale="Test vulnerability to ReDoS or hang",
        execution_snippet="import time\ntime.sleep(5)\n",
        expected_behavior="Complete within timeout",
        timeout_seconds=1,
    )

    report = runner.run_all([case])
    assert report.cases_generated == 1
    assert report.cases_timed_out == 1
    assert case.result == AttackResultStatus.TIMEOUT
    assert len(report.findings) == 1
    assert "timed out" in report.findings[0].description


def test_runner_syntax_error_case(tmp_path: Path):
    runner = AdversarialRunner(repo_root=tmp_path, timeout=5)

    case = AttackCase(
        id="adv_test_syntax_1",
        category=AttackCategory.INVALID_FORMAT,
        target_file="syntax.py",
        target_symbol="none",
        rationale="Malformed code snippet",
        execution_snippet="def broken(: return",
        expected_behavior="Valid execution",
    )

    report = runner.run_all([case])
    assert report.cases_generated == 1
    assert case.result == AttackResultStatus.ERROR


def test_runner_output_truncation(tmp_path: Path):
    runner = AdversarialRunner(repo_root=tmp_path, timeout=5)

    # Print 100,000 characters
    case = AttackCase(
        id="adv_test_output_1",
        category=AttackCategory.MAXIMUM_VALUE,
        target_file="output.py",
        target_symbol="printer",
        rationale="Test huge output",
        execution_snippet="print('A' * 100000)",
        expected_behavior="Run without crashing memory",
    )

    report = runner.run_all([case])
    assert case.result == AttackResultStatus.PASS
    assert len(case.stdout) <= 65536 + 200
