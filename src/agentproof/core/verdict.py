"""Verdict evaluation logic for synthesizing checks, risk warnings, drift, and missing work."""

from typing import List, Optional, Tuple
from agentproof.core.models import (
    CheckCategory,
    CheckResult,
    CheckStatus,
    DriftLevel,
    DriftReport,
    MissingWorkReport,
    RiskSeverity,
    RiskWarning,
    Verdict,
)


def evaluate_verdict(
    checks: List[CheckResult],
    warnings: List[RiskWarning],
    drift: Optional[DriftReport] = None,
    missing_work: Optional[MissingWorkReport] = None,
) -> Tuple[Verdict, str]:
    """
    Evaluate the final verification verdict based on independent check results,
    detected risk warnings, task drift, and missing work.

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

    # 3. If checks passed, evaluate drift, missing work, and risk warnings
    caution_signals: List[str] = []

    # A. Check drift
    if drift and drift.drift_level in (DriftLevel.HIGH, DriftLevel.MEDIUM):
        caution_signals.append(f"{drift.drift_level.value} scope drift detected ({len(drift.unexpected_files)} unexpected file(s))")

    # B. Check missing work
    if missing_work and missing_work.findings:
        high_missing = [f for f in missing_work.findings if f.severity == RiskSeverity.HIGH]
        if high_missing:
            caution_signals.append(f"Critical missing work: {high_missing[0].title}")
        else:
            caution_signals.append(f"{len(missing_work.findings)} missing work gap(s) detected")

    # C. Check general risk warnings
    high_risks = [w for w in warnings if w.severity == RiskSeverity.HIGH]
    warning_risks = [w for w in warnings if w.severity == RiskSeverity.WARNING]
    if high_risks:
        caution_signals.append(f"{len(high_risks)} high-risk signal(s)")
    elif warning_risks:
        caution_signals.append(f"{len(warning_risks)} risk warning(s)")

    if caution_signals:
        passed_names = ", ".join(c.name for c in passed_checks)
        return (
            Verdict.VERIFIED_WITH_WARNINGS,
            f"Checks passed ({passed_names}), but caution is required: {'; '.join(caution_signals)}.",
        )

    # 4. Clean pass with independent evidence
    test_passed = any(c.category == CheckCategory.TEST for c in passed_checks)
    passed_names = ", ".join(c.name for c in passed_checks)
    if test_passed:
        return (
            Verdict.VERIFIED,
            f"All independent checks passed ({passed_names}) with no drift, omissions, or risk warnings.",
        )
    return (
        Verdict.VERIFIED,
        f"Validation checks passed ({passed_names}) with no drift, omissions, or risk warnings.",
    )
