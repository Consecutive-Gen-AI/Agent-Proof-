"""Integration tests for AgentProof V2 verification workflows."""

import json
import subprocess
import sys
from pathlib import Path
import pytest


@pytest.fixture
def git_v2_repo(tmp_path: Path) -> Path:
    """Fixture to create and initialize a clean Git repository with basic config."""
    repo_dir = tmp_path / "v2_test_repo"
    repo_dir.mkdir()

    subprocess.run(["git", "init", "-b", "main"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "V2 User"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "v2@example.com"], cwd=repo_dir, check=True, capture_output=True)

    # Initial commit
    readme = repo_dir / "README.md"
    readme.write_text("# V2 Test Repo\n", encoding="utf-8")
    pyproject = repo_dir / "pyproject.toml"
    pyproject.write_text("[tool.pytest.ini_options]\ntestpaths = ['tests']\npythonpath = ['src']\n", encoding="utf-8")
    src = repo_dir / "src"
    src.mkdir()
    (src / "math_lib.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    tests = repo_dir / "tests"
    tests.mkdir()
    (tests / "test_math.py").write_text("from math_lib import add\ndef test_add(): assert add(1, 2) == 3\n", encoding="utf-8")

    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_dir, check=True, capture_output=True)

    return repo_dir


def test_v2_terminal_report_sections(git_v2_repo: Path):
    # Modify a file to create a working tree change
    (git_v2_repo / "src" / "math_lib.py").write_text(
        "def add(a, b):\n    return a + b\n\ndef subtract(a, b):\n    return a - b\n",
        encoding="utf-8"
    )

    cmd = [sys.executable, "-m", "agentproof.cli.main", "verify", "-d", str(git_v2_repo), "--no-color"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode == 0
    output = proc.stdout

    # Verify that all 6 V2 report sections are present
    assert "1. CHANGE (Repository Facts)" in output
    assert "2. IMPACT (Change Impact Analysis)" in output
    assert "3. CHECKS (Validation Execution)" in output
    assert "4. RISKS & FINDINGS" in output
    assert "5. EVIDENCE (Facts & Provenance)" in output
    assert "FINAL VERDICT:" in output


def test_v2_json_schema_and_impact(git_v2_repo: Path):
    # Modify math_lib
    (git_v2_repo / "src" / "math_lib.py").write_text(
        "def add(a, b):\n    return a + b\n\ndef multiply(a, b):\n    return a * b\n",
        encoding="utf-8"
    )

    cmd = [sys.executable, "-m", "agentproof.cli.main", "verify", "-d", str(git_v2_repo), "--json"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode == 0
    data = json.loads(proc.stdout)

    assert data["schema_version"] == "1.1.0"
    assert "impact" in data
    assert "findings" in data
    assert "staged_files_count" in data["change_summary"]
    assert "unstaged_files_count" in data["change_summary"]

    # Check impact analysis detected math_lib
    impact = data["impact"]
    assert "math_lib" in impact["changed_modules"]
    # Check related test suite was detected
    impacted_tests = [t["file_path"] for t in impact["impacted_test_files"]]
    assert any("test_math.py" in p for p in impacted_tests)


def test_v2_staged_vs_unstaged_breakdown(git_v2_repo: Path):
    # Stage one file
    (git_v2_repo / "staged_file.txt").write_text("hello staged\n", encoding="utf-8")
    subprocess.run(["git", "add", "staged_file.txt"], cwd=git_v2_repo, check=True, capture_output=True)

    # Leave one unstaged file
    (git_v2_repo / "unstaged_file.txt").write_text("hello unstaged\n", encoding="utf-8")

    cmd = [sys.executable, "-m", "agentproof.cli.main", "verify", "-d", str(git_v2_repo), "--json"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode == 0
    data = json.loads(proc.stdout)

    summary = data["change_summary"]
    assert summary["staged_files_count"] >= 1
    assert summary["unstaged_files_count"] >= 1


def test_v2_tests_reduced_finding(git_v2_repo: Path):
    # Delete the test file
    test_file = git_v2_repo / "tests" / "test_math.py"
    test_file.unlink()

    cmd = [sys.executable, "-m", "agentproof.cli.main", "verify", "-d", str(git_v2_repo), "--json"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    data = json.loads(proc.stdout)

    finding_codes = [f["code"] for f in data["findings"]]
    assert "TESTS_REDUCED" in finding_codes
