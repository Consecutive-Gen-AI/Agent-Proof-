"""End-to-end integration tests for the full verification workflow on real Git repositories."""

import json
import subprocess
import sys
from pathlib import Path
import pytest


@pytest.fixture
def git_test_repo(tmp_path: Path) -> Path:
    """Fixture to create and initialize a clean Git repository with basic config."""
    repo_dir = tmp_path / "test_repo"
    repo_dir.mkdir()

    subprocess.run(["git", "init", "-b", "main"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, check=True, capture_output=True)

    # Initial commit
    readme = repo_dir / "README.md"
    readme.write_text("# Test Repo\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_dir, check=True, capture_output=True)

    return repo_dir


def test_verify_clean_repository(git_test_repo: Path):
    cmd = [sys.executable, "-m", "agentproof.cli.main", "verify", "-d", str(git_test_repo), "--json"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["change_summary"]["total_files"] == 0
    assert data["verdict"] in ("VERIFIED", "INCONCLUSIVE")


def test_verify_passing_tests_workflow(git_test_repo: Path):
    # Setup a python project with pytest & a passing test
    pyproject = git_test_repo / "pyproject.toml"
    pyproject.write_text("[tool.pytest.ini_options]\ntestpaths = ['tests']\n", encoding="utf-8")
    tests_dir = git_test_repo / "tests"
    tests_dir.mkdir()
    test_file = tests_dir / "test_math.py"
    test_file.write_text("def test_add(): assert 1 + 1 == 2\n", encoding="utf-8")

    cmd = [sys.executable, "-m", "agentproof.cli.main", "verify", "-d", str(git_test_repo), "--json"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["verdict"] == "VERIFIED"
    assert len(data["checks"]) >= 1
    assert data["checks"][0]["status"] == "PASS"
    assert data["change_summary"]["total_files"] >= 2


def test_verify_failing_tests_workflow(git_test_repo: Path):
    # Setup a python project with a failing test
    pyproject = git_test_repo / "pyproject.toml"
    pyproject.write_text("[tool.pytest.ini_options]\ntestpaths = ['tests']\n", encoding="utf-8")
    tests_dir = git_test_repo / "tests"
    tests_dir.mkdir()
    test_file = tests_dir / "test_broken.py"
    test_file.write_text("def test_fail(): assert 1 == 2\n", encoding="utf-8")

    cmd = [sys.executable, "-m", "agentproof.cli.main", "verify", "-d", str(git_test_repo), "--json"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode == 1  # Should exit with non-zero on test failure
    data = json.loads(proc.stdout)
    assert data["verdict"] == "FAILED"
    assert any(c["status"] == "FAIL" for c in data["checks"])


def test_verify_untested_source_change_warning(git_test_repo: Path):
    # Setup existing passing test that is committed
    pyproject = git_test_repo / "pyproject.toml"
    pyproject.write_text("[tool.pytest.ini_options]\ntestpaths = ['tests']\n", encoding="utf-8")
    tests_dir = git_test_repo / "tests"
    tests_dir.mkdir()
    test_file = tests_dir / "test_dummy.py"
    test_file.write_text("def test_ok(): pass\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=git_test_repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Add tests"], cwd=git_test_repo, check=True, capture_output=True)

    # Now modify only a source file without modifying any test
    src_dir = git_test_repo / "src"
    src_dir.mkdir()
    (src_dir / "calc.py").write_text("def multiply(a, b): return a * b\n", encoding="utf-8")

    cmd = [sys.executable, "-m", "agentproof.cli.main", "verify", "-d", str(git_test_repo), "--json"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["verdict"] == "VERIFIED_WITH_WARNINGS"
    warning_codes = [w["code"] for w in data["warnings"]]
    assert "UNTESTED_SOURCE_CHANGE" in warning_codes
