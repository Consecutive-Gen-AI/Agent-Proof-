"""Verdict evaluation logic for synthesizing checks and risk warnings."""

from typing import List, Tuple
from agentproof.core.models import (
    CheckResult,
    CheckStatus,
    CheckCategory,
    RiskSeverity,
    RiskWarning,
    Verdict,
)


def evaluate_verdict(
    checks: List[CheckResult],
    warnings: List[RiskWarning],
) -> Tuple[Verdict, str]:
    """
    Evaluate the final verification verdict based on independent check results
    and detected risk warnings.

    Returns:
        Tuple of (Verdict, human-readable reasoning).
    """
    # 1. Check for hard failures
    failed_checks = [c for c in checks if c.status == CheckStatus.FAIL]
    timed_out_checks = [c for c in checks if c.status == CheckStatus.TIMEOUT]
    errored_checks = [c for c in checks if c.status == CheckStatus.ERROR]

    if failed_checks or timed_out_checks:
        reasons = []
        if failed_checks:
            names = ", ".join(c.name for c in failed_checks)
            reasons.append(f"Check(s) failed: {names}")
        if timed_out_checks:
            names = ", ".join(c.name for c in timed_out_checks)
            reasons.append(f"Check(s) timed out: {names}")
        return Verdict.FAILED, ". ".join(reasons) + "."

    if errored_checks:
        names = ", ".join(c.name for c in errored_checks)
        return Verdict.ERROR, f"Check execution error in: {names}."

    # 2. Check for passed checks vs absence of checks
    passed_checks = [c for c in checks if c.status == CheckStatus.PASS]
    unavailable_checks = [c for c in checks if c.status == CheckStatus.UNAVAILABLE]

    if not passed_checks:
        if unavailable_checks:
            names = ", ".join(c.name for c in unavailable_checks)
            return (
                Verdict.INCONCLUSIVE,
                f"No independent verification checks could run. Configured or detected tools were unavailable: {names}.",
            )
        return (
            Verdict.INCONCLUSIVE,
            "No verification checks were executed or detected for this repository.",
        )

    # 3. If checks passed, evaluate risk warnings
    high_risks = [w for w in warnings if w.severity == RiskSeverity.HIGH]
    warning_risks = [w for w in warnings if w.severity == RiskSeverity.WARNING]

    if high_risks or warning_risks:
        reasons = []
        if high_risks:
            reasons.append(f"{len(high_risks)} high-risk signal(s) detected")
        if warning_risks:
            reasons.append(f"{len(warning_risks)} warning(s) detected")
        passed_names = ", ".join(c.name for c in passed_checks)
        return (
            Verdict.VERIFIED_WITH_WARNINGS,
            f"Checks passed ({passed_names}), but caution is required: {'; '.join(reasons)}.",
        )

    # 4. Clean pass with independent evidence
    test_passed = any(c.category == CheckCategory.TEST for c in passed_checks)
    passed_names = ", ".join(c.name for c in passed_checks)
    if test_passed:
        return (
            Verdict.VERIFIED,
            f"All independent checks passed ({passed_names}) with no risk warnings detected.",
        )
    return (
        Verdict.VERIFIED,
        f"Validation checks passed ({passed_names}) with no risk warnings detected.",
    )
