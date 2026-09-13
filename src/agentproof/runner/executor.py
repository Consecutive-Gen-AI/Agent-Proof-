"""Secure command execution engine with argument vectors, timeouts, and output capping."""

from __future__ import annotations

import datetime
import os
import re
import subprocess
import time
from pathlib import Path
from typing import List, Optional

from agentproof.core.models import CheckResult, CheckStatus
from agentproof.detector.tools import CheckDefinition

# Maximum characters captured from stdout and stderr to prevent memory blowups
DEFAULT_MAX_OUTPUT_CHARS = 50_000

# Redaction pattern for common secret tokens
SECRET_PATTERNS = [
    re.compile(r"(api[_-]?key\s*[:=]\s*['\"]?)([\w\-]{16,})(['\"]?)", re.IGNORECASE),
    re.compile(r"(bearer\s+)([\w\-\.]{20,})", re.IGNORECASE),
    re.compile(r"(ghp_[A-Za-z0-9_]{36})"),
    re.compile(r"(sk-[A-Za-z0-9]{32,})"),
]


class CheckExecutor:
    """Executes validation checks safely with sandboxed parameters and timeouts."""

    def __init__(
        self,
        cwd: str | Path,
        timeout: int = 60,
        max_output_chars: int = DEFAULT_MAX_OUTPUT_CHARS,
    ) -> None:
        self.cwd = Path(cwd).resolve()
        self.timeout = timeout
        self.max_output_chars = max_output_chars

    def _sanitize(self, text: str) -> str:
        """Mask potential secrets or auth tokens in output."""
        sanitized = text
        for pattern in SECRET_PATTERNS:
            sanitized = pattern.sub(r"\1***REDACTED***", sanitized)
        return sanitized

    def _cap_output(self, text: str) -> str:
        """Cap text length if exceeding max threshold."""
        if len(text) > self.max_output_chars:
            return (
                text[: self.max_output_chars]
                + f"\n... [Output truncated to {self.max_output_chars} characters]"
            )
        return text

    def run_check(self, check_def: CheckDefinition) -> CheckResult:
        """
        Execute an individual check definition and return a structured CheckResult.
        """
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Handle unavailable checks without attempting execution
        if not check_def.is_available:
            return CheckResult(
                name=check_def.name,
                category=check_def.category,
                command=check_def.command,
                status=CheckStatus.UNAVAILABLE,
                exit_code=None,
                duration_ms=0,
                stdout="",
                stderr=check_def.reason_if_unavailable or "Tool is not available in environment.",
                timestamp=now_iso,
            )

        if not check_def.command:
            return CheckResult(
                name=check_def.name,
                category=check_def.category,
                command=[],
                status=CheckStatus.SKIPPED,
                exit_code=None,
                duration_ms=0,
                stdout="",
                stderr="Empty command definition.",
                timestamp=now_iso,
            )

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        # Avoid interactive prompts or pagers
        env["CI"] = "1"
        env["PAGER"] = "cat"

        start_time = time.perf_counter()
        stdout_text = ""
        stderr_text = ""
        exit_code: Optional[int] = None
        status = CheckStatus.ERROR

        try:
            # Strictly use argument vectors: NO shell=True
            proc = subprocess.run(
                check_def.command,
                cwd=str(self.cwd),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout,
                env=env,
            )
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            exit_code = proc.returncode
            stdout_text = proc.stdout
            stderr_text = proc.stderr

            if exit_code == 0:
                status = CheckStatus.PASS
            else:
                status = CheckStatus.FAIL

        except subprocess.TimeoutExpired as te:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            status = CheckStatus.TIMEOUT
            stdout_text = te.stdout or "" if isinstance(te.stdout, str) else ""
            stderr_text = f"Command timed out after {self.timeout} seconds."

        except FileNotFoundError as fnf:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            status = CheckStatus.UNAVAILABLE
            stderr_text = f"Executable not found: {fnf}"

        except Exception as exc:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            status = CheckStatus.ERROR
            stderr_text = f"Execution error: {exc}"

        return CheckResult(
            name=check_def.name,
            category=check_def.category,
            command=check_def.command,
            status=status,
            exit_code=exit_code,
            duration_ms=duration_ms,
            stdout=self._cap_output(self._sanitize(stdout_text)),
            stderr=self._cap_output(self._sanitize(stderr_text)),
            timestamp=now_iso,
        )

    def run_all(self, check_defs: List[CheckDefinition]) -> List[CheckResult]:
        """Execute a series of checks sequentially and gather results."""
        results: List[CheckResult] = []
        for c in check_defs:
            results.append(self.run_check(c))
        return results
