"""Standardized agent verification protocol and actionable feedback formatting."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from agentproof.core.models import (
    CheckStatus,
    Verdict,
    VerificationReport,
)


@dataclass
class AgentFeedback:
    """Actionable verification summary tailored for AI coding agent tool consumption."""
    verdict: str
    is_verified: bool
    exit_code: int
    summary: str
    blockers: List[str] = field(default_factory=list)
    drift_level: str = "NONE"
    drift_description: Optional[str] = None
    missing_work: List[str] = field(default_factory=list)
    adversarial_findings: List[str] = field(default_factory=list)
    passed_checks: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verdict": self.verdict,
            "is_verified": self.is_verified,
            "exit_code": self.exit_code,
            "summary": self.summary,
            "blockers": self.blockers,
            "drift_level": self.drift_level,
            "drift_description": self.drift_description,
            "missing_work": self.missing_work,
            "adversarial_findings": self.adversarial_findings,
            "passed_checks": self.passed_checks,
        }

    def to_markdown(self) -> str:
        """Render concise, token-efficient markdown suitable for an agent context window."""
        lines = [
            f"# AgentProof Verification: {self.verdict}",
            "",
            f"**Status**: {'PASS' if self.is_verified else 'ACTION REQUIRED'}",
            f"**Summary**: {self.summary}",
            "",
        ]

        if self.blockers:
            lines.append("## Blockers to Fix")
            for b in self.blockers:
                lines.append(f"- [!] {b}")
            lines.append("")

        if self.adversarial_findings:
            lines.append("## Adversarial Attack Failures")
            for af in self.adversarial_findings:
                lines.append(f"- [x] {af}")
            lines.append("")

        if self.missing_work:
            lines.append("## Missing Work / Omissions")
            for mw in self.missing_work:
                lines.append(f"- [?] {mw}")
            lines.append("")

        if self.drift_level not in ("NONE", "LOW", "UNKNOWN"):
            lines.append("## Scope Drift")
            lines.append(f"- **Level**: {self.drift_level}")
            if self.drift_description:
                lines.append(f"- **Details**: {self.drift_description}")
            lines.append("")

        if self.passed_checks:
            lines.append("## Passed Verification Checks")
            for pc in self.passed_checks:
                lines.append(f"- [x] {pc}")
            lines.append("")

        return "\n".join(lines).strip()

    @classmethod
    def from_report(cls, report: VerificationReport) -> AgentFeedback:
        """Transform a VerificationReport into AgentFeedback."""
        is_verified = report.verdict in (Verdict.VERIFIED, Verdict.VERIFIED_WITH_WARNINGS)
        exit_code = 0 if is_verified else 1

        blockers: List[str] = []
        passed_checks: List[str] = []

        # Collect check failures
        for chk in report.checks:
            cat_name = chk.category.value if hasattr(chk.category, "value") else str(chk.category)
            if chk.status == CheckStatus.PASS:
                passed_checks.append(f"{chk.name} ({cat_name})")
            elif chk.status in (CheckStatus.FAIL, CheckStatus.ERROR, CheckStatus.TIMEOUT):
                err_detail = chk.output_summary or (chk.stderr.strip().splitlines()[-1] if chk.stderr.strip() else "")
                err = f": {err_detail}" if err_detail else ""
                blockers.append(f"Check failed: {chk.name} [{chk.status.value}]{err}")

        # Collect missing work
        missing_work: List[str] = []
        if report.missing_work:
            for f in report.missing_work.findings:
                desc = f"{f.code}: {f.what_was_detected}"
                missing_work.append(desc)
                if f.severity.value == "HIGH":
                    blockers.append(desc)

        # Collect drift
        drift_level = "NONE"
        drift_desc = None
        if report.drift:
            drift_level = report.drift.drift_level.value
            drift_desc = report.drift.summary
            if drift_level == "HIGH":
                blockers.append(f"Scope Drift HIGH: {report.drift.summary}")

        # Collect adversarial findings
        adversarial_findings: List[str] = []
        if report.adversarial:
            for af in report.adversarial.findings:
                desc = f"{af.category.value} on {af.target_symbol}: expected '{af.expected_behavior}', observed '{af.observed_behavior}'"
                adversarial_findings.append(desc)
                blockers.append(desc)

        summary = report.reasoning or f"Verification finished with verdict {report.verdict.value}."

        return cls(
            verdict=report.verdict.value,
            is_verified=is_verified,
            exit_code=exit_code,
            summary=summary,
            blockers=blockers,
            drift_level=drift_level,
            drift_description=drift_desc,
            missing_work=missing_work,
            adversarial_findings=adversarial_findings,
            passed_checks=passed_checks,
        )
