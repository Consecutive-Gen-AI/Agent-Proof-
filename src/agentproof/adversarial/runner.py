"""Safe subprocess runner for adversarial attack execution."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional

from agentproof.adversarial.models import (
    AdversarialFinding,
    AdversarialReport,
    AttackCase,
    AttackCategory,
    AttackResultStatus,
)
from agentproof.core.models import RiskSeverity
from agentproof.graph.integrity import compute_integrity_hash


class AdversarialRunner:
    """Safely executes adversarial test cases in isolated, bounded Python subprocesses."""

    def __init__(
        self,
        repo_root: Optional[Path] = None,
        timeout_seconds: int = 5,
        timeout: Optional[int] = None,
        **kwargs: Any,
    ):
        self.repo_root = Path(repo_root).resolve() if repo_root else Path(".").resolve()
        self.timeout_seconds = timeout if timeout is not None else timeout_seconds

    def run_all(self, attack_cases: List[AttackCase]) -> AdversarialReport:
        """Execute a list of attack cases and formulate findings."""
        passed = 0
        failed = 0
        timed_out = 0
        not_applicable = 0
        findings: List[AdversarialFinding] = []

        if not attack_cases:
            return AdversarialReport(
                cases_generated=0,
                cases_passed=0,
                cases_failed=0,
                cases_timed_out=0,
                cases_not_applicable=0,
                cases=[],
                findings=[],
                summary="No suitable attack targets discovered in changed code.",
            )

        for case in attack_cases:
            if not case.execution_code or not case.execution_code.strip():
                case.status = AttackResultStatus.NOT_APPLICABLE
                not_applicable += 1
                continue

            self._execute_single_case(case)

            if case.status == AttackResultStatus.PASS:
                passed += 1
            elif case.status == AttackResultStatus.FAIL:
                failed += 1
                finding = self._create_finding(case)
                findings.append(finding)
            elif case.status == AttackResultStatus.TIMEOUT:
                timed_out += 1
                failed += 1
                finding = self._create_finding(case)
                findings.append(finding)
            elif case.status in (AttackResultStatus.NOT_APPLICABLE, AttackResultStatus.UNAVAILABLE):
                not_applicable += 1
            elif case.status == AttackResultStatus.ERROR:
                failed += 1
                finding = self._create_finding(case)
                findings.append(finding)

        summary_text = (
            f"Adversarial checks completed: {len(attack_cases)} generated, "
            f"{passed} passed, {failed} failed ({timed_out} timed out), {not_applicable} not applicable."
        )

        return AdversarialReport(
            cases_generated=len(attack_cases),
            cases_passed=passed,
            cases_failed=failed,
            cases_timed_out=timed_out,
            cases_not_applicable=not_applicable,
            cases=attack_cases,
            findings=findings,
            summary=summary_text,
        )

    def _execute_single_case(self, case: AttackCase) -> None:
        """Execute one attack case in a secure argument-vector subprocess."""
        # Set up PYTHONPATH so target modules can be loaded
        env = os.environ.copy()
        python_paths = [str(self.repo_root), str(self.repo_root / "src")]
        existing_pp = env.get("PYTHONPATH", "")
        if existing_pp:
            python_paths.append(existing_pp)
        env["PYTHONPATH"] = os.pathsep.join(python_paths)

        start_time = time.perf_counter()
        cmd = [sys.executable, "-c", case.execution_code]

        timeout_to_use = getattr(case, "timeout_seconds", None) or self.timeout_seconds

        try:
            proc = subprocess.run(
                cmd,
                cwd=str(self.repo_root),
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout_to_use,
            )
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            case.duration_ms = duration_ms
            case.stdout = proc.stdout[:65536]
            case.stderr = proc.stderr[:65536]
            case.exit_code = proc.returncode

            if proc.returncode == 0:
                case.status = AttackResultStatus.PASS
                if "HANDLED_EXPECTED_ERROR:" in case.stdout:
                    case.observed_behavior = case.stdout.strip()
                elif "RESULT:" in case.stdout:
                    case.observed_behavior = case.stdout.strip()
                else:
                    case.observed_behavior = "Executed cleanly without error"
            else:
                # Check if target symbol is unavailable/import error
                if "ModuleNotFoundError" in case.stderr or "ImportError" in case.stderr:
                    case.status = AttackResultStatus.UNAVAILABLE
                    case.observed_behavior = "Target module could not be imported in isolation"
                elif "AttributeError" in case.stderr and f"has no attribute '{case.target_symbol}'" in case.stderr:
                    case.status = AttackResultStatus.UNAVAILABLE
                    case.observed_behavior = f"Symbol '{case.target_symbol}' not found in module"
                elif "SyntaxError" in case.stderr:
                    case.status = AttackResultStatus.ERROR
                    case.observed_behavior = "Syntax error in adversarial snippet"
                elif "UNHANDLED_EXCEPTION:" in case.stderr:
                    case.status = AttackResultStatus.FAIL
                    lines = case.stderr.strip().splitlines()
                    case.observed_behavior = lines[-1] if lines else "Unhandled exception during adversarial execution"
                else:
                    case.status = AttackResultStatus.FAIL
                    lines = [l.strip() for l in case.stderr.strip().splitlines() if l.strip()]
                    case.observed_behavior = lines[-1] if lines else f"Process exited with non-zero code {proc.returncode}"

        except subprocess.TimeoutExpired:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            case.duration_ms = duration_ms
            case.status = AttackResultStatus.TIMEOUT
            case.exit_code = None
            case.observed_behavior = f"Execution timed out after {timeout_to_use}s"
        except Exception as e:
            case.status = AttackResultStatus.ERROR
            case.exit_code = None
            case.observed_behavior = f"Subprocess invocation error: {str(e)}"

        # Compute evidence ID and integrity hash
        evidence_payload = f"{case.id}:{case.status.value}:{case.observed_behavior}"
        case.evidence_id = f"evidence:adversarial:{compute_integrity_hash(case.id)[:12]}"
        case.integrity_hash = compute_integrity_hash(evidence_payload)

    def _create_finding(self, case: AttackCase) -> AdversarialFinding:
        """Create a structured finding for a failed or timed-out adversarial case."""
        severity = RiskSeverity.HIGH if case.category in (
            AttackCategory.PERMISSION_OR_AUTH_EDGE_CASE,
            AttackCategory.MALFORMED_INPUT,
            AttackCategory.ERROR_PATH,
            AttackCategory.BOUNDARY_VALUE,
        ) or case.status == AttackResultStatus.TIMEOUT else RiskSeverity.WARNING

        finding_id = f"finding:adversarial:{case.id}"
        action = "timed out" if case.status == AttackResultStatus.TIMEOUT else "failed"
        desc = f"Adversarial attack {case.category.value} {action} against {case.target_symbol}."

        evidence_items = []
        if case.observed_behavior:
            evidence_items.append(f"Observed: {case.observed_behavior}")
        if case.stderr.strip():
            evidence_items.append(f"Stderr: {case.stderr.strip()[:200]}")

        return AdversarialFinding(
            finding_id=finding_id,
            category=case.category,
            severity=severity,
            target_file=case.target_file,
            target_symbol=case.target_symbol,
            description=desc,
            expected_behavior=case.expected_behavior,
            observed_behavior=case.observed_behavior,
            attack_case_id=case.id,
            evidence=evidence_items,
        )
