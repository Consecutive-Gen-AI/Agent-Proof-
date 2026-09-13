"""Unit tests for subprocess executor."""

import sys
from pathlib import Path
from agentproof.core.models import CheckCategory, CheckStatus
from agentproof.detector.tools import CheckDefinition
from agentproof.runner.executor import CheckExecutor


def test_executor_run_passing_command(tmp_path: Path):
    executor = CheckExecutor(cwd=tmp_path, timeout=5)
    check_def = CheckDefinition(
        name="test_pass",
        category=CheckCategory.TEST,
        command=[sys.executable, "-c", "print('hello world')"],
    )
    result = executor.run_check(check_def)
    assert result.status == CheckStatus.PASS
    assert result.exit_code == 0
    assert "hello world" in result.stdout
    assert result.duration_ms >= 0


def test_executor_run_failing_command(tmp_path: Path):
    executor = CheckExecutor(cwd=tmp_path, timeout=5)
    check_def = CheckDefinition(
        name="test_fail",
        category=CheckCategory.TEST,
        command=[sys.executable, "-c", "import sys; sys.stderr.write('failed'); sys.exit(2)"],
    )
    result = executor.run_check(check_def)
    assert result.status == CheckStatus.FAIL
    assert result.exit_code == 2
    assert "failed" in result.stderr


def test_executor_run_timeout(tmp_path: Path):
    executor = CheckExecutor(cwd=tmp_path, timeout=1)
    check_def = CheckDefinition(
        name="test_timeout",
        category=CheckCategory.TEST,
        command=[sys.executable, "-c", "import time; time.sleep(3)"],
    )
    result = executor.run_check(check_def)
    assert result.status == CheckStatus.TIMEOUT
    assert "timed out" in result.stderr.lower()


def test_executor_unavailable_check(tmp_path: Path):
    executor = CheckExecutor(cwd=tmp_path, timeout=5)
    check_def = CheckDefinition(
        name="missing_tool",
        category=CheckCategory.TEST,
        command=[],
        is_available=False,
        reason_if_unavailable="Tool not installed",
    )
    result = executor.run_check(check_def)
    assert result.status == CheckStatus.UNAVAILABLE
    assert result.exit_code is None
    assert "Tool not installed" in result.stderr


def test_executor_sanitizes_secrets(tmp_path: Path):
    executor = CheckExecutor(cwd=tmp_path, timeout=5)
    check_def = CheckDefinition(
        name="secret_check",
        category=CheckCategory.SECURITY,
        command=[sys.executable, "-c", "print('api_key=abcdef12345678901234')"],
    )
    result = executor.run_check(check_def)
    assert "abcdef12345678901234" not in result.stdout
    assert "REDACTED" in result.stdout


def test_executor_truncates_large_output(tmp_path: Path):
    executor = CheckExecutor(cwd=tmp_path, timeout=5, max_output_chars=100)
    check_def = CheckDefinition(
        name="large_output",
        category=CheckCategory.TEST,
        command=[sys.executable, "-c", "print('x' * 500)"],
    )
    result = executor.run_check(check_def)
    assert len(result.stdout) < 200
    assert "truncated" in result.stdout.lower()
